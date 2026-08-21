"""Plan-limit enforcement for Lilian.

Why:
- ``Subscription.documents_limit`` and ``Subscription.analyses_limit`` are
  in the schema but nothing was checking them. A free-tier tenant could
  upload unlimited documents and run unlimited analyses — defeating the
  whole point of having plans.
- This module exposes ``enforce_document_limit`` and
  ``enforce_analysis_limit`` FastAPI dependencies that endpoints attach
  via ``Depends(...)``. When the tenant is over quota they raise
  ``HTTPException(402, ...)`` (Payment Required).

Design notes:
- We count *all* documents/analyses for the tenant, not per-matter,
  matching the way ``documents_limit`` is defined on the Subscription row.
- ``-1`` is treated as "unlimited" so enterprise / grandfathered tenants
  bypass the check.
- The active subscription is the most recent ``status == "active"`` row,
  matching the lookup in ``saas.get_current_subscription``. Tenants with
  no active subscription fall back to the ``free`` plan so a brand-new
  signup is not blocked.
- The check is intentionally fast (two ``COUNT(*)`` queries) and runs
  *before* any expensive work, so a denied user gets a 402 immediately.

Wiring:
- ``app/api/endpoints/documents.py`` -> ``POST /documents/matters/{matter_id}/documents``
- ``app/api/endpoints/analysis.py`` -> ``POST /analysis``
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.analysis_report import AnalysisReport
from app.models.document import Document
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.subscription import Plan, Subscription
from app.models.user import User

logger = logging.getLogger("lilian.plan_limits")

# Sentinel for "unlimited" stored limits (enterprise tier).
UNLIMITED = -1


@dataclass(frozen=True)
class _PlanLimit:
    plan_name: str
    documents_limit: int
    analyses_limit: int


def _resolve_plan_limit(db: Session, organization_id: int) -> _PlanLimit:
    """Return the active plan's limits for the org, falling back to ``free``.

    Resolution order:
      1. Most recent active subscription.
      2. Free plan row.
      3. Hard-coded default (10 / 10) — defensive only.
    """
    subscription: Optional[Subscription] = (
        db.query(Subscription)
        .filter(
            Subscription.organization_id == organization_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.id.desc())
        .first()
    )

    if subscription is not None:
        return _PlanLimit(
            plan_name=subscription.plan_name,
            documents_limit=subscription.documents_limit or 0,
            analyses_limit=subscription.analyses_limit or 0,
        )

    free_plan: Optional[Plan] = db.query(Plan).filter(Plan.name == "free").first()
    if free_plan is not None:
        return _PlanLimit(
            plan_name=free_plan.name,
            documents_limit=free_plan.documents_limit or 0,
            analyses_limit=free_plan.analyses_limit or 0,
        )

    return _PlanLimit(plan_name="free", documents_limit=10, analyses_limit=10)


def _count_documents(db: Session, organization_id: int) -> int:
    return (
        db.query(func.count(Document.id))
        .filter(Document.organization_id == organization_id)
        .scalar()
        or 0
    )


def _count_analyses(db: Session, organization_id: int) -> int:
    return (
        db.query(func.count(AnalysisReport.id))
        .filter(AnalysisReport.organization_id == organization_id)
        .scalar()
        or 0
    )


def _payment_required(resource: str, used: int, limit: int, plan: str) -> HTTPException:
    """Build a 402 with a structured detail and the relevant headers."""
    detail = (
        f"Has alcanzado el límite de {resource} de tu plan '{plan}' "
        f"({used}/{limit}). Sube de plan para continuar."
    )
    headers = {
        # RFC 8594 (not yet an RFC, but widely adopted draft) — clients
        # can use these to know what to bill/upgrade.
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Resource": resource,
    }
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=detail,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def enforce_document_limit(
    membership: OrganizationMember = Depends(require_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationMember:
    """Dependency: blocks POST /documents/matters/{id}/documents when the
    org has reached its plan's ``documents_limit``.

    Returns the membership so callers can keep using it after the check.
    """
    org_id = membership.organization_id
    limits = _resolve_plan_limit(db, org_id)

    if limits.documents_limit == UNLIMITED:
        return membership

    used = _count_documents(db, org_id)
    if used >= limits.documents_limit:
        logger.info(
            "document upload blocked: org=%s plan=%s used=%s limit=%s",
            org_id,
            limits.plan_name,
            used,
            limits.documents_limit,
        )
        raise _payment_required("documentos", used, limits.documents_limit, limits.plan_name)

    return membership


def enforce_analysis_limit(
    membership: OrganizationMember = Depends(require_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationMember:
    """Dependency: blocks POST /analysis when the org has reached its plan's
    ``analyses_limit``.

    Returns the membership so callers can keep using it after the check.
    """
    org_id = membership.organization_id
    limits = _resolve_plan_limit(db, org_id)

    if limits.analyses_limit == UNLIMITED:
        return membership

    used = _count_analyses(db, org_id)
    if used >= limits.analyses_limit:
        logger.info(
            "analysis blocked: org=%s plan=%s used=%s limit=%s",
            org_id,
            limits.plan_name,
            used,
            limits.analyses_limit,
        )
        raise _payment_required("análisis", used, limits.analyses_limit, limits.plan_name)

    return membership


# ---------------------------------------------------------------------------
# Convenience helpers (used by callers that need to know, not enforce)
# ---------------------------------------------------------------------------


def get_org_usage_snapshot(
    db: Session, organization_id: int
) -> dict[str, int | str]:
    """Return a dict of current usage vs limits — useful for the billing
    page and for analytics dashboards. Never raises."""
    limits = _resolve_plan_limit(db, organization_id)
    documents_used = _count_documents(db, organization_id)
    analyses_used = _count_analyses(db, organization_id)
    return {
        "plan_name": limits.plan_name,
        "documents_used": documents_used,
        "documents_limit": limits.documents_limit,
        "analyses_used": analyses_used,
        "analyses_limit": limits.analyses_limit,
    }
