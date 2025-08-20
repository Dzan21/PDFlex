from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from app.pricing import PRICES_CENTS_ONE_TIME, CHARITY_PERCENT_BY_PLAN

from app.db import get_db

# Cenník v centoch
SERVICE_PRICES = {
    'convert_docx': 100,
    'protect': 50,
    'text_counter': 20,
    'ocr_text': 50,
}

def price_for_service(name: str) -> int:
    if name not in SERVICE_PRICES:
        raise ValueError(f'Unknown service: {name}')
    return SERVICE_PRICES[name]

from app.auth import get_current_user_id
from app import models
from app.pricing import PRICES_CENTS_ONE_TIME, charity_percent_for_plan

router = APIRouter(prefix="/billing", tags=["billing"])

# ------------ Schemy ------------
class CharityOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None

class SelectCharityIn(BaseModel):
    charity_id: int

class MockPurchaseIn(BaseModel):
    service: str   # 'convert_docx' | 'ocr_text' | 'protect' | 'tables_xlsx' | 'redact'

class CreditsOut(BaseModel):
    subscription_plan: str
    charity_id: Optional[int] = None
    charity_percent: float
    total_charity_eur: float

# ------------ Helpers ------------
def _get_user(db: Session, uid: int) -> models.User:
    user = db.query(models.User).filter(models.User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def log_transaction(db: Session, user_id: int, service: str, amount_cents: int, charity_cents: int, charity_id: Optional[int], meta: Optional[dict]=None):
    tx = models.Transaction(
        user_id=user_id,
        service=service,
        amount_cents=amount_cents,
        charity_cents=charity_cents,
        charity_id=charity_id,
        meta=meta or {}
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx

# ------------ Endpoints ------------
def price_for(service: str) -> int:
    """Vráti cenu služby v centoch podľa PRICES_CENTS_ONE_TIME."""
    return int(PRICES_CENTS_ONE_TIME.get(service, 0))

def charity_percent_for_plan(plan: str) -> int:
    """Percento venované na charitu podľa plánu."""
    plan = (plan or "free").lower()
    return int(CHARITY_PERCENT_BY_PLAN.get(plan, CHARITY_PERCENT_BY_PLAN.get("free", 0)))


@router.get("/charities", response_model=List[CharityOut])
def list_charities(db: Session = Depends(get_db)):
    chars = db.query(models.Charity).order_by(models.Charity.id.asc()).all()
    return [
        CharityOut(id=c.id, name=c.name, description=c.description, website=c.website, logo_url=c.logo_url)
        for c in chars
    ]

@router.post("/select-charity")
def select_charity(body: SelectCharityIn, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    # overme, že charity existuje
    ch = db.query(models.Charity).filter(models.Charity.id == body.charity_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Charity not found")

    user = _get_user(db, int(current_user_id))
    user.charity_id =  ch.id
    db.add(user)
    db.commit()
    return {"ok": True, "charity_id": ch.id, "charity_name": ch.name}

@router.get("/me", response_model=CreditsOut)
def billing_me(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = _get_user(db, int(current_user_id))
    plan = getattr(user, 'subscription_plan', None) or getattr(user, 'plan', 'free')
    raw_percent = charity_percent_for_plan(plan)
    percent = int(round(raw_percent * 100))
    total_cents = db.query(func.coalesce(func.sum(models.Transaction.charity_cents), 0))                    .filter(models.Transaction.user_id == user.id)                    .scalar() or 0
    total_eur = float(total_cents) / 100.0
    return CreditsOut(
        subscription_plan=plan,
        charity_id=getattr(user, 'charity_id', None) or 1,
        charity_percent=percent,
        total_charity_eur=total_eur,
    )

@router.post("/mock/purchase")
def mock_purchase(body: MockPurchaseIn, current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Simulácia platby bez brány:
      - nájde cenu služby
      - vypočíta charity % podľa plánu
      - zapíše transakciu
    POZOR: nič nesťahuje z karty – len loguje transakciu.
    """
    user = _get_user(db, int(current_user_id))
    price = PRICES_CENTS_ONE_TIME.get(body.service)
    if price is None:
        raise HTTPException(status_code=400, detail="Unknown service")

    percent = charity_percent_for_plan(getattr(user, "subscription_plan", None) or getattr(user, "plan", "free"))
    charity_cents = int(round(price * percent))
    tx = log_transaction(db, user.id, body.service, price, charity_cents, getattr(user, 'charity_id', None) or 1)
    return {
        "ok": True,
        "transaction_id": tx.id,
        "service": body.service,
        "amount_eur": round(price/100.0,2),
        "charity_eur": round(charity_cents/100.0,2),
        "charity_id": getattr(user, 'charity_id', None) or 1
    }

@router.get("/stats/charity")
def charity_stats(db: Session = Depends(get_db)):
    total = db.query(func.coalesce(func.sum(models.Transaction.charity_cents), 0)).scalar() or 0
    return {"total_charity_eur": round(total/100.0, 2)}


@router.get("/me")
def billing_me(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Vráti transakcie prihláseného usera + sumár.
    Robustné voči None, používa COALESCE.
    """
    uid = int(current_user_id)

    # načítaj transakcie (posledné najprv)
    txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == uid)
        .order_by(models.Transaction.id.desc())
        .all()
    )

    # bezpečné mapovanie -> JSON serializovateľné typy
    items = []
    for t in txs:
        items.append({
            "id": t.id,
            "service": t.service,
            "amount_cents": int(t.amount_cents or 0),
            "charity_cents": int(t.charity_cents or 0),
            "charity_id": int(t.charity_id or 0),
            "created_at": t.created_at.isoformat() if getattr(t, "created_at", None) else None,
            "meta": (t.meta if isinstance(t.meta, dict) else {}),
        })

    # sumáre s COALESCE
    from sqlalchemy import func
    total_amount = db.query(func.coalesce(func.sum(models.Transaction.amount_cents), 0))\
        .filter(models.Transaction.user_id == uid).scalar()
    total_charity = db.query(func.coalesce(func.sum(models.Transaction.charity_cents), 0))\
        .filter(models.Transaction.user_id == uid).scalar()

    return {
        "user_id": uid,
        "total_amount_cents": int(total_amount or 0),
        "total_charity_cents": int(total_charity or 0),
        "transactions": items,
    }

