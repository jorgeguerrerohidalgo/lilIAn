from sqlalchemy import Column, String, Integer, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class OrganizationType(str, enum.Enum):
    INTERNAL = "internal"
    LAW_FIRM = "law_firm"
    COMPANY = "company"
    INDIVIDUAL = "individual"


class OrganizationStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(Enum(OrganizationType), default=OrganizationType.INDIVIDUAL)
    rut = Column(String(50), nullable=True)
    billing_email = Column(String(255), nullable=True)
    plan_id = Column(String(100), nullable=True)
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization")
    matters = relationship("Matter", back_populates="organization")
