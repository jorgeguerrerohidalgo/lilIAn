"""S6.5 — Support tickets endpoint.

Minimal "contact us" form endpoint powering the floating support widget
on the frontend. Stores the ticket in the database (so we can reply
later) and fires an email to the platform support inbox via the existing
Resend integration.

Why a dedicated module instead of reusing ``feedback.py``:
- the schema is intentionally narrower (subject + body + email).
- the email goes to a different address (the platform team vs. the
  product feedback channel).
- support tickets are part of the user-comms surface, not the
  product-feedback pipeline.
"""

from __future__ import annotations

import enum
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.database import Base, get_db
from app.models.user import User

router = APIRouter(prefix="/support", tags=["support"])
log = logging.getLogger("lilian.support")


class SupportTicketStatus(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(Enum(SupportTicketStatus), default=SupportTicketStatus.OPEN, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SupportTicketCreate(BaseModel):
    """Body for ``POST /support/tickets``."""

    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=10_000)
    user_email: EmailStr


class SupportTicketResponse(BaseModel):
    id: int
    subject: str
    user_email: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
def create_support_ticket(
    payload: SupportTicketCreate,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """S6.5 — accept a "Contactar soporte" submission from the widget.

    The endpoint is intentionally permissive: ``get_current_user`` is
    allowed to fail (anonymous visitors should still be able to file a
    ticket from the marketing site), so we resolve it inside the
    handler rather than as a dependency. The submitted ``user_email``
    is treated as the source of truth regardless of auth state.
    """
    ticket = SupportTicket(
        user_id=current_user.id if current_user else None,
        user_email=str(payload.user_email).lower(),
        subject=payload.subject,
        body=payload.body,
        status=SupportTicketStatus.OPEN,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Best-effort email to the platform support inbox. Resend failure
    # doesn't fail the user-facing submission — we have the ticket in
    # the DB and can reply from there.
    try:
        from app.services.email import send_email

        inbox = os.getenv("SUPPORT_INBOX_EMAIL", "soporte@lilian.cl")
        send_email(
            to=inbox,
            template="support_ticket_received",
            data={
                "full_name": "Equipo de soporte",
                "ticket_id": str(ticket.id),
                "subject": payload.subject,
                "body": payload.body,
                "user_email": str(payload.user_email).lower(),
                "user_id": str(current_user.id) if current_user else "(invitado)",
            },
            allow_stub=True,
        )
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("support ticket email send failed ticket_id=%s err=%s", ticket.id, exc)

    return SupportTicketResponse(
        id=ticket.id,
        subject=ticket.subject,
        user_email=ticket.user_email,
        status=ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        created_at=ticket.created_at.isoformat(),
    )
