from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember, MemberRole
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.api.deps.auth import get_current_user, require_organization

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    memberships = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).all()

    org_ids = [m.organization_id for m in memberships]
    organizations = db.query(Organization).filter(Organization.id.in_(org_ids)).all()

    return organizations


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org = Organization(
        name=org_data.name,
        type=org_data.type,
        rut=org_data.rut,
        billing_email=org_data.billing_email,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role=MemberRole.OWNER
    )
    db.add(membership)
    db.commit()

    return org


@router.get("/me", response_model=OrganizationResponse)
def get_my_organization(
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    return org


@router.get("/me/members")
def get_organization_members(
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == membership.organization_id
    ).all()

    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append({
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role.value,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status.value if hasattr(user.status, 'value') else user.status
            } if user else None
        })

    return result
