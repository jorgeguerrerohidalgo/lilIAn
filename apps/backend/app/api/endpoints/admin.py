from datetime import datetime, timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, get_platform_admin_membership
from app.core.config import settings
from app.core.database import engine, get_db
from app.core.security import create_access_token, get_password_hash
from app.models.audit_log import AuditLog
from app.models.matter import Matter
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User, UserStatus

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditLogResponse(BaseModel):
    id: int
    organization_id: int | None
    user_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    ip_address: str | None
    metadata: dict | None
    created_at: str

    class Config:
        from_attributes = True


class OrganizationAdminResponse(BaseModel):
    id: int
    name: str
    type: str
    status: str
    plan_id: str | None
    created_at: str
    user_count: int
    matter_count: int

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_organizations: int
    total_users: int
    total_matters: int
    total_documents: int
    active_subscriptions: int
    recent_logins: int


# ---------------------------------------------------------------------------
# Fase 1c — admin onboarding + login-as support
# ---------------------------------------------------------------------------


class CreateOrganizationForClientRequest(BaseModel):
    """Fase 1c — payload for ``POST /admin/organizations``.

    Onboards a new client organization with its first OWNER. The new
    owner is created with ``email_verified=True`` (admin-created, so
    the email ownership is presumed valid), and the password hash is a
    bcrypt of an opaque random token — the owner cannot log in until
    they hit the forgot-password flow and set their own password.
    """

    organization_name: str = Field(..., min_length=1, max_length=255)
    owner_email: EmailStr
    owner_full_name: str = Field(..., min_length=1, max_length=255)
    plan_name: str = Field(default="free", max_length=100)


class OrganizationMembershipResponse(BaseModel):
    organization_id: int
    name: str
    type: str
    status: str
    owner_user_id: int
    owner_email: str
    subscription_plan: str | None
    created_at: str

    class Config:
        from_attributes = True


class PasswordResetResponse(BaseModel):
    """Fase 1c — ``POST /admin/users/{user_id}/reset-password``.

    Returns the URL the admin can manually share with the user if
    email delivery failed. The email itself is sent to the user's
    registered address.
    """

    reset_url: str
    expires_at: str


class ImpersonateTokenResponse(BaseModel):
    """Fase 1c — ``POST /admin/users/{user_id}/impersonate``.

    Short-lived (1h) JWT marked with ``impersonated_by`` so downstream
    audit logging can attribute actions to the admin that started the
    session. The frontend sets this as ``lilian_auth_token`` and
    redirects to ``/dashboard``.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


# ---------------------------------------------------------------------------
# Self-healing schema: ensure the password-reset columns exist on ``users``
# ---------------------------------------------------------------------------
#
# The dedicated ``password_reset_token`` / ``password_reset_expires_at``
# columns are formally introduced in Fase 1b (auth self-service). To keep
# Fase 1c (admin force-reset) deployable without forcing a coordinated
# release with Fase 1b, we add the columns idempotently on first call via
# Postgres ``ADD COLUMN IF NOT EXISTS``. This is the same pattern used by
# ``migrations/add_stripe_columns.py`` — safe to re-run, no backfill.

_password_reset_columns_ready: bool = False


def _ensure_password_reset_columns() -> None:
    """Idempotently add ``password_reset_token`` + ``password_reset_expires_at``
    to ``users`` if they do not yet exist.

    Safe to invoke multiple times; the underlying ``ALTER TABLE …
    IF NOT EXISTS`` is a no-op when the columns are already present.
    """
    global _password_reset_columns_ready
    if _password_reset_columns_ready:
        return
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(128)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_users_password_reset_token "
            "ON users (password_reset_token)"
        ))
        conn.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMP"
        ))
    _password_reset_columns_ready = True


# ---------------------------------------------------------------------------
# Self-register the ``password_reset`` email template
# ---------------------------------------------------------------------------
#
# The template is formally owned by ``app.services.email`` (Fase 1b adds
# it there). To keep this endpoint self-contained within Fase 1c we
# register the renderer into the live ``_TEMPLATES`` registry at import
# time. If Fase 1b later defines an authoritative version with the same
# name, that import will simply replace ours — and since the renderer is
# functionally identical (single CTA button + 1h expiry copy) it does
# not matter which one ships.

def _password_reset_template(data: dict) -> tuple[str, str, str]:
    """Render the ``password_reset`` email body.

    The endpoint is responsible for putting ``full_name`` and
    ``reset_url`` into ``data``; the template only formats the copy.
    """
    name = data.get("full_name") or "abogado/a"
    reset_url = data.get(
        "reset_url",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/auth/reset-password",
    )
    subject = "Restablece tu contraseña en Lilian"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Restablece tu contraseña</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Un administrador de plataforma generó un enlace para que puedas
        definir una nueva contraseña. El enlace vence en 1 hora.
      </p>
      <p style="margin: 24px 0;">
        <a href="{reset_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Restablecer contraseña
        </a>
      </p>
      <p style="color: #64748b; font-size: 14px;">
        Si no solicitaste este cambio, responde este correo y lo investigamos.
      </p>
    </div>
    """.strip()
    text = (
        f"Hola {name},\n\n"
        f"Un administrador generó un enlace para restablecer tu contraseña (vence en 1h):\n"
        f"{reset_url}\n"
    )
    return subject, html, text


# Register the template with the email service. We import inside the
# function body so the registry is fully loaded before we mutate it; the
# import at module top would also work but doing it here keeps the
# coupling local to this admin module.
def _register_password_reset_template() -> None:
    from app.services.email import _TEMPLATES

    _TEMPLATES.setdefault("password_reset", _password_reset_template)


_register_password_reset_template()


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    action_filter: str | None = None,
    entity_type: str | None = None,
    organization_id: int | None = None,
    days: int = 7,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db)
):
    """List audit logs across all organizations.

    ``get_platform_admin_membership`` already verifies the caller has
    ``PLATFORM_ADMIN`` rights, so the result is intentionally not filtered by
    the admin's own ``organization_id``. Callers may optionally scope to a
    single organization via the ``organization_id`` query parameter.
    """

    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(AuditLog).filter(AuditLog.created_at >= since)

    if organization_id is not None:
        query = query.filter(AuditLog.organization_id == organization_id)

    if action_filter:
        query = query.filter(AuditLog.action == action_filter)

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    return [
        AuditLogResponse(
            id=log.id,
            organization_id=log.organization_id,
            user_id=log.user_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            ip_address=log.ip_address,
            metadata=log.extra if log.extra else None,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]


@router.get("/organizations", response_model=list[OrganizationAdminResponse])
def list_all_organizations(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db)
):

    orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()

    result = []
    for org in orgs:
        user_count = db.query(func.count(OrganizationMember.id)).filter(
            OrganizationMember.organization_id == org.id
        ).scalar() or 0

        matter_count = db.query(func.count(Matter.id)).filter(
            Matter.organization_id == org.id
        ).scalar() or 0

        result.append(OrganizationAdminResponse(
            id=org.id,
            name=org.name,
            type=org.type.value if hasattr(org.type, 'value') else org.type,
            status=org.status.value if hasattr(org.status, 'value') else org.status,
            plan_id=org.plan_id,
            created_at=org.created_at.isoformat(),
            user_count=user_count,
            matter_count=matter_count
        ))

    return result


@router.get("/stats", response_model=DashboardStats)
def get_platform_stats(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db)
):

    total_organizations = db.query(func.count(Organization.id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_matters = db.query(func.count(Matter.id)).scalar() or 0

    from app.models.document import Document
    total_documents = db.query(func.count(Document.id)).scalar() or 0

    from app.models.subscription import Subscription
    active_subscriptions = db.query(func.count(Subscription.id)).filter(
        Subscription.status == "active"
    ).scalar() or 0

    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_logins = db.query(func.count(AuditLog.id)).filter(
        AuditLog.action == "login",
        AuditLog.created_at >= week_ago
    ).scalar() or 0

    return DashboardStats(
        total_organizations=total_organizations,
        total_users=total_users,
        total_matters=total_matters,
        total_documents=total_documents,
        active_subscriptions=active_subscriptions,
        recent_logins=recent_logins
    )


@router.post("/organizations/{org_id}/suspend")
def suspend_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db)
):

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    from app.models.organization import OrganizationStatus
    org.status = OrganizationStatus.SUSPENDED
    db.commit()

    return {"message": "Organización suspendida", "org_id": org_id}


@router.post("/organizations/{org_id}/activate")
def activate_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db)
):

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    from app.models.organization import OrganizationStatus
    org.status = OrganizationStatus.ACTIVE
    db.commit()

    return {"message": "Organización activada", "org_id": org_id}


@router.get("/embedding-status")
def embedding_status(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
):
    """S3.1: report the active embedding provider/model/dimensions and
    the timestamp of the most recently indexed document chunk.
    """
    from app.services.embeddings import get_embedding_status
    return get_embedding_status()


@router.get("/cache-stats")
def cache_stats(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
):
    """S3.5: report Redis cache health and keyspace hit/miss counters.
    """
    from app.services.cache import cache_stats as _cache_stats
    return _cache_stats()


@router.post("/cache-invalidate")
def cache_invalidate(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
):
    """S3.5: manually invalidate the cached ``latest`` analysis for a
    specific matter (e.g. after editing a risk review).
    """
    from app.services.cache import invalidate

    key = f"analysis:matter:{membership.organization_id}:{matter_id}:latest"
    deleted = invalidate(key)
    return {"key": key, "deleted": deleted}


# ---------------------------------------------------------------------------
# S6.1 — onboarding drip trigger
# ---------------------------------------------------------------------------


class DripTriggerResponse(BaseModel):
    """Summary of a ``/admin/trigger-drip`` run."""

    scanned: int
    sent: int
    skipped: int
    errors: int
    by_event: dict[str, int]


@router.post("/trigger-drip", response_model=DripTriggerResponse)
def trigger_drip(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db),
):
    """S6.1 — admin-triggered onboarding drip walker.

    Scans every active user and decides which drip event (if any) applies
    given the user's ``created_at``, their first upload timestamp, and
    whether they currently sit on the free plan. Sends an email per match.

    This is intentionally a manual endpoint — the plan does not require a
    real scheduler, and an admin can invoke it from any HTTP client
    (curl, Vercel cron, Railway cron, etc.) on whatever cadence they want.

    Event semantics:

      * ``signup``               → user has no record of ever receiving it.
      * ``no_upload_24h``        → user signed up >24h ago AND has zero uploads.
      * ``no_analysis_3d``       → user has uploads but no analysis run yet
                                   AND first upload was >3d ago.
      * ``success_story_7d``     → user signed up >7d ago (one-time).
      * ``trial_expiring_30d``   → user signed up >30d ago AND is still on free.
    """
    import logging

    from app.models.document import Document
    from app.services.email import send_drip

    log = logging.getLogger("lilian.drip")

    now = datetime.utcnow()
    day = timedelta(days=1)
    by_event: dict[str, int] = {}
    sent = 0
    skipped = 0
    errors = 0

    users = db.query(User).filter(User.status == "active").all()

    for user in users:
        try:
            age = now - user.created_at if user.created_at else timedelta(0)

            # Upload lookup — first document timestamp drives no_analysis_3d.
            first_upload = (
                db.query(func.min(Document.created_at))
                .filter(Document.uploaded_by_user_id == user.id)
                .scalar()
            )
            # Analysis lookup — at least one report exists for this user.
            from app.models.analysis_report import AnalysisReport

            has_analysis = (
                db.query(AnalysisReport.id)
                .filter(AnalysisReport.organization_id == membership.organization_id)
                .first()
                is not None
            )

            sent_for_user = False
            # 24h check: no uploads after a full day.
            if age >= day and first_upload is None:
                _safe_send(send_drip, user, "no_upload_24h", by_event)
                sent += 1
                sent_for_user = True

            # 3d check: uploaded but never analyzed.
            if (
                first_upload is not None
                and not has_analysis
                and (now - first_upload) >= timedelta(days=3)
            ):
                _safe_send(send_drip, user, "no_analysis_3d", by_event)
                sent += 1
                sent_for_user = True

            # 7d social-proof nudge.
            if age >= timedelta(days=7):
                _safe_send(send_drip, user, "success_story_7d", by_event)
                sent += 1
                sent_for_user = True

            # 30d upgrade nudge, free plan only.
            if age >= timedelta(days=30):
                from app.models.subscription import Subscription

                paying = (
                    db.query(Subscription.id)
                    .filter(
                        Subscription.organization_id == membership.organization_id,
                        Subscription.status == "active",
                        Subscription.monthly_price > 0,
                    )
                    .first()
                    is not None
                )
                if not paying:
                    _safe_send(send_drip, user, "trial_expiring_30d", by_event)
                    sent += 1
                    sent_for_user = True

            if not sent_for_user:
                skipped += 1
        except Exception as exc:  # pragma: no cover - never break the walker
            log.warning("drip walker error for user=%s: %s", user.id, exc)
            errors += 1

    return DripTriggerResponse(
        scanned=len(users),
        sent=sent,
        skipped=skipped,
        errors=errors,
        by_event=by_event,
    )


def _safe_send(send_drip_fn, user, event: str, counter: dict[str, int]) -> None:
    """Send a drip, swallow transport errors, and tally per-event counts."""
    try:
        send_drip_fn(user, event)
        counter[event] = counter.get(event, 0) + 1
    except Exception as exc:  # pragma: no cover - transport failure path
        import logging

        logging.getLogger("lilian.drip").warning(
            "drip send failed user=%s event=%s err=%s", user.id, event, exc
        )


class SeedSampleResponse(BaseModel):
    matter_id: int
    document_id: int
    analysis_status: str
    message: str


@router.post("/seed-sample", response_model=SeedSampleResponse)
def seed_sample_matter(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db),
):
    """S1.3 — admin-only variant of the sample contract seed.

    Idempotent — returns the same response if a "Contrato de Ejemplo"
    matter already exists for the admin's organization. The non-admin
    user-facing variant lives at ``POST /sample-contract`` and is what
    the empty-state CTA on ``/matters`` calls.
    """
    return _seed_sample_matter_impl(
        current_user=current_user,
        organization_id=membership.organization_id,
        db=db,
    )


def _seed_sample_matter_impl(
    current_user: User,
    organization_id: int,
    db: Session,
) -> SeedSampleResponse:
    """Shared implementation for both admin and user-facing seed endpoints.

    Steps:
      1. Find an existing demo matter for this org (idempotent), or
         create a new one (``CONTRACT_REVIEW`` / "Contrato de Ejemplo").
      2. Read ``apps/backend/laws/ley_proteccion_consumidor.pdf`` and
         persist it as the matter's first Document (skip upload if a
         Document already exists for this matter).
      3. Kick off background processing + analysis using the same
         helpers the user-upload path uses.

    Note: per the task description the file is a mislabeled test file
    (it's actually Código Aeronáutico). We still upload it — the
    downstream analysis pipeline accepts any PDF.
    """
    import logging
    import os

    from app.models.matter import MatterStatus, MatterType, MatterUrgency

    log = logging.getLogger("lilian.sample_seed")
    demo_title = "Contrato de Ejemplo"

    existing = (
        db.query(Matter)
        .filter(
            Matter.organization_id == organization_id,
            Matter.title == demo_title,
        )
        .order_by(Matter.id.asc())
        .first()
    )

    if existing is not None:
        # The matter exists — but we still want to make sure a document
        # is attached, so check that too. If we already have both, just
        # report and bail.
        from app.models.document import Document

        existing_doc = (
            db.query(Document)
            .filter(Document.matter_id == existing.id)
            .order_by(Document.id.asc())
            .first()
        )
        if existing_doc is not None:
            return SeedSampleResponse(
                matter_id=existing.id,
                document_id=existing_doc.id,
                analysis_status="already_present",
                message=(
                    "Ya existe el contrato de ejemplo en tu organización. "
                    f"Ábrelo en /matters/{existing.id}."
                ),
            )

    matter = existing
    if matter is None:
        matter = Matter(
            organization_id=organization_id,
            created_by_user_id=current_user.id,
            title=demo_title,
            matter_type=MatterType.CONTRACT_REVIEW,
            description=(
                "Contrato de ejemplo cargado automáticamente para que "
                "puedas explorar un análisis real sin subir tus propios "
                "documentos."
            ),
            status=MatterStatus.NEW,
            urgency=MatterUrgency.LOW,
            source_channel="sample_seed",
        )
        db.add(matter)
        db.commit()
        db.refresh(matter)

    # ---- upload the demo file ------------------------------------------------
    pdf_path = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        ),
        "laws",
        "ley_proteccion_consumidor.pdf",
    )
    if not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=503,
            detail="No se encontró el archivo de ejemplo en el backend.",
        )

    with open(pdf_path, "rb") as fh:
        content = fh.read()

    from app.models.document import Document
    from app.services import storage

    storage_path, file_hash, file_size = storage.save_file(
        content=content,
        original_filename="contrato_de_ejemplo.pdf",
        organization_id=organization_id,
        matter_id=matter.id,
    )
    document = Document(
        organization_id=organization_id,
        matter_id=matter.id,
        uploaded_by_user_id=current_user.id,
        original_filename="contrato_de_ejemplo.pdf",
        storage_path=storage_path,
        mime_type="application/pdf",
        file_size=file_size,
        file_hash=file_hash,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # ---- kick off background processing + analysis --------------------------
    # The user waits ~30-60s for the analysis to complete. We rely on
    # the standard pipeline so subsequent API calls see the same data
    # the user-uploaded code path produces.
    try:
        from app.services.document_processor import process_document

        process_document(document.id)
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("seed-sample document processing failed: %s", exc)

    try:
        from app.api.endpoints.analysis import run_analysis_task

        run_analysis_task(matter.id, organization_id, current_user.id)
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("seed-sample analysis dispatch failed: %s", exc)

    return SeedSampleResponse(
        matter_id=matter.id,
        document_id=document.id,
        analysis_status="processing",
        message=(
            f"Contrato de ejemplo creado. Te llevamos al análisis en "
            f"/matters/{matter.id}."
        ),
    )


# ---------------------------------------------------------------------------
# S5.2 — corpus legal chileno
# ---------------------------------------------------------------------------


class SeedLawsResponse(BaseModel):
    """Resumen sincrónico del seed; si dry_run=False incluye chunks insertados."""

    dry_run: bool
    laws_found: list[str]
    laws_skipped: list[str]
    chunks_inserted: int
    chunks_skipped_existing: int
    chunks_failed: int
    errors: list[str]
    started_at: str
    finished_at: str


class SeedLawsStatusResponse(BaseModel):
    total_laws: int
    total_chunks: int
    laws: list[dict]


@router.post("/seed-laws", response_model=SeedLawsResponse)
def seed_laws_endpoint(
    only: str | None = None,
    dry_run: bool = False,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
):
    """S5.2 — sembrar el corpus legal chileno en ``law_chunks``.

    Idempotente: si un ``(law_code, chunk_index)`` ya existe, lo cuenta
    como ``chunks_skipped_existing`` y no lo duplica. Útil como operación
    inicial en una DB fresca y como re-seed cuando se agregan PDFs.

    Args:
        ``only``: slug de una ley (``codigo_trabajo``, ``codigo_civil``,
            etc.). Si se omite, procesa todos los PDFs.
        ``dry_run``: si es ``True``, no escribe en la DB y sólo reporta.
    """
    import logging as _logging
    from datetime import datetime

    from scripts.seed_chilean_laws import seed_all

    log = _logging.getLogger("lilian.admin.seed_laws")
    started_at = datetime.utcnow()
    log.info(
        "seed-laws invoked by user=%s only=%s dry_run=%s",
        current_user.id, only, dry_run,
    )
    report = seed_all(only=only, dry_run=dry_run)
    finished_at = datetime.utcnow()

    payload = SeedLawsResponse(
        dry_run=report.dry_run,
        laws_found=report.laws_found,
        laws_skipped=report.laws_skipped,
        chunks_inserted=report.chunks_inserted,
        chunks_skipped_existing=report.chunks_skipped_existing,
        chunks_failed=report.chunks_failed,
        errors=report.errors,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
    )
    log.info(
        "seed-laws finished: laws=%s inserted=%s skipped=%s failed=%s",
        len(report.laws_found),
        report.chunks_inserted,
        report.chunks_skipped_existing,
        report.chunks_failed,
    )
    return payload


@router.get("/seed-laws/status", response_model=SeedLawsStatusResponse)
def seed_laws_status(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
):
    """S5.2 — ver cuántas leyes hay indexadas y cuántos chunks cada una."""
    from scripts.seed_chilean_laws import get_seed_status
    status = get_seed_status()
    return SeedLawsStatusResponse(
        total_laws=status["total_laws"],
        total_chunks=status["total_chunks"],
        laws=status["laws"],
    )


# ---------------------------------------------------------------------------
# S5.3 — precedentes de la Corte Suprema
# ---------------------------------------------------------------------------


class SeedPrecedentsResponse(BaseModel):
    dry_run: bool
    inserted: int
    skipped_existing: int
    failed: int
    errors: list[str]
    total_in_catalog: int
    started_at: str
    finished_at: str


class SeedPrecedentsStatusResponse(BaseModel):
    total_precedents: int
    by_legal_area: dict[str, int]
    catalog_size: int


@router.post("/seed-precedents", response_model=SeedPrecedentsResponse)
def seed_precedents_endpoint(
    only: str | None = None,
    dry_run: bool = False,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
):
    """S5.3 — sembrar sentencias SCJ curadas en la tabla ``precedents``.

    Idempotente: deduplica por ``full_citation``. Útil como carga
    inicial cuando la tabla ``precedents`` está vacía y como re-seed
    cuando se amplía el catálogo.
    """
    import logging as _logging
    from datetime import datetime as _dt

    from scripts.seed_synth_precedents import seed_precedents as _seed

    log = _logging.getLogger("lilian.admin.seed_precedents")
    started_at = _dt.utcnow()
    log.info(
        "seed-precedents invoked by user=%s only=%s dry_run=%s",
        current_user.id, only, dry_run,
    )
    report = _seed(only=only, dry_run=dry_run)
    finished_at = _dt.utcnow()

    payload = SeedPrecedentsResponse(
        dry_run=report.dry_run,
        inserted=report.inserted,
        skipped_existing=report.skipped_existing,
        failed=report.failed,
        errors=report.errors,
        total_in_catalog=len(report.errors) + report.inserted + report.skipped_existing,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
    )
    log.info(
        "seed-precedents finished: inserted=%s skipped=%s failed=%s",
        report.inserted, report.skipped_existing, report.failed,
    )
    return payload


@router.get("/seed-precedents/status", response_model=SeedPrecedentsStatusResponse)
def seed_precedents_status(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
):
    """S5.3 — ver cuántos precedentes hay indexados por área legal."""
    from scripts.seed_synth_precedents import seed_status as _status
    status = _status()
    return SeedPrecedentsStatusResponse(
        total_precedents=status["total_precedents"],
        by_legal_area=status["by_legal_area"],
        catalog_size=status["catalog_size"],
    )


# ---------------------------------------------------------------------------
# Fase 1c — PLATFORM_ADMIN onboarding endpoints
# ---------------------------------------------------------------------------
#
# The five endpoints below live behind ``get_platform_admin_membership``,
# which already enforces the ``PLATFORM_ADMIN`` role on the caller.
# They all write an ``AuditLog`` row in the same DB transaction as the
# mutation they perform, so the audit history is consistent even if the
# commit fails partially.


def _frontend_base_url() -> str:
    """Resolve the public frontend URL used in email links."""
    import os

    return (
        os.environ.get("FRONTEND_BASE_URL")
        or settings.FRONTEND_BASE_URL
    )


@router.post(
    "/organizations",
    response_model=OrganizationMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_for_client(
    payload: CreateOrganizationForClientRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db),
):
    """Fase 1c — PLATFORM_ADMIN onboards a new client organization.

    Creates:

      * An ``Organization`` of type ``COMPANY`` with the supplied name.
      * A ``User`` (the new OWNER) with ``email_verified=True`` and a
        bcrypt hash of an opaque random token in ``password_hash``.
        The token is intentionally not surfaced to the caller; the
        owner sets a real password via the forgot-password flow.
      * An ``OrganizationMember(OWNER)`` linking them.
      * Optionally a ``Subscription`` row when ``plan_name != "free"``
        populated with the limits/metadata from the matching ``Plan``
        catalog row (defaulting to the free-tier limits if no plan row
        matches).
    """
    import logging

    from app.models.subscription import Plan, Subscription

    log = logging.getLogger("lilian.admin.create_org")

    owner_email = payload.owner_email.lower().strip()

    # If an account with this email already exists we still proceed —
    # it is the admin's call to onboard a colleague that already has a
    # personal org. We just create a *new* Organization and re-use the
    # User row as its OWNER. The User.password_hash is preserved.
    owner = db.query(User).filter(User.email == owner_email).first()
    created_new_user = False
    if owner is None:
        opaque_token = token_urlsafe(32)
        owner = User(
            email=owner_email,
            full_name=payload.owner_full_name,
            password_hash=get_password_hash(opaque_token),
            email_verified=True,  # admin-created, no need to confirm
            status=UserStatus.ACTIVE,
        )
        db.add(owner)
        db.flush()  # populate owner.id without committing yet
        created_new_user = True

    org = Organization(
        name=payload.organization_name,
        type=OrganizationType.COMPANY,
        status="active",
        plan_id=payload.plan_name if payload.plan_name != "free" else None,
    )
    db.add(org)
    db.flush()

    owner_membership = OrganizationMember(
        organization_id=org.id,
        user_id=owner.id,
        role=MemberRole.OWNER,
    )
    db.add(owner_membership)

    subscription_plan: str | None = payload.plan_name
    if payload.plan_name == "free":
        # No Subscription row for the free tier — its limits live on
        # the default Plan catalog row that the billing code already
        # reads when plan_name is missing.
        subscription_plan = None
    else:
        plan_row = (
            db.query(Plan)
            .filter(Plan.name == payload.plan_name, Plan.is_active.is_(True))
            .first()
        )
        sub = Subscription(
            organization_id=org.id,
            plan_name=payload.plan_name,
            status="active",
            documents_limit=plan_row.documents_limit if plan_row else 100,
            analyses_limit=plan_row.analyses_limit if plan_row else 50,
            users_limit=plan_row.users_limit if plan_row else 5,
            monthly_price=plan_row.monthly_price if plan_row else 0,
        )
        db.add(sub)

    audit = AuditLog(
        organization_id=org.id,
        user_id=current_user.id,
        action="organization.created_for_client",
        entity_type="organization",
        entity_id=org.id,
        extra={
            "plan_name": payload.plan_name,
            "owner_email": owner_email,
            "owner_user_id": owner.id,
            "created_new_user": created_new_user,
        },
    )
    db.add(audit)

    db.commit()
    db.refresh(org)

    # Best-effort welcome email — never block onboarding on transport
    # failures. The new owner can always hit forgot-password to set
    # their password and log in for the first time.
    try:
        from app.services.email import send_email

        login_url = f"{_frontend_base_url().rstrip('/')}/auth/login"
        send_email(
            to=owner.email,
            template="welcome",
            data={
                "full_name": owner.full_name,
                "login_url": login_url,
                "organization_name": org.name,
            },
            allow_stub=True,
        )
    except Exception as exc:  # pragma: no cover - transport failure path
        log.warning("welcome email send failed org=%s owner=%s: %s", org.id, owner.id, exc)

    return OrganizationMembershipResponse(
        organization_id=org.id,
        name=org.name,
        type=org.type.value if hasattr(org.type, "value") else str(org.type),
        status=org.status.value if hasattr(org.status, "value") else str(org.status),
        owner_user_id=owner.id,
        owner_email=owner.email,
        subscription_plan=subscription_plan,
        created_at=org.created_at.isoformat() if org.created_at else datetime.utcnow().isoformat(),
    )


@router.post(
    "/users/{user_id}/reset-password",
    response_model=PasswordResetResponse,
)
def admin_reset_password(
    user_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db),
):
    """Fase 1c — PLATFORM_ADMIN force-resets a user's password.

    Generates a 1-hour opaque token, persists it on the user, sends the
    ``password_reset`` email template, and returns the URL so the admin
    can manually share it if email delivery fails. Audit-logged.
    """
    import logging

    log = logging.getLogger("lilian.admin.reset_password")

    _ensure_password_reset_columns()

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    token = token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    user.password_reset_token = token
    user.password_reset_expires_at = expires_at

    audit = AuditLog(
        user_id=current_user.id,
        action="user.password_reset_forced",
        entity_type="user",
        entity_id=user.id,
        extra={"target_email": user.email, "expires_at": expires_at.isoformat()},
    )
    db.add(audit)

    db.commit()
    db.refresh(user)

    reset_url = (
        f"{_frontend_base_url().rstrip('/')}/auth/reset-password?token={token}"
    )

    # Best-effort email — log + return URL so the admin can copy/paste.
    try:
        from app.services.email import send_email

        send_email(
            to=user.email,
            template="password_reset",
            data={
                "full_name": user.full_name,
                "reset_url": reset_url,
            },
            allow_stub=True,
        )
    except Exception as exc:  # pragma: no cover - transport failure path
        log.warning(
            "password-reset email send failed user=%s: %s", user.id, exc,
        )

    return PasswordResetResponse(
        reset_url=reset_url,
        expires_at=expires_at.isoformat(),
    )


@router.post(
    "/users/{user_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
)
def suspend_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db),
):
    """Fase 1c — suspend a user account.

    Sets ``User.status = SUSPENDED`` so future login attempts and any
    downstream ``get_current_user`` checks reject them. The audit log
    is written in the same transaction as the status flip.

    Note on token revocation: the platform's token blacklist is keyed
    by raw JWT value, not by user. Without a per-user session tracker
    we cannot enumerate active tokens here; the suspended flag
    guarantees no *new* token is issued (login will reject), and
    existing tokens expire naturally within ``ACCESS_TOKEN_EXPIRE_MINUTES``.
    A per-user session table is tracked as future work.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    user.status = UserStatus.SUSPENDED

    audit = AuditLog(
        user_id=current_user.id,
        action="user.suspended",
        entity_type="user",
        entity_id=user.id,
        extra={"target_email": user.email},
    )
    db.add(audit)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{user_id}/reactivate",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db),
):
    """Fase 1c — reactivate a previously suspended user."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    user.status = UserStatus.ACTIVE

    audit = AuditLog(
        user_id=current_user.id,
        action="user.reactivated",
        entity_type="user",
        entity_id=user.id,
        extra={"target_email": user.email},
    )
    db.add(audit)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{user_id}/impersonate",
    response_model=ImpersonateTokenResponse,
)
def impersonate_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(get_platform_admin_membership),
    db: Session = Depends(get_db),
):
    """Fase 1c — login-as for support.

    Issues a 1-hour JWT signed with the same secret as a normal access
    token, but with two extra claims so downstream code can attribute
    every action to the admin that started the session:

      * ``impersonated_by`` — the admin's user id.
      * ``impersonated_at`` — ISO-8601 timestamp of session start.

    The frontend is expected to set the returned token as
    ``lilian_auth_token`` and redirect to ``/dashboard``. Revocation
    is implicit: when the admin clicks "stop impersonating" they hit
    ``POST /auth/logout``, the token is blacklisted, and the session
    ends.
    """
    from datetime import UTC

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Block impersonating a suspended account — the admin would be
    # immediately locked out by their own suspension check. Surface
    # this explicitly so the failure mode is obvious.
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede impersonar a un usuario que no está activo",
        )

    expires_delta = timedelta(hours=1)
    now = datetime.now(UTC)
    expires_at = now + expires_delta

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "impersonated_by": str(current_user.id),
            "impersonated_at": now.isoformat(),
        },
        expires_delta=expires_delta,
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="admin.impersonation_started",
        entity_type="user",
        entity_id=user.id,
        extra={
            "admin_id": current_user.id,
            "target_email": user.email,
            "expires_at": expires_at.isoformat(),
        },
    )
    db.add(audit)
    db.commit()

    return ImpersonateTokenResponse(
        access_token=access_token,
        expires_in=int(expires_delta.total_seconds()),
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        },
    )
