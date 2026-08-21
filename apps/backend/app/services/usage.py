"""Usage event tracking for Lilian.

Why a separate service:
- Every billable action (upload, analysis run, LLM call) writes here, so
  usage-based billing can be added later without scattering writes.
- ``record_event`` swallows exceptions deliberately: an analytics write
  must never block the user-visible request that triggered it.
- The existing ``record_usage_event`` in ``app/api/endpoints/saas.py`` is
  a thin function on the same ``UsageEvent`` model; we keep it as a
  backward-compat wrapper so legacy callers do not break.

Caller pattern::

    from app.services.usage import record_event

    record_event(
        organization_id=org_id,
        user_id=user_id,
        event_type="document_uploaded",
        quantity=1,
        metadata={"matter_id": matter_id, "size_bytes": size},
    )

The optional ``db`` parameter lets a caller pass its open session to
reuse the same transaction. If omitted, a fresh ``SessionLocal`` is
opened, used, and closed — safe to call from background tasks too.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.subscription import UsageEvent

logger = logging.getLogger("lilian.usage")


# Event-type constants — single source of truth so dashboards, billing,
# and the audit log all speak the same vocabulary.
EVENT_DOCUMENT_UPLOADED = "document_uploaded"
EVENT_DOCUMENT_PROCESSED = "document_processed"
EVENT_ANALYSIS_RUN = "analysis_run"
EVENT_LLM_CALL = "llm_call"
EVENT_CHAT_MESSAGE = "chat_message"
EVENT_EXPORT_PDF = "export_pdf"


def record_event(
    organization_id: int,
    event_type: str,
    quantity: int = 1,
    *,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    db: Session | None = None,
) -> UsageEvent | None:
    """Persist a single usage event.

    Args:
        organization_id: Tenant that owns the event.
        event_type: One of the EVENT_* constants (or a custom string).
        quantity: How many units this event represents (pages, tokens, etc.).
        user_id: Optional actor — useful for per-user reports.
        metadata: Free-form dict serialised to JSON in ``event_metadata``.
        db: Optional SQLAlchemy session. If None, a new session is opened
            and closed. Errors are logged and swallowed so analytics writes
            never break the calling request.

    Returns:
        The created ``UsageEvent`` on success, ``None`` on failure.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        event = UsageEvent(
            organization_id=organization_id,
            user_id=user_id,
            event_type=event_type,
            quantity=quantity,
            event_metadata=json.dumps(metadata) if metadata else None,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as exc:  # pragma: no cover - never block callers
        logger.warning(
            "failed to record usage event org=%s type=%s err=%s",
            organization_id,
            event_type,
            exc,
        )
        try:
            if owns_session and db is not None:
                db.rollback()
        except Exception:
            pass
        return None
    finally:
        if owns_session and db is not None:
            db.close()


def get_period_totals(
    organization_id: int,
    *,
    days: int = 30,
    db: Session | None = None,
) -> dict[str, int]:
    """Aggregate event counts for the last ``days`` days, grouped by event_type.

    Useful for dashboards. Returns ``{event_type: total_quantity}``.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func

    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        since = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(UsageEvent.event_type, func.coalesce(func.sum(UsageEvent.quantity), 0))
            .filter(
                UsageEvent.organization_id == organization_id,
                UsageEvent.created_at >= since,
            )
            .group_by(UsageEvent.event_type)
            .all()
        )
        return {event_type: int(total) for event_type, total in rows}
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "failed to compute period totals org=%s err=%s",
            organization_id,
            exc,
        )
        return {}
    finally:
        if owns_session and db is not None:
            db.close()
