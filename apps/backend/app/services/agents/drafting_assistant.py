"""drafting_assistant: given a matter and template_id, produces a filled-in
legal document. Used in the chat as the "Redactar documento" mode.
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
        "variables_used": {
            "type": "object",
            "description": "Mapa variable -> valor efectivamente usado.",
            "additionalProperties": {"type": "string"},
        },
        "draft_content": {
            "type": "string",
            "description": "Cuerpo completo del documento final.",
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notas sobre decisiones de redacción o supuestos.",
        },
    },
    "required": ["variables_used", "draft_content"],
}


SYSTEM_PROMPT = """Eres un abogado chileno redactor. Tu trabajo es completar un documento
legal usando la plantilla entregada, las variables sugeridas del caso y
las leyes chilenas aplicables.

REGLAS OBLIGATORIAS:
1. Sustituye TODAS las variables {{}} de la plantilla con valores
   coherentes derivados del caso y el contexto. Si falta información
   crítica, deja la variable con "[FALTA: <campo>]".
2. Cita leyes chilenas solo cuando sea normativamente necesario
   (cláusulas de competencia, jurisdicción, normativa aplicable).
3. Tono formal apropiado para contexto legal chileno.
4. Incluye al final del documento: "Documento preliminar sujeto a
   revisión por abogado habilitado antes de su presentación."

Responde ÚNICAMENTE con un JSON válido siguiendo el esquema entregado."""


def drafting_assistant(ctx: AgentContext) -> AgentResult:
    template_id = ctx.input.get("template_id") or "generic"
    template_text = ctx.input.get("template_text") or _FALLBACK_TEMPLATE
    suggested_vars = ctx.input.get("variables") or {}
    user_query = ctx.input.get("query") or ""

    user_prompt_parts: list[str] = []
    if ctx.memory_block:
        user_prompt_parts.append(ctx.memory_block)
        user_prompt_parts.append("")
    if ctx.matter_summary:
        user_prompt_parts.append("INFORMACIÓN DEL CASO:")
        user_prompt_parts.append(ctx.matter_summary)
        user_prompt_parts.append("")
    user_prompt_parts.append(f"PLANTILLA ({template_id}):")
    user_prompt_parts.append(template_text)
    user_prompt_parts.append("")
    if suggested_vars:
        user_prompt_parts.append("VARIABLES SUGERIDAS:")
        user_prompt_parts.append(json.dumps(suggested_vars, ensure_ascii=False, indent=2))
        user_prompt_parts.append("")
    if user_query:
        user_prompt_parts.append(f"INSTRUCCIONES ADICIONALES DEL USUARIO:\n{user_query}")
        user_prompt_parts.append("")
    user_prompt_parts.append("Genera el documento completo en JSON.")

    user_prompt = "\n".join(user_prompt_parts)
    provider = get_llm_provider()
    raw = provider.generate(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT + f"\n\nEsquema JSON: {json.dumps(SCHEMA)}",
        max_tokens=4096,
        temperature=0.4,
    )

    parsed: dict[str, Any]
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("drafting_assistant: failed to parse LLM JSON output")
        parsed = {
            "variables_used": suggested_vars if isinstance(suggested_vars, dict) else {},
            "draft_content": raw or "Sin contenido generado",
            "notes": ["El LLM no devolvió JSON válido; mostrando respuesta cruda."],
            "_raw": True,
        }

    return AgentResult(
        output=parsed,
        total_tokens=0,
        raw_response=raw,
    )


_FALLBACK_TEMPLATE = """Estimado/a {{destinatario}}:

Por medio de la presente, en mi calidad de {{remitente_cargo}} de {{remitente_organizacion}},
me dirijo a usted en relación con {{asunto}}.

{{cuerpo}}

Atentamente,
{{remitente_nombre}}
{{remitente_cargo}}
{{remitente_organizacion}}
{{fecha}}"""