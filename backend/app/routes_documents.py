import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import PyPDF2
from pdf2docx import Converter

from app import models
from app.db import get_db
from app.auth import get_current_user_id
# Billing – používame jednotné funkcie z routes_billing, aby bola logika cien a % na jednom mieste
from app.routes_billing import log_transaction, price_for, charity_percent_for_plan

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------- helpers ----------
def uploads_dir() -> str:
    # backend/app -> backend/uploads
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


def _ensure_user_doc(db: Session, uid: int, doc_id: int) -> models.Document:
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == doc_id, models.Document.user_id == uid)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ---------- (voliteľné) schémy ak by si chcel JSON verzie neskôr ----------
class ProtectRequest(BaseModel):
    password: str
    donate: bool = False
    charity_id: Optional[int] = None


class ConvertOptions(BaseModel):
    donate: bool = False
    charity_id: Optional[int] = None


# ---------- endpoints ----------
@router.get("/")
def list_documents(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    docs: List[models.Document] = (
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
    ]


@router.get("/{doc_id}")
def get_document(
    doc_id: int,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doc = _ensure_user_doc(db, int(current_user_id), doc_id)
    return {
        "id": doc.id,
        "original_filename": doc.original_filename,
        "stored_filename": doc.stored_filename,
        "status": doc.status,
        "pages": doc.pages,
    }


@router.get("/{doc_id}/download")
def download_document(
    doc_id: int,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doc = _ensure_user_doc(db, int(current_user_id), doc_id)
    file_path = os.path.join(uploads_dir(), doc.stored_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=410, detail="File no longer exists")

    return FileResponse(
        path=file_path,
        filename=doc.original_filename,
        media_type="application/pdf"
    )


@router.get("/{doc_id}/download-protected")
def download_protected(
    doc_id: int,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doc = _ensure_user_doc(db, int(current_user_id), doc_id)
    name, _ = os.path.splitext(doc.stored_filename)
    file_path = os.path.join(uploads_dir(), f"{name}_protected.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Protected copy not found. Call /protect first.")

    download_name = f"{os.path.splitext(doc.original_filename)[0]} (protected).pdf"
    return FileResponse(path=file_path, filename=download_name, media_type="application/pdf")


@router.post("/{doc_id}/protect")
def protect_document(
    doc_id: int,
    password: str = Form(...),
    donate: bool = Form(False),
    charity_id: Optional[int] = Form(None),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    if not password or len(password) < 3:
        raise HTTPException(status_code=400, detail="Password must be at least 3 characters")

    uid = int(current_user_id)
    doc = _ensure_user_doc(db, uid, doc_id)

    src_path = os.path.join(uploads_dir(), doc.stored_filename)
    if not os.path.exists(src_path):
        raise HTTPException(status_code=410, detail="Source file is missing")

    name, _ = os.path.splitext(doc.stored_filename)
    dst_path = os.path.join(uploads_dir(), f"{name}_protected.pdf")

    # --- create protected PDF ---
    try:
        reader = PyPDF2.PdfReader(src_path)
        writer = PyPDF2.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(user_password=password, owner_password=password, use_128bit=True)
        with open(dst_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Encrypt failed: {e}")

    # --- billing log ---
    user = db.query(models.User).filter(models.User.id == uid).first()
    service = "protect"
    price = price_for(service)  # napr. 30 centov
    plan = getattr(user, "subscription_plan", None) or getattr(user, "plan", "free")
    eff_plan = ("one_time" if str(plan).lower()=="free" else plan)
    percent = charity_percent_for_plan(eff_plan) if donate else 0.0
    charity_cents = int(round(price * percent))
    cid = charity_id or getattr(user, "charity_id", None) or 1

    log_transaction(db, uid, service, price, charity_cents, cid, meta={"doc_id": doc_id})

    return {
        "ok": True,
        "original_filename": doc.original_filename,
        "protected_filename": os.path.basename(dst_path),
        "stored_dir": uploads_dir()
    }


@router.post("/{doc_id}/convert/docx")
def convert_to_docx(
    doc_id: int,
    donate: bool = Form(False),
    charity_id: Optional[int] = Form(None),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Konvertuje PDF -> DOCX do uploads/<base>.docx a zaloguje transakciu.
    """
    uid = int(current_user_id)
    doc = _ensure_user_doc(db, uid, doc_id)

    src_path = os.path.join(uploads_dir(), doc.stored_filename)
    if not os.path.exists(src_path):
        raise HTTPException(status_code=410, detail="Source file is missing")

    base, _ = os.path.splitext(doc.stored_filename)
    dst_path = os.path.join(uploads_dir(), f"{base}.docx")

    # prípadné staré verzie odstráň
    for name in [f"{base}_protected.pdf", f"{base}.docx"]:
        path = os.path.join(uploads_dir(), name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    # --- convert PDF -> DOCX ---
    try:
        cv = Converter(src_path)
        cv.convert(dst_path, start=0, end=None)
        cv.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF->DOCX failed: {e}")

    # --- billing log ---
    user = db.query(models.User).filter(models.User.id == uid).first()
    service = "convert_docx"
    price = price_for(service)  # napr. 100 centov
    plan = getattr(user, "subscription_plan", None) or getattr(user, "plan", "free")
    eff_plan = ("one_time" if str(plan).lower()=="free" else plan)
    percent = charity_percent_for_plan(eff_plan) if donate else 0.0
    charity_cents = int(round(price * percent))
    cid = charity_id or getattr(user, "charity_id", None) or 1

    log_transaction(db, uid, service, price, charity_cents, cid, meta={"doc_id": doc_id})

    return {
        "ok": True,
        "original_filename": doc.original_filename,
        "docx_filename": os.path.basename(dst_path),
        "stored_dir": uploads_dir()
    }