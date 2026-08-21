import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, get_platform_admin_membership
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.matter import Matter
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User

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
