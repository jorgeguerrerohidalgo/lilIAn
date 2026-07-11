from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class MatterType(str, enum.Enum):
    CONTRACT_REVIEW = "contract_review"
    LEASE = "lease"
    LABOR = "labor"
    COMPANY = "company"
    DATA_PROTECTION = "data_protection"
    CONSUMER = "consumer"
    FAMILY = "family"
    DEBT = "debt"
    OTHER = "other"


class MatterStatus(str, enum.Enum):
    NEW = "new"
    PROCESSING = "processing"
    ANALYSIS_READY = "analysis_ready"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    MISSING_INFORMATION = "missing_information"
    CONTACT_CLIENT = "contact_client"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MatterUrgency(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Matter(Base):
    __tablename__ = "matters"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_lawyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(500), nullable=False)
    matter_type = Column(Enum(MatterType), default=MatterType.OTHER)
    description = Column(Text, nullable=True)
    status = Column(Enum(MatterStatus), default=MatterStatus.NEW)
    urgency = Column(Enum(MatterUrgency), default=MatterUrgency.MEDIUM)
    counterparty_name = Column(String(255), nullable=True)
    relevant_date = Column(DateTime, nullable=True)
    source_channel = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="matters")
    created_by = relationship("User", back_populates="matters", foreign_keys=[created_by_user_id])
