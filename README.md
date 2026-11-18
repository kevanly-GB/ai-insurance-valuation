# Multi-Agent AI Insurance Valuation Support Platform

Capstone **development MVP**, not a production insurer decision engine. React frontend + FastAPI backend + PostgreSQL + AWS infrastructure in Terraform.

## Implemented workflow

1. Cognito login (local development supports explicitly enabled demo identities).
2. Claimants create claims and upload PDF, DOCX, XLSX, CSV and JPEG/PNG evidence.
3. Documents go directly into private S3 using a presigned POST. SQS queues processing; a separate Lambda validates signatures and extracts text, tabular content and optional Textract OCR.
4. Five valuation domains process labelled amounts: assets, human capital, finance, property, and policy/legal. The orchestrator consolidates evidence IDs, line references, missing-evidence flags and heuristic scores. Optional Bedrock generates narrative summaries only.
5. Assessors initiate valuation, request further evidence, override amounts with a reason, edit draft reports, approve a report and inspect audit activity.
6. Claimants can see and download approved text reports. Approved cases can be archived and locked from changes.

**Important:** Five prototype domain analyzers are currently rule-based, not autonomous LLM agents. There is no LangGraph orchestration yet. This is deliberately evidence-constrained arithmetic, not validated insurance valuation, policy coverage analysis or a payment recommendation.

## Quick local start

Requirements: Docker, Node.js 22+, npm.

    docker compose up --build -d
    cp frontend/.env.example frontend/.env.local
    cd frontend
    npm install
    npm run dev

Visit http://localhost:5173. Choose claimant to create a synthetic claim and upload a sample document. Sign out and choose assessor to run the valuation and approve the report. Backend health: http://localhost:8000/health

Stop with: docker compose down. Adding -v deletes local demo database and evidence.

## AWS deployment

Follow the full step-by-step instructions in docs/setup/AWS_STEP_BY_STEP.md. The default region is Sydney (ap-southeast-2). You will need an AWS account, short-lived AWS CLI credentials, Docker, Python 3.12, Terraform and npm. AWS resources are chargeable; NAT gateway and RDS have idle charges.

- Infrastructure: infrastructure/terraform/main.tf
- Build Lambda deployment ZIP: python infrastructure/scripts/build_lambda.py
- Build/publish React: bash infrastructure/scripts/deploy_frontend.sh
- Deployment output: terraform -chdir=infrastructure/terraform output

## Tests and collaboration

    PYTHONPATH=backend APP_ENV=local ALLOW_DEV_AUTH=true pytest backend/tests -q
    cd frontend && npm install && npm run build
    terraform -chdir=infrastructure/terraform fmt
    terraform -chdir=infrastructure/terraform validate

Work on feature branches, review PRs, and never commit secrets or real insurance records.

## Known non-implemented items

Guided AI intake, sophisticated anomaly checks, autonomous LangGraph agent workflow, quantitative visual-photo damage evaluation, anti-malware quarantine, benchmark-reconciled financial valuations, calibrated confidence, PDF/DOCX reports, notification delivery, audit log immutability, tested NFRs and production migration/secrets/retention practices. Details in docs/requirements/IMPLEMENTATION_MATRIX.md.

This capstone software must be tested only with fabricated or non-sensitive documents.
