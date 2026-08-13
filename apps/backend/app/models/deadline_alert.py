from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DeadlineAlert(Base):
    __tablename__ = "deadline_alerts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Alert identification
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=False)

    # Dates
    due_date = Column(Date, nullable=False, index=True)
    days_remaining = Column(Integer, nullable=True)
    is_overdue = Column(Boolean, default=False)

    # Urgency
    urgency = Column(String(20), nullable=False, index=True)
    importance_score = Column(Integer, default=50)

    # Status
    status = Column(String(20), default="pending", index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Source from contract_timeline
    source_event = Column(String(255), nullable=True)
    legal_reference = Column(String(500), nullable=True)
    consequence = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization")
    matter = relationship("Matter")
    document = relationship("Document")
    user = relationship("User", foreign_keys=[user_id])
