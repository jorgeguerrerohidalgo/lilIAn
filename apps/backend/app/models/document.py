from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(500), nullable=False)
    storage_path = Column(String(1000))
    mime_type = Column(String(100))
    file_size = Column(Integer)
    file_hash = Column(String(255))
    status = Column(String(50), default="uploaded")
    extracted_text = Column(Text)
    page_count = Column(Integer)
    detected_document_type = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

    # Relación con análisis estructurado
    analysis = relationship(
        "DocumentAnalysis",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    # Relación con chunks
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
