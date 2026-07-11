from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON
from datetime import datetime
from app.core.database import Base


class LegalSource(Base):
    __tablename__ = "legal_sources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    source_type = Column(String(100), nullable=False)
    origin = Column(String(255))
    url = Column(String(1000))
    jurisdiction = Column(String(100), default="Chile")
    matter_area = Column(String(100))
    license_info = Column(Text)
    reliability_level = Column(String(50), default="medium")
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LegalSourceVersion(Base):
    __tablename__ = "legal_source_versions"

    id = Column(Integer, primary_key=True, index=True)
    legal_source_id = Column(Integer, nullable=False)
    version_label = Column(String(100))
    content = Column(Text, nullable=False)
    content_hash = Column(String(255))
    published_at = Column(DateTime)
    consulted_at = Column(DateTime)
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)
    is_current = Column(Boolean, default=False)
    version_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
