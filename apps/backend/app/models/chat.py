from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from datetime import datetime
from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    model_provider = Column(String(100))
    model_name = Column(String(100))
    message_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
