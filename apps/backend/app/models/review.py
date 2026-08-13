"""
Review Model - Workflow de revisión de análisis.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class ReviewStatus:
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    analysis_report_id = Column(Integer, ForeignKey("analysis_reports.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # Creador del review
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Reviewer que aprobó/rechazó
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Estado del workflow
    status = Column(String(20), default=ReviewStatus.DRAFT, nullable=False)

    # Comentarios generales
    comments = Column(Text, nullable=True)

    # Razón de rechazo (requerida si status = rejected)
    rejection_reason = Column(Text, nullable=True)

    # Cambios sugeridos (si fue rechazado)
    suggested_changes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    # Relaciones
    analysis_report = relationship("AnalysisReport", back_populates="reviews")
    organization = relationship("Organization", back_populates="reviews")
    creator = relationship("User", foreign_keys=[created_by_user_id], back_populates="reviews_created")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id], back_populates="reviews_done")
