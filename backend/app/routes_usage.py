from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.auth import get_current_user_id
from app import models
from app.usage import monthly_count, FREE_MONTHLY_LIMIT

router = APIRouter(prefix="/usage", tags=["usage"])

def month_bounds_utc(now: datetime):
    now = now.astimezone(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    end = datetime(now.year + (1 if now.month == 12 else 0),
                   1 if now.month == 12 else now.month + 1, 1, tzinfo=timezone.utc)
    return start, end

@router.get("/me")
def my_usage(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    uid = int(current_user_id)
    used = monthly_count(db, uid)
    limit = FREE_MONTHLY_LIMIT

    start, end = month_bounds_utc(datetime.now(timezone.utc))
    rows = (
        db.query(models.UsageEvent.action, func.count(models.UsageEvent.id))
          .filter(models.UsageEvent.user_id == uid)
          .filter(models.UsageEvent.created_at >= start)
          .filter(models.UsageEvent.created_at < end)
          .group_by(models.UsageEvent.action)
          .all()
    )
    by_action = {action: cnt for action, cnt in rows}

    return {
        "user_id": uid,
        "used_this_month": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "by_action": by_action,
        "month_start_utc": start.isoformat(),
    }
