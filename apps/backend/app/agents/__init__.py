"""S5.1 — Biblioteca declarativa de agentes de dominio chilenos.

Véase ``app.agents.registry`` para el catálogo. La galería pública
``/agents`` consume ``get_agent_library()``.
"""
from app.agents.registry import (
    AGENT_LIBRARY,
    DomainAgent,
    get_agent_by_slug,
    get_agent_library,
    get_agents_by_category,
    list_library_categories,
)

__all__ = [
    "AGENT_LIBRARY",
    "DomainAgent",
    "get_agent_by_slug",
    "get_agent_library",
    "get_agents_by_category",
    "list_library_categories",
]
