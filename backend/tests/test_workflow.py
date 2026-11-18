"""Synthetic end-to-end API test: claimant -> assessor -> published report -> archive."""
import io
import os
os.environ["APP_ENV"] = "local"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./ci_test.db"

from fastapi.testclient import TestClient
from app.main import app

CLAIMANT = {"Authorization": "Bearer dev-claimant"}
ASSESSOR = {"Authorization": "Bearer dev-assessor"}

def test_complete_claim_workflow():
    with TestClient(app) as client:
        c = client.post("/claims", headers=CLAIMANT, json={
            "business_name": "Synthetic Machinery Pty Ltd",
            "policy_number": "DEMO-SYN-2030",
            "incident_type": "Fire",
            "incident_date": "2026-09-01",
            "description": "Fictional incident and documents only."
        })
        assert c.status_code == 201, c.text
        cid = c.json()["id"]
        assert client.post("/claims/" + cid + "/valuations", headers=CLAIMANT).status_code == 403
        p = client.post("/claims/" + cid + "/documents/presign", headers=CLAIMANT, json={"filename": "asset_inventory.csv"})
        assert p.status_code == 201, p.text
        did = p.json()["document"]["id"]
        file_content = b"item,description\nMilling machine,replacement cost: AUD 12500.00\n"
        result = client.post("/claims/" + cid + "/documents/" + did + "/local-upload",
                             headers=CLAIMANT, files={"file": ("asset_inventory.csv", io.BytesIO(file_content), "text/csv")})
        assert result.status_code == 200, result.text
        assert result.json()["state"] == "processed"
        assert result.json()["classification"] == "assets"
        v = client.post("/claims/" + cid + "/valuations", headers=ASSESSOR)
        assert v.status_code == 201, v.text
        assert v.json()["estimate"] == 12500
        assert v.json()["findings"]["human_approval_required"]
        vid = v.json()["id"]
        override = client.post("/claims/" + cid + "/valuations/" + vid + "/override",
                               headers=ASSESSOR, json={"amount_aud": 12000, "reason": "Synthetic review adjustment"})
        assert override.status_code == 200
        draft = client.post("/claims/" + cid + "/reports", headers=ASSESSOR)
        assert draft.status_code == 201
        rid = draft.json()["id"]
        before = client.get("/claims/" + cid, headers=CLAIMANT).json()
        assert before["reports"] == []
        approval = client.post("/claims/" + cid + "/reports/" + rid + "/approve", headers=ASSESSOR)
        assert approval.status_code == 200
        published = client.get("/claims/" + cid, headers=CLAIMANT).json()
        assert published["reports"][0]["status"] == "approved"
        assert "12,000.00" in published["reports"][0]["body"]
        assert client.get("/claims/" + cid + "/audit", headers=CLAIMANT).status_code == 403
        audit = client.get("/claims/" + cid + "/audit", headers=ASSESSOR)
        assert audit.status_code == 200 and len(audit.json()) >= 5
        archive = client.post("/claims/" + cid + "/archive", headers=ASSESSOR)
        assert archive.status_code == 200
        assert archive.json()["status"] == "archived"
        assert client.post("/claims/" + cid + "/documents/presign", headers=CLAIMANT,
                           json={"filename": "new.csv"}).status_code == 409
