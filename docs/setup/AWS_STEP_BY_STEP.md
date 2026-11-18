# AWS setup instructions — Multi-Agent Insurance Valuation capstone

Deployment region: Sydney (ap-southeast-2). Platform status: unverified cloud deployment, development/synthetic data only.

## Architecture

CloudFront → private S3 bucket → React website.
React → HTTPS API Gateway → FastAPI on Lambda → private RDS PostgreSQL.
Browser → S3 presigned POST → private evidence bucket.
FastAPI → SQS queue → document Lambda → Textract OCR and PostgreSQL.
Cognito provides user authentication. Five local domain analyzers and optional Bedrock narrative run within API Lambda. Secrets Manager holds DB credentials. CloudWatch captures logs.

API Gateway is the HTTPS entry point; FastAPI handles endpoints, request validation and permission checks. Cognito logs in human users, not the AI agents.

## Step 1. AWS account and cost safeguards

Sign into https://console.aws.amazon.com and choose Asia Pacific (Sydney). Enable root MFA; do not make root access keys. Set up IAM Identity Center for each of your three team members with short-lived login sessions. Designate one teammate to deploy Terraform. Set AWS Budgets monthly alerts and cost-anomaly alerts, then check notifications work. A budget alert does not enforce a spending cap.

The default design includes a **24/7 NAT gateway, public IPv4 allocation, private RDS DB and storage**. Those can cost tens of USD per month even with no active users. Other possible charges: CloudFront transfer, S3 objects and requests, Lambda, OCR Textract, optional Bedrock, CloudWatch, Secrets Manager, API Gateway. Use AWS Pricing Calculator for a current Sydney estimate. Do not assume free tier covers these services.

## Step 2. Install tools

Use Git, Docker Engine/Desktop, Python 3.12, Node.js 22+, npm, AWS CLI v2 and Terraform 1.6+.

    git clone https://github.com/kevanly-GB/ai-insurance-valuation.git
    cd ai-insurance-valuation
    git fetch origin
    git checkout feature/aws-insurance-platform-mvp-20261119

## Step 3. AWS CLI login

Use AWS IAM Identity Center with a distinct user per team member.

    aws configure sso --profile insurance-dev
    aws sso login --profile insurance-dev
    export AWS_PROFILE=insurance-dev
    aws sts get-caller-identity

For PowerShell, set the profile with the PowerShell environment syntax. Confirm account ID is the intended development account. The deployer needs relevant IAM permissions for S3, VPC, RDS, Lambda, SQS, Cognito, CloudFront, API Gateway, Secrets Manager and IAM role creation.

## Step 4. Test locally before spending money

    docker compose up --build -d
    cp frontend/.env.example frontend/.env.local
    cd frontend && npm install && npm run dev

Visit http://localhost:5173. Local mode enables fake claimant and assessor tokens only when ALLOW_DEV_AUTH=true and APP_ENV=local; never deploy with these settings. Local photo OCR is unavailable: use text-based synthetic data.

## Step 5. Build the Lambda ZIP with Docker

From project root:

    python infrastructure/scripts/build_lambda.py

This creates build/insurance-lambda.zip with Python 3.12-compatible binary dependencies. Terraform uploads it to a private S3 artifact bucket, then uses it for both Lambda functions. AWS Lambda has a 250 MiB uncompressed ZIP deployment limit. If it is too large, trim dependencies or migrate functions to container images.

## Step 6. Provision the stack

    terraform -chdir=infrastructure/terraform init
    terraform -chdir=infrastructure/terraform fmt
    terraform -chdir=infrastructure/terraform validate
    terraform -chdir=infrastructure/terraform plan -out=dev.tfplan
    terraform -chdir=infrastructure/terraform apply dev.tfplan

Review the full plan before apply. It will create VPC (public and private subnets, NAT), private RDS PostgreSQL, Secrets Manager-managed database credentials, private S3 buckets, CloudFront, Cognito, Lambda, API Gateway, SQS and CloudWatch logs. This design uses a single NAT gateway for capstone-cost simplification, not high availability.

Terraform state is local and intentionally gitignored. For team-managed infrastructure, first establish a secure S3 remote backend with locking, bucket encryption and access controls; until then only one designated deployer should run apply/destroy. Do not exchange Terraform state casually since it may include sensitive fields.

## Step 7. Validate backend and outputs

    terraform -chdir=infrastructure/terraform output
    API=$(terraform -chdir=infrastructure/terraform output -raw api_url)
    curl "$API/health"

The expected health endpoint indicates status ok and environment aws. If unhealthy, use AWS Console → CloudWatch Logs → Lambda API group, and inspect Lambda runtime permissions, PostgreSQL connectivity and deployment package.

## Step 8. Publish the website

From project root:

    bash infrastructure/scripts/deploy_frontend.sh

This writes ignored frontend/.env.production.local with Cognito pool/client IDs and API endpoint. It builds Vite, uploads compiled assets to the private website bucket and invalidates CloudFront. Retrieve HTTPS URL:

    terraform -chdir=infrastructure/terraform output -raw website_url

## Step 9. Create test accounts and assessor permissions

The website supports Cognito email/password signup, email verification and login. Newly registered accounts get claimant permissions by default. Never let untrusted users grant themselves assessor privileges.

After creating a verified assessor account, an authorized AWS admin runs:

    POOL=$(terraform -chdir=infrastructure/terraform output -raw cognito_pool_id)
    aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username assessor@example.edu --group-name assessor --region ap-southeast-2

Replace example address with actual verified test account. Sign out and sign back in to refresh the access token. Ensure MFA is enabled according to team risk requirements.

## Step 10. Full acceptance test

1. Claimant creates fictional claim (business, incident type/date and policy ID).
2. Claimant uploads a small fictional asset inventory CSV or PDF.
3. API confirms object via S3 HEAD, queues processing in SQS; document status becomes processed or failed after worker finishes. Refresh claim page to see status.
4. Assessor opens claim, inspects extracted text, requests evidence and receives claimant response if necessary.
5. Assessor runs valuation and checks evidence IDs, source lines, anomaly flags and values for each of five domains.
6. Assessor records override reason if needed, generates draft report, edits and approves it.
7. Claimant can see/download only approved report; a different claimant cannot access the first claim.
8. Assessor inspects audit events; approved case can be archived and locked.

For a failed OCR job check SQS DLQ, worker CloudWatch logs, Textract permissions/availability and billing limits. If enabling Bedrock, supply a supported accessible regional model ID via Terraform variable bedrock_model_id and verify availability and cost before use.

## Step 11. Stop costs

Terraform destroy requires the same state/workspace:

    terraform -chdir=infrastructure/terraform destroy

Evidence and artifact buckets are configured NOT to force-delete objects; an initial destroy can fail if they contain objects or versions. Manually empty all object versions from the development evidence bucket, web bucket and artifact bucket, rerun destroy, then verify NAT Gateway, RDS, S3, CloudFront, Lambdas, log groups and other chargeable services are gone. Do not remove real customer data this way.

## Security and production boundaries

Do not upload genuine insurance files. This MVP lacks malware scanning, decompression sandboxing, WAF, formal migration lifecycle, immutable audit logs, validated confidence, payment/coverage evaluation, backup restore tests, lawful retention handling and external security review. These are prerequisites before any real insurer pilot.
