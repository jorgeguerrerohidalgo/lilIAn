import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    # S1.1: self-service signup requires email verification before login.
    # `verification_token` is opaque, cleared on success — see auth.py.
    email_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String(128), nullable=True, index=True)
    verification_sent_at = Column(DateTime, nullable=True)
    # Phase 1b: self-service password recovery.
    # ``password_reset_token`` is opaque (token_urlsafe(32)), one-shot,
    # and cleared on use. ``password_reset_expires_at`` is the hard TTL
    # (1h). See auth.forgot_password / auth.reset_password.
    password_reset_token = Column(String(128), nullable=True, index=True)
    password_reset_expires_at = Column(DateTime, nullable=True)

    memberships = relationship("OrganizationMember", back_populates="user")
    matters = relationship("Matter", back_populates="created_by", foreign_keys="Matter.created_by_user_id")
    clients = relationship("Client", back_populates="created_by")
    reviews_created = relationship("Review", foreign_keys="Review.created_by_user_id", back_populates="creator")
    reviews_done = relationship("Review", foreign_keys="Review.reviewed_by_user_id", back_populates="reviewer")
