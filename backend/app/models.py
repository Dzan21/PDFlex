from datetime import datetime
from sqlalchemy import JSON,Column, String, Integer, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename:  Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="uploaded", nullable=False)  # uploaded|processed|failed
    pages:  Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_excerpt: Mapped[str] = mapped_column(Text, default="")

# ---- Usage / Credits ----
from sqlalchemy import JSON, String  # ak ešte nie je importované

class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # 'upload' | 'convert' | 'protect' | 'analyze'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Charity(Base):
    __tablename__ = "charities"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    website = Column(String)
    logo_url = Column(String)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan = Column(String, nullable=False)  # 'premium' | 'pro'
    charity_id = Column(Integer, ForeignKey("charities.id"))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    renewed_at = Column(DateTime(timezone=True))
    next_renew_at = Column(DateTime(timezone=True))
    active = Column(Boolean, default=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    service = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    charity_cents = Column(Integer, nullable=False)
    charity_id = Column(Integer, ForeignKey("charities.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meta = Column(JSON)

