
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.chat import ChatSession
from app.models.legal_area import LegalArea
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services import chat as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


# S3-06: cap user-supplied chat input to prevent DoS / abuse of LLM budget.
CHAT_MESSAGE_MAX_LEN = 4_000


class CreateSessionRequest(BaseModel):
    matter_id: int
    title: str | None = Field(default=None, max_length=200)


class SendMessageRequest(BaseModel):
    session_id: int
    message: str = Field(min_length=1, max_length=CHAT_MESSAGE_MAX_LEN)
    legal_area_override: str | None = Field(default=None, max_length=64)


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    model_provider: str | None = None
    model_name: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    matter_id: int
    title: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    content: str
    session_id: int
    message_id: int


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == request.matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    session = chat_service.create_chat_session(
        matter_id=request.matter_id,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        title=request.title
    )

    return ChatSessionResponse(
        id=session.id,
        matter_id=session.matter_id,
        title=session.title,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat()
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    matter_id: int | None = None,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    query = db.query(ChatSession).filter(
        ChatSession.organization_id == membership.organization_id
    )

    if matter_id:
        query = query.filter(ChatSession.matter_id == matter_id)

    sessions = query.order_by(ChatSession.updated_at.desc()).all()

    return [
        ChatSessionResponse(
            id=s.id,
            matter_id=s.matter_id,
            title=s.title,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat()
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.organization_id == membership.organization_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    messages = chat_service.get_session_messages(session_id)

    return [
        ChatMessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            model_provider=m.model_provider,
            model_name=m.model_name,
            created_at=m.created_at.isoformat()
        )
        for m in messages
    ]


@router.post("/message", response_model=MessageResponse)
def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Persist a user message, generate an LLM response, persist it,
    and emit audit rows for both turns.

    S4-19: previously a 92-line function that did its own DB lookups,
    audit-log calls, and persistence in one body. Refactored to delegate
    each step to a small helper so the top-level reads as a linear
    pipeline. Audit logging is best-effort: a failure to write an audit
    row never aborts the user-visible flow.
    """
    import logging
    logger = logging.getLogger(__name__)

    session = _load_chat_session(db, request.session_id, membership.organization_id)
    matter = _load_matter_for_session(db, session, membership.organization_id)
    matter_type = _resolve_matter_type(matter)
    legal_area_override = _parse_legal_area_override(request.legal_area_override)

    chat_service.save_chat_message(
        session_id=request.session_id,
        role="user",
        content=request.message,
    )
    _audit_user_message(db, current_user, membership, request, logger)

    response_content, error = chat_service.generate_chat_response(
        session_id=request.session_id,
        matter_id=session.matter_id,
        organization_id=membership.organization_id,
        user_message=request.message,
        matter_type=matter_type,
        legal_area_override=legal_area_override,
        user_id=current_user.id,
    )

    saved_message = chat_service.save_chat_message(
        session_id=request.session_id,
        role="assistant",
        content=response_content,
        metadata={"error": error} if error else None,
    )
    _audit_assistant_message(
        db, current_user, membership, request.session_id, saved_message, response_content, logger
    )

    return MessageResponse(
        content=response_content,
        session_id=request.session_id,
        message_id=saved_message["id"],
    )


# ---------------------------------------------------------------------------
# S4-19: send_message helpers
# ---------------------------------------------------------------------------
def _load_chat_session(db, session_id: int, organization_id: int) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.organization_id == organization_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return session


def _load_matter_for_session(db, session: ChatSession, organization_id: int):
    """Look up the matter for the session, scoped to the caller's org.

    S2-03: scoping by organization_id here prevents a dangling-FK
    exploit where a forged session_id could pull a Matter from another
    tenant via session.matter_id.
    """
    return (
        db.query(Matter)
        .filter(
            Matter.id == session.matter_id,
            Matter.organization_id == organization_id,
        )
        .first()
    )


def _resolve_matter_type(matter) -> str | None:
    if matter and matter.matter_type:
        return matter.matter_type.value
    return None


def _parse_legal_area_override(raw: str | None) -> LegalArea | None:
    if not raw:
        return None
    try:
        return LegalArea(raw.lower())
    except ValueError:
        return None


def _audit_user_message(
    db, current_user, membership, request, logger
) -> None:
    """Best-effort audit row for the user turn.

    S3-03: the audit table records a SHA-256 prefix instead of the raw
    text so it doesn't bloat with duplicates of every message.
    """
    from app.services.audit import AuditLogger
    try:
        AuditLogger(
            db=db,
            user_id=current_user.id,
            organization_id=membership.organization_id,
        ).log_chat_message(
            session_id=request.session_id,
            message_id=0,  # user message id is set after persistence
            role="user",
            content_preview=request.message,
        )
    except Exception as exc:
        logger.warning("audit_log_chat_user_failed: %s", exc)


def _audit_assistant_message(
    db, current_user, membership, session_id: int, saved_message: dict,
    response_content: str, logger,
) -> None:
    """Best-effort audit row for the assistant turn."""
    from app.services.audit import AuditLogger
    try:
        AuditLogger(
            db=db,
            user_id=current_user.id,
            organization_id=membership.organization_id,
        ).log_chat_message(
            session_id=session_id,
            message_id=saved_message.get("id", 0),
            role="assistant",
            content_preview=response_content or "",
        )
    except Exception as exc:
        logger.warning("audit_log_chat_assistant_failed: %s", exc)


