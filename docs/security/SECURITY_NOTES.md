# Security posture and outstanding risks

Use only synthetic documents; no genuine customer PII or financial data.

Implemented: Cognito signed-access JWT validation, claimant-ownership checks, privileged assessor group, private S3 buckets and CloudFront origin control, 50MB presigned upload policy, SHA256 digest, basic file signature validation, DB encryption, RDS in private subnets, Secrets Manager DB password, segregated SQS worker, CloudWatch logs and database audit events. Approved/archived claims prevent further writes.

Unresolved and necessary for a real deployment: malware quarantine and file content sniffing, DOCX/XLSX decompression-bomb protection, direct media image analysis, OCR accuracy validation, case-by-case authorization review, IP protections/rate limiting, WAF, strict retention and backup restoration, migration lifecycle, immutable audit storage, alerting, penetration tests, privacy impact assessment, and compliant data residency and deletion practices. Bedrock prompts explicitly treat documents as untrusted data but this is not a formal prompt injection defense.
