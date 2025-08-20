from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app import models


def log_transaction(
    db: Session,
    user_id: int,
    service: str,
    amount_cents: int,
    charity_cents: int,
    charity_id: Optional[int],
    meta: Optional[Dict[str, Any]] = None,
):
    """Zapíše transakciu a vráti ju."""
    tx = models.Transaction(
        user_id=user_id,
        service=service,
        amount_cents=amount_cents,
        charity_cents=charity_cents,
        charity_id=charity_id,
        meta=meta or {},
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
