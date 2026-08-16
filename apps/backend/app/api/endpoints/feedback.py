"""Feedback endpoint: records thumbs up/down on assistant chat messages and
optionally promotes a correction into a persistent user_facts entry.

This is the only path through which user_facts get populated from the UI.
Without this endpoint, user_facts stays empty and the memory block injected
into every chat prompt is wasted space.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.chat import ChatMessage
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services import memory as memory_service_module

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    chat_message_id: int = Field(ge=1)
    rating: int = Field(ge=-1, le=1)
    correction: str | None = Field(default=None, max_length=2_000)
    extracted_fact: str | None = Field(default=None, max_length=500)
    extracted_kind: str = Field(default="preference", max_length=64)


class FeedbackResponse(BaseModel):
    id: int
    promoted_to_user_facts: bool


@router.post("", response_model=FeedbackResponse)
def post_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Record a feedback signal on an assistant message. Defense in depth:
    we re-check that the chat message belongs to the caller's org even
    though the chat_message_id is opaque enough that the check is mostly
    paranoid. The cost is one indexed query and the win is rejecting
    cross-tenant feedback."""
    msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == request.chat_message_id)
        .first()
    )
    if msg is None:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Solo se puede dar feedback a mensajes del asistente")

    # The chat_message row doesn't carry organization_id directly; we go
    # through chat_session. This is the same lookup S2-03 hardened for
    # the chat endpoint.
    from app.models.chat import ChatSession

    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == msg.chat_session_id)
        .first()
    )
    if session is None or session.organization_id != membership.organization_id:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado en esta organización")

    promoted = bool(request.extracted_fact)

    signal = memory_service_module.record_feedback(
        db,
        organization_id=membership.organization_id,
        chat_message_id=request.chat_message_id,
        user_id=current_user.id,
        rating=request.rating,
        correction=request.correction,
        extracted_fact=request.extracted_fact,
        extracted_kind=request.extracted_kind,
    )

    return FeedbackResponse(
        id=signal.id,
        promoted_to_user_facts=promoted,
    )