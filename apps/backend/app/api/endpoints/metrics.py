"""GET /metrics — process-local observability surface.

Returns a JSON snapshot of the in-memory :mod:`app.core.metrics` registry plus
business counts pulled live from the database. Kept dependency-free so it can
ship in any environment without extra configuration.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.metrics import registry
from app.models.matter import Matter, MatterStatus
from app.models.document import Document

router = APIRouter(tags=["observability"])
log = logging.getLogger(__name__)


_ACTIVE_STATUSES = {
    MatterStatus.NEW,
    MatterStatus.PROCESSING,
    MatterStatus.ANALYSIS_READY,
    MatterStatus.PENDING_HUMAN_REVIEW,
    MatterStatus.MISSING_INFORMATION,
    MatterStatus.CONTACT_CLIENT,
    MatterStatus.IN_PROGRESS,
}


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)) -> dict:
    """Snapshot of request counters, latency percentiles, and business counts.

    Business counts are queried lazily and cached in the registry for 60s so
    a chatty scraper cannot turn this endpoint into a hot SELECT path.
    """
    snapshot = registry.snapshot()
    counts_stale = (
        snapshot["business_counts_loaded_at"] is None
        or (datetime.utcnow().timestamp() - snapshot["business_counts_loaded_at"]) > 60
    )
    if counts_stale:
        try:
            active_matters = (
                db.query(func.count(Matter.id))
                .filter(Matter.status.in_(_ACTIVE_STATUSES))
                .scalar()
                or 0
            )
            active_documents = (
                db.query(func.count(Document.id))
                .filter(Document.processed_at.is_(None))
                .scalar()
                or 0
            )
        except Exception as exc:
            log.warning("metrics_business_counts_failed", extra={"error": str(exc)})
            registry.record_error("metrics_db_failure")
            return snapshot
        registry.set_business_counts(
            active_matters=active_matters,
            active_documents=active_documents,
        )
        snapshot = registry.snapshot()

    return snapshot
