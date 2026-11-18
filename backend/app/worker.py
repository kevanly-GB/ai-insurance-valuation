"""SQS worker invoked after S3 upload completes; failed docs remain inspectable."""
from app.models import initialize
from app.processing import process_document

def handler(event, context):
    initialize()
    failures = []
    for record in event.get("Records", []):
        try:
            process_document(record["body"])
        except Exception:
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
