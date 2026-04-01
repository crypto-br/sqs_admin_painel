#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-sqs-admin-panel}"
REGION="${AWS_DEFAULT_REGION:-us-east-2}"
ADMIN_EMAIL="${2:-}"

echo "🚀 Deploying SQS Admin Panel..."
echo "   Stack:  $STACK_NAME"
echo "   Region: $REGION"
[ -n "$ADMIN_EMAIL" ] && echo "   Admin:  $ADMIN_EMAIL"
echo ""

# 1. Build & deploy SAM
echo "📦 Building backend..."
sam build --use-container --region "$REGION"

echo "☁️  Deploying stack..."
PARAMS="SqsEndpointUrl=''"
[ -n "$ADMIN_EMAIL" ] && PARAMS="$PARAMS AdminEmail='$ADMIN_EMAIL'"

sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides $PARAMS \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset

# 2. Get outputs
echo "📋 Reading stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs' --output json)

API_URL=$(echo "$OUTPUTS" | python3 -c "import sys,json; print([o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='ApiUrl'][0])")
BUCKET=$(echo "$OUTPUTS" | python3 -c "import sys,json; print([o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='FrontendBucket'][0])")
CF_URL=$(echo "$OUTPUTS" | python3 -c "import sys,json; print([o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='FrontendUrl'][0])")
POOL_ID=$(echo "$OUTPUTS" | python3 -c "import sys,json; print([o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='UserPoolId'][0])")
CLIENT_ID=$(echo "$OUTPUTS" | python3 -c "import sys,json; print([o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='UserPoolClientId'][0])")

# 3. Build frontend
echo "🔨 Building frontend..."
cd frontend
npm install --silent
VITE_API_URL="$API_URL" \
VITE_COGNITO_USER_POOL_ID="$POOL_ID" \
VITE_COGNITO_CLIENT_ID="$CLIENT_ID" \
  npm run build

# 4. Upload to S3
echo "📤 Uploading to S3..."
aws s3 sync dist/ "s3://$BUCKET/" --delete --region "$REGION"

# 5. Invalidate CloudFront
CF_DIST_ID=$(echo "$OUTPUTS" | python3 -c "
import sys,json
url=[o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='FrontendUrl'][0]
# Extract distribution domain to get ID
print('')" 2>/dev/null || echo "")

echo ""
echo "✅ Deploy complete!"
echo ""
echo "   🌐 Panel URL:  $CF_URL"
echo "   🔌 API URL:    $API_URL"
echo "   🔐 User Pool:  $POOL_ID"
echo "   📱 Client ID:  $CLIENT_ID"
echo ""
[ -n "$ADMIN_EMAIL" ] && echo "   📧 Check $ADMIN_EMAIL for your temporary password."
echo ""
