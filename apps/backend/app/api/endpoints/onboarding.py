"""Onboarding endpoints (S4.2).

The sample-data seed is normally triggered by the Stripe checkout
webhook (see ``_handle_checkout_completed`` in ``saas.py``). The
endpoints here are the manual escape hatches:

- ``POST /onboarding/sample-data``: re-seed if the tenant has no
  matters yet. Useful for tenants who skipped Stripe (early-access
  invites) or who just want to refresh the demo state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.deps.tenant import get_tenant_context
from app.core.database import get_db
from app.models.user import User
from app.services.seed import seed_demo_data

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class SampleDataResponse(BaseModel):
    created: bool
    reason: str
    matters: int
    documents: int
    reports: int


@router.post("/sample-data", response_model=SampleDataResponse)
def post_sample_data(
    db: Session = Depends(get_db),
    tenant_ctx=Depends(get_tenant_context),
    current_user: User = Depends(get_current_user),
) -> SampleDataResponse:
    """Seed demo matters + documents for the current tenant.

    Idempotent: a tenant that already has the seed marker in any
    matter description will get ``created=False``. Free-plan tenants
    are skipped (mirrors the Stripe webhook behaviour).
    """
    result = seed_demo_data(db, tenant_ctx.organization_id, user_id=current_user.id)
    return SampleDataResponse(**result)
