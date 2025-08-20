from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models

Action = Literal["upload", "convert", "protect", "analyze", "ocr_text"]

FREE_MONTHLY_LIMIT = 20  # môžeš neskôr prehodiť pod užívateľa/plan

def _month_bounds_utc(dt: datetime):
    dt = dt.astimezone(timezone.utc)
    start = datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)
    # ďalší mesiac:
    if dt.month == 12:
        end = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
    return start, end

def monthly_count(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    start, end = _month_bounds_utc(now)
    return db.query(func.count(models.UsageEvent.id))\
             .filter(models.UsageEvent.user_id == user_id)\
             .filter(models.UsageEvent.created_at >= start)\
             .filter(models.UsageEvent.created_at < end)\
             .scalar() or 0

def require_quota(db: Session, user_id: int, limit: int = FREE_MONTHLY_LIMIT):
    used = monthly_count(db, user_id)
    if used >= limit:
        # 402 Payment Required je presne na tento účel
        raise HTTPException(
            status_code=402,
            detail={"error": "limit_exceeded", "used": used, "limit": limit,
                    "message": "Mesačný limit bezplatného plánu bol vyčerpaný."}
        )

def record_event(db: Session, user_id: int, action: Action):
    evt = models.UsageEvent(user_id=user_id, action=action)
    db.add(evt)
    db.commit()

def remaining_quota(db: Session, user_id: int, limit: int = FREE_MONTHLY_LIMIT) -> int:
    """Vráti počet zostávajúcich akcií pre aktuálny mesiac."""
    used = monthly_count(db, user_id)
    return max(0, limit - used)
