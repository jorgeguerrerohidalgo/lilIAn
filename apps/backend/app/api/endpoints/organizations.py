
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.invitation import Invitation, InvitationStatus
from app.models.organization import Organization
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services.audit import record_audit_log

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


# ---------------------------------------------------------------------------
# S6.3 — accept invitation (Phase 0 of multi-tenant work)
# ---------------------------------------------------------------------------
#
# Routes under ``/organizations/invitations/accept`` — NOT
# ``/organizations/me/invitations/accept`` — because the receiver may
# not be authenticated yet. The token alone authorizes the call.


@router.post("/invitations/accept")
def accept_invitation(
    payload: "app.schemas.invitation.InvitationAcceptRequest",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """S6.3 — consume a pending invitation token.

    Marks the row ``ACCEPTED`` and inserts (or upserts) an
    ``OrganizationMember`` row. Idempotent: replaying with the same
    token returns the same payload instead of erroring, so the
    frontend can safely retry on transient network failures.

    Cases:
      - Existing user (email already in ``users``) — just add the
        membership; user is already authenticated.
      - New user — we do **not** auto-create the account here. The
        user must register first (the invite email links to
        ``/auth/register?invite=<token>`` so we capture the token
        across the signup boundary) and re-call accept after
        authenticating. The frontend uses ``requires_verification``
        to decide whether to skip the verify-email step.

    Errors:
      - 404: token unknown.
      - 410: invitation is no longer pending (accepted/expired/revoked).
      - 400: invitation expired by date.
    """
    from app.schemas.invitation import InvitationAcceptRequest, InvitationAcceptResponse

    # Pydantic coercion — let FastAPI validate the payload shape.
    if not isinstance(payload, InvitationAcceptRequest):
        payload = InvitationAcceptRequest.model_validate(payload)

    token = payload.token
    now = datetime.utcnow()

    invite = (
        db.query(Invitation)
        .filter(Invitation.token == token)
        .first()
    )
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitación no encontrada",
        )

    # Idempotency: an already-accepted invitation returns the same
    # payload so the frontend can retry safely.
    if invite.status == InvitationStatus.ACCEPTED:
        org = (
            db.query(Organization)
            .filter(Organization.id == invite.organization_id)
            .first()
        )
        existing_member = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == invite.organization_id,
                OrganizationMember.user_id == current_user.id,
            )
            .first()
        )
        return InvitationAcceptResponse(
            invitation_id=invite.id,
            organization_id=invite.organization_id,
            organization_name=org.name if org else "",
            role=existing_member.role.value if existing_member and hasattr(existing_member.role, "value") else invite.role,
            user_id=current_user.id,
            email=current_user.email,
            email_already_registered=True,
            requires_verification=not current_user.email_verified,
        )

    if invite.status in {InvitationStatus.REVOKED, InvitationStatus.EXPIRED}:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Esta invitación ya no es válida",
        )

    if invite.expires_at < now:
        # Best-effort: flip status so subsequent calls don't repeat the
        # date math. Failure to update is non-fatal — we still raise.
        try:
            invite.status = InvitationStatus.EXPIRED
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La invitación ha expirado",
        )

    # Email match: only the person invited may accept. If the
    # authenticated email doesn't match the invite email, refuse —
    # this prevents a logged-in user from consuming someone else's
    # token.
    if current_user.email.lower() != invite.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta invitación fue enviada a otro correo",
        )

    # Upsert membership: if the user was already a member (e.g.
    # re-accept after role change), keep the existing role.
    existing_member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == invite.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if existing_member is None:
        member_role = (
            MemberRole(invite.role)
            if invite.role in {r.value for r in MemberRole}
            else MemberRole.LAWYER
        )
        member = OrganizationMember(
            organization_id=invite.organization_id,
            user_id=current_user.id,
            role=member_role,
        )
        db.add(member)
    else:
        # Optional: update the role to whatever the invite says.
        # Most SaaS treats re-accepting as "no-op for existing members".
        pass

    invite.status = InvitationStatus.ACCEPTED
    invite.accepted_at = now

    db.commit()

    org = (
        db.query(Organization)
        .filter(Organization.id == invite.organization_id)
        .first()
    )

    return InvitationAcceptResponse(
        invitation_id=invite.id,
        organization_id=invite.organization_id,
        organization_name=org.name if org else "",
        role=invite.role,
        user_id=current_user.id,
        email=current_user.email,
        email_already_registered=True,
        requires_verification=not current_user.email_verified,
    )


# ---------------------------------------------------------------------------
# Phase 1a — membership management (PATCH member, DELETE member, DELETE invitation)
# ---------------------------------------------------------------------------
#
# These three endpoints close the team-management loop so the OWNER/ADMIN
# can change roles, remove members, and revoke pending invites without
# dropping down to the DB. PLATFORM_ADMIN can do everything across any
# organization.

# Roles the PATCH endpoint is allowed to set (mirrors INVITE_ALLOWED_ROLES —
# PLATFORM_ADMIN can only be assigned via the dedicated admin endpoint).
PATCH_ALLOWED_ROLES = {
    MemberRole.LAWYER,
    MemberRole.ADMIN,
    MemberRole.COMPANY_USER,
    MemberRole.VIEWER,
}


class MemberRoleUpdateRequest(BaseModel):
    """Body for ``PATCH /organizations/me/members/{user_id}``."""

    role: MemberRole

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: MemberRole) -> MemberRole:
        if value not in PATCH_ALLOWED_ROLES:
            raise ValueError("Rol no permitido")
        return value


class MemberUserPayload(BaseModel):
    """Inner ``user`` block on member responses (omits sensitive fields)."""

    id: int
    full_name: str | None = None
    email: str | None = None


class MemberResponse(BaseModel):
    """Response for member endpoints.

    Same shape the list endpoint already returns so the frontend can reuse
    its existing row component after a PATCH.
    """

    id: int
    user_id: int
    role: str
    user: MemberUserPayload


def _serialize_member(member: OrganizationMember, user: User) -> MemberResponse:
    """Build a ``MemberResponse`` from a row + its user, matching the list endpoint."""
    user_payload = MemberUserPayload(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
    )
    role_value = (
        member.role.value if hasattr(member.role, "value") else str(member.role)
    )
    return MemberResponse(
        id=member.id,
        user_id=member.user_id,
        role=role_value,
        user=user_payload,
    )


@router.patch("/me/members/{user_id}", response_model=MemberResponse)
def update_member_role(
    user_id: int,
    payload: MemberRoleUpdateRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Phase 1a — change the role of an existing member.

    Authorization:
      * Caller must be ``OWNER``, ``ADMIN``, or ``PLATFORM_ADMIN``.
      * ``OWNER`` cannot promote or demote another ``OWNER`` (locks the
        other OWNER out of their own org and prevents accidental
        demotions). ``PLATFORM_ADMIN`` bypasses this — they can move
        ownership via support tooling.
      * ``OWNER`` cannot change their own role (self-demote protection).
      * ``PLATFORM_ADMIN`` cannot be assigned through this endpoint
        (enforced by ``PATCH_ALLOWED_ROLES``); that's an admin-only
        operation.

    Errors:
      - 403: caller is not OWNER/ADMIN/PLATFORM_ADMIN, or caller is
        OWNER targeting another OWNER / themselves.
      - 404: target ``user_id`` is not a member of the caller's
        organization.
    """
    caller_role = membership.role

    # Authorization gate.
    if caller_role not in {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.PLATFORM_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para cambiar roles en esta organización",
        )

    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == membership.organization_id,
        )
        .first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no es miembro de esta organización",
        )

    # OWNER self-modification lockout guard.
    if caller_role == MemberRole.OWNER and target.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes cambiar tu propio rol",
        )

    # OWNER-cannot-touch-other-OWNER guard. PLATFORM_ADMIN is exempt so
    # support tooling can rebalance ownership if an OWNER is locked out.
    if (
        caller_role == MemberRole.OWNER
        and target.role == MemberRole.OWNER
        and target.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar el rol de otro OWNER",
        )

    old_role_value = (
        target.role.value if hasattr(target.role, "value") else str(target.role)
    )
    new_role_value = (
        payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    )

    target.role = payload.role
    db.commit()
    db.refresh(target)

    target_user = db.query(User).filter(User.id == target.user_id).first()
    if target_user is None:
        # Should not happen — FK enforces it — but guard so the response
        # shape stays consistent.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario asociado al miembro no encontrado",
        )

    record_audit_log(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        action="member.role_changed",
        entity_type="organization_member",
        entity_id=target.id,
        metadata={
            "target_user_id": target.user_id,
            "old_role": old_role_value,
            "new_role": new_role_value,
        },
    )

    return _serialize_member(target, target_user)


@router.delete("/me/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Phase 1a — remove a member from the organization.

    Authorization:
      * Caller must be ``OWNER``, ``ADMIN``, or ``PLATFORM_ADMIN``.
      * ``OWNER`` cannot remove themselves (lockout guard — ownership
        transfer is out of scope for this phase).
      * ``ADMIN`` cannot remove an ``OWNER`` (only another ``OWNER`` or
        ``PLATFORM_ADMIN`` can remove an OWNER).

    Errors:
      - 403: caller lacks permission, self-removal by OWNER, or ADMIN
        removing an OWNER.
      - 404: target ``user_id`` is not a member of the caller's
        organization.

    Returns 204 on success.
    """
    caller_role = membership.role

    if caller_role not in {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.PLATFORM_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para remover miembros de esta organización",
        )

    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == membership.organization_id,
        )
        .first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no es miembro de esta organización",
        )

    # OWNER self-removal lockout guard.
    if caller_role == MemberRole.OWNER and target.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes removerte a ti mismo; transfiere la propiedad primero",
        )

    # ADMIN cannot remove an OWNER. PLATFORM_ADMIN and OWNERs can.
    if caller_role == MemberRole.ADMIN and target.role == MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un OWNER o PLATFORM_ADMIN puede remover a un OWNER",
        )

    old_role_value = (
        target.role.value if hasattr(target.role, "value") else str(target.role)
    )
    target_user_id = target.user_id
    target_id = target.id

    db.delete(target)
    db.commit()

    record_audit_log(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        action="member.removed",
        entity_type="organization_member",
        entity_id=target_id,
        metadata={
            "target_user_id": target_user_id,
            "removed_role": old_role_value,
        },
    )

    return None


@router.delete("/me/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Phase 1a — revoke a pending invitation.

    Authorization:
      * Caller must be ``OWNER``, ``ADMIN``, or ``PLATFORM_ADMIN``.
      * The invitation must belong to the caller's organization.
      * The invitation must currently be ``PENDING``. Accepted/expired/
        revoked invitations return 409 Conflict because the state
        transition is meaningless (and reusing a consumed invite is
        always a UX bug).

    Errors:
      - 403: caller lacks permission.
      - 404: invitation does not exist.
      - 409: invitation is no longer in PENDING status.

    Returns 204 on success.
    """
    caller_role = membership.role

    if caller_role not in {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.PLATFORM_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para revocar invitaciones",
        )

    invite = (
        db.query(Invitation)
        .filter(
            Invitation.id == invitation_id,
            Invitation.organization_id == membership.organization_id,
        )
        .first()
    )
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitación no encontrada",
        )

    if invite.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden revocar invitaciones pendientes",
        )

    invite.status = InvitationStatus.REVOKED
    db.commit()

    record_audit_log(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        action="invitation.revoked",
        entity_type="invitation",
        entity_id=invite.id,
        metadata={
            "invited_email": invite.email,
            "invited_role": invite.role,
        },
    )

    return None
