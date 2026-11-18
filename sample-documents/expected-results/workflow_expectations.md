# Synthetic smoke-test expectations

Using sample-documents/asset-registers/asset_inventory.csv, an assessor should see an Asset Valuation Agent value of AUD 12,500.00 when it is the only accepted source. The four other domain agents should flag missing evidence, as no financial, payroll, property or policy documents were supplied. The overall estimate is illustrative, not a fair-value assessment. Human approval is mandatory.

The automated integration test in backend/tests/test_workflow.py exercises claim creation, CSV upload/processing, valuation, evidence traceability, override justification, draft report confidentiality, approval, audit and archive lock.
