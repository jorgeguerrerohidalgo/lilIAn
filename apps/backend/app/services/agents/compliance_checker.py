"""compliance_checker: given a document_id, detects clauses that violate
Chilean law and returns a structured list of violations with severity
and cited law. Used in the chat as the "Revisar cumplimiento" mode.
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
        "compliant": {
            "type": "boolean",
            "description": "True si el documento cumple con toda la normativa aplicable.",
        },
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause_excerpt": {"type": "string"},
                    "law_name": {"type": "string"},
                    "article": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "description": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
            },
        },
        "observations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observaciones menores o puntos a revisar sin ser violaciones formales.",
        },
    },
    "required": ["compliant", "violations"],
}


SYSTEM_PROMPT = """Eres un abogado chileno revisor de cumplimiento normativo. Tu trabajo
es analizar un documento legal entregado y detectar cláusulas que
violen legislación chilena vigente.

REGLAS OBLIGATORIAS:
1. SOLO puedes citar leyes chilenas que aparezcan explícitamente en el
   contexto proporcionado. NO inventes artículos.
2. Marca como violación solo lo que constituya un incumplimiento real;
   las observaciones menores van en el array "observations".
3. Para cada violación, incluye: extracto de la cláusula, ley infringida,
   artículo, severidad, descripción y recomendación concreta.
4. Sé conservador: en caso de duda entre violación y observación, usa
   "observations" con severidad "low".
5. Siempre incluye la advertencia: "Este análisis es preliminar y no
   reemplaza la revisión profesional de un abogado habilitado en Chile."

Responde ÚNICAMENTE con un JSON válido siguiendo el esquema entregado."""


def _build_user_prompt(ctx: AgentContext) -> str:
    parts: list[str] = []
    if ctx.memory_block:
        parts.append(ctx.memory_block)
        parts.append("")
    if ctx.matter_summary:
        parts.append("CONTEXTO DEL CASO:")
        parts.append(ctx.matter_summary)
        parts.append("")
    if ctx.document_text:
        parts.append("DOCUMENTO A REVISAR:")
        # Truncate to avoid blowing the context window; analysts always
        # warn about full-doc review in production but for v1 this works.
        parts.append(ctx.document_text[:12_000])
        parts.append("")
    if ctx.rag_chunks:
        parts.append("LEYES APLICABLES (contexto):")
        for i, chunk in enumerate(ctx.rag_chunks[:8], 1):
            parts.append(f"[Ley {i}] {chunk.get('text', '')[:1500]}")
        parts.append("")
    parts.append("Identifica violaciones y observaciones siguiendo el esquema JSON.")
    return "\n".join(parts)


def compliance_checker(ctx: AgentContext) -> AgentResult:
    user_prompt = _build_user_prompt(ctx)
    provider = get_llm_provider()

    raw = provider.generate(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT + f"\n\nEsquema JSON: {json.dumps(SCHEMA)}",
        max_tokens=3000,
        temperature=0.2,
    )

    parsed: dict[str, Any]
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("compliance_checker: failed to parse LLM JSON output")
        parsed = {
            "compliant": False,
            "violations": [],
            "observations": [
                "El LLM no devolvió JSON válido; mostrando respuesta cruda para revisión manual."
            ],
            "_raw_response": (raw or "")[:1500],
        }

    parsed["_disclaimer"] = (
        "Este análisis es preliminar y no reemplaza la revisión profesional "
        "de un abogado habilitado en Chile."
    )

    return AgentResult(
        output=parsed,
        total_tokens=0,
        raw_response=raw,
    )