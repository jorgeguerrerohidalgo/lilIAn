from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(Integer)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    # `metadata` is reserved by SQLAlchemy's Declarative API. Map the
    # Python attribute `extra` to the DB column `metadata` (JSONB).
    extra = Column("metadata", JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
