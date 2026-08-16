"""ReAct-style multi-step agent loop.

A generic runner that drives an agent through multiple reasoning → tool_call
→ observation cycles until the LLM emits a `final_answer` action or we
hit the iteration cap.

Tools available to the agent:

  * search_laws(query, top_k)
  * search_precedents(query, top_k)
  * search_matter_documents(query, top_k)

The agent decides what to do at each step by emitting JSON with shape:

    {"thought": "...",
     "action": "tool_name" | "final_answer",
     "action_input": {...}}

A malformed JSON or unknown action is logged and the loop continues with
a synthetic observation telling the agent to fix its output, until the
iteration cap or final_answer arrives.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.services.agents.base import AgentContext, AgentResult
from app.services.llm import get_llm_provider

logger = logging.getLogger(__name__)


MAX_ITERATIONS = 6
DEFAULT_TOP_K = 5


REACT_SYSTEM_PROMPT = """Eres un abogado investigador chileno senior ejecutando un análisis
estructurado de un caso. Tienes acceso a 3 herramientas:

  1. search_laws(query, top_k=5) — busca en el corpus de legislación
     chilena indexado (Códigos Civil, Penal, Trabajo, Comercio, etc.).
     Devuelve hasta `top_k` fragmentos relevantes con cita de ley y
     artículo.

  2. search_precedents(query, top_k=3) — busca en sentencias judiciales
     chilenas previamente indexadas. Devuelve hasta `top_k` precedentes
     con tribunal, año y disposition.

  3. search_matter_documents(query, top_k=5) — busca en los documentos
     del caso actual (contratos, escritos, etc.).

En cada paso, responde ÚNICAMENTE con JSON válido de la forma:

    {"thought": "<razonamiento en 1 frase>",
     "action": "<search_laws | search_precedents | search_matter_documents | final_answer>",
     "action_input": { ... }}

Cuando hayas recopilado suficiente información, emite
`action: "final_answer"` con `action_input` siendo el brief estructurado
del caso en JSON siguiendo el esquema:

    {
      "summary": "...",
      "applicable_laws": [{"law_name":"...","article":"...","summary":"..."}],
      "relevant_precedents": [{"court":"...","year":2024,"summary":"..."}],
      "identified_risks": [{"title":"...","severity":"high","description":"..."}],
      "next_steps": ["..."],
      "_disclaimer": "Este análisis es preliminar..."
    }

REGLAS:
- No cites leyes que NO te devolvieron las herramientas.
- Usa las herramientas múltiples veces con queries diferentes si la
  primera búsqueda no es suficiente.
- Sé conciso en `thought`; el espacio es para razonar, no para repetir
  los resultados."""


def _safe_json_loads(raw: str | None) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        last_fence = text.rfind("```")
        if first_nl != -1 and last_fence != -1:
            text = text[first_nl + 1 : last_fence].strip()
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start : end + 1])
                return result if isinstance(result, dict) else None
            except json.JSONDecodeError:
                return None
        return None


def _tool_search_laws(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    """Search the indexed Chilean law corpus."""
    from app.models.law_chunk import LawChunk
    from app.services.rag import search_laws_by_embedding, search_chunks_by_keyword

    if not query.strip():
        return []
    try:
        # Try embedding first, fall back to keyword if it errors.
        try:
            results = search_laws_by_embedding(query=query, top_k=top_k)
        except Exception:
            results = search_chunks_by_keyword(query=query, top_k=top_k, source="laws")
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("react loop search_laws failed: %s", exc)
        return []

    formatted: list[dict[str, Any]] = []
    for r in results[:top_k]:
        formatted.append({
            "law_code": r.get("law_code"),
            "law_name": r.get("law_name"),
            "article_number": r.get("article_number"),
            "chunk_index": r.get("chunk_index"),
            "content": (r.get("content") or "")[:1000],
        })
    return formatted


def _tool_search_precedents(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Search Chilean judicial precedents."""
    from app.services.precedent_rag import search_precedents_by_keyword

    if not query.strip():
        return []
    try:
        results = search_precedents_by_keyword(
            query=query,
            organization_id=None,
            top_k=top_k,
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("react loop search_precedents failed: %s", exc)
        return []

    formatted: list[dict[str, Any]] = []
    for r in results[:top_k]:
        formatted.append({
            "court": r.get("court"),
            "year": r.get("year"),
            "roll_number": r.get("roll_number"),
            "legal_area": r.get("legal_area"),
            "summary": (r.get("summary") or "")[:600],
            "decision": (r.get("decision") or "")[:400],
        })
    return formatted


def _tool_search_matter_documents(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    *,
    matter_id: int | None,
    organization_id: int | None,
) -> list[dict[str, Any]]:
    """Search the matter's uploaded documents via hybrid RAG."""
    from app.services.rag import hybrid_search

    if not query.strip() or matter_id is None or organization_id is None:
        return []
    try:
        results = hybrid_search(
            query=query,
            organization_id=organization_id,
            matter_id=matter_id,
            top_k=top_k,
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("react loop search_matter_documents failed: %s", exc)
        return []

    formatted: list[dict[str, Any]] = []
    for r in results[:top_k]:
        formatted.append({
            "document_id": r.get("document_id"),
            "page_number": r.get("page_number"),
            "content": (r.get("content") or "")[:1200],
        })
    return formatted


def _execute_tool(action: str, action_input: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
    if action == "search_laws":
        query = action_input.get("query") or ""
        top_k = int(action_input.get("top_k") or DEFAULT_TOP_K)
        return {"tool": "search_laws", "results": _tool_search_laws(query, top_k)}

    if action == "search_precedents":
        query = action_input.get("query") or ""
        top_k = int(action_input.get("top_k") or 3)
        return {"tool": "search_precedents", "results": _tool_search_precedents(query, top_k)}

    if action == "search_matter_documents":
        query = action_input.get("query") or ""
        top_k = int(action_input.get("top_k") or DEFAULT_TOP_K)
        return {
            "tool": "search_matter_documents",
            "results": _tool_search_matter_documents(
                query, top_k,
                matter_id=ctx.matter_id,
                organization_id=ctx.organization_id,
            ),
        }

    return {"tool": action, "error": f"unknown action: {action}"}


def react_loop(
    *,
    initial_prompt: str,
    context_block: str | None,
    final_answer_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a ReAct loop and return the final_answer payload.

    `initial_prompt` is the user-side instruction (case query, plus any
    matter summary that the agent should know about). `context_block`
    is the persistent memory block; it is included in the first message
    only to avoid wasting tokens on every step.

    Returns a dict with two keys:
      - `output`: the final_answer dict (or a synthetic one if the LLM
        never emitted final_answer).
      - `steps`: a list of {step_index, kind, tool_name, reasoning,
        output, tokens_used, duration_ms} for audit.
    """
    provider = get_llm_provider()
    transcript: list[dict[str, str]] = []
    steps: list[dict[str, Any]] = []

    system_prompt = REACT_SYSTEM_PROMPT
    if final_answer_schema:
        system_prompt += f"\n\nEsquema JSON del final_answer: {json.dumps(final_answer_schema)}"

    if context_block:
        transcript.append({"role": "user", "content": f"{context_block}\n\n{initial_prompt}"})
    else:
        transcript.append({"role": "user", "content": initial_prompt})

    final_output: dict[str, Any] | None = None
    for iteration in range(MAX_ITERATIONS):
        t0 = time.monotonic()
        raw = provider.generate(
            prompt="\n".join(m["content"] for m in transcript),
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.3,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        action_payload = _safe_json_loads(raw)
        thought = ""
        action = ""
        action_input: dict[str, Any] = {}
        if action_payload is None:
            action = "final_answer"
            action_input = {"_malformed_thought": raw[:500]}
        else:
            thought = str(action_payload.get("thought") or "")
            action = str(action_payload.get("action") or "final_answer")
            raw_input = action_payload.get("action_input")
            action_input = raw_input if isinstance(raw_input, dict) else {}

        steps.append({
            "step_index": iteration,
            "kind": "reasoning" if action != "final_answer" else "final_answer",
            "tool_name": action if action != "final_answer" else None,
            "reasoning": thought,
            "raw_response": raw[:2000],
            "tokens_used": 0,
            "duration_ms": elapsed_ms,
        })

        if action == "final_answer":
            final_output = action_input if isinstance(action_input, dict) else {"_raw": raw}
            break

        observation = _execute_tool(action, action_input, ctx=None)  # ctx unused at this layer
        steps.append({
            "step_index": iteration,
            "kind": "tool_result",
            "tool_name": action,
            "output": observation,
            "tokens_used": 0,
            "duration_ms": 0,
        })

        transcript.append({"role": "assistant", "content": raw})
        transcript.append({
            "role": "user",
            "content": (
                f"Observation de {action}:\n"
                f"{json.dumps(observation, ensure_ascii=False)[:3000]}"
            ),
        })

    if final_output is None:
        final_output = {
            "summary": "El agente no produjo un final_answer en el número máximo de iteraciones.",
            "_truncated": True,
            "_iterations": len(steps),
        }

    return {"output": final_output, "steps": steps}


def build_initial_prompt(
    *,
    matter_summary: str | None,
    rag_chunks: list[dict[str, Any]],
    precedents: list[dict[str, Any]],
    user_query: str,
) -> str:
    """Compose the first message that primes the ReAct loop."""
    parts: list[str] = []
    if matter_summary:
        parts.append("CONTEXTO DEL CASO:")
        parts.append(matter_summary)
        parts.append("")
    if rag_chunks:
        parts.append("FRAGMENTOS YA RECOPILADOS DEL CASO (úsalos solo como referencia inicial):")
        for i, chunk in enumerate(rag_chunks[:4], 1):
            parts.append(f"[Doc {i}] {chunk.get('text', '')[:1200]}")
        parts.append("")
    if precedents:
        parts.append("PRECEDENTES YA RECOPILADOS (referencia inicial):")
        for i, p in enumerate(precedents[:3], 1):
            parts.append(f"[Precedente {i}] {p.get('text', '')[:800]}")
        parts.append("")
    parts.append("CONSULTA DEL USUARIO:")
    parts.append(user_query)
    parts.append("")
    parts.append(
        "Decide qué herramienta invocar primero para responder mejor la consulta. "
        "Recuerda que SOLO puedes citar lo que las herramientas te devuelvan."
    )
    return "\n".join(parts)