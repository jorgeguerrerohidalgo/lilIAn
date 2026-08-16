
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import SessionLocal, get_db
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


@router.post("/message/stream")
async def send_message_stream(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Stream the assistant response as Server-Sent Events.

    Wire format (text/event-stream):

        data: {"type":"start","session_id":42}
        data: {"type":"delta","content":"..."}   # repeated as tokens arrive
        data: {"type":"done","message_id":123,"content":"<full text>"}

    The user message is persisted synchronously before the stream starts.
    The assistant message is persisted at the end via a fresh DB session
    so the streaming generator does not hold a long-lived ORM session.
    """
    import logging
    logger = logging.getLogger(__name__)

    def prep() -> tuple[int, str | None, LegalArea | None, int]:
        sync_db = SessionLocal()
        try:
            session = _load_chat_session(
                sync_db, request.session_id, membership.organization_id
            )
            matter = _load_matter_for_session(
                sync_db, session, membership.organization_id
            )
            matter_type = _resolve_matter_type(matter)
            legal_area_override = _parse_legal_area_override(
                request.legal_area_override
            )
            chat_service.save_chat_message(
                session_id=request.session_id,
                role="user",
                content=request.message,
            )
            try:
                from app.services.audit import AuditLogger
                AuditLogger(
                    db=sync_db,
                    user_id=current_user.id,
                    organization_id=membership.organization_id,
                ).log_chat_message(
                    session_id=request.session_id,
                    message_id=0,
                    role="user",
                    content_preview=request.message,
                )
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("audit_log_chat_user_failed: %s", exc)
            return (
                session.matter_id,
                matter_type,
                legal_area_override,
                membership.organization_id,
            )
        finally:
            sync_db.close()

    matter_id, matter_type, legal_area_override, organization_id = await run_in_threadpool(prep)

    async def event_generator():
        from app.services.llm import get_llm_provider

        yield f"data: {json.dumps({'type': 'start', 'session_id': request.session_id})}\n\n"

        def build_prompts() -> tuple[str, str | None, str]:
            from app.models.legal_area import MATTER_TYPE_TO_LEGAL_AREA, LegalArea

            if legal_area_override is not None:
                legal_area = legal_area_override
            elif matter_type:
                legal_area = MATTER_TYPE_TO_LEGAL_AREA.get(
                    matter_type.lower(), LegalArea.OTHER
                )
            else:
                legal_area = None

            context = chat_service.get_relevant_context(
                matter_id, organization_id, request.message,
                top_k=5, legal_area=legal_area,
            )
            base_system_prompt = chat_service.get_chat_system_prompt(
                matter_type, context, request.message, legal_area=legal_area
            )

            memory_block = ""
            try:
                from app.services import memory as memory_service
                mem_db = SessionLocal()
                try:
                    memory_block = memory_service.inject_into_prompt(
                        mem_db,
                        organization_id=organization_id,
                        user_id=current_user.id,
                        matter_id=matter_id,
                    )
                finally:
                    mem_db.close()
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("memory.inject_into_prompt (stream) failed: %s", exc)

            system_prompt = (
                f"{memory_block}\n\n{base_system_prompt}" if memory_block else base_system_prompt
            )

            history = chat_service.get_chat_history(request.session_id, limit=5)
            conversation = "\n".join(
                f"{msg['role'].upper()}: {msg['content']}" for msg in history
            )
            full_prompt = (
                f"Conversación anterior:\n{conversation}\n\n"
                f"Nueva pregunta del usuario: {request.message}\n\n"
                "Responde basándote únicamente en el contexto proporcionado arriba."
            )
            return full_prompt, system_prompt, legal_area.value if legal_area else ""

        full_prompt, system_prompt, legal_area_value = await run_in_threadpool(build_prompts)

        provider = get_llm_provider()
        full_content_parts: list[str] = []
        try:
            async for chunk in provider.generate_stream(
                prompt=full_prompt,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.5,
            ):
                if not chunk:
                    continue
                full_content_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"
        except Exception as exc:
            logger.exception("streaming LLM failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            return

        full_content = "".join(full_content_parts)

        def persist_assistant() -> int:
            saved = chat_service.save_chat_message(
                session_id=request.session_id,
                role="assistant",
                content=full_content,
                metadata={"streamed": True, "legal_area": legal_area_value},
            )
            try:
                from app.services.audit import AuditLogger
                sync_db = SessionLocal()
                try:
                    AuditLogger(
                        db=sync_db,
                        user_id=current_user.id,
                        organization_id=organization_id,
                    ).log_chat_message(
                        session_id=request.session_id,
                        message_id=saved["id"],
                        role="assistant",
                        content_preview=full_content,
                    )
                finally:
                    sync_db.close()
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("audit_log_chat_assistant_failed: %s", exc)
            return int(saved["id"])

        message_id = await run_in_threadpool(persist_assistant)
        yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'content': full_content})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx, Railway)
        },
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


