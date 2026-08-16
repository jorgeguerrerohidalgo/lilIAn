"""case_researcher: given a matter, produces a structured brief with
applicable Chilean laws, similar judicial precedents, identified risks,
and suggested next steps. Used in the chat as the "Investigar caso"
mode.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import AgentContext, AgentResult
from app.services.llm import get_llm_provider

logger = logging.getLogger(__name__)


SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Resumen ejecutivo del caso en 3-5 frases."},
        "applicable_laws": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "law_name": {"type": "string"},
                    "article": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
        },
        "relevant_precedents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "court": {"type": "string"},
                    "year": {"type": "integer"},
                    "summary": {"type": "string"},
                    "relevance": {"type": "string"},
                },
            },
        },
        "identified_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "description": {"type": "string"},
                },
            },
        },
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "applicable_laws", "identified_risks", "next_steps"],
}


SYSTEM_PROMPT = """Eres un abogado investigador chileno senior. Tu trabajo es producir un
brief estructurado de un caso legal para otro abogado del equipo.

REGLAS OBLIGATORIAS:
1. SOLO puedes citar leyes chilenas que aparezcan explícitamente en el
   contexto proporcionado. NO inventes artículos ni jurisprudencia.
2. Si el contexto no contiene información suficiente para una sección,
   devuelve esa sección con un array vacío y un mensaje breve.
3. Las leyes y precedentes que cites DEBEN provenir de los fragmentos
   entregados en el contexto (marcados como "[Ley]" o "[Precedente]").
4. Siempre incluye la advertencia final: "Este análisis es preliminar y
   no reemplaza la revisión profesional de un abogado habilitado en
   Chile."

Responde ÚNICAMENTE con un JSON válido siguiendo el esquema entregado."""


def _build_user_prompt(ctx: AgentContext) -> str:
    parts: list[str] = []
    if ctx.memory_block:
        parts.append(ctx.memory_block)
        parts.append("")
    if ctx.matter_summary:
        parts.append("INFORMACIÓN DEL CASO:")
        parts.append(ctx.matter_summary)
        parts.append("")
    if ctx.rag_chunks:
        parts.append("FRAGMENTOS DE DOCUMENTOS DEL CASO:")
        for i, chunk in enumerate(ctx.rag_chunks[:8], 1):
            parts.append(f"[Doc {i}] {chunk.get('text', '')[:1500]}")
        parts.append("")
    if ctx.precedents:
        parts.append("PRECEDENTES JUDICIALES:")
        for i, p in enumerate(ctx.precedents[:5], 1):
            parts.append(f"[Precedente {i}] {p.get('text', '')[:1500]}")
        parts.append("")
    parts.append("Genera el brief estructurado del caso en JSON siguiendo el esquema.")
    return "\n".join(parts)


def case_researcher(ctx: AgentContext) -> AgentResult:
    user_query = ctx.input.get("query") or "Resumen general del caso"
    user_prompt = _build_user_prompt(ctx)
    provider = get_llm_provider()

    raw = provider.generate(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT + f"\n\nEsquema JSON: {json.dumps(SCHEMA)}",
        max_tokens=3000,
        temperature=0.3,
    )

    parsed: dict[str, Any]
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("case_researcher: failed to parse LLM JSON output, returning raw")
        parsed = {
            "summary": raw[:1500] if raw else "Sin respuesta",
            "applicable_laws": [],
            "relevant_precedents": [],
            "identified_risks": [],
            "next_steps": [],
            "_raw": True,
            "_query": user_query,
        }

    parsed["_query"] = user_query
    parsed["_disclaimer"] = (
        "Este análisis es preliminar y no reemplaza la revisión profesional "
        "de un abogado habilitado en Chile."
    )

    return AgentResult(
        output=parsed,
        total_tokens=0,  # LLM provider does not surface token counts today
        raw_response=raw,
    )