from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr
from app.db import get_db
from app import models
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user = models.User(
        email=user.email,
        password_hash=hash_password(user.password),
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        return {"id": new_user.id, "email": new_user.email}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    # nájdeme usera podľa emailu
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # overíme heslo
    if not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # vytvoríme JWT token
    token = create_access_token(subject=str(db_user.id))
    return {"access_token": token, "token_type": "bearer"}
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user_id
from app.db import get_db
from app import models

@router.get("/me", operation_id="get_current_user_profile")
def me(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == int(current_user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "email": user.email, "plan": user.plan, "created_at": user.created_at}

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user_id
from app.db import get_db
from app import models

@router.get("/me")
def me(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == int(current_user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "created_at": user.created_at
    }


from app.usage import monthly_count, FREE_MONTHLY_LIMIT

@router.get("/usage")
def usage(current_user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    used = monthly_count(db, int(current_user_id))
    return {
        "used": used,
        "limit": FREE_MONTHLY_LIMIT,
        "remaining": max(FREE_MONTHLY_LIMIT - used, 0)
    }
