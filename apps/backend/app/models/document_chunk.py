from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer)
    section_title = Column(String(500))
    embedding = Column(Text)
    legal_area = Column(String(50), nullable=True, index=True)
    chunk_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relación con documento
    document = relationship("Document", back_populates="chunks")
