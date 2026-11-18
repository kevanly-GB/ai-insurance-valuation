"""REST service for insured claimants and independent human assessors."""
import json
import os
import re
import uuid
from datetime import date
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from mangum import Mangum
from app.auth import current_user, assessor
from app.config import APP_ENV, BUCKET, FORMATS, MAX_BYTES, QUEUE_URL, ORIGINS, REGION
from app.models import Claim, Document, Valuation, Report, EvidenceRequest, Audit, Session, initialize, audit
from app.storage import prepare_upload, save_local, document_link
from app.processing import process_document
from app.agents.valuation import evaluate

app = FastAPI(title="AI Insurance Valuation Support API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

@app.on_event("startup")
def startup():
    initialize()

class ClaimIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=200)
    policy_number: str = Field(min_length=2, max_length=100)
    incident_type: str = Field(min_length=2, max_length=100)
    incident_date: date
    description: str = Field(default="", max_length=6000)

class UploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)

class RequestIn(BaseModel):
    message: str = Field(min_length=5, max_length=2000)

class ReplyIn(BaseModel):
    response: str = Field(min_length=1, max_length=2000)

class OverrideIn(BaseModel):
    amount_aud: float = Field(ge=0, le=1_000_000_000)
    reason: str = Field(min_length=10, max_length=2000)

class ReportIn(BaseModel):
    body: str = Field(min_length=10, max_length=30000)

def claim_record(c):
    return {"id": c.id, "owner_sub": c.owner_sub, "business_name": c.business_name, "policy_number": c.policy_number, "incident_type": c.incident_type, "incident_date": c.incident_date, "description": c.description, "status": c.status, "created_at": c.created_at}

def document_record(d):
    return {"id": d.id, "filename": d.filename, "state": d.state, "classification": d.classification, "error": d.error, "size": d.byte_size, "text_preview": d.text[:1200] if d.state == "processed" else ""}

def run_record(v):
    return {"id": v.id, "version": v.version, "estimate": v.estimate, "override_amount": v.override_amount, "override_reason": v.override_reason, "findings": json.loads(v.findings_json), "created_at": v.created_at}

def report_record(r, include_body=True):
    d = {"id": r.id, "status": r.status, "valuation_id": r.valuation_id, "approved_by": r.approved_by, "created_at": r.created_at}
    if include_body:
        d["body"] = r.body
    return d

def visible_claim(db, cid, user, write=False):
    c = db.get(Claim, cid)
    if c is None or (user["role"] != "assessor" and c.owner_sub != user["sub"]):
        raise HTTPException(404, "Claim not found")
    if write and c.status == "archived":
        raise HTTPException(409, "Archived claims are read-only")
    return c

@app.get("/health")
def health():
    return {"status": "ok", "environment": APP_ENV}

@app.get("/config")
def config():
    return {"demo_mode": APP_ENV == "local" and os.getenv("ALLOW_DEV_AUTH") == "true", "max_upload_mb": 50}

@app.get("/me")
def me(user=Depends(current_user)):
    return user

@app.post("/claims", status_code=201)
def create_claim(payload: ClaimIn, user=Depends(current_user)):
    if user["role"] != "claimant":
        raise HTTPException(403, "Only claimants create claims")
    with Session() as db:
        c = Claim(owner_sub=user["sub"], **payload.model_dump(mode="json"))
        db.add(c)
        db.flush()
        audit(db, c.id, user["sub"], "claim.created")
        db.commit()
        return claim_record(c)

@app.get("/claims")
def list_claims(user=Depends(current_user)):
    with Session() as db:
        stmt = select(Claim).order_by(Claim.created_at.desc())
        if user["role"] != "assessor":
            stmt = stmt.where(Claim.owner_sub == user["sub"])
        return [claim_record(c) for c in db.scalars(stmt)]

@app.get("/claims/{cid}")
def get_claim(cid: str, user=Depends(current_user)):
    with Session() as db:
        c = visible_claim(db, cid, user)
        docs = db.scalars(select(Document).where(Document.claim_id == cid).order_by(Document.created_at)).all()
        runs = db.scalars(select(Valuation).where(Valuation.claim_id == cid).order_by(Valuation.version.desc())).all()
        reports = db.scalars(select(Report).where(Report.claim_id == cid).order_by(Report.created_at.desc())).all()
        requests = db.scalars(select(EvidenceRequest).where(EvidenceRequest.claim_id == cid)).all()
        return {**claim_record(c), "documents": [document_record(d) for d in docs],
                "valuations": [run_record(v) for v in runs],
                "reports": [report_record(r, user["role"] == "assessor" or r.status == "approved") for r in reports if user["role"] == "assessor" or r.status == "approved"],
                "evidence_requests": [{"id": e.id, "message": e.message, "response": e.response} for e in requests]}

@app.post("/claims/{cid}/documents/presign", status_code=201)
def presign(cid: str, payload: UploadIn, user=Depends(current_user)):
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        if user["role"] != "claimant":
            raise HTTPException(403, "Claimant upload only")
        filename = Path(payload.filename).name
        ext = Path(filename).suffix.lower()
        if ext not in FORMATS or filename in (".", ".."):
            raise HTTPException(400, "Unsupported extension")
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)[:100]
        d = Document(claim_id=cid, filename=filename, mime_type=FORMATS[ext], object_key="claims/" + cid + "/" + uuid.uuid4().hex + "/" + safe)
        db.add(d)
        db.flush()
        result = prepare_upload(d.object_key, d.mime_type)
        audit(db, cid, user["sub"], "document.presigned", d.id)
        db.commit()
        return {"document": document_record(d), "upload": result}

@app.post("/claims/{cid}/documents/{did}/local-upload")
async def local_upload(cid: str, did: str, file: UploadFile = File(...), user=Depends(current_user)):
    if APP_ENV != "local":
        raise HTTPException(404, "Local upload disabled")
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        d = db.get(Document, did)
        if user["role"] != "claimant" or d is None or d.claim_id != cid or d.state != "pending":
            raise HTTPException(403, "Upload not permitted")
        data = await file.read(MAX_BYTES + 1)
        if not data or len(data) > MAX_BYTES:
            raise HTTPException(413, "Upload size exceeds limit")
        save_local(d.object_key, data)
        d.state = "queued"
        audit(db, cid, user["sub"], "document.uploaded", did)
        db.commit()
    process_document(did)
    with Session() as db:
        return document_record(db.get(Document, did))

@app.post("/claims/{cid}/documents/{did}/complete")
def complete_upload(cid: str, did: str, user=Depends(current_user)):
    if APP_ENV == "local":
        raise HTTPException(400, "Use local-upload in local mode")
    import boto3
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        d = db.get(Document, did)
        if user["role"] != "claimant" or not d or d.claim_id != cid:
            raise HTTPException(403, "Upload not permitted")
        if d.state != "pending":
            return document_record(d)
        try:
            obj = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=d.object_key)
        except Exception:
            raise HTTPException(400, "S3 upload missing")
        if int(obj.get("ContentLength", 0)) < 1 or int(obj["ContentLength"]) > MAX_BYTES:
            raise HTTPException(400, "Invalid S3 object size")
        if obj.get("ContentType") != d.mime_type:
            raise HTTPException(400, "Unexpected content type")
        d.state = "queued"
        audit(db, cid, user["sub"], "document.uploaded", did)
        db.commit()
    if QUEUE_URL:
        boto3.client("sqs", region_name=REGION).send_message(QueueUrl=QUEUE_URL, MessageBody=did)
    else:
        process_document(did)
    return {"id": did, "state": "queued"}

@app.get("/claims/{cid}/documents/{did}/download")
def download_document(cid: str, did: str, user=Depends(current_user)):
    with Session() as db:
        visible_claim(db, cid, user)
        d = db.get(Document, did)
        if d is None or d.claim_id != cid or d.state not in ("processed", "queued"):
            raise HTTPException(404, "Document unavailable")
        link = document_link(d)
        if link is None:
            raise HTTPException(400, "Local downloads not supported; use source test files")
        return {"url": link, "expires_seconds": 120}

@app.post("/claims/{cid}/evidence-requests", status_code=201)
def request_evidence(cid: str, payload: RequestIn, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        e = EvidenceRequest(claim_id=cid, message=payload.message)
        db.add(e)
        c.status = "additional_evidence_requested"
        audit(db, cid, user["sub"], "evidence.requested", payload.message)
        db.commit()
        return {"id": e.id, "message": e.message}

@app.post("/claims/{cid}/evidence-requests/{rid}/reply")
def reply_evidence(cid: str, rid: str, payload: ReplyIn, user=Depends(current_user)):
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        e = db.get(EvidenceRequest, rid)
        if user["role"] != "claimant" or e is None or e.claim_id != cid:
            raise HTTPException(403, "Not authorised")
        e.response = payload.response
        c.status = "submitted"
        audit(db, cid, user["sub"], "evidence.replied", rid)
        db.commit()
        return {"id": rid, "response": e.response}

@app.post("/claims/{cid}/valuations", status_code=201)
def run_valuation(cid: str, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        docs = db.scalars(select(Document).where(Document.claim_id == cid, Document.state == "processed")).all()
        if not docs:
            raise HTTPException(409, "No processed evidence")
        result = evaluate(docs)
        n = (db.scalar(select(func.max(Valuation.version)).where(Valuation.claim_id == cid)) or 0) + 1
        v = Valuation(claim_id=cid, version=n, estimate=result["total_aud"], findings_json=json.dumps(result))
        db.add(v)
        c.status = "valuation_review"
        audit(db, cid, user["sub"], "valuation.ran", "version " + str(n))
        db.commit()
        return run_record(v)

@app.post("/claims/{cid}/valuations/{vid}/override")
def override(cid: str, vid: str, payload: OverrideIn, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        visible_claim(db, cid, user, write=True)
        v = db.get(Valuation, vid)
        if not v or v.claim_id != cid:
            raise HTTPException(404, "Valuation not found")
        v.override_amount = payload.amount_aud
        v.override_reason = payload.reason
        audit(db, cid, user["sub"], "valuation.overridden", "version " + str(v.version) + " reason: " + payload.reason)
        db.commit()
        return run_record(v)

@app.post("/claims/{cid}/reports", status_code=201)
def create_report(cid: str, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        v = db.scalar(select(Valuation).where(Valuation.claim_id == cid).order_by(Valuation.version.desc()))
        if not v:
            raise HTTPException(409, "Run valuation first")
        result = json.loads(v.findings_json)
        amount = v.override_amount if v.override_amount is not None else v.estimate
        lines = ["INSURANCE VALUATION SUPPORT REPORT — DRAFT", "Business: " + c.business_name, "Policy: " + c.policy_number, "Incident: " + c.incident_type + " (" + c.incident_date + ")", "Assessment version: " + str(v.version), "Indicative documented total: AUD " + format(amount, ",.2f"), ""]
        for agent in result["agents"]:
            lines.append(agent["agent"] + ": AUD " + format(agent["estimate_aud"], ",.2f"))
            for ref in agent["evidence"]:
                lines.append("  Evidence " + ref["document_id"] + " line " + str(ref["line"]) + ": " + ref["excerpt"])
            lines.append("  " + agent["summary"])
        lines += ["", "FLAGS / GAPS"] + ["- " + a for a in result["anomalies"]]
        if v.override_reason:
            lines += ["", "Assessor override: " + v.override_reason]
        lines += ["", "Human assessor review is mandatory; this is not a coverage or payment decision."]
        r = Report(claim_id=cid, valuation_id=v.id, body="\n".join(lines))
        db.add(r)
        audit(db, cid, user["sub"], "report.drafted", "valuation " + str(v.version))
        db.commit()
        return report_record(r)

@app.post("/claims/{cid}/reports/{rid}/edit")
def edit_report(cid: str, rid: str, payload: ReportIn, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        visible_claim(db, cid, user, write=True)
        r = db.get(Report, rid)
        if not r or r.claim_id != cid or r.status != "draft":
            raise HTTPException(409, "Report is not editable")
        r.body = payload.body
        audit(db, cid, user["sub"], "report.edited", rid)
        db.commit()
        return report_record(r)

@app.post("/claims/{cid}/reports/{rid}/approve")
def approve_report(cid: str, rid: str, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        r = db.get(Report, rid)
        if r is None or r.claim_id != cid or r.status != "draft":
            raise HTTPException(409, "Only draft reports can be approved")
        r.status = "approved"
        r.approved_by = user["sub"]
        c.status = "approved"
        audit(db, cid, user["sub"], "report.approved", rid)
        db.commit()
        return report_record(r)

@app.post("/claims/{cid}/archive")
def archive(cid: str, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        c = visible_claim(db, cid, user, write=True)
        if c.status != "approved":
            raise HTTPException(409, "Only approved claims can be archived")
        c.status = "archived"
        audit(db, cid, user["sub"], "claim.archived")
        db.commit()
        return claim_record(c)

@app.get("/claims/{cid}/audit")
def audit_trail(cid: str, user=Depends(current_user)):
    assessor(user)
    with Session() as db:
        visible_claim(db, cid, user)
        items = db.scalars(select(Audit).where(Audit.claim_id == cid).order_by(Audit.created_at)).all()
        return [{"action": x.action, "actor": x.actor_sub, "details": x.details, "created_at": x.created_at} for x in items]

handler = Mangum(app, lifespan="on")
