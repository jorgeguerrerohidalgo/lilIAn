from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

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
    """Mensaje individual dentro de una ``ChatSession``.

    Representa un turno de la conversación (usuario o asistente). Los
    mensajes del asistente (``role="assistant"``) registran el
    ``model_provider`` y ``model_name`` usados para auditoría. El
    ``message_metadata`` (JSON libre) guarda información adicional
    como fuentes citadas, tokens consumidos, etc.

    Attributes:
        id: Identificador primario.
        chat_session_id: FK a ``chat_sessions.id``.
        role: ``"user"`` o ``"assistant"`` (típico de OpenAI Chat API).
        content: Contenido textual del mensaje.
        model_provider: Proveedor del modelo (``"openai"``, ``"anthropic"``).
        model_name: Modelo concreto (``"gpt-4o-mini"``, ``"claude-..."``).
        message_metadata: JSON libre con metadatos adicionales.
        created_at: Timestamp de creación (UTC).
    """

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    model_provider = Column(String(100))
    model_name = Column(String(100))
    message_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
