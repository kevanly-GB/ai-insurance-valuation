# Implementation traceability — approved NIT3003 specification

Implemented or partially implemented in this branch:
- FR01 authentication and roles: Cognito JWT, claim ownership, assessor group.
- FR02–03 create claims and capture incident details: basic workflow.
- FR05 multi-format upload: PDF/DOCX/XLSX/CSV/JPG/PNG.
- FR06 validate files: extension, signature, upload size, hash duplicate, parse error; malware scanning not implemented.
- FR07 classify/extract: heuristic classification, PDF/Word/Excel/CSV text and Textract OCR; image damage valuation absent.
- FR09 assessor review: claim/document details view.
- FR10–11 request/reply additional evidence: implemented.
- FR12 run/re-run AI: implemented as synchronous evidence-driven evaluation.
- FR13–16 five domain analyses, anomalies, consolidated result: prototype rule-based specialists with optional Bedrock summaries; no autonomous LangGraph orchestration or calibrated confidences.
- FR19–20 manual override and valuation versions: implemented partially; overrides modify stored run.
- FR21–24 report draft, edit, approve and deliver: implemented in plain text, not PDF/DOCX.
- FR25–26 audit event recording and viewing: basic database audit.
- FR28–30 archive and lock: basic status lock.

Unimplemented or incomplete: FR04 AI intake assistant, dedicated FR08 summary, FR14 calibrated confidence, FR15 contradiction/outlier detection, FR17 version comparison, FR18 chat assistant, FR27 audit export, FR31 archived ML training (outside proposal scope). Claimed report turnaround, 90% OCR accuracy, 50 MB upload speed, five-minute AI completion, 99.5% uptime, accessibility compliance and security acceptance criteria have NOT been validated.

Valuation totals are sums of recognised line-labelled amounts from evidence, not fair market assessments, loss-adjustment recommendations or insurance entitlement decisions. Human assessor approval is mandatory.
