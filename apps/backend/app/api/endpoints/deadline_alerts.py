"""
Deadline Alerts API Endpoints
"""
from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps.auth import get_current_user, require_organization
from app.models.user import User
from app.models.organization_member import OrganizationMember
from app.models.deadline_alert import DeadlineAlert
from app.models.matter import Matter
from app.schemas.deadline_alert import (
    DeadlineAlertResponse,
    DeadlineAlertUpdate,
    AlertsSummary,
)

router = APIRouter(prefix="/alerts", tags=["deadline-alerts"])


def alert_to_response(alert: DeadlineAlert) -> dict:
    """Convert alert to response dict with matter title."""
    return {
        "id": alert.id,
        "organization_id": alert.organization_id,
        "matter_id": alert.matter_id,
        "document_id": alert.document_id,
        "user_id": alert.user_id,
        "title": alert.title,
        "description": alert.description,
        "event_type": alert.event_type,
        "due_date": alert.due_date,
        "days_remaining": alert.days_remaining,
        "is_overdue": alert.is_overdue,
        "urgency": alert.urgency,
        "importance_score": alert.importance_score,
        "status": alert.status,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "acknowledged_by": alert.acknowledged_by,
        "resolved_by": alert.resolved_by,
        "source_event": alert.source_event,
        "legal_reference": alert.legal_reference,
        "consequence": alert.consequence,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
        "matter_title": alert.matter.title if alert.matter else None,
    }


@router.get("/", response_model=List[dict])
def list_alerts(
    status: Optional[str] = Query(None, description="Filter by status"),
    urgency: Optional[str] = Query(None, description="Filter by urgency"),
    overdue: Optional[bool] = Query(None, description="Filter overdue only"),
    matter_id: Optional[int] = Query(None, description="Filter by matter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """List deadline alerts for the user's organization."""
    query = db.query(DeadlineAlert).filter(
        DeadlineAlert.organization_id == membership.organization_id
    )

    if status:
        query = query.filter(DeadlineAlert.status == status)
    if urgency:
        query = query.filter(DeadlineAlert.urgency == urgency)
    if overdue is not None:
        query = query.filter(DeadlineAlert.is_overdue == overdue)
    if matter_id:
        query = query.filter(DeadlineAlert.matter_id == matter_id)

    alerts = query.order_by(
        DeadlineAlert.due_date.asc()
    ).offset(offset).limit(limit).all()

    return [alert_to_response(a) for a in alerts]


@router.get("/summary", response_model=AlertsSummary)
def get_alerts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Get summary of alerts for dashboard."""
    org_id = membership.organization_id

    total = db.query(DeadlineAlert).filter(
        DeadlineAlert.organization_id == org_id
    ).count()

    overdue = db.query(DeadlineAlert).filter(
        DeadlineAlert.organization_id == org_id,
        DeadlineAlert.is_overdue == True
    ).count()

    critical = db.query(DeadlineAlert).filter(
        DeadlineAlert.organization_id == org_id,
        DeadlineAlert.urgency == "critical",
        DeadlineAlert.status.in_(["pending", "acknowledged"])
    ).count()

    high = db.query(DeadlineAlert).filter(
        DeadlineAlert.organization_id == org_id,
        DeadlineAlert.urgency == "high",
        DeadlineAlert.status.in_(["pending", "acknowledged"])
    ).count()

    medium = db.query(DeadlineAlert).filter(
        DeadlineAlert.organization_id == org_id,
        DeadlineAlert.urgency == "medium",
        DeadlineAlert.status.in_(["pending", "acknowledged"])
    ).count()

    low = db.query(DeadlineAlert).filter(
        DeadlineAlert.organization_id == org_id,
        DeadlineAlert.urgency == "low",
        DeadlineAlert.status.in_(["pending", "acknowledged"])
    ).count()

    # Alerts by matter
    matters = db.query(
        DeadlineAlert.matter_id,
        Matter.title,
    ).join(Matter).filter(
        DeadlineAlert.organization_id == org_id,
        DeadlineAlert.status.in_(["pending", "acknowledged"])
    ).group_by(
        DeadlineAlert.matter_id, Matter.title
    ).all()

    by_matter = [
        {"matter_id": m.matter_id, "matter_title": m.title, "count": db.query(DeadlineAlert).filter(
            DeadlineAlert.matter_id == m.matter_id,
            DeadlineAlert.status.in_(["pending", "acknowledged"])
        ).count()}
        for m in matters
    ]

    return AlertsSummary(
        total=total,
        overdue=overdue,
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        by_matter=by_matter,
    )


@router.get("/matters/{matter_id}", response_model=List[dict])
def get_matter_alerts(
    matter_id: int,
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Get alerts for a specific matter."""
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    query = db.query(DeadlineAlert).filter(
        DeadlineAlert.matter_id == matter_id
    )

    if status:
        query = query.filter(DeadlineAlert.status == status)
    if urgency:
        query = query.filter(DeadlineAlert.urgency == urgency)

    alerts = query.order_by(DeadlineAlert.due_date.asc()).all()
    return [alert_to_response(a) for a in alerts]


@router.get("/{alert_id}", response_model=dict)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Get a specific alert."""
    alert = db.query(DeadlineAlert).filter(
        DeadlineAlert.id == alert_id,
        DeadlineAlert.organization_id == membership.organization_id
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert_to_response(alert)


@router.patch("/{alert_id}", response_model=dict)
def update_alert(
    alert_id: int,
    update: DeadlineAlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Update alert status (acknowledge, resolve, dismiss)."""
    alert = db.query(DeadlineAlert).filter(
        DeadlineAlert.id == alert_id,
        DeadlineAlert.organization_id == membership.organization_id
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if update.status:
        alert.status = update.status

        if update.status == "acknowledged":
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = current_user.id
        elif update.status == "resolved":
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = current_user.id

    db.commit()
    db.refresh(alert)

    return alert_to_response(alert)


@router.post("/matter/{matter_id}/refresh", response_model=dict)
def refresh_matter_alerts(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Recalculate overdue status for all alerts in a matter."""
    from app.services.deadline_generator import update_overdue_status

    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    count = update_overdue_status(matter_id, membership.organization_id)


    return {"updated": count}
