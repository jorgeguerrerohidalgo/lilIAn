"""Agents module: simple in-process agent runner for Harvey-grade capabilities.

Each agent is a single-shot LLM call over pre-collected context (RAG +
precedents + matter info). The agent runner persists every step to
agent_steps so runs are replayable and auditable. A true multi-step
agent loop can replace this later without touching the public API.
"""
from app.services.agents.base import AgentContext, AgentResult, run_agent
from app.services.agents.case_researcher import case_researcher
from app.services.agents.compliance_checker import compliance_checker
from app.services.agents.drafting_assistant import drafting_assistant


_REGISTRY: dict[str, callable] = {
    "case_researcher": case_researcher,
    "drafting_assistant": drafting_assistant,
    "compliance_checker": compliance_checker,
}


def get_agent(kind: str):
    """Return the agent callable for a given kind, or None if unknown."""
    return _REGISTRY.get(kind)


def list_agents() -> list[dict[str, str]]:
    """List available agent kinds for the UI dropdown."""
    return [
        {"kind": "case_researcher", "label": "Investigar caso", "description": "Resume el caso, identifica leyes y precedentes aplicables, riesgos y próximos pasos."},
        {"kind": "drafting_assistant", "label": "Redactar documento", "description": "Completa una plantilla con variables sugeridas del caso y la devuelve como borrador."},
        {"kind": "compliance_checker", "label": "Revisar cumplimiento", "description": "Detecta cláusulas de un documento que violan legislación chilena."},
    ]


__all__ = [
    "AgentContext",
    "AgentResult",
    "run_agent",
    "get_agent",
    "list_agents",
    "case_researcher",
    "drafting_assistant",
    "compliance_checker",
]