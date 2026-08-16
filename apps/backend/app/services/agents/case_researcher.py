"""case_researcher: given a matter, produces a structured brief with
applicable Chilean laws, similar judicial precedents, identified risks,
and suggested next steps. Used in the chat as the "Investigar caso"
mode.

Runs as a multi-step ReAct loop: the agent decides which tools to call
(search_laws / search_precedents / search_matter_documents) based on
the initial matter context and the user's query, iterates up to 6
times, then emits a final_answer in the SCHEMA below.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import AgentContext, AgentResult
from app.services.agents.loop import build_initial_prompt, react_loop

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


def case_researcher(ctx: AgentContext) -> AgentResult:
    user_query = ctx.input.get("query") or "Resumen general del caso"

    initial_prompt = build_initial_prompt(
        matter_summary=ctx.matter_summary,
        rag_chunks=ctx.rag_chunks,
        precedents=ctx.precedents,
        user_query=user_query,
    )

    loop_result = react_loop(
        initial_prompt=initial_prompt,
        context_block=ctx.memory_block,
        final_answer_schema=SCHEMA,
    )

    parsed: dict[str, Any] = loop_result["output"]
    parsed["_query"] = user_query
    parsed["_disclaimer"] = (
        "Este análisis es preliminar y no reemplaza la revisión profesional "
        "de un abogado habilitado en Chile."
    )
    parsed["_iterations"] = len(loop_result["steps"])

    # Serialize the step trace for inclusion in the agent_run.output_json
    # so the UI / API consumer can show what the agent actually did.
    parsed["_steps"] = [
        {
            "step_index": s.get("step_index"),
            "kind": s.get("kind"),
            "tool_name": s.get("tool_name"),
            "reasoning": (s.get("reasoning") or "")[:300],
            "duration_ms": s.get("duration_ms", 0),
        }
        for s in loop_result["steps"]
    ]

    return AgentResult(
        output=parsed,
        total_tokens=0,
        raw_response=json.dumps(parsed, ensure_ascii=False)[:4000],
    )