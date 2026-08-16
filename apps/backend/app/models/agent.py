"""Agent run + step models. One AgentRun per execution; one AgentStep per
reasoning/tool cycle in the run.
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class AgentRun(Base):
    """A single execution of an agent.

    `output_artifact_id` + `output_artifact_kind` together point at the
    row the agent produced (Document, AnalysisReport) when the agent
    creates a real artifact rather than just emitting text.
    """

    __tablename__ = "agent_runs"

    id = Column(BigInteger, primary_key=True, index=True)
    organization_id = Column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matter_id = Column(
        BigInteger, ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_kind = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="running")

    input_json = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=False, default=dict)

    output_artifact_id = Column(BigInteger, nullable=True)
    output_artifact_kind = Column(String(32), nullable=True)

    total_tokens = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    steps = relationship(
        "AgentStep", back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.step_index"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="agent_runs_status_valid",
        ),
        CheckConstraint(
            "output_artifact_kind IS NULL OR output_artifact_kind IN ('document', 'analysis_report')",
            name="agent_runs_artifact_kind_valid",
        ),
        Index("idx_agent_runs_org_user_started", "organization_id", "user_id", "started_at"),
        Index("idx_agent_runs_kind_status", "agent_kind", "status"),
    )

    def __repr__(self) -> str:
        return f"<AgentRun {self.agent_kind} status={self.status} matter={self.matter_id}>"


class AgentStep(Base):
    """One step in an agent run: a reasoning pass, a tool call, the result
    of a tool call, or the final synthesized answer.
    """

    __tablename__ = "agent_steps"

    id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    organization_id = Column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    step_index = Column(Integer, nullable=False)
    kind = Column(String(32), nullable=False)
    tool_name = Column(String(64), nullable=True)

    input_json = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=False, default=dict)
    reasoning = Column(Text, nullable=True)

    tokens_used = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("AgentRun", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="agent_steps_run_index_unique"),
        CheckConstraint(
            "kind IN ('reasoning', 'tool_call', 'tool_result', 'final_answer')",
            name="agent_steps_kind_valid",
        ),
        Index("idx_agent_steps_run_index", "run_id", "step_index"),
    )

    def __repr__(self) -> str:
        return f"<AgentStep run={self.run_id} idx={self.step_index} kind={self.kind}>"