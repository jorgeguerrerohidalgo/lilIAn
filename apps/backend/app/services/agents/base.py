"""Agent runner base. Each agent is a callable that receives a pre-collected
AgentContext and returns an AgentResult. The runner persists the run + each
step to the database for audit and replay.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.agent import AgentRun, AgentStep
from app.services import memory as memory_service

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Everything the agent needs to do its work. Pre-collected by the
    endpoint (which has DB access), so the agent itself stays pure."""

    organization_id: int
    user_id: int
    matter_id: int | None
    input: dict[str, Any] = field(default_factory=dict)
    matter_summary: str | None = None
    document_text: str | None = None
    rag_chunks: list[dict[str, Any]] = field(default_factory=list)
    precedents: list[dict[str, Any]] = field(default_factory=list)
    memory_block: str | None = None


@dataclass
class AgentResult:
    """What the agent produces. `output` is an arbitrary JSON-serializable
    dict with the agent-specific schema (case summary, draft text, etc.).
    """

    output: dict[str, Any]
    artifact_id: int | None = None
    artifact_kind: str | None = None
    total_tokens: int = 0
    raw_response: str | None = None


AgentCallable = Callable[[AgentContext], AgentResult]


def run_agent(
    *,
    agent_kind: str,
    context: AgentContext,
    db: Session | None = None,
) -> AgentRun:
    """Run an agent end-to-end: persist the run, execute the agent, persist
    every step, mark the run succeeded/failed, return the AgentRun row."""
    own_db = db is None
    session = db or SessionLocal()
    try:
        agent = _resolve_agent(agent_kind)

        run = AgentRun(
            organization_id=context.organization_id,
            user_id=context.user_id,
            matter_id=context.matter_id,
            agent_kind=agent_kind,
            status="running",
            input_json=context.input,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        # Step 1: pre-collected context snapshot (for replay/audit).
        context_step = AgentStep(
            run_id=run.id,
            organization_id=context.organization_id,
            step_index=0,
            kind="tool_result",
            tool_name="context_collection",
            output_json={
                "matter_summary": context.matter_summary,
                "rag_chunks_count": len(context.rag_chunks),
                "precedents_count": len(context.precedents),
                "memory_block_present": bool(context.memory_block),
                "document_chars": len(context.document_text) if context.document_text else 0,
            },
            reasoning="Pre-collected context for agent run.",
        )
        session.add(context_step)
        session.commit()

        t0 = time.monotonic()
        try:
            result = agent(context)
        except Exception as exc:
            logger.exception("agent %s failed", agent_kind)
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.utcnow()
            run.total_tokens = 0
            session.commit()
            session.refresh(run)
            return run

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        run.total_tokens = result.total_tokens
        run.output_json = result.output
        run.output_artifact_id = result.artifact_id
        run.output_artifact_kind = result.artifact_kind
        run.status = "succeeded"
        run.completed_at = datetime.utcnow()
        session.commit()

        # Step 2: final answer with reasoning metadata.
        final_step = AgentStep(
            run_id=run.id,
            organization_id=context.organization_id,
            step_index=1,
            kind="final_answer",
            tool_name=agent_kind,
            input_json={"memory_block_chars": len(context.memory_block) if context.memory_block else 0},
            output_json=result.output,
            reasoning=result.raw_response[:2000] if result.raw_response else None,
            tokens_used=result.total_tokens,
            duration_ms=elapsed_ms,
        )
        session.add(final_step)
        session.commit()
        session.refresh(run)
        return run
    finally:
        if own_db:
            session.close()


def _resolve_agent(kind: str) -> AgentCallable:
    from app.services.agents import get_agent
    agent = get_agent(kind)
    if agent is None:
        raise ValueError(f"unknown agent kind: {kind}")
    return agent


def build_context(
    *,
    organization_id: int,
    user_id: int,
    matter_id: int | None,
    input: dict[str, Any] | None = None,
) -> AgentContext:
    """Pre-collect matter summary, RAG chunks, precedents, and memory block
    for an agent run. The endpoint calls this before invoking the agent
    so the agent only deals with a fully-formed context object."""
    from app.models.matter import Matter
    from app.services.chat import get_relevant_context
    from app.services.precedent_rag import get_precedent_context

    own_db = input is None  # heuristic, doesn't matter for behavior
    session = SessionLocal()
    try:
        matter_summary: str | None = None
        if matter_id is not None:
            matter = (
                session.query(Matter)
                .filter(
                    Matter.id == matter_id,
                    Matter.organization_id == organization_id,
                )
                .first()
            )
            if matter is not None:
                parts = [matter.title or "(sin título)"]
                if matter.matter_type:
                    parts.append(f"Tipo: {matter.matter_type.value}")
                if matter.description:
                    parts.append(matter.description)
                if matter.counterparty_name:
                    parts.append(f"Contraparte: {matter.counterparty_name}")
                matter_summary = "\n".join(parts)

        # RAG over documents in the matter.
        rag_text = ""
        if matter_id is not None:
            try:
                rag_text = get_relevant_context(
                    matter_id, organization_id,
                    query=input.get("query") if input else "",
                    top_k=5,
                )
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("agent build_context: rag failed (%s)", exc)

        # Precedentes relevantes por materia.
        precedents_text = ""
        if matter_id is not None:
            try:
                precedents_text = get_precedent_context(
                    query=input.get("query") if input else "",
                    organization_id=organization_id,
                    legal_area=None,
                    top_k=3,
                )
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("agent build_context: precedents failed (%s)", exc)

        memory_block = ""
        try:
            memory_block = memory_service.inject_into_prompt(
                session,
                organization_id=organization_id,
                user_id=user_id,
                matter_id=matter_id,
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("agent build_context: memory failed (%s)", exc)

        return AgentContext(
            organization_id=organization_id,
            user_id=user_id,
            matter_id=matter_id,
            input=input or {},
            matter_summary=matter_summary,
            rag_chunks=[{"text": rag_text}] if rag_text else [],
            precedents=[{"text": precedents_text}] if precedents_text else [],
            memory_block=memory_block or None,
        )
    finally:
        session.close()