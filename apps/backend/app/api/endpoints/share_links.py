"""Public, read-only share links for analysis reports (S4.5).

Lawyers frequently need to send the AI analysis to a client or
counterparty who is not a Lilian user. The flow is:

1. Lawyer POSTs ``/api/v1/shares`` with a ``matter_id`` (or
   ``report_id``). The backend signs a token with the report id
   using ``itsdangerous.URLSafeSerializer`` and returns
   ``{"token": "...", "url": ".../share/<token>"}``.
2. The lawyer copies the URL and sends it via email / WhatsApp.
3. The recipient follows the URL. The frontend page at
   ``/share/<token>`` calls ``GET /api/v1/shares/<token>`` — which
   is **unauthenticated** — and renders the report.

The token encodes ``organization_id:report_id:expires_ts`` and is
signed with ``SHARE_LINK_SECRET`` (defaults to ``JWT_SECRET``). The
recipient only sees the fields documented in ``SharedReportResponse``
— no PII or other tenant data. Audit logs track every "share
created" and "share viewed" event for compliance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.deps.tenant import get_tenant_context
from app.core.config import settings
from app.core.database import get_db
from app.models.analysis_report import AnalysisReport
from app.models.matter import Matter
from app.models.user import User
from app.services.audit import get_client_ip, record_audit_log

router = APIRouter(prefix="/shares", tags=["shares"])
_logger = logging.getLogger("lilian.shares")

# Prefer a dedicated secret; fall back to JWT_SECRET so deployments
# never fail just because SHARE_LINK_SECRET is unset. Rotating
# JWT_SECRET will invalidate every existing share link, which is
# acceptable for this low-frequency feature.
_SIGNER_SECRET = settings.SHARE_LINK_SECRET or settings.JWT_SECRET
_serializer = URLSafeSerializer(_SIGNER_SECRET, salt="lilian.share")


# ---------- Schemas ---------- #


class CreateShareRequest(BaseModel):
    matter_id: Optional[int] = None
    report_id: Optional[int] = None
    # Lifetime of the link in days. Defaults to 30, capped at 365.
    ttl_days: int = Field(default=30, ge=1, le=365)


class CreateShareResponse(BaseModel):
    token: str
    url: str
    expires_at: datetime
    report_id: int


class SharedReportResponse(BaseModel):
    report_id: int
    matter_id: int
    matter_title: str
    summary: Optional[str] = None
    facts: Optional[str] = None
    next_steps: Optional[str] = None
    disclaimer: Optional[str] = None
    confidence: Optional[str] = None
    created_at: Optional[datetime] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None


# ---------- Endpoints ---------- #


@router.post("", response_model=CreateShareResponse, status_code=status.HTTP_201_CREATED)
def create_share_link(
    payload: CreateShareRequest,
    request: Request,
    db: Session = Depends(get_db),
    tenant_ctx=Depends(get_tenant_context),
    current_user: User = Depends(get_current_user),
) -> CreateShareResponse:
    """Mint a signed token for one report.

    Exactly one of ``matter_id`` or ``report_id`` must be provided.
    When ``matter_id`` is given, the *latest* report for that matter
    is shared.
    """
    if not payload.matter_id and not payload.report_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar matter_id o report_id",
        )
    if payload.matter_id and payload.report_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Indica solo uno: matter_id o report_id",
        )

    organization_id = tenant_ctx.organization_id

    report: Optional[AnalysisReport] = None
    if payload.report_id:
        report = (
            db.query(AnalysisReport)
            .filter(
                AnalysisReport.id == payload.report_id,
                AnalysisReport.organization_id == organization_id,
            )
            .first()
        )
    else:
        report = (
            db.query(AnalysisReport)
            .filter(
                AnalysisReport.matter_id == payload.matter_id,
                AnalysisReport.organization_id == organization_id,
            )
            .order_by(AnalysisReport.created_at.desc())
            .first()
        )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el informe para ese caso",
        )

    expires_at = datetime.utcnow() + timedelta(days=payload.ttl_days)
    expires_ts = int(expires_at.timestamp())

    payload_str = f"{organization_id}:{report.id}:{expires_ts}"
    token = _serializer.dumps(payload_str)

    # Audit log entry: who shared what.
    try:
        record_audit_log(
            db=db,
            organization_id=organization_id,
            user_id=current_user.id,
            action="share.create",
            entity_type="analysis_report",
            entity_id=report.id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            metadata={
                "matter_id": report.matter_id,
                "ttl_days": payload.ttl_days,
                "expires_at": expires_at.isoformat(),
            },
        )
    except Exception as exc:  # pragma: no cover - audit logging must never fail the request
        _logger.warning("audit log (share.create) failed: %s", exc)
        db.rollback()

    base_url = (settings.FRONTEND_BASE_URL or "").rstrip("/")
    url = f"{base_url}/share/{token}"

    return CreateShareResponse(
        token=token,
        url=url,
        expires_at=expires_at,
        report_id=report.id,
    )


@router.get("/{token}", response_model=SharedReportResponse)
def read_shared_report(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> SharedReportResponse:
    """Return the report body for a signed token. No auth required.

    The token encodes ``organization_id:report_id:expires_ts``. We
    verify the signature, the expiry, and load the report.
    """
    try:
        decoded = _serializer.loads(token)
    except BadSignature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Enlace inválido o manipulado",
        )

    try:
        org_id_str, report_id_str, expires_ts_str = decoded.split(":")
        organization_id = int(org_id_str)
        report_id = int(report_id_str)
        expires_ts = int(expires_ts_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enlace malformado",
        )

    if expires_ts < int(datetime.utcnow().timestamp()):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Este enlace ha expirado",
        )

    report = (
        db.query(AnalysisReport)
        .filter(
            AnalysisReport.id == report_id,
            AnalysisReport.organization_id == organization_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El informe ya no está disponible",
        )

    # Audit: the share was just viewed. We can't log the viewer
    # (no auth), but we record the IP against the organization so
    # the owner can see when their link was opened.
    try:
        record_audit_log(
            db=db,
            organization_id=organization_id,
            user_id=None,
            action="share.view",
            entity_type="analysis_report",
            entity_id=report.id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as exc:  # pragma: no cover
        _logger.warning("audit log (share.view) failed: %s", exc)
        db.rollback()

    matter = db.query(Matter).filter(Matter.id == report.matter_id).first()
    matter_title = matter.title if matter else "Caso sin título"

    return SharedReportResponse(
        report_id=report.id,
        matter_id=report.matter_id,
        matter_title=matter_title,
        summary=report.summary,
        facts=report.facts,
        next_steps=report.next_steps,
        disclaimer=report.disclaimer,
        confidence=report.confidence,
        created_at=report.created_at,
        model_provider=report.model_provider,
        model_name=report.model_name,
    )
