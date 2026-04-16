# SQS Admin Panel

Painel web de administração do Amazon SQS — 100% serverless.

## Funcionalidades

- 📋 Listar filas (Standard + FIFO) com métricas em tempo real
- ➕ Criar / deletar filas
- ⚙️ Editar atributos (visibility timeout, retention, redrive policy)
- 🗑️ Purgar filas
- 📨 Enviar mensagens (com suporte a FIFO group/dedup ID e delay)
- 📦 Envio em batch (JSON array)
- 👁️ Peek de mensagens (visualizar sem remover da fila)
- 🔍 Filtro de mensagens por conteúdo
- ❌ Deletar mensagens individuais
- 🔄 Redrive de DLQ (reprocessar mensagens que falharam)
- 🔀 Mover mensagens entre filas
- 📤 Export / Import de mensagens (JSON)
- 📊 Dashboard com KPIs e visão geral de todas as filas
- 🔐 Autenticação via Cognito (no deploy AWS)

## Arquitetura

- **Frontend**: React + Vite → S3 + CloudFront
- **Backend**: API Gateway + Lambda (Python) → AWS SAM
- **Auth**: Amazon Cognito User Pool
- **Local**: Docker Compose (LocalStack + Backend + Frontend)

## Setup Local

### Pré-requisito

- Docker

### Subir o ambiente (um único comando)

```bash
docker compose up --build
```

Acesse `http://localhost:5173`. Pronto.

Os 3 serviços sobem juntos:
- **localstack** (porta 4566) — SQS emulado
- **backend** (porta 3001) — API Python que invoca o mesmo handler da Lambda
- **frontend** (porta 5173) — Vite dev server com proxy para o backend

> No ambiente local a autenticação é desabilitada automaticamente.

### Rodar testes

```bash
# Localmente (com containers já rodando)
bash tests.sh

# Via Docker (sobe tudo e roda os testes)
docker compose --profile test run --rm tests
```

Os testes cobrem: CRUD de filas, envio/recebimento, batch, export/import, move, DLQ/redrive, purge e delete.

## Deploy na AWS

### Pré-requisitos

- AWS CLI configurado
- AWS SAM CLI (`brew install aws-sam-cli`)
- Node.js 18+

### One-click deploy

```bash
./deploy.sh sqs-admin-panel admin@example.com
```

Parâmetros:
- `sqs-admin-panel` — nome do stack CloudFormation (opcional, default: `sqs-admin-panel`)
- `admin@example.com` — email do admin inicial (opcional, recebe senha temporária por email)

O script faz tudo automaticamente:
1. `sam build` + `sam deploy` (Lambda, API Gateway, Cognito, S3, CloudFront)
2. Build do frontend com as variáveis do Cognito e API URL
3. Upload do frontend pro S3
4. Exibe a URL do painel

### Deploy manual

```bash
# 1. Deploy do backend
sam build
sam deploy --guided

# 2. Copie os outputs (ApiUrl, UserPoolId, UserPoolClientId, FrontendBucket)

# 3. Build do frontend
cd frontend
VITE_API_URL=https://xxx.execute-api.us-east-1.amazonaws.com/api \
VITE_COGNITO_USER_POOL_ID=us-east-1_xxx \
VITE_COGNITO_CLIENT_ID=xxx \
  npm run build

# 4. Upload pro S3
aws s3 sync dist/ s3://BUCKET_NAME/ --delete
```

## Remover da AWS

```bash
./destroy.sh sqs-admin-panel
```

Esvazia o bucket S3 e deleta todo o stack CloudFormation (Lambda, API Gateway, Cognito, S3, CloudFront).

## Estrutura do Projeto

```
sqs_admin_painel/
├── backend/
│   ├── app.py              # Lambda handler — API completa do SQS
│   ├── local_server.py     # Servidor HTTP local que emula API Gateway
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Componente principal (queue detail)
│   │   ├── App.css         # Estilos globais
│   │   ├── Dashboard.tsx   # Dashboard com KPIs e tabela de filas
│   │   ├── Dashboard.css   # Estilos do dashboard
│   │   ├── Login.tsx       # Tela de login (Cognito)
│   │   ├── api.ts          # Cliente HTTP para a API
│   │   ├── auth.ts         # Módulo de autenticação (Cognito)
│   │   ├── main.tsx        # Entry point com fluxo de auth
│   │   └── vite-env.d.ts
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── package.json
├── template.yaml           # SAM template (Lambda, API GW, Cognito, S3, CloudFront)
├── samconfig.toml
├── docker-compose.yml      # Ambiente local (LocalStack + Backend + Frontend + Tests)
├── deploy.sh               # Script de deploy one-click
├── tests.sh                # Testes de integração
├── .gitignore
└── README.md
```

## Variáveis de Ambiente (Frontend)

| Variável | Descrição | Obrigatória |
|---|---|---|
| `VITE_API_URL` | URL do API Gateway | Sim (deploy) |
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool ID | Sim (deploy) |
| `VITE_COGNITO_CLIENT_ID` | Cognito App Client ID | Sim (deploy) |

> Quando as variáveis do Cognito não estão definidas, a autenticação é desabilitada (modo local).

## Segurança

- API protegida por Cognito Authorizer (JWT)
- Frontend servido via CloudFront (HTTPS)
- S3 bucket privado (acesso apenas via CloudFront OAC)
- Lambda com policy `sqs:*` — intencional, pois é um painel de administração
- CORS configurado no API Gateway

## License

MIT
