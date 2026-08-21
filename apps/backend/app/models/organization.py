import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class OrganizationType(enum.StrEnum):
    INTERNAL = "internal"
    LAW_FIRM = "law_firm"
    COMPANY = "company"
    INDIVIDUAL = "individual"


class OrganizationStatus(enum.StrEnum):
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
    # S2-01: persisted the first time the tenant starts a Checkout so we
    # can show "Manage subscription" without hitting Stripe on every page
    # load. Nullable for legacy tenants (free signups without Stripe).
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization")
    matters = relationship("Matter", back_populates="organization")
    clients = relationship("Client", back_populates="organization")
    precedents = relationship("Precedent", back_populates="organization")
    reviews = relationship("Review", back_populates="organization")
