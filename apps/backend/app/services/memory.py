"""Memory service: long-term per-user facts, rolling case summaries, and
feedback signals. Injects personalized context into every chat prompt so
the assistant remembers who the user is, what the case is about, and how
the user prefers to be answered.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import CaseContextSnapshot, FeedbackSignal, UserFact

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------

def get_user_facts(
    db: Session,
    *,
    organization_id: int,
    user_id: int,
    kinds: list[str] | None = None,
    limit: int = 25,
) -> list[UserFact]:
    """Return persistent facts for a user, ordered by confidence desc then recency.

    `kinds` filters by semantic category (e.g. ["practice_area", "preference"]).
    Always tenant-scoped via organization_id.
    """
    stmt = (
        select(UserFact)
        .where(UserFact.organization_id == organization_id)
        .where((UserFact.user_id == user_id) | (UserFact.user_id.is_(None)))
        .order_by(UserFact.confidence.desc(), UserFact.updated_at.desc())
        .limit(limit)
    )
    if kinds:
        stmt = stmt.where(UserFact.kind.in_(kinds))
    return list(db.scalars(stmt).all())


def get_case_snapshot(
    db: Session,
    *,
    organization_id: int,
    matter_id: int,
) -> CaseContextSnapshot | None:
    """Return the rolling summary for a matter, or None if there is no
    snapshot yet (first session on the case)."""
    stmt = (
        select(CaseContextSnapshot)
        .where(CaseContextSnapshot.organization_id == organization_id)
        .where(CaseContextSnapshot.matter_id == matter_id)
    )
    return db.scalars(stmt).first()


def inject_into_prompt(
    db: Session,
    *,
    organization_id: int,
    user_id: int,
    matter_id: int | None,
    max_chars: int = 2_000,
) -> str:
    """Build the memory block to prepend to the chat system prompt.

    Layout (when content is non-empty):

        CONTEXTO PERSISTENTE (memoria del usuario y del caso):

        Sobre el usuario:
        - [practice_area] Esta firma se especializa en derecho laboral chileno.
        - [preference] El usuario prefiere respuestas concisas y formales.

        Sobre el caso:
        Resumen: ...
        Preguntas abiertas: ...

    Returns an empty string when there is nothing to inject so callers can
    skip the section cleanly.
    """
    sections: list[str] = []
    facts = get_user_facts(db, organization_id=organization_id, user_id=user_id)
    if facts:
        user_lines = [f"- [{f.kind}] {f.content}" for f in facts]
        sections.append("Sobre el usuario:\n" + "\n".join(user_lines))

    if matter_id is not None:
        snapshot = get_case_snapshot(db, organization_id=organization_id, matter_id=matter_id)
        if snapshot is not None:
            case_lines = [f"Resumen: {snapshot.summary}"]
            if snapshot.open_questions:
                questions = snapshot.open_questions
                if isinstance(questions, list) and questions:
                    joined = "\n".join(f"- {q}" for q in questions[:8])
                    case_lines.append(f"Preguntas abiertas:\n{joined}")
            sections.append("Sobre el caso:\n" + "\n\n".join(case_lines))

    if not sections:
        return ""

    block = "CONTEXTO PERSISTENTE (memoria del usuario y del caso):\n\n" + "\n\n".join(sections)
    if len(block) > max_chars:
        block = block[: max_chars - 3] + "..."
    return block


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------

def record_user_fact(
    db: Session,
    *,
    organization_id: int,
    user_id: int | None,
    kind: str,
    content: str,
    confidence: float = 1.0,
    source: str = "manual",
    embedding: list[float] | None = None,
) -> UserFact:
    """Insert a persistent fact. Idempotent on (organization_id, user_id, kind,
    content): if an identical row already exists we just bump updated_at."""
    import json

    stmt = select(UserFact).where(
        UserFact.organization_id == organization_id,
        UserFact.user_id == user_id,
        UserFact.kind == kind,
        UserFact.content == content,
    )
    existing = db.scalars(stmt).first()
    if existing is not None:
        existing.confidence = max(existing.confidence or 0, confidence)
        existing.updated_at = _now()
        db.commit()
        return existing

    fact = UserFact(
        organization_id=organization_id,
        user_id=user_id,
        kind=kind,
        content=content,
        confidence=confidence,
        source=source,
        embedding=json.dumps(embedding) if embedding is not None else None,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return fact


def update_case_snapshot(
    db: Session,
    *,
    organization_id: int,
    matter_id: int,
    summary: str,
    key_entities: dict[str, Any] | None = None,
    open_questions: list[str] | None = None,
    last_chat_message_id: int | None = None,
) -> CaseContextSnapshot:
    """Upsert the rolling summary for a matter. Bumps `version` on every
    update so consumers can detect changes."""
    snapshot = get_case_snapshot(
        db, organization_id=organization_id, matter_id=matter_id
    )
    if snapshot is None:
        snapshot = CaseContextSnapshot(
            organization_id=organization_id,
            matter_id=matter_id,
            summary=summary,
            key_entities=key_entities or {},
            open_questions=open_questions or [],
            last_chat_message_id=last_chat_message_id,
            version=1,
        )
        db.add(snapshot)
    else:
        snapshot.summary = summary
        snapshot.key_entities = key_entities or {}
        snapshot.open_questions = open_questions or []
        snapshot.last_chat_message_id = last_chat_message_id or snapshot.last_chat_message_id
        snapshot.version = (snapshot.version or 1) + 1
        snapshot.updated_at = _now()
    db.commit()
    db.refresh(snapshot)
    return snapshot


def record_feedback(
    db: Session,
    *,
    organization_id: int,
    chat_message_id: int,
    user_id: int,
    rating: int,
    correction: str | None = None,
    extracted_fact: str | None = None,
    extracted_kind: str = "preference",
) -> FeedbackSignal:
    """Record a feedback signal. When `extracted_fact` is provided, also
    promote it into user_facts so the next prompt picks it up."""
    if rating not in (-1, 0, 1):
        raise ValueError(f"rating must be -1, 0 or 1 (got {rating})")

    signal = FeedbackSignal(
        organization_id=organization_id,
        chat_message_id=chat_message_id,
        user_id=user_id,
        rating=rating,
        correction=correction,
        extracted_fact=extracted_fact,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    if extracted_fact:
        try:
            record_user_fact(
                db,
                organization_id=organization_id,
                user_id=user_id,
                kind=extracted_kind,
                content=extracted_fact,
                confidence=0.9 if rating == 1 else 0.7,
                source="feedback",
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("record_feedback: failed to promote fact (%s)", exc)

    return signal


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _now():
    from datetime import datetime
    return datetime.utcnow()