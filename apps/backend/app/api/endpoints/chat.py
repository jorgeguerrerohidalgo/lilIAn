from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.models.chat import ChatSession, ChatMessage
from app.models.matter import Matter
from app.models.legal_area import LegalArea
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.api.deps.auth import get_current_user, require_organization
from app.services import chat as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    matter_id: int
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    session_id: int
    message: str
    legal_area_override: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    matter_id: int
    title: Optional[str]
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


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_sessions(
    matter_id: Optional[int] = None,
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


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
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
    session = db.query(ChatSession).filter(
        ChatSession.id == request.session_id,
        ChatSession.organization_id == membership.organization_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    # Obtener matter_type del caso
    matter = db.query(Matter).filter(Matter.id == session.matter_id).first()
    matter_type = matter.matter_type.value if matter and matter.matter_type else None

    # Convertir legal_area_override de string a enum si viene
    legal_area_override = None
    if request.legal_area_override:
        try:
            legal_area_override = LegalArea(request.legal_area_override.lower())
        except ValueError:
            pass

    chat_service.save_chat_message(
        session_id=request.session_id,
        role="user",
        content=request.message
    )

    response_content, error = chat_service.generate_chat_response(
        session_id=request.session_id,
        matter_id=session.matter_id,
        organization_id=membership.organization_id,
        user_message=request.message,
        matter_type=matter_type,
        legal_area_override=legal_area_override
    )

    saved_message = chat_service.save_chat_message(
        session_id=request.session_id,
        role="assistant",
        content=response_content,
        metadata={"error": error} if error else None
    )

    return MessageResponse(
        content=response_content,
        session_id=request.session_id,
        message_id=saved_message["id"]
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
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

    db.delete(session)
    db.commit()
