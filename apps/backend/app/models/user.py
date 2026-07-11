from sqlalchemy import Column, String, Integer, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class UserStatus(str, enum.Enum):
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

    memberships = relationship("OrganizationMember", back_populates="user")
    matters = relationship("Matter", back_populates="created_by")
