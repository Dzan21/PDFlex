import os, uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.auth import get_current_user_id
from app.db import get_db
from app import models
import pdfplumber

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # len PDF
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF is allowed")

    # názov súboru: <userId>_<uuid>.pdf
    safe_name = f"{int(current_user_id)}_{uuid.uuid4().hex}.pdf"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)

    # uloženie streamu na disk
    with open(dest_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    # pokus o základné spracovanie: počet strán + krátky výťah textu
    pages_count = 0
    text_excerpt = ""
    status = "uploaded"
    try:
        with pdfplumber.open(dest_path) as pdf:
            pages_count = len(pdf.pages)
            collected = []
            for p in pdf.pages[:3]:  # prvé 3 strany pre krátky výťah
                collected.append(p.extract_text() or "")
            text_excerpt = ("\n".join(collected)).strip()[:500]
            status = "processed"
    except Exception:
        # keď PDF nevieme prečítať, záznam uložíme aj tak
        status = "uploaded"

    # zápis do DB
    doc = models.Document(
        user_id=int(current_user_id),
        original_filename=file.filename or safe_name,
        stored_filename=safe_name,
        status=status,
        pages=pages_count,
        text_excerpt=text_excerpt,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "id": doc.id,
        "original_filename": doc.original_filename,
        "stored_filename": doc.stored_filename,
        "status": doc.status,
        "pages": doc.pages,
        "path": dest_path,
    }
