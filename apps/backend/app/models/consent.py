"""Ley 21.719 (Chile) — privacy & data protection tables.

Models in this module implement the operator-facing record-keeping that
the Chilean data-protection reform requires from any SaaS that handles
personal data:

- ``ConsentRecord``        — verifiably-recorded user consent per scope
                             (terms, privacy, marketing, cookies). One row
                             per (user, scope, version) so we can prove
                             what text the user actually agreed to.
- ``DataProcessingActivity``— Registro de Actividades de Tratamiento
                             (ROPA) per tenant (art. 17). One row per
                             purpose; documents legal basis, retention,
                             recipients, and data categories.
- ``RightsRequest``        — ARCO + portability + blocking requests from
                             data subjects (art. 27, 30-day SLA).
- ``BreachIncident``       — security incidents, with the timestamp at
                             which we notified the Agencia and affected
                             users (art. 29).

The split between these and the ``AuditLog`` table is intentional:
``AuditLog`` records who did what for security/forensics; these tables
record what users *consented to* and what *we promised to do* with
their data — the legal compliance trail. They outlive the product
itself (we keep them ≥5 years as required by Ley 21.719)."""

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB  # noqa: F401  (JSONB intentionally kept for tooling familiarity)
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.core.database import Base


class ConsentScope(str, enum.Enum):
    """What the user is consenting to.

    Keep stable: changing the value of an existing scope is a breaking
    change for the legal trail. Add new scopes instead."""

    TERMS = "terms"
    PRIVACY = "privacy"
    MARKETING = "marketing"
    COOKIES_ANALYTICS = "cookies_analytics"
    DATA_PROCESSING_AGREEMENT = "dpa"


class RightsRequestType(str, enum.Enum):
    """Subset of rights granted by Ley 21.719 art. 12-27.

    Mapping (Ley 21.719 → our enum):
      Acceso          → ACCESS
      Rectificación   → RECTIFICATION
      Supresión       → SUPPRESSION       (the law replaces "cancelación"
                                            with "supresión")
      Oposición       → OPPOSITION
      Portabilidad    → PORTABILITY
      Bloqueo         → BLOCKING
    """

    ACCESS = "access"
    RECTIFICATION = "rectification"
    SUPPRESSION = "suppression"
    OPPOSITION = "opposition"
    PORTABILITY = "portability"
    BLOCKING = "blocking"


class RightsRequestStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BreachSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConsentRecord(Base):
    """One row per (user, scope, version) grant.

    Revocation does NOT delete the row — it stamps ``revoked_at`` so
    we can answer "did this user ever consent to version X of the
    privacy policy" years later.
    """

    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scope = Column(Enum(ConsentScope), nullable=False)
    version = Column(String(32), nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    # Free-form extra context, e.g. which form/checklist the consent came
    # from. Never store the actual legal text here — keep it under
    # docs/legal/.
    # ``JSON().with_variant(JSONB(), "postgresql")`` so tests can run on
    # SQLite (which doesn't have JSONB) without mocking the column type.
    extra = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_consent_user_scope", "user_id", "scope"),
        Index("ix_consent_user_scope_version", "user_id", "scope", "version"),
    )

    user = relationship("User")


class DataProcessingActivity(Base):
    """Registro de Actividades de Tratamiento (ROPA) per tenant.

    Each row describes ONE purpose for which the tenant processes
    personal data (e.g. "Gestión de casos legales", "Marketing
    transaccional"). The compliance checker (§C.3 in the plan) walks
    these rows to produce a 0-100 compliance score.
    """

    __tablename__ = "data_processing_activities"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=False)
    # One of: consent | contract | legal_obligation | vital_interest |
    # public_interest | legitimate_interest | judicial_claim
    legal_basis = Column(String(64), nullable=False)
    # List of data categories involved (e.g. ["identificacion",
    # "contacto", "datos_juridicos", "datos_sensibles_salud"]).
    data_categories = Column(JSON, nullable=False, default=list)
    # Categories of data subjects (e.g. ["clientes_del_bufete",
    # "contrapartes", "empleados"]).
    data_subjects = Column(JSON, nullable=False, default=list)
    # Days the data is kept after the relationship ends. None = "while
    # the matter is active + legal minimum retention applies".
    retention_days = Column(Integer, nullable=True)
    # Third parties the data is shared with (e.g. ["OpenAI", "Stripe",
    # "Supabase"]). Drives the "transferencias internacionales" field
    # in the public privacy policy.
    recipients = Column(JSON, nullable=False, default=list)
    # True if this treatment involves sensitive data (art. 11).
    involves_sensitive_data = Column(Integer, nullable=False, default=0)
    # True if any decision is automated with significant effects on
    # the data subject (art. 25 — DPIA trigger).
    involves_automated_decisions = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    extra = Column(JSON, nullable=True)

    organization = relationship("Organization")


class RightsRequest(Base):
    """ARCO + portability + blocking request.

    The 30-day clock (Ley 21.719 art. 27) starts at ``requested_at``.
    A nightly worker scans for requests nearing the deadline and
    raises alerts. When the request is fulfilled, ``completed_at``
    is stamped and the response payload (e.g. a ZIP URL for
    portability) is stored in ``response_payload_url``.
    """

    __tablename__ = "rights_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(RightsRequestType), nullable=False)
    status = Column(Enum(RightsRequestStatus), nullable=False, default=RightsRequestStatus.PENDING)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    # If the request is rejected, this holds the legal justification
    # (e.g. "el dato es necesario para el cumplimiento de una
    # obligación legal — Ley 19.628 derogada por 21.719 art. 7").
    rejection_reason = Column(Text, nullable=True)
    # For PORTABILITY / ACCESS: signed URL to the generated export ZIP
    # (24h TTL). For RECTIFICATION / SUPPRESSION: free-form notes.
    response_payload_url = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_rights_user_status", "user_id", "status"),
        Index("ix_rights_status_requested", "status", "requested_at"),
    )

    user = relationship("User")


class BreachIncident(Base):
    """Security incident record (Ley 21.719 art. 29).

    We log the moment we detected the incident, and separately when
    we notified the Agencia de Protección de Datos Personales and the
    affected users. ``affected_user_ids`` is a denormalised list — for
    very large breaches we'd swap to a join table, but the regulatory
    deadline is 72h so the trade-off favours speed of capture.
    """

    __tablename__ = "breach_incidents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    severity = Column(Enum(BreachSeverity), nullable=False, default=BreachSeverity.MEDIUM)
    description = Column(Text, nullable=False)
    mitigation = Column(Text, nullable=True)
    affected_user_ids = Column(JSON, nullable=False, default=list)
    reported_to_agency_at = Column(DateTime, nullable=True)
    reported_to_users_at = Column(DateTime, nullable=True)
    # If we ever integrate with the Agencia's reporting API, the
    # submitted payload + agency reference go here.
    agency_reference = Column(String(255), nullable=True)
    extra = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_breach_org_discovered", "organization_id", "discovered_at"),
    )

    organization = relationship("Organization")
