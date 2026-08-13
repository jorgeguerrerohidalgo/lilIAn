from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from app.core.database import Base


class LawChunk(Base):
    __tablename__ = "law_chunks"

    id = Column(Integer, primary_key=True, index=True)
    law_code = Column(String(100), nullable=False, index=True)
    law_name = Column(String(500), nullable=False)
    article_number = Column(String(50))
    chapter_title = Column(String(500))
    section_title = Column(String(500))
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text)
    legal_area = Column(String(50), nullable=False, index=True)
    chunk_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
