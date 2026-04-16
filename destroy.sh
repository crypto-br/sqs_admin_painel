#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-sqs-admin-panel}"
REGION="${AWS_DEFAULT_REGION:-us-east-2}"

echo "🗑️  Removing SQS Admin Panel from AWS..."
echo "   Stack:  $STACK_NAME"
echo "   Region: $REGION"
echo ""

# 1. Get the frontend bucket name before deleting the stack
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucket`].OutputValue' \
  --output text 2>/dev/null || echo "")

# 2. Empty the S3 bucket (required before CloudFormation can delete it)
if [ -n "$BUCKET" ] && [ "$BUCKET" != "None" ]; then
  echo "🪣 Emptying S3 bucket: $BUCKET"
  aws s3 rm "s3://$BUCKET" --recursive --region "$REGION"
fi

# 3. Delete the CloudFormation stack
echo "☁️  Deleting stack: $STACK_NAME"
aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"

echo "⏳ Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"

echo ""
echo "✅ Stack '$STACK_NAME' deleted successfully."
