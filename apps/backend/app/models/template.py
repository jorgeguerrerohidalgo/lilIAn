from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean
from datetime import datetime
from app.core.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    template_type = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    content = Column(Text, nullable=False)
    is_global = Column(Boolean, default=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MatterNote(Base):
    __tablename__ = "matter_notes"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MatterStatusHistory(Base):
    __tablename__ = "matter_status_history"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    old_status = Column(String(50))
    new_status = Column(String(50), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
