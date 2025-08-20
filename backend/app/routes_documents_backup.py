import os, re
from app.usage import require_quota, record_event, remaining_quota  # credits
from collections import Counter
from typing import Listfrom fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Sessionfrom app.db import get_db
from app.auth import get_current_user_id
from app.routes_billing import price_for, charity_percent_for_plan, log_transaction
from app.routes_billing import log_transaction
from app import models
from app.pricing import PRICES_CENTS_ONE_TIME, charity_percent_for_plan# PDF/Text libs
import pdfplumber
from pdf2docx import Converter
import PyPDF2# OCR libs
import pytesseract
from pdf2image import convert_from_path
from PIL import Image# Ak máš Homebrew Tesseract, uisti sa, že vieme nájsť binárku
if os.path.exists("/opt/homebrew/bin/tesseract"):
    pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"router = APIRouter(prefix="/documents", tags=["documents"])def _log_one_time(db, user_id: int, service: str, donate: bool = False, chosen_charity_id: int | None = None):
    """
    Zaloguje jednorazovú transakciu za službu 'service'.
    - donate=True => vypočíta charity_cents podľa plánu/politiky, inak 0
    - chosen_charity_id má prednosť, potom user.charity_id, potom 1
    """
    from app.models import User
    from app.pricing import PRICES_CENTS_ONE_TIME, charity_percent_for_plan
    from app.routes_billing import log_transaction    user = db.query(User).filter(User.id == user_id).first()    price = PRICES_CENTS_ONE_TIME.get(service)
    if price is None:
        return  # neznáma služba -> nič nelogujeme    # plán používateľa (ak nie je, berieme 'free')
    plan = getattr(user, "subscription_plan", None) or getattr(user, "plan", None) or "free"    # percento pre charitu: len keď donate=True
    percent = charity_percent_for_plan('one_time' if plan == 'free' else plan) if donate else 0.0    charity_cents = int(round(price * percent))
    cid = chosen_charity_id or (getattr(user, 'charity_id', None) or 1)    # zapíš transakciu (amount_cents = celá cena, charity_cents = dar)
    log_transaction(db, user_id, service, price, charity_cents, cid, meta={})# --- Helpers
# --- Helpers ---
# --- Helpers ---
def uploads_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")def _clean_text(txt: str) -> str:
    return re.sub(r"\s+", " ", (txt or "")).strip()def _stats(txt: str) -> dict:
    words = re.findall(r"\b\w+\b", txt.lower(), flags=re.UNICODE)
    return {
        "chars": len(txt),
        "words": len(words),
        "unique_words": len(set(words)),
        "top_words": Counter(w for w in words if len(w) > 2).most_common(10),
    }def _extract_text_pdfplumber(path: str) -> str:
    """Skúsime bežný extraktor (funguje, ak PDF má textovú vrstvu)."""
    try:
        with pdfplumber.open(path) as pdf:
            chunks: List[str] = []
            for p in pdf.pages:
                chunks.append(p.extract_text() or "")
            text = "\n".join(chunks)
            return _clean_text(text)
    except Exception:
        return ""def _extract_text_ocr(path: str) -> str:
    """OCR fallback."""
    try:
        images = convert_from_path(path)  # vyžaduje poppler (brew install poppler)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF to image failed: {e}")    out_texts: List[str] = []
    for img in images:
        try:
            txt = pytesseract.image_to_string(img, lang="eng")
        except Exception:
            txt = pytesseract.image_to_string(img)
        out_texts.append(txt or "")    return _clean_text("\n".join(out_texts))def _extract_text_with_ocr_fallback(path: str) -> str:
    text = _extract_text_pdfplumber(path)
    if text:
        return text
    return _extract_text_ocr(path)# --- Endpoints ---
@router.get("/")
def list_documents(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    docs = (
        db.query(models.Document)
        .filter(models.Document.user_id == int(current_user_id))
        .order_by(models.Document.id.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "original_filename": d.original_filename,
            "stored_filename": d.stored_filename,
            "status": d.status,
            "pages": d.pages,
        }
        for d in docs
    ]@router.get("/{doc_id}")
def get_document(doc_id: int, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == doc_id, models.Document.user_id == int(current_user_id))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc.id,
        "original_filename": doc.original_filename,
        "stored_filename": doc.stored_filename,
        "status": doc.status,
        "pages": doc.pages,
    }@router.get("/{doc_id}/download")
def download_document(doc_id: int, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == doc_id, models.Document.user_id == int(current_user_id))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")    file_path = os.path.join(uploads_dir(), doc.stored_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=410, detail="File no longer exists")    return FileResponse(
        path=file_path,
        filename=doc.original_filename,
        media_type="application/pdf"
    )@router.get("/{doc_id}/download-protected")
def download_protected(doc_id: int, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == doc_id, models.Document.user_id == int(current_user_id))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")    name, _ = os.path.splitext(doc.stored_filename)
    file_path = os.path.join(uploads_dir(), f"{name}_protected.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Protected copy not found. Call /protect first.")    download_name = f"{os.path.splitext(doc.original_filename)[0]} (protected).pdf"
    return FileResponse(path=file_path, filename=download_name, media_type="application/pdf")class ProtectRequest(BaseModel):
    password: str
    donate: bool | None = False
    charity_id: int | None = None
    donate: bool = False
    charity_id: int | None = Noneclass ConvertOptions(BaseModel):
    donate: bool = False
    charity_id: int | None = None@router.post("/{doc_id}/protect")
def protect_document(
    doc_id: int,
    body: ProtectRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if not body.password or len(body.password) < 3:
        raise HTTPException(status_code=400, detail="Password must be at least 3 characters")    doc = (
        db.query(models.Document)
        .filter(models.Document.id == doc_id, models.Document.user_id == int(current_user_id))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")    src_path = os.path.join(uploads_dir(), doc.stored_filename)
    if not os.path.exists(src_path):
        raise HTTPException(status_code=410, detail="Source file is missing")    name, _ = os.path.splitext(doc.stored_filename)
    dst_path = os.path.join(uploads_dir(), f"{name}_protected.pdf")    try:
        reader = PyPDF2.PdfReader(src_path)
        writer = PyPDF2.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(user_password=body.password, owner_password=body.password, use_128bit=True)
        with open(dst_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Encrypt failed: {e}")    from app.routes_billing import log_transaction, price_for
    user = db.query(models.User).filter(models.User.id == int(current_user_id)).first()
    price = price_for("protect")
    percent = charity_percent_for_plan(getattr(user, "subscription_plan", None) or getattr(user, "plan", "free")) if body.donate else 0.0
    charity_cents = int(round(price * percent))
    cid = body.charity_id or getattr(user, "charity_id", None) or 1
    log_transaction(db, int(current_user_id), "protect", price, charity_cents, cid)
    return {
        "ok": True,
        "original_filename": doc.original_filename,
        "protected_filename": os.path.basename(dst_path),
        "stored_dir": uploads_dir()
    }@router.post("/{doc_id}/convert/docx")
def convert_to_docx(doc_id: int, body: ConvertOptions = ConvertOptions(), current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == doc_id, models.Document.user_id == int(current_user_id))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")    base, _ = os.path.splitext(doc.stored_filename)
    for name in [doc.stored_filename, f"{base}_protected.pdf", f"{base}.docx"]:
        path = os.path.join(uploads_dir(), name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass    db.delete(doc)
    db.commit()
    return {"ok": True, "deleted_id": doc_id}