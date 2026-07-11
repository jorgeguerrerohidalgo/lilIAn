from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import json

from app.core.database import get_db
from app.models.subscription import Subscription, UsageEvent, Plan
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember, MemberRole
from app.models.document import Document
from app.models.analysis_report import AnalysisReport
from app.models.matter import Matter
from app.models.user import User
from app.api.deps.auth import get_current_user, require_organization

router = APIRouter(prefix="/saas", tags=["saas"])


class PlanResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    documents_limit: int
    analyses_limit: int
    users_limit: int
    monthly_price: int

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: int
    plan_name: str
    status: str
    documents_limit: int
    analyses_limit: int
    users_limit: int
    monthly_price: int
    started_at: str
    renews_at: Optional[str]
    documents_used: int
    analyses_used: int
    users_used: int

    class Config:
        from_attributes = True


class OrganizationMetrics(BaseModel):
    total_matters: int
    total_documents: int
    total_analyses: int
    total_users: int
    matters_by_status: dict
    matters_by_type: dict
    documents_this_month: int
    analyses_this_month: int


@router.get("/plans", response_model=List[PlanResponse])
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).filter(Plan.is_active == True).order_by(Plan.monthly_price).all()
    return plans


@router.get("/subscription", response_model=Optional[SubscriptionResponse])
def get_current_subscription(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    subscription = db.query(Subscription).filter(
        Subscription.organization_id == membership.organization_id,
        Subscription.status == "active"
    ).order_by(Subscription.id.desc()).first()

    if not subscription:
        return None

    documents_used = db.query(func.count(Document.id)).filter(
        Document.organization_id == membership.organization_id
    ).scalar() or 0

    analyses_used = db.query(func.count(AnalysisReport.id)).filter(
        AnalysisReport.organization_id == membership.organization_id
    ).scalar() or 0

    users_used = db.query(func.count(OrganizationMember.id)).filter(
        OrganizationMember.organization_id == membership.organization_id
    ).scalar() or 0

    return SubscriptionResponse(
        id=subscription.id,
        plan_name=subscription.plan_name,
        status=subscription.status,
        documents_limit=subscription.documents_limit,
        analyses_limit=subscription.analyses_limit,
        users_limit=subscription.users_limit,
        monthly_price=subscription.monthly_price,
        started_at=subscription.started_at.isoformat(),
        renews_at=subscription.renews_at.isoformat() if subscription.renews_at else None,
        documents_used=documents_used,
        analyses_used=analyses_used,
        users_used=users_used
    )


@router.post("/subscription")
def create_subscription(
    plan_name: str,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role not in [MemberRole.OWNER, MemberRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Solo el dueño o admin puede modificar el plan")

    plan = db.query(Plan).filter(Plan.name == plan_name, Plan.is_active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    existing = db.query(Subscription).filter(
        Subscription.organization_id == membership.organization_id,
        Subscription.status == "active"
    ).first()

    if existing:
        existing.status = "cancelled"
        existing.cancelled_at = datetime.utcnow()

    new_sub = Subscription(
        organization_id=membership.organization_id,
        plan_name=plan.name,
        status="active",
        documents_limit=plan.documents_limit,
        analyses_limit=plan.analyses_limit,
        users_limit=plan.users_limit,
        monthly_price=plan.monthly_price,
        started_at=datetime.utcnow(),
        renews_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)

    org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
    if org:
        org.plan_id = plan.name
        db.commit()

    return {"message": "Suscripción creada", "plan": plan.name}


@router.get("/metrics", response_model=OrganizationMetrics)
def get_organization_metrics(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    total_matters = db.query(func.count(Matter.id)).filter(
        Matter.organization_id == membership.organization_id
    ).scalar() or 0

    total_documents = db.query(func.count(Document.id)).filter(
        Document.organization_id == membership.organization_id
    ).scalar() or 0

    total_analyses = db.query(func.count(AnalysisReport.id)).filter(
        AnalysisReport.organization_id == membership.organization_id
    ).scalar() or 0

    total_users = db.query(func.count(OrganizationMember.id)).filter(
        OrganizationMember.organization_id == membership.organization_id
    ).scalar() or 0

    matters_status = db.query(Matter.status, func.count(Matter.id)).filter(
        Matter.organization_id == membership.organization_id
    ).group_by(Matter.status).all()
    matters_by_status = {m.value if hasattr(m, 'value') else m: count for m, count in matters_status}

    matters_types = db.query(Matter.matter_type, func.count(Matter.id)).filter(
        Matter.organization_id == membership.organization_id
    ).group_by(Matter.matter_type).all()
    matters_by_type = {m.value if hasattr(m, 'value') else m: count for m, count in matters_types}

    month_ago = datetime.utcnow() - timedelta(days=30)
    documents_this_month = db.query(func.count(Document.id)).filter(
        Document.organization_id == membership.organization_id,
        Document.created_at >= month_ago
    ).scalar() or 0

    analyses_this_month = db.query(func.count(AnalysisReport.id)).filter(
        AnalysisReport.organization_id == membership.organization_id,
        AnalysisReport.created_at >= month_ago
    ).scalar() or 0

    return OrganizationMetrics(
        total_matters=total_matters,
        total_documents=total_documents,
        total_analyses=total_analyses,
        total_users=total_users,
        matters_by_status=matters_by_status,
        matters_by_type=matters_by_type,
        documents_this_month=documents_this_month,
        analyses_this_month=analyses_this_month
    )


@router.get("/usage/events")
def get_usage_events(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)

    events = db.query(UsageEvent).filter(
        UsageEvent.organization_id == membership.organization_id,
        UsageEvent.created_at >= since
    ).order_by(UsageEvent.created_at.desc()).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "quantity": e.quantity,
            "user_id": e.user_id,
            "metadata": json.loads(e.event_metadata) if e.event_metadata else None,
            "created_at": e.created_at.isoformat()
        }
        for e in events
    ]


def record_usage_event(
    organization_id: int,
    user_id: int,
    event_type: str,
    quantity: int = 1,
    metadata: dict = None,
    db: Session = None
):
    if db is None:
        db = next(get_db().__iter__().__next__())

    event = UsageEvent(
        organization_id=organization_id,
        user_id=user_id,
        event_type=event_type,
        quantity=quantity,
        event_metadata=json.dumps(metadata) if metadata else None
    )
    db.add(event)
    db.commit()
