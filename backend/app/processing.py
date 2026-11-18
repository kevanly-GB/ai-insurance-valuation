"""File signature checking, multimodal text extraction, OCR and transparent classification."""
import hashlib
import io
import re
from pathlib import Path
import boto3
import fitz
from docx import Document as WordDoc
from openpyxl import load_workbook
from sqlalchemy import select
from app.config import MAX_BYTES, REGION, APP_ENV
from app.models import Session, Document, audit
from app.storage import read_content

LABELS = {
    "assets": ("asset", "inventory", "machine", "equipment", "replacement"),
    "human_capital": ("payroll", "salary", "wage", "staff", "employee"),
    "finance": ("revenue", "profit", "financial", "income", "business interruption"),
    "property": ("property", "repair", "building", "damage", "survey"),
    "legal": ("policy", "exclusion", "coverage", "insurance contract"),
}
def classify(filename, text):
    hay = (filename + " " + text[:4000]).lower()
    scores = {label: sum(hay.count(word) for word in words) for label, words in LABELS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "unknown"

def validate_signature(ext, data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Document empty or exceeds 50 MB")
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise ValueError("Invalid PDF signature")
    if ext in (".docx", ".xlsx") and not data.startswith(b"PK\x03\x04"):
        raise ValueError("Invalid Office file signature")
    if ext in (".jpg", ".jpeg") and not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("Invalid JPEG signature")
    if ext == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG signature")
    if ext == ".csv" and b"\x00" in data[:4096]:
        raise ValueError("Invalid CSV data")

def ocr_image(data):
    if APP_ENV == "local" or len(data) > 5 * 1024 * 1024:
        return "[Image OCR unavailable in local mode or image too large]"
    response = boto3.client("textract", region_name=REGION).detect_document_text(Document={"Bytes": data})
    return "\n".join(block["Text"] for block in response.get("Blocks", []) if block.get("BlockType") == "LINE")

def extract(ext, data):
    if ext == ".pdf":
        output = []
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.page_count > 100:
                raise ValueError("PDF exceeds 100-page demo processing limit")
            for page in pdf:
                value = page.get_text("text")
                if not value.strip():
                    image = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False).tobytes("jpeg", jpg_quality=75)
                    value = ocr_image(image)
                output.append("[page " + str(page.number + 1) + "] " + value)
        return "\n".join(output)[:120000]
    if ext == ".docx":
        doc = WordDoc(io.BytesIO(data))
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                lines.append(" | ".join(c.text for c in row.cells))
        return "\n".join(lines)[:120000]
    if ext == ".xlsx":
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        rows = []
        for sheet in wb.worksheets:
            rows.append("[sheet " + sheet.title + "]")
            for row in sheet.iter_rows(max_row=3000, values_only=True):
                rows.append(" | ".join(str(v) if v is not None else "" for v in row[:30]))
        wb.close()
        return "\n".join(rows)[:120000]
    if ext == ".csv":
        return data.decode("utf-8-sig", errors="replace")[:120000]
    return ocr_image(data)

def process_document(document_id):
    with Session() as db:
        doc = db.get(Document, document_id)
        if doc is None or doc.state == "processed":
            return
        try:
            data = read_content(doc)
            ext = Path(doc.filename).suffix.lower()
            validate_signature(ext, data)
            digest = hashlib.sha256(data).hexdigest()
            duplicate = db.scalar(select(Document).where(Document.claim_id == doc.claim_id, Document.sha256 == digest, Document.id != doc.id))
            if duplicate:
                raise ValueError("Duplicate evidence: " + duplicate.id)
            text = extract(ext, data)
            doc.sha256 = digest
            doc.byte_size = len(data)
            doc.classification = classify(doc.filename, text)
            doc.text = text
            doc.error = ""
            doc.state = "processed"
            audit(db, doc.claim_id, "system", "document.processed", doc.id + " " + doc.classification)
        except Exception as exc:
            doc.state = "failed"
            doc.error = str(exc)[:300]
            audit(db, doc.claim_id, "system", "document.failed", doc.id + " " + doc.error)
        db.commit()
