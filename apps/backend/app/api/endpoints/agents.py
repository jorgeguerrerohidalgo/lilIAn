"""Agents endpoint: execute one of the registered Harvey-grade agents on a
matter or document, persist the run + steps, return the result.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import SessionLocal, get_db
from app.models.document import Document
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services import agents as agents_service

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentRunRequest(BaseModel):
    agent_kind: str = Field(min_length=1, max_length=64)
    matter_id: int | None = None
    document_id: int | None = None
    input: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    id: int
    agent_kind: str
    status: str
    matter_id: int | None
    output: dict[str, Any]
    output_artifact_id: int | None
    output_artifact_kind: str | None
    total_tokens: int
    error_message: str | None
    started_at: str
    completed_at: str | None


class AgentListResponse(BaseModel):
    agents: list[dict[str, str]]


@router.get("", response_model=AgentListResponse)
def list_agents(
    current_user: User = Depends(get_current_user),
):
    """List available agent kinds + labels for the UI dropdown."""
    return AgentListResponse(agents=agents_service.list_agents())


@router.post("/run", response_model=AgentRunResponse)
def run_agent_endpoint(
    request: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Execute an agent end-to-end and return the persisted run."""
    if agents_service.get_agent(request.agent_kind) is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown agent_kind: {request.agent_kind}",
        )

    organization_id = membership.organization_id
    matter_id = request.matter_id

    # Validate matter_id belongs to the org (defense in depth on top of
    # build_context's own checks).
    if matter_id is not None:
        ok = (
            db.query(Matter)
            .filter(Matter.id == matter_id, Matter.organization_id == organization_id)
            .first()
        )
        if ok is None:
            raise HTTPException(status_code=404, detail="Caso no encontrado en esta organización")

    document_text: str | None = None
    if request.document_id is not None:
        doc = (
            db.query(Document)
            .filter(Document.id == request.document_id, Document.organization_id == organization_id)
            .first()
        )
        if doc is None:
            raise HTTPException(status_code=404, detail="Documento no encontrado en esta organización")
        document_text = doc.extracted_text or ""

    context = agents_service.build_context(
        organization_id=organization_id,
        user_id=current_user.id,
        matter_id=matter_id,
        input=request.input,
    )
    if document_text is not None:
        context.document_text = document_text

    run = agents_service.run_agent(
        agent_kind=request.agent_kind,
        context=context,
        db=db,
    )

    return AgentRunResponse(
        id=run.id,
        agent_kind=run.agent_kind,
        status=run.status,
        matter_id=run.matter_id,
        output=run.output_json or {},
        output_artifact_id=run.output_artifact_id,
        output_artifact_kind=run.output_artifact_kind,
        total_tokens=run.total_tokens,
        error_message=run.error_message,
        started_at=run.started_at.isoformat() if run.started_at else "",
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )