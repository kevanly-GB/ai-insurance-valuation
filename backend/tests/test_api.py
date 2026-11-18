import os
os.environ["APP_ENV"] = "local"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./ci_test.db"
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from app.models import engine, Base
from app.main import app

def test_health_and_auth_required():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/claims").status_code == 401

def test_claimant_cannot_assess():
    with TestClient(app) as client:
        response = client.post("/claims", headers={"Authorization": "Bearer dev-claimant"},
            json={"business_name":"Sample Manufacturing", "policy_number":"TEST-100", "incident_type":"Fire",
                  "incident_date":"2026-11-01"})
        assert response.status_code == 201
        cid = response.json()["id"]
        assert client.post("/claims/" + cid + "/valuations", headers={"Authorization":"Bearer dev-claimant"}).status_code == 403
        assert client.get("/claims/" + cid, headers={"Authorization":"Bearer dev-assessor"}).status_code == 200
