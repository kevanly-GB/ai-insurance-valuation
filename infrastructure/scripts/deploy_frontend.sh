#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
TF_DIR=infrastructure/terraform
API=$(terraform -chdir="$TF_DIR" output -raw api_url)
POOL=$(terraform -chdir="$TF_DIR" output -raw cognito_pool_id)
CLIENT=$(terraform -chdir="$TF_DIR" output -raw cognito_client_id)
BUCKET=$(terraform -chdir="$TF_DIR" output -raw web_bucket)
DISTRIBUTION=$(terraform -chdir="$TF_DIR" output -raw cloudfront_id)
printf 'VITE_API_URL=%s\nVITE_COGNITO_USER_POOL_ID=%s\nVITE_COGNITO_APP_CLIENT_ID=%s\nVITE_DEMO_MODE=false\n' "$API" "$POOL" "$CLIENT" > frontend/.env.production.local
(cd frontend && npm install && npm run build)
aws s3 sync frontend/dist "s3://$BUCKET" --delete
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION" --paths '/*'
terraform -chdir="$TF_DIR" output -raw website_url
