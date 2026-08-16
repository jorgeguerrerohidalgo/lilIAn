"""Memory models: long-term per-user facts, rolling case summaries, and
feedback signals. These power the persistent-memory feature in the chat
experience — without them, every new chat session starts cold.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserFact(Base):
    """Long-term fact about a user (or their firm) injected into every
    chat prompt as persistent context.
    """

    __tablename__ = "user_facts"

    id = Column(BigInteger, primary_key=True, index=True)
    organization_id = Column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    confidence = Column(Numeric(3, 2), nullable=False, default=1.00)
    source = Column(String(64), nullable=False, default="manual")
    embedding = Column(Text, nullable=True)  # JSON-stringified float vector

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    organization = relationship("Organization")

    __table_args__ = (
        Index("idx_user_facts_org_user", "organization_id", "user_id"),
        Index("idx_user_facts_org_kind", "organization_id", "kind"),
        Index("idx_user_facts_org_updated", "organization_id", "updated_at"),
        CheckConstraint(
            "user_id IS NOT NULL OR kind = 'firm'",
            name="user_facts_user_or_org_only",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserFact {self.kind}: {self.content[:40]}>"


class CaseContextSnapshot(Base):
    """Rolling LLM-generated summary of a matter, refreshed after every
    chat session. Injected into new sessions so the user does not have to
    re-explain the case from scratch.
    """

    __tablename__ = "case_context_snapshots"

    id = Column(BigInteger, primary_key=True, index=True)
    matter_id = Column(
        BigInteger,
        ForeignKey("matters.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    organization_id = Column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    summary = Column(Text, nullable=False)
    key_entities = Column(JSONB, nullable=False, default=dict)
    open_questions = Column(JSONB, nullable=False, default=list)
    last_chat_message_id = Column(
        BigInteger, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    matter = relationship("Matter")
    organization = relationship("Organization")

    __table_args__ = (
        Index("idx_case_context_snapshots_org_matter", "organization_id", "matter_id"),
    )

    def __repr__(self) -> str:
        return f"<CaseContextSnapshot matter={self.matter_id} v{self.version}>"


class FeedbackSignal(Base):
    """User feedback on an assistant chat message. Optional `extracted_fact`
    is filled when the correction yields a fact worth promoting to user_facts.
    """

    __tablename__ = "feedback_signals"

    id = Column(BigInteger, primary_key=True, index=True)
    organization_id = Column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    chat_message_id = Column(
        BigInteger, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating = Column(SmallInteger, nullable=False)  # -1, 0, or 1
    correction = Column(Text, nullable=True)
    extracted_fact = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("rating BETWEEN -1 AND 1", name="feedback_signals_rating_range"),
        Index(
            "idx_feedback_signals_org_user_created",
            "organization_id",
            "user_id",
            "created_at",
        ),
        Index("idx_feedback_signals_message", "chat_message_id"),
    )

    def __repr__(self) -> str:
        return f"<FeedbackSignal message={self.chat_message_id} rating={self.rating}>"