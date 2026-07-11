from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import json

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.user import User
from app.models.organization_member import OrganizationMember, MemberRole
from app.models.matter import Matter
from app.api.deps.auth import get_current_user, require_organization

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditLogResponse(BaseModel):
    id: int
    organization_id: Optional[int]
    user_id: Optional[int]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[int]
    ip_address: Optional[str]
    metadata: Optional[dict]
    created_at: str

    class Config:
        from_attributes = True


class OrganizationAdminResponse(BaseModel):
    id: int
    name: str
    type: str
    status: str
    plan_id: Optional[str]
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


@router.get("/audit-logs", response_model=List[AuditLogResponse])
def list_audit_logs(
    action_filter: Optional[str] = None,
    entity_type: Optional[str] = None,
    days: int = 7,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Solo el owner puede ver logs de auditoría")

    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(AuditLog).filter(
        AuditLog.organization_id == membership.organization_id,
        AuditLog.created_at >= since
    )

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
            metadata=json.loads(log.log_metadata) if log.log_metadata else None,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]


@router.get("/organizations", response_model=List[OrganizationAdminResponse])
def list_all_organizations(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Solo el owner puede ver organizaciones")

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
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Solo el owner puede ver estadísticas")

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
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Solo el owner puede suspender organizaciones")

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
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role != MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Solo el owner puede activar organizaciones")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    from app.models.organization import OrganizationStatus
    org.status = OrganizationStatus.ACTIVE
    db.commit()

    return {"message": "Organización activada", "org_id": org_id}
