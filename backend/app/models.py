"""Relational record of claims, source evidence, agent runs, human decisions and audits."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import database_url

def ident():
    return str(uuid.uuid4())

def utcnow():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    owner_sub: Mapped[str] = mapped_column(String(100), index=True)
    business_name: Mapped[str] = mapped_column(String(200))
    policy_number: Mapped[str] = mapped_column(String(100))
    incident_type: Mapped[str] = mapped_column(String(100))
    incident_date: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(150))
    object_key: Mapped[str] = mapped_column(String(650), unique=True)
    state: Mapped[str] = mapped_column(String(25), default="pending")
    classification: Mapped[str] = mapped_column(String(50), default="unknown")
    text: Mapped[str] = mapped_column(Text, default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("claim_id", "sha256", name="uq_claim_document_digest"),)

class Valuation(Base):
    __tablename__ = "valuations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    estimate: Mapped[float] = mapped_column(Float, default=0)
    override_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    override_reason: Mapped[str] = mapped_column(Text, default="")
    findings_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("claim_id", "version", name="uq_claim_run"),)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    valuation_id: Mapped[str] = mapped_column(ForeignKey("valuations.id"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(25), default="draft")
    approved_by: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class EvidenceRequest(Base):
    __tablename__ = "evidence_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Audit(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    actor_sub: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

url = database_url()
engine = create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False} if str(url).startswith("sqlite") else {}, pool_size=2 if not str(url).startswith("sqlite") else 5, max_overflow=1)
Session = sessionmaker(bind=engine, expire_on_commit=False)

def initialize():
    Base.metadata.create_all(engine)

def audit(db, claim_id, actor, action, details=""):
    db.add(Audit(claim_id=claim_id, actor_sub=actor, action=action, details=str(details)[:2000]))
