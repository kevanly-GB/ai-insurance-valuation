"""S3 direct upload and protected local demo file storage."""
from pathlib import Path
import os
import boto3
from fastapi import HTTPException
from app.config import APP_ENV, BUCKET, MAX_BYTES, REGION

s3 = boto3.client("s3", region_name=REGION)
LOCAL_DIR = Path(os.getenv("LOCAL_UPLOAD_DIR", ".local_uploads"))

def prepare_upload(key, mime):
    if APP_ENV == "local":
        return {"mode": "local"}
    if not BUCKET:
        raise HTTPException(503, "S3 bucket not configured")
    form = s3.generate_presigned_post(
        Bucket=BUCKET, Key=key, Fields={"Content-Type": mime},
        Conditions=[{"Content-Type": mime}, ["content-length-range", 1, MAX_BYTES]],
        ExpiresIn=600,
    )
    return {"mode": "s3", **form}

def read_content(doc):
    if APP_ENV == "local":
        path = (LOCAL_DIR / doc.object_key).resolve()
        if not path.is_relative_to(LOCAL_DIR.resolve()):
            raise ValueError("Invalid local path")
        return path.read_bytes()
    obj = s3.get_object(Bucket=BUCKET, Key=doc.object_key)
    if int(obj.get("ContentLength", 0)) > MAX_BYTES:
        raise ValueError("File exceeds 50 MB")
    return obj["Body"].read(MAX_BYTES + 1)

def save_local(key, data):
    path = (LOCAL_DIR / key).resolve()
    if not path.is_relative_to(LOCAL_DIR.resolve()):
        raise ValueError("Invalid path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def document_link(doc):
    if APP_ENV == "local":
        return None
    return s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": doc.object_key}, ExpiresIn=120)
