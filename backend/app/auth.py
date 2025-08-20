import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import jwt

# Heslá (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    # 1) pokus o bcrypt
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        # 2) fallback na starý SHA-256 formát (ktorý sme použili pri prvých registráciách)
        import hashlib
        return hashlib.sha256(plain.encode("utf-8")).hexdigest() == hashed

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_env")
JWT_ALGO = "HS256"
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "60"))

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=JWT_EXPIRE_MIN)
    to_encode = {
        "sub": subject,
        "exp": datetime.now(tz=timezone.utc) + expires_delta,
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGO)

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

security = HTTPBearer()

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(security)) -> str:
    payload = decode_token(creds.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return sub
