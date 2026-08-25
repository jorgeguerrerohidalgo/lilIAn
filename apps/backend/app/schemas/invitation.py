"""S6.3 — invitation schemas (Phase 0 of multi-tenant work).

Lives at app/schemas/invitation.py to keep accept-invitation and
the existing in-router InvitationRequest/InvitationResponse
separate. New endpoints import from here; the in-router classes
stay as-is to avoid touching every caller.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class InvitationAcceptRequest(BaseModel):
    """Body for ``POST /organizations/invitations/accept``."""

    token: str = Field(min_length=1, max_length=128)


class InvitationAcceptResponse(BaseModel):
    """Returned after a successful (or idempotent) accept.

    The frontend uses ``requires_verification`` to decide whether to
    send the user through ``/auth/verify-email`` or straight to
    ``/dashboard``. ``email_already_registered`` lets the UI skip the
    password-setup step on its registration form when the email
    already maps to an existing user.
    """

    invitation_id: int
    organization_id: int
    organization_name: str
    role: str
    user_id: int
    email: str
    email_already_registered: bool
    requires_verification: bool
