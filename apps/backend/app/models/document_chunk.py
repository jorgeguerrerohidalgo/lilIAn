from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
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
    chunk_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
