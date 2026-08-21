"""S6.3 — organization invitation model.

A pending invitation is a record that maps ``(organization_id, email,
role, token)``. When the recipient clicks the link in the email, the
frontend POSTs the token to ``/api/v1/organizations/invitations/accept``
and we convert the record into a real ``OrganizationMember`` row.

Why not just invite via email link? Same as every other SaaS: we want
the recipient to land on a verified signup/sign-in flow that ties the
new account to the inviting organization, not auto-create a half-broken
account from the email address alone.

The token is opaque, single-use, and short-lived (14 days). The record
is purged (or marked ``accepted_at``) once consumed.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class InvitationStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    invited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="LAWYER")
    token = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(Enum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="invitations")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])
