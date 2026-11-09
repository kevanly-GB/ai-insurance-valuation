# Multi-Agent AI Insurance Valuation Platform

University capstone project: a multi-modal document assessment and evidence-linked insurance valuation support platform for commercial and property claims.

> **Current state:** repository folder scaffold only. The frontend, backend, AWS resources, database, and AI workflows still need to be implemented. Nothing in this repository should be treated as a deployed insurance decision system.

## Intended workflow
1. Claimant signs in and creates an insurance claim.
2. Claimant uploads supporting PDFs, DOCX, XLSX/CSV files and photographs.
3. Backend validates files and stores evidence in Amazon S3.
4. Document processing classifies and extracts content, including OCR as needed.
5. Specialised AI agents analyse assets, human capital, finance, property damage and legal/policy evidence; an orchestrator consolidates findings and checks anomalies.
6. Claims assessor reviews evidence-linked valuations, corrects results where necessary, approves and publishes a client-facing report.
7. Assessment versions, actions and approvals are logged for audit.

## Planned technologies
- **Frontend:** React
- **Backend:** Python and FastAPI
- **Data:** PostgreSQL for records; Amazon S3 for evidence and generated reports
- **Authentication:** Amazon Cognito (proposed)
- **Document processing:** Amazon Textract, PyMuPDF, pandas, openpyxl, and image processing tools as appropriate
- **Agent coordination:** LangGraph and a configurable LLM provider
- **Infrastructure:** AWS, with Terraform configuration to be added in `infrastructure/`
- **Tests:** pytest, frontend tests and end-to-end workflows

## Repository layout
- `frontend/` — React user interfaces for claimants and assessors
- `backend/app/api/` — FastAPI endpoints
- `backend/app/agents/` — intake, specialist agents, orchestrator, anomaly detection, prompts and tools
- `backend/app/services/` — document extraction, S3 storage, valuation, reporting, audit and notifications
- `backend/tests/` — backend unit and integration tests
- `database/` — PostgreSQL migrations, schemas/queries and seed data
- `infrastructure/` — AWS infrastructure-as-code, scripts and monitoring
- `sample-documents/` — **synthetic/non-sensitive** test evidence, organised by document type
- `docs/` — system design, requirements, diagrams, setup and security decisions
- `tests/` — cross-service end-to-end, performance and security tests
- `.github/` — CI workflows and contribution templates when implemented

## Development sequence
1. Initialise React and FastAPI projects; add a working health-check endpoint and an API call from React.
2. Set up PostgreSQL migrations, Cognito authentication and role-based access control.
3. Implement claim creation, S3 upload, validation and document classification/extraction.
4. Implement one AI specialist end-to-end, then add the other agents and LangGraph orchestration.
5. Add assessor review, valuation report generation, version tracking and audit logging.
6. Add automated tests, deploy to a controlled AWS development environment, and validate with synthetic documents.

Use `.env.example` for configuration names. Never commit API keys, cloud credentials, real insurance records or personally identifiable claimant information. See `CONTRIBUTING.md` for collaboration guidance.
