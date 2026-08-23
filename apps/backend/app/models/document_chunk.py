from datetime import datetime

from pgvector.sqlalchemy import Vector
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
    # pgvector column — ANN-searchable via <=> with the HNSW index
    # ix_document_chunks_embedding_vec_hnsw. Replaces the legacy
    # JSON-as-text ``embedding`` column (see migration 034).
    embedding_vec = Column(Vector(1536), nullable=True)
    legal_area = Column(String(50), nullable=True, index=True)
    chunk_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relación con documento
    document = relationship("Document", back_populates="chunks")
