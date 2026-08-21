
from datetime import datetime, timedelta
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.invitation import Invitation, InvitationStatus
from app.models.organization import Organization
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationResponse])
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
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    # S1-12: a VIEWER/CLIENT must not see other members' email addresses.
    # OWNER/ADMIN see everyone; everyone else sees only themselves.
    is_privileged = membership.role in {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.PLATFORM_ADMIN}

    query = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == membership.organization_id
    )
    if not is_privileged:
        query = query.filter(OrganizationMember.user_id == current_user.id)

    members = query.all()

    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user is None:
            continue
        user_payload = {
            "id": user.id,
            "full_name": user.full_name,
            "status": user.status.value if hasattr(user.status, 'value') else user.status,
        }
        # Email is sensitive — only include it for privileged roles.
        if is_privileged:
            user_payload["email"] = user.email
        result.append({
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role.value,
            "user": user_payload,
        })

    return result


# ---------------------------------------------------------------------------
# S6.3 — invitations
# ---------------------------------------------------------------------------

# Roles we surface in the invite modal. Maps to ``MemberRole`` values.
INVITE_ALLOWED_ROLES = {
    MemberRole.LAWYER,
    MemberRole.ADMIN,
    MemberRole.COMPANY_USER,
    MemberRole.VIEWER,
}


class InvitationCreateRequest(BaseModel):
    """Body for ``POST /organizations/me/invitations``."""

    email: EmailStr
    role: MemberRole = MemberRole.LAWYER

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: MemberRole) -> MemberRole:
        # Pydantic v1 / v2 compatible: ``field_validator`` is the v2 name,
        # ``validator`` is the v1 name. The user's env decides which one
        # we get at runtime — see ``schemas/user.py`` for the same trick.
        if value not in INVITE_ALLOWED_ROLES:
            raise ValueError("Rol no permitido")
        return value


class InvitationResponse(BaseModel):
    id: int
    email: str
    role: str
    status: str
    created_at: str
    expires_at: str
    accept_url: str

    class Config:
        from_attributes = True


def _invite_accept_url(token: str) -> str:
    """Build the absolute accept URL embedded in the invite email."""
    import os

    base = os.getenv(
        "FRONTEND_BASE_URL",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app",
    )
    return f"{base}/invitations/accept?token={token}"


@router.post("/me/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    payload: InvitationCreateRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """S6.3 — invite a colleague to join the current organization.

    The owner/admin can send a single-use invitation link by email. The
    link routes through ``/invitations/accept?token=…`` which the
    frontend will use to call ``POST /organizations/invitations/accept``
    and convert the record into a real ``OrganizationMember`` row.
    """
    # De-dup: if there's already a pending invite for this email, reuse it.
    now = datetime.utcnow()
    existing = (
        db.query(Invitation)
        .filter(
            Invitation.organization_id == membership.organization_id,
            Invitation.email == payload.email.lower(),
            Invitation.status == InvitationStatus.PENDING,
            Invitation.expires_at > now,
        )
        .order_by(Invitation.created_at.desc())
        .first()
    )

    if existing is not None:
        return InvitationResponse(
            id=existing.id,
            email=existing.email,
            role=existing.role,
            status=existing.status.value if hasattr(existing.status, "value") else str(existing.status),
            created_at=existing.created_at.isoformat(),
            expires_at=existing.expires_at.isoformat(),
            accept_url=_invite_accept_url(existing.token),
        )

    token = secrets.token_urlsafe(32)
    invite = Invitation(
        organization_id=membership.organization_id,
        invited_by_user_id=current_user.id,
        email=payload.email.lower(),
        role=payload.role.value if hasattr(payload.role, "value") else str(payload.role),
        token=token,
        status=InvitationStatus.PENDING,
        expires_at=now + timedelta(days=14),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    # Fire-and-forget email — the user gets the toast immediately; if
    # Resend is down we still return success so the UX isn't blocked.
    try:
        from app.services.email import send_email

        inviter = current_user.full_name or "un miembro"
        org_name = (
            db.query(Organization)
            .filter(Organization.id == membership.organization_id)
            .first()
        )
        org_label = org_name.name if org_name else "tu organización"
        accept_url = _invite_accept_url(token)
        send_email(
            to=payload.email,
            template="invitation_received",
            data={
                "full_name": payload.email.split("@")[0],
                "inviter_name": inviter,
                "organization_name": org_label,
                "role": payload.role.value if hasattr(payload.role, "value") else str(payload.role),
                "accept_url": accept_url,
            },
            allow_stub=True,
        )
    except Exception:  # pragma: no cover - email is best-effort
        pass

    return InvitationResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        status=invite.status.value if hasattr(invite.status, "value") else str(invite.status),
        created_at=invite.created_at.isoformat(),
        expires_at=invite.expires_at.isoformat(),
        accept_url=_invite_accept_url(invite.token),
    )


@router.get("/me/invitations", response_model=list[InvitationResponse])
def list_invitations(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """List pending + recent invitations for the current organization."""
    rows = (
        db.query(Invitation)
        .filter(Invitation.organization_id == membership.organization_id)
        .order_by(Invitation.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        InvitationResponse(
            id=row.id,
            email=row.email,
            role=row.role,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            created_at=row.created_at.isoformat(),
            expires_at=row.expires_at.isoformat(),
            accept_url=_invite_accept_url(row.token),
        )
        for row in rows
    ]
