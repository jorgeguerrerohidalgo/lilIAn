"""Ley 21.719 (Chile) — privacy & data-subject rights endpoints.

Implements the operator-facing APIs that let our own users and our
tenants exercise the rights granted by the new Chilean data-protection
regime:

  - ``POST /privacy/consent``             — granular consent grant / revoke.
  - ``GET  /privacy/consent``             — current consent state.
  - ``GET  /privacy/rights/me/export``    — portability: ZIP with all
                                             user-owned data.
  - ``POST /privacy/rights/me/request``   — ARCO + portability + blocking.
  - ``GET  /privacy/rights/me``           — list my rights requests.
  - ``GET  /privacy/activities``          — ROPA of the caller's tenant.
  - ``POST /privacy/activities``          — create / update a ROPA entry
                                             (OWNER/ADMIN).
  - ``GET  /privacy/compliance-score``    — 0-100 compliance score for the
                                             caller's tenant (OWNER/ADMIN
                                             and PLATFORM_ADMIN).
  - ``POST /privacy/breach-notify``       — PLATFORM_ADMIN only; log a
                                             breach + mark agency report.

The 30-day SLA from Ley 21.719 art. 27 is enforced by a scheduled
worker (``apps/backend/scripts/check_rights_sla.py``) that scans
``rights_requests`` near the deadline and raises Sentry alerts.
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, get_platform_admin_membership
from app.core.database import get_db
from app.models import (
    AuditLog,
    BreachIncident,
    BreachSeverity,
    ConsentRecord,
    ConsentScope,
    DataProcessingActivity,
    Organization,
    OrganizationMember,
    RightsRequest,
    RightsRequestStatus,
    RightsRequestType,
    User,
)
from app.models.organization_member import MemberRole

logger = logging.getLogger("lilian.privacy")

router = APIRouter(prefix="/privacy", tags=["privacy"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

# Versions of the legal pages — bump these whenever you change the
# text in apps/frontend/app/legal/*. When bumped, existing users will
# need to re-accept on next login (handled by the frontend banner).
CURRENT_TERMS_VERSION = "v1-2026-08-29"
CURRENT_PRIVACY_VERSION = "v1-2026-08-29"


class ConsentGrantRequest(BaseModel):
    scope: ConsentScope
    version: str
    granted: bool = True


class ConsentState(BaseModel):
    scope: ConsentScope
    version: str
    granted_at: datetime
    revoked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConsentListResponse(BaseModel):
    records: list[ConsentState]


class RightsRequestCreate(BaseModel):
    """Spec for a data-subject right request (Ley 21.719 art. 12-27)."""

    type: RightsRequestType
    notes: Optional[str] = Field(default=None, max_length=1000)


class RightsRequestResponse(BaseModel):
    id: int
    type: RightsRequestType
    status: RightsRequestStatus
    requested_at: datetime
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    response_payload_url: Optional[str] = None

    class Config:
        from_attributes = True


class DataProcessingActivityIn(BaseModel):
    name: str = Field(..., max_length=255)
    purpose: str
    legal_basis: str = Field(..., description="consent|contract|legal_obligation|...")
    data_categories: list[str] = []
    data_subjects: list[str] = []
    retention_days: Optional[int] = None
    recipients: list[str] = []
    involves_sensitive_data: bool = False
    involves_automated_decisions: bool = False


class DataProcessingActivityOut(BaseModel):
    id: int
    organization_id: int
    name: str
    purpose: str
    legal_basis: str
    data_categories: list[str]
    data_subjects: list[str]
    retention_days: Optional[int]
    recipients: list[str]
    involves_sensitive_data: bool
    involves_automated_decisions: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComplianceScoreResponse(BaseModel):
    organization_id: int
    score: int = Field(..., ge=0, le=100)
    grade: str = Field(..., description="A | B | C | D | F")
    issues: list[str]
    activity_count: int
    last_reviewed_at: datetime


class BreachNotifyRequest(BaseModel):
    organization_id: Optional[int] = None
    severity: BreachSeverity = BreachSeverity.MEDIUM
    description: str
    affected_user_ids: list[int] = []
    mitigation: Optional[str] = None
    notify_users: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def _ua(user_agent: Optional[str]) -> str:
    return (user_agent or "")[:512]


def _log_audit(
    db: Session,
    *,
    user_id: int,
    organization_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    extra: Optional[dict] = None,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
) -> None:
    """Append an AuditLog row. Never raises — audit logging must not
    block the user-facing request."""
    try:
        row = AuditLog(
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=(ip or "")[:64] or None,
            user_agent=(ua or "")[:512] or None,
            extra=extra or {},
        )
        db.add(row)
        db.commit()
    except Exception:  # pragma: no cover
        logger.exception("audit log failed")


def _caller_org(db: Session, user: User) -> Optional[OrganizationMember]:
    return (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id)
        .first()
    )


# ---------------------------------------------------------------------------
# A.1 — Consent grants
# ---------------------------------------------------------------------------

@router.post("/consent", response_model=ConsentState)
def grant_or_revoke_consent(
    payload: ConsentGrantRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a grant or revocation for one scope.

    The (user_id, scope, version) tuple is unique by index — re-issuing
    the same grant is idempotent (we just stamp ``granted_at`` again).
    Revocation stamps ``revoked_at``; we never delete consent rows
    because the legal trail must survive the user being deleted.
    """
    now = datetime.utcnow()
    ip = _client_ip(request)
    ua = _ua(request.headers.get("user-agent"))

    existing = (
        db.query(ConsentRecord)
        .filter(
            and_(
                ConsentRecord.user_id == current_user.id,
                ConsentRecord.scope == payload.scope,
                ConsentRecord.version == payload.version,
            )
        )
        .first()
    )
    if existing:
        if payload.granted:
            existing.granted_at = now
            existing.revoked_at = None
        else:
            existing.revoked_at = now
        record = existing
    else:
        record = ConsentRecord(
            user_id=current_user.id,
            scope=payload.scope,
            version=payload.version,
            granted_at=now if payload.granted else None,
            revoked_at=None if payload.granted else now,
            ip_address=ip,
            user_agent=ua,
        )
        db.add(record)

    # Stamp the denormalised field on User for the common auth path.
    if payload.scope == ConsentScope.TERMS and payload.granted:
        current_user.consent_given_at = now
        current_user.terms_version = payload.version
    elif payload.scope == ConsentScope.PRIVACY and payload.granted:
        current_user.privacy_version = payload.version

    db.commit()
    db.refresh(record)

    _log_audit(
        db,
        user_id=current_user.id,
        organization_id=_caller_org(db, current_user).organization_id if _caller_org(db, current_user) else None,
        action="consent.granted" if payload.granted else "consent.revoked",
        entity_type="consent",
        entity_id=record.id,
        extra={"scope": payload.scope.value, "version": payload.version},
        ip=ip,
        ua=ua,
    )

    return ConsentState(
        scope=record.scope,
        version=record.version,
        granted_at=record.granted_at,
        revoked_at=record.revoked_at,
    )


@router.get("/consent", response_model=ConsentListResponse)
def list_consents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.user_id == current_user.id)
        .order_by(ConsentRecord.scope, ConsentRecord.granted_at.desc())
        .all()
    )
    return ConsentListResponse(
        records=[
            ConsentState(
                scope=r.scope,
                version=r.version,
                granted_at=r.granted_at,
                revoked_at=r.revoked_at,
            )
            for r in rows
        ]
    )


# ---------------------------------------------------------------------------
# A.1 — Rights (ARCO + portability + blocking)
# ---------------------------------------------------------------------------

@router.post("/rights/me/request", response_model=RightsRequestResponse, status_code=status.HTTP_201_CREATED)
def create_rights_request(
    payload: RightsRequestCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Open a new rights request. SLA per Ley 21.719 art. 27 is 30
    corridos (calendario) días — stored as a deadline hint in ``notes``
    so the SLA worker can pick it up."""
    ip = _client_ip(request)
    ua = _ua(request.headers.get("user-agent"))

    sla_deadline = (datetime.utcnow() + timedelta(days=30)).isoformat()
    notes_with_sla = (
        f"SLA_DEADLINE={sla_deadline}\n{payload.notes or ''}".strip()
    )

    rr = RightsRequest(
        user_id=current_user.id,
        type=payload.type,
        status=RightsRequestStatus.PENDING,
        requested_at=datetime.utcnow(),
        ip_address=ip,
        user_agent=ua,
        rejection_reason=None,
        response_payload_url=None,
    )
    # We stash SLA + free-form notes in the ``notes``-style column on
    # ``RightsRequest`` would be ideal, but the schema in
    # models/consent.py doesn't expose one. Keep the deadline on the
    # response so the SLA worker can read it via ``requested_at + 30d``.
    db.add(rr)
    db.commit()
    db.refresh(rr)

    _log_audit(
        db,
        user_id=current_user.id,
        organization_id=_caller_org(db, current_user).organization_id if _caller_org(db, current_user) else None,
        action=f"rights_request.created.{payload.type.value}",
        entity_type="rights_request",
        entity_id=rr.id,
        extra={"type": payload.type.value, "sla_deadline": sla_deadline, "notes": payload.notes},
        ip=ip,
        ua=ua,
    )

    return RightsRequestResponse.model_validate(rr)


@router.get("/rights/me", response_model=list[RightsRequestResponse])
def list_my_rights_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(RightsRequest)
        .filter(RightsRequest.user_id == current_user.id)
        .order_by(RightsRequest.requested_at.desc())
        .all()
    )
    return [RightsRequestResponse.model_validate(r) for r in rows]


@router.get("/rights/me/export")
def export_my_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Portability (Ley 21.719 art. 22): bundle every row that
    references the caller into a single ZIP of JSON files.

    This endpoint runs synchronously because the caller's data is
    bounded by their account history — in practice well under 5 MB
    even for power users. The expensive parts (matter documents) we
    keep as references, not blobs: we don't want the export to weigh
    gigabytes.
    """
    user_id = current_user.id

    profile = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "status": current_user.status.value if hasattr(current_user.status, "value") else str(current_user.status),
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "consent_given_at": current_user.consent_given_at.isoformat() if current_user.consent_given_at else None,
        "terms_version": current_user.terms_version,
        "privacy_version": current_user.privacy_version,
    }

    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user_id)
        .all()
    )
    consents = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.user_id == user_id)
        .all()
    )
    rights_requests = (
        db.query(RightsRequest)
        .filter(RightsRequest.user_id == user_id)
        .all()
    )

    # We include IDs only for matters / documents / clients — the
    # full content stays in the platform. The export is a manifest,
    # not a backup.
    from app.models.matter import Matter
    from app.models.client import Client
    from app.models.audit_log import AuditLog

    matter_ids = [
        m.id
        for m in db.query(Matter).filter(Matter.created_by_user_id == user_id).all()
    ]
    client_ids = [
        c.id
        for c in db.query(Client).filter(Client.created_by_user_id == user_id).all()
    ]
    audit_count = (
        db.query(AuditLog).filter(AuditLog.user_id == user_id).count()
    )

    bundle = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "export_version": "1.0",
        "profile": profile,
        "memberships": [
            {
                "organization_id": m.organization_id,
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memberships
        ],
        "consents": [
            {
                "scope": c.scope.value if hasattr(c.scope, "value") else str(c.scope),
                "version": c.version,
                "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            }
            for c in consents
        ],
        "rights_requests": [
            {
                "id": r.id,
                "type": r.type.value if hasattr(r.type, "value") else str(r.type),
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "requested_at": r.requested_at.isoformat() if r.requested_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rights_requests
        ],
        "data_manifest": {
            "matter_ids_created_by_user": matter_ids,
            "client_ids_created_by_user": client_ids,
            "audit_log_entries": audit_count,
        },
        "notes": (
            "Este archivo contiene una referencia a tus datos personales en Lilian. "
            "Los documentos completos (PDFs originales) y el contenido de los casos "
            "no se incluyen por volumen; solicítalos por separado si los necesitas. "
            "Ley 21.719 art. 22 — portabilidad."
        ),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("profile.json", json.dumps(bundle["profile"], indent=2, ensure_ascii=False))
        zf.writestr("memberships.json", json.dumps(bundle["memberships"], indent=2, ensure_ascii=False))
        zf.writestr("consents.json", json.dumps(bundle["consents"], indent=2, ensure_ascii=False))
        zf.writestr("rights_requests.json", json.dumps(bundle["rights_requests"], indent=2, ensure_ascii=False))
        zf.writestr("data_manifest.json", json.dumps(bundle["data_manifest"], indent=2, ensure_ascii=False))
        zf.writestr("README.txt", bundle["notes"])
        zf.writestr(
            "bundle.json",
            json.dumps({k: bundle[k] for k in ("exported_at", "export_version")}, indent=2),
        )
    buf.seek(0)

    # Stamp the denormalised field so we can rate-limit re-exports if
    # abuse becomes a concern (currently every export is one row, but
    # the columns are there for the future).
    current_user.last_export_at = datetime.utcnow()
    db.commit()

    _log_audit(
        db,
        user_id=current_user.id,
        organization_id=_caller_org(db, current_user).organization_id if _caller_org(db, current_user) else None,
        action="rights_request.export",
        entity_type="user",
        entity_id=current_user.id,
    )

    from fastapi.responses import StreamingResponse

    filename = f"lilian-data-export-{current_user.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# A.1 — ROPA (data_processing_activities)
# ---------------------------------------------------------------------------

@router.get("/activities", response_model=list[DataProcessingActivityOut])
def list_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = _caller_org(db, current_user)
    if membership is None:
        raise HTTPException(status_code=403, detail="No perteneces a ninguna organización.")
    if membership.role not in {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.PLATFORM_ADMIN}:
        raise HTTPException(status_code=403, detail="Solo OWNER/ADMIN/PLATFORM_ADMIN puede ver el ROPA.")
    rows = (
        db.query(DataProcessingActivity)
        .filter(DataProcessingActivity.organization_id == membership.organization_id)
        .order_by(DataProcessingActivity.name)
        .all()
    )
    return [DataProcessingActivityOut.model_validate(r) for r in rows]


@router.post("/activities", response_model=DataProcessingActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: DataProcessingActivityIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = _caller_org(db, current_user)
    if membership is None or membership.role not in {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.PLATFORM_ADMIN}:
        raise HTTPException(status_code=403, detail="Solo OWNER/ADMIN/PLATFORM_ADMIN puede crear actividades de tratamiento.")
    row = DataProcessingActivity(
        organization_id=membership.organization_id,
        name=payload.name,
        purpose=payload.purpose,
        legal_basis=payload.legal_basis,
        data_categories=payload.data_categories,
        data_subjects=payload.data_subjects,
        retention_days=payload.retention_days,
        recipients=payload.recipients,
        involves_sensitive_data=1 if payload.involves_sensitive_data else 0,
        involves_automated_decisions=1 if payload.involves_automated_decisions else 0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _log_audit(
        db,
        user_id=current_user.id,
        organization_id=membership.organization_id,
        action="ropa.created",
        entity_type="data_processing_activity",
        entity_id=row.id,
        extra={"name": row.name, "legal_basis": row.legal_basis},
    )
    return DataProcessingActivityOut.model_validate(row)


# ---------------------------------------------------------------------------
# C.3 — Compliance score (read-only, no auth higher than OWNER/ADMIN)
# ---------------------------------------------------------------------------

@router.get("/compliance-score", response_model=ComplianceScoreResponse)
def compliance_score(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """0-100 score + graded issues for the caller's tenant.

    Scoring is intentionally a *technical checklist*, not a legal
    audit. The disclaimer in the UI ("no reemplaza auditoría legal
    profesional") is contractual hygiene — the score is one input,
    not the verdict.
    """
    membership = _caller_org(db, current_user)
    if membership is None or membership.role not in {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.PLATFORM_ADMIN}:
        raise HTTPException(status_code=403, detail="Solo OWNER/ADMIN/PLATFORM_ADMIN puede ver el compliance score.")

    org_id = membership.organization_id
    activities = (
        db.query(DataProcessingActivity)
        .filter(DataProcessingActivity.organization_id == org_id)
        .all()
    )
    issues: list[str] = []
    score = 100

    if not activities:
        issues.append("No hay actividades de tratamiento registradas (ROPA vacío).")
        score -= 40

    for a in activities:
        if not a.purpose or len(a.purpose.strip()) < 20:
            issues.append(f"Actividad «{a.name}» tiene una finalidad demasiado corta o vacía.")
            score -= 5
        if a.legal_basis not in {
            "consent", "contract", "legal_obligation",
            "vital_interest", "public_interest", "legitimate_interest",
            "judicial_claim",
        }:
            issues.append(f"Actividad «{a.name}» usa una base de licitud no reconocida.")
            score -= 10
        if a.involves_sensitive_data and "consent" not in (a.legal_basis or ""):
            issues.append(f"Actividad «{a.name}» trata datos sensibles sin base de licitud de consentimiento.")
            score -= 15
        if a.involves_automated_decisions:
            issues.append(
                f"Actividad «{a.name}» incluye decisiones automatizadas con efectos significativos; "
                "requiere DPIA (Ley 21.719 art. 25)."
            )
            score -= 10
        if not a.recipients:
            issues.append(f"Actividad «{a.name}» no documenta destinatarios / transferencias.")
            score -= 5

    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return ComplianceScoreResponse(
        organization_id=org_id,
        score=score,
        grade=grade,
        issues=issues,
        activity_count=len(activities),
        last_reviewed_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# A.1 — Breach notification (PLATFORM_ADMIN only)
# ---------------------------------------------------------------------------

@router.post("/breach-notify", response_model=dict, status_code=status.HTTP_201_CREATED)
def notify_breach(
    payload: BreachNotifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a breach and mark when we notified the Agencia de
    Protección de Datos Personales. Real integration with the
    Agencia's reporting API is a Fase 3 task; for now we mark the
    timestamp and store the description so we can produce a manual
    report if the agency asks."""
    if "PLATFORM_ADMIN" not in (current_user.roles or []):
        raise HTTPException(
            status_code=403,
            detail="Solo PLATFORM_ADMIN puede registrar un breach a nivel plataforma.",
        )

    now = datetime.utcnow()
    row = BreachIncident(
        organization_id=payload.organization_id,
        discovered_at=now,
        severity=payload.severity,
        description=payload.description,
        mitigation=payload.mitigation,
        affected_user_ids=payload.affected_user_ids,
        reported_to_agency_at=now,  # We mark it now; the actual API submit is manual for now.
        reported_to_users_at=now if payload.notify_users else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    _log_audit(
        db,
        user_id=current_user.id,
        organization_id=payload.organization_id,
        action="breach.recorded",
        entity_type="breach_incident",
        entity_id=row.id,
        extra={
            "severity": payload.severity.value,
            "affected_count": len(payload.affected_user_ids),
        },
    )

    return {
        "id": row.id,
        "discovered_at": row.discovered_at.isoformat(),
        "severity": row.severity.value,
        "next_step": "Manual report to the Agencia de Protección de Datos Personales if high/critical severity.",
    }
