import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class MatterType(enum.StrEnum):
    CONTRACT_REVIEW = "contract_review"
    LEASE = "lease"
    LABOR = "labor"
    COMPANY = "company"
    DATA_PROTECTION = "data_protection"
    CONSUMER = "consumer"
    FAMILY = "family"
    DEBT = "debt"
    OTHER = "other"


class MatterStatus(enum.StrEnum):
    NEW = "new"
    PROCESSING = "processing"
    ANALYSIS_READY = "analysis_ready"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    MISSING_INFORMATION = "missing_information"
    CONTACT_CLIENT = "contact_client"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MatterUrgency(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Matter(Base):
    """Modelo principal de un caso legal (matter) en lilIAn.

    Cada caso pertenece a una ``Organization`` (multi-tenant) y opcional-
    mente a un ``Client``. Puede tener un abogado asignado (``User``)
    distinto del creador, y pasa por un ciclo de vida definido por el
    enum ``MatterStatus`` (``NEW`` → ``PROCESSING`` →
    ``ANALYSIS_READY`` → ... → ``CLOSED``).

    Attributes:
        id: Identificador primario.
        organization_id: FK a ``organizations.id`` (multi-tenant).
        created_by_user_id: FK al usuario que creó el caso.
        assigned_lawyer_id: FK opcional al abogado responsable.
        client_id: FK opcional al cliente asociado.
        title: Título del caso (máx. 500 chars).
        matter_type: Tipo legal (``MatterType`` enum).
        description: Descripción libre del caso.
        status: Estado actual del workflow (``MatterStatus`` enum).
        urgency: Nivel de urgencia (``MatterUrgency`` enum).
        counterparty_name: Contraparte (parte opuesta).
        relevant_date: Fecha relevante del caso (audiencia, plazo).
        source_channel: Canal de origen (web, email, referido, etc.).
        created_at: Timestamp de creación (UTC).
        updated_at: Timestamp de última modificación (UTC).
        closed_at: Timestamp de cierre (nullable).

    Relationships:
        organization: ``Organization`` a la que pertenece.
        created_by: ``User`` que creó el caso.
        client: ``Client`` asociado al caso (si existe).
    """

    __tablename__ = "matters"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_lawyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)  # Cliente asociado
    title = Column(String(500), nullable=False)
    matter_type = Column(Enum(MatterType), default=MatterType.OTHER)
    description = Column(Text, nullable=True)
    status = Column(Enum(MatterStatus), default=MatterStatus.NEW)
    urgency = Column(Enum(MatterUrgency), default=MatterUrgency.MEDIUM)
    counterparty_name = Column(String(255), nullable=True)
    relevant_date = Column(DateTime, nullable=True)
    source_channel = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="matters")
    created_by = relationship("User", back_populates="matters", foreign_keys=[created_by_user_id])
    client = relationship("Client", back_populates="matters")
