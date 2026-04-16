# SQS Admin Panel

Web administration panel for Amazon SQS — 100% serverless.

## Features

- 📋 List queues (Standard + FIFO) with real-time metrics
- ➕ Create / delete queues
- ⚙️ Edit attributes (visibility timeout, retention, redrive policy)
- 🗑️ Purge queues
- 📨 Send messages (with FIFO group/dedup ID and delay support)
- 📦 Batch send (JSON array)
- 👁️ Peek messages (view without removing from queue)
- 🔍 Filter messages by content
- ❌ Delete individual messages
- 🔄 DLQ redrive (reprocess failed messages)
- 🔀 Move messages between queues
- 📤 Export / Import messages (JSON)
- 📊 Dashboard with KPIs and overview of all queues
- 🔐 Cognito authentication (on AWS deploy)

## Architecture

- **Frontend**: React + Vite → S3 + CloudFront
- **Backend**: API Gateway + Lambda (Python) → AWS SAM
- **Auth**: Amazon Cognito User Pool
- **Local**: Docker Compose (LocalStack + Backend + Frontend)

## Local Setup

### Prerequisite

- Docker

### Start the environment (single command)

```bash
docker compose up --build
```

Open `http://localhost:5173`. Done.

Three services start together:
- **localstack** (port 4566) — emulated SQS
- **backend** (port 3001) — Python API that invokes the same Lambda handler
- **frontend** (port 5173) — Vite dev server with proxy to the backend

> Authentication is automatically disabled in the local environment.

### Run tests

```bash
# Locally (with containers already running)
bash tests.sh

# Via Docker (starts everything and runs the tests)
docker compose --profile test run --rm tests
```

Tests cover: queue CRUD, send/receive, batch, export/import, move, DLQ/redrive, purge and delete.

## Deploy to AWS

### Prerequisites

- AWS CLI configured
- AWS SAM CLI (`brew install aws-sam-cli`)
- Node.js 18+

### One-click deploy

```bash
./deploy.sh sqs-admin-panel admin@example.com
```

Parameters:
- `sqs-admin-panel` — CloudFormation stack name (optional, default: `sqs-admin-panel`)
- `admin@example.com` — initial admin email (optional, receives temporary password via email)

The script does everything automatically:
1. `sam build` + `sam deploy` (Lambda, API Gateway, Cognito, S3, CloudFront)
2. Frontend build with Cognito and API URL variables
3. Upload frontend to S3
4. Displays the panel URL

### Manual deploy

```bash
# 1. Deploy the backend
sam build
sam deploy --guided

# 2. Copy the outputs (ApiUrl, UserPoolId, UserPoolClientId, FrontendBucket)

# 3. Build the frontend
cd frontend
VITE_API_URL=https://xxx.execute-api.us-east-1.amazonaws.com/api \
VITE_COGNITO_USER_POOL_ID=us-east-1_xxx \
VITE_COGNITO_CLIENT_ID=xxx \
  npm run build

# 4. Upload to S3
aws s3 sync dist/ s3://BUCKET_NAME/ --delete
```

## Remove from AWS

```bash
./destroy.sh sqs-admin-panel
```

Empties the S3 bucket and deletes the entire CloudFormation stack (Lambda, API Gateway, Cognito, S3, CloudFront).

## Project Structure

```
sqs_admin_painel/
├── backend/
│   ├── app.py              # Lambda handler — full SQS API
│   ├── local_server.py     # Local HTTP server that emulates API Gateway
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main component (queue detail)
│   │   ├── App.css         # Global styles
│   │   ├── Dashboard.tsx   # Dashboard with KPIs and queue table
│   │   ├── Dashboard.css   # Dashboard styles
│   │   ├── Login.tsx       # Login screen (Cognito)
│   │   ├── api.ts          # HTTP client for the API
│   │   ├── auth.ts         # Authentication module (Cognito)
│   │   ├── main.tsx        # Entry point with auth flow
│   │   └── vite-env.d.ts
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── package.json
├── template.yaml           # SAM template (Lambda, API GW, Cognito, S3, CloudFront)
├── samconfig.toml
├── docker-compose.yml      # Local environment (LocalStack + Backend + Frontend + Tests)
├── deploy.sh               # One-click deploy script
├── tests.sh                # Integration tests
├── .gitignore
└── README.md
```

## Environment Variables (Frontend)

| Variable | Description | Required |
|---|---|---|
| `VITE_API_URL` | API Gateway URL | Yes (deploy) |
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool ID | Yes (deploy) |
| `VITE_COGNITO_CLIENT_ID` | Cognito App Client ID | Yes (deploy) |

> When Cognito variables are not set, authentication is disabled (local mode).

## Security

- API protected by Cognito Authorizer (JWT)
- Frontend served via CloudFront (HTTPS)
- Private S3 bucket (access only via CloudFront OAC)
- Lambda with `sqs:*` policy — intentional, as this is an admin panel
- CORS configured on API Gateway

## License

MIT
