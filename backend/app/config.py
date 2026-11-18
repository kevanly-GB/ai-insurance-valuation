"""Environment-specific configuration; production credentials are never stored in Git."""
import json
import os
from functools import lru_cache
from sqlalchemy.engine import URL

APP_ENV = os.getenv("APP_ENV", "local")
REGION = os.getenv("AWS_REGION", "ap-southeast-2")
BUCKET = os.getenv("S3_BUCKET_NAME", "")
QUEUE_URL = os.getenv("PROCESS_QUEUE_URL", "")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID", "")
ORIGINS = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
MAX_BYTES = 50 * 1024 * 1024
FORMATS = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".csv": "text/csv", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

@lru_cache
def database_url():
    explicit = os.getenv("DATABASE_URL", "")
    if explicit:
        return explicit
    arn = os.getenv("DB_SECRET_ARN", "")
    if arn:
        import boto3
        secret = json.loads(boto3.client("secretsmanager", region_name=REGION).get_secret_value(SecretId=arn)["SecretString"])
        return URL.create("postgresql+psycopg", username=secret["username"], password=secret["password"], host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")), database=os.getenv("PGDATABASE", "insurance"))
    if APP_ENV == "local":
        return "sqlite:///./local_insurance.db"
    raise RuntimeError("Missing DB_SECRET_ARN or DATABASE_URL")
