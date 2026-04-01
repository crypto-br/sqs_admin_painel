import json
import os
import re
import boto3

def get_sqs_client():
    endpoint = os.environ.get('SQS_ENDPOINT_URL')
    if endpoint:
        return boto3.client('sqs', endpoint_url=endpoint, region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
    return boto3.client('sqs')

def _is_dlq_of(source_queue, target_arn):
    rp = source_queue['attributes'].get('RedrivePolicy')
    if not rp:
        return False
    try:
        return json.loads(rp).get('deadLetterTargetArn') == target_arn
    except Exception:
        return False

def cors_response(status, body=None):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Allow-Headers': '*',
        },
        'body': json.dumps(body, default=str) if body is not None else '',
    }

def lambda_handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('path', '')
    params = event.get('queryStringParameters') or {}
    body = json.loads(event.get('body') or '{}')
    sqs = get_sqs_client()

    try:
        if method == 'OPTIONS':
            return cors_response(200)

        # GET /queues
        if method == 'GET' and path == '/queues':
            urls = sqs.list_queues().get('QueueUrls', [])
            queues = []
            for url in urls:
                attr = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['All']).get('Attributes', {})
                name = url.split('/')[-1]
                queues.append({'name': name, 'url': url, 'attributes': attr})
            # Enrich: detect which queues are DLQs and map source->dlq relationships
            arn_to_name = {q['attributes'].get('QueueArn', ''): q['name'] for q in queues}
            for q in queues:
                rp = q['attributes'].get('RedrivePolicy')
                if rp:
                    try:
                        dlq_arn = json.loads(rp).get('deadLetterTargetArn', '')
                        q['dlqName'] = arn_to_name.get(dlq_arn)
                    except Exception:
                        pass
                # Check if this queue IS a DLQ for others
                q['isDeadLetterQueue'] = any(
                    _is_dlq_of(other, q['attributes'].get('QueueArn', ''))
                    for other in queues if other['name'] != q['name']
                )
            return cors_response(200, queues)

        # POST /queues
        if method == 'POST' and path == '/queues':
            name = body['name']
            attrs = body.get('attributes', {})
            if name.endswith('.fifo'):
                attrs.setdefault('FifoQueue', 'true')
            result = sqs.create_queue(QueueName=name, Attributes=attrs)
            return cors_response(201, {'queueUrl': result['QueueUrl']})

        # Match /queues/{queueName}/**
        m = re.match(r'^/queues/([^/]+)(/.*)?$', path)
        if not m:
            return cors_response(404, {'error': 'Not found'})

        queue_name = m.group(1)
        sub_path = m.group(2) or ''

        # Resolve queue URL
        queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']

        # DELETE /queues/{queueName}
        if method == 'DELETE' and sub_path == '':
            sqs.delete_queue(QueueUrl=queue_url)
            return cors_response(200, {'deleted': queue_name})

        # PUT /queues/{queueName}
        if method == 'PUT' and sub_path == '':
            sqs.set_queue_attributes(QueueUrl=queue_url, Attributes=body.get('attributes', {}))
            return cors_response(200, {'updated': queue_name})

        # POST /queues/{queueName}/purge
        if method == 'POST' and sub_path == '/purge':
            sqs.purge_queue(QueueUrl=queue_url)
            return cors_response(200, {'purged': queue_name})

        # POST /queues/{queueName}/messages
        if method == 'POST' and sub_path == '/messages':
            kwargs = {'QueueUrl': queue_url, 'MessageBody': body['messageBody']}
            if body.get('messageGroupId'):
                kwargs['MessageGroupId'] = body['messageGroupId']
            if body.get('messageDeduplicationId'):
                kwargs['MessageDeduplicationId'] = body['messageDeduplicationId']
            if body.get('delaySeconds') is not None:
                kwargs['DelaySeconds'] = int(body['delaySeconds'])
            result = sqs.send_message(**kwargs)
            return cors_response(200, {'messageId': result['MessageId']})

        # GET /queues/{queueName}/messages (peek)
        if method == 'GET' and sub_path == '/messages':
            max_msgs = int(params.get('maxMessages', '5'))
            wait = int(params.get('waitTime', '0'))
            result = sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=min(max_msgs, 10),
                WaitTimeSeconds=wait, AttributeNames=['All'],
            )
            messages = result.get('Messages', [])
            # Return messages to queue by setting visibility to 0
            for msg in messages:
                sqs.change_message_visibility(QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle'], VisibilityTimeout=0)
            return cors_response(200, messages)

        # DELETE /queues/{queueName}/messages
        if method == 'DELETE' and sub_path == '/messages':
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=body['receiptHandle'])
            return cors_response(200, {'deleted': True})

        # POST /queues/{queueName}/redrive — move messages from DLQ back to source queue
        if method == 'POST' and sub_path == '/redrive':
            max_msgs = int(body.get('maxMessages', 10))
            # Find source queues that use this DLQ
            dlq_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['QueueArn'])['Attributes']['QueueArn']
            all_urls = sqs.list_queues().get('QueueUrls', [])
            source_url = None
            for url in all_urls:
                attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['RedrivePolicy']).get('Attributes', {})
                rp = attrs.get('RedrivePolicy')
                if rp:
                    try:
                        if json.loads(rp).get('deadLetterTargetArn') == dlq_arn:
                            source_url = url
                            break
                    except Exception:
                        pass
            if not source_url:
                return cors_response(400, {'error': 'No source queue found for this DLQ'})

            # Check if source is FIFO
            source_attrs = sqs.get_queue_attributes(QueueUrl=source_url, AttributeNames=['FifoQueue']).get('Attributes', {})
            is_fifo = source_attrs.get('FifoQueue') == 'true'

            moved = 0
            while moved < max_msgs:
                batch = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=min(10, max_msgs - moved), WaitTimeSeconds=0, AttributeNames=['All'])
                msgs = batch.get('Messages', [])
                if not msgs:
                    break
                for msg in msgs:
                    send_kwargs = {'QueueUrl': source_url, 'MessageBody': msg['Body']}
                    if is_fifo:
                        send_kwargs['MessageGroupId'] = msg.get('Attributes', {}).get('MessageGroupId', 'redrive')
                        send_kwargs['MessageDeduplicationId'] = msg['MessageId'] + '-redrive'
                    sqs.send_message(**send_kwargs)
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle'])
                    moved += 1
            return cors_response(200, {'moved': moved, 'sourceQueue': source_url.split('/')[-1]})

        # POST /queues/{queueName}/messages/batch
        if method == 'POST' and sub_path == '/messages/batch':
            msgs = body.get('messages', [])
            is_fifo = queue_name.endswith('.fifo')
            sent, failed = 0, 0
            for i in range(0, len(msgs), 10):
                entries = []
                for j, m in enumerate(msgs[i:i+10]):
                    entry = {'Id': str(i+j), 'MessageBody': m.get('messageBody', m) if isinstance(m, dict) else str(m)}
                    if is_fifo:
                        entry['MessageGroupId'] = m.get('messageGroupId', 'batch') if isinstance(m, dict) else 'batch'
                        entry['MessageDeduplicationId'] = m.get('messageDeduplicationId', f'batch-{i+j}') if isinstance(m, dict) else f'batch-{i+j}'
                    if isinstance(m, dict) and m.get('delaySeconds') is not None:
                        entry['DelaySeconds'] = int(m['delaySeconds'])
                    entries.append(entry)
                result = sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)
                sent += len(result.get('Successful', []))
                failed += len(result.get('Failed', []))
            return cors_response(200, {'sent': sent, 'failed': failed})

        # POST /queues/{queueName}/export
        if method == 'POST' and sub_path == '/export':
            max_msgs = int(body.get('maxMessages', 100))
            exported = []
            while len(exported) < max_msgs:
                batch = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=min(10, max_msgs - len(exported)), WaitTimeSeconds=0, AttributeNames=['All'])
                msgs = batch.get('Messages', [])
                if not msgs:
                    break
                for msg in msgs:
                    sqs.change_message_visibility(QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle'], VisibilityTimeout=0)
                    exported.append({'messageId': msg['MessageId'], 'body': msg['Body'], 'attributes': msg.get('Attributes', {})})
            return cors_response(200, exported)

        # POST /queues/{queueName}/import
        if method == 'POST' and sub_path == '/import':
            msgs = body.get('messages', [])
            is_fifo = queue_name.endswith('.fifo')
            sent = 0
            for m in msgs:
                kwargs = {'QueueUrl': queue_url, 'MessageBody': m.get('body', m.get('messageBody', ''))}
                if is_fifo:
                    kwargs['MessageGroupId'] = m.get('attributes', {}).get('MessageGroupId', 'import')
                    kwargs['MessageDeduplicationId'] = m.get('messageId', f'import-{sent}') + '-import'
                sqs.send_message(**kwargs)
                sent += 1
            return cors_response(200, {'imported': sent})

        # POST /queues/{queueName}/move
        if method == 'POST' and sub_path == '/move':
            target_name = body.get('targetQueue')
            max_msgs = int(body.get('maxMessages', 100))
            if not target_name:
                return cors_response(400, {'error': 'targetQueue is required'})
            target_url = sqs.get_queue_url(QueueName=target_name)['QueueUrl']
            target_attrs = sqs.get_queue_attributes(QueueUrl=target_url, AttributeNames=['FifoQueue']).get('Attributes', {})
            is_target_fifo = target_attrs.get('FifoQueue') == 'true'
            moved = 0
            while moved < max_msgs:
                batch = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=min(10, max_msgs - moved), WaitTimeSeconds=0, AttributeNames=['All'])
                msgs = batch.get('Messages', [])
                if not msgs:
                    break
                for msg in msgs:
                    send_kwargs = {'QueueUrl': target_url, 'MessageBody': msg['Body']}
                    if is_target_fifo:
                        send_kwargs['MessageGroupId'] = msg.get('Attributes', {}).get('MessageGroupId', 'move')
                        send_kwargs['MessageDeduplicationId'] = msg['MessageId'] + '-move'
                    sqs.send_message(**send_kwargs)
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg['ReceiptHandle'])
                    moved += 1
            return cors_response(200, {'moved': moved, 'targetQueue': target_name})

        return cors_response(404, {'error': 'Not found'})

    except Exception as e:
        return cors_response(500, {'error': str(e)})
