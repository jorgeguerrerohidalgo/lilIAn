import logging
from datetime import datetime

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.models.legal_area import MATTER_TYPE_TO_LEGAL_AREA, LegalArea

logger = logging.getLogger(__name__)

_CHAT_RULES = (
    "REGLAS:\n"
    "- Responde usando los fragmentos proporcionados en CONTEXTO, que pueden\n"
    "  provenir de tres fuentes: (1) documentos del caso actual, (2) leyes\n"
    "  chilenas relevantes, (3) precedentes judiciales.\n"
    "- NO inventes normas, artículos ni jurisprudencia. Solo cita lo que\n"
    "  aparece explícitamente en los fragmentos.\n"
    "- Cuando cites una ley, incluye el nombre del cuerpo legal y el\n"
    "  número de artículo. Cuando cites un documento del caso, indica\n"
    "  el nombre del archivo.\n"
    "- Si ninguna fuente tiene información suficiente, indícalo claramente.\n"
    "- Tono profesional, contexto legal chileno.\n"
    '- Incluye: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile."\n'
    "\nCONTEXTO:\n{context}\n\nPregunta: {question}"
)


SYSTEM_PROMPT_CHAT = (
    "Eres un asistente legal chileno especializado en análisis documental y "
    "apoyo jurídico preliminar.\n\n" + _CHAT_RULES
)


CHAT_PROMPTS_BY_AREA: dict[LegalArea, str] = {
    LegalArea.LABOR: (
        "Eres un asistente legal laboral chileno. Aplicas: contratos, "
        "remuneraciones, jornada, despidos, negociación colectiva, "
        "subcontrato, salud ocupacional.\n\n" + _CHAT_RULES
    ),
    LegalArea.CIVIL: (
        "Eres un asistente legal civil chileno. Aplicas: contratos, "
        "obligaciones, bienes, prescripción, sucesiones, personas.\n\n" + _CHAT_RULES
    ),
    LegalArea.CONSUMER: (
        "Eres un asistente legal de consumo chileno. Aplicas: cláusulas "
        "abusivas, garantías, servicios financieros, publicidad, datos "
        "personales.\n\n" + _CHAT_RULES
    ),
    LegalArea.FAMILY: (
        "Eres un asistente legal de familia chileno. Aplicas: divorcio, "
        "custodia, pensiones, medidas de protección, filiación, VIF, "
        "régimen matrimonial.\n\n" + _CHAT_RULES
    ),
    LegalArea.COMMERCE: (
        "Eres un asistente legal comercial chileno. Aplicas: sociedades, "
        "títulos de crédito, insolvencia, contratos mercantiles, corretaje, "
        "seguros, propiedad industrial.\n\n" + _CHAT_RULES
    ),
    LegalArea.PENAL: (
        "Eres un asistente legal penal chileno. Aplicas: delitos, medidas "
        "cautelares, procedimiento penal, derechos del imputado, ejecución de "
        "penas, delitos económicos.\n\n" + _CHAT_RULES
    ),
    LegalArea.OTHER: SYSTEM_PROMPT_CHAT,
}






def get_chat_prompt_for_area(legal_area: LegalArea | None) -> str:
    """Retorna el prompt según el área legal."""
    if legal_area is None:
        return SYSTEM_PROMPT_CHAT
    return CHAT_PROMPTS_BY_AREA.get(legal_area, SYSTEM_PROMPT_CHAT)


def get_chat_system_prompt(
    matter_type: str | None,
    context: str,
    question: str,
    legal_area: LegalArea | None = None
) -> str:
    """Genera el prompt del sistema para chat, especializado por área legal."""
    # Si se pasó legal_area override, usarlo directamente
    if legal_area is not None:
        prompt_template = get_chat_prompt_for_area(legal_area)
    else:
        # Inferir del matter_type
        prompt_template = get_chat_prompt_for_area(
            MATTER_TYPE_TO_LEGAL_AREA.get(matter_type.lower(), LegalArea.OTHER) if matter_type else LegalArea.OTHER
        )
    return prompt_template.format(context=context, question=question)


def get_relevant_context(
    matter_id: int,
    organization_id: int,
    query: str,
    top_k: int = 5,
    legal_area: LegalArea | None = None,
    include_precedents: bool = True,
    include_laws: bool = True,
) -> str:
    from app.services.embeddings import get_embedding_provider
    from app.services.rag import hybrid_search, search_laws_by_embedding

    try:
        provider = get_embedding_provider()
        # S5.1: force 1536-dim embeddings for the query so we stay
        # compatible with law_chunks (all indexed at 1536 — the
        # EMBEDDING_DIM_SHORT=512 branch only triggers for batched calls
        # where every text is short, which never happens with our mixed
        # batches). Without this, short Spanish queries get a 512-dim
        # vector and cosine_similarity raises against the 1536-dim
        # corpus.
        query_embedding = provider.generate_embedding(
            query if len(query) >= 2000 else query + " " * (2000 - len(query)),
        )

        results = hybrid_search(
            query=query,
            organization_id=organization_id,
            matter_id=matter_id,
            top_k=top_k,
            legal_area=legal_area
        )

        context_parts = []

        # Agregar contexto de documentos del caso
        if results:
            for i, result in enumerate(results, 1):
                doc = None
                db = SessionLocal()
                try:
                    doc = db.query(Document).filter(Document.id == result["document_id"]).first()
                finally:
                    db.close()

                doc_name = doc.original_filename if doc else f"Documento {result['document_id']}"
                page_info = f" (Página {result['page_number']})" if result.get("page_number") else ""

                context_parts.append(
                    f"[{i}] De: {doc_name}{page_info}\n"
                    f"Contenido relevante:\n{result['content'][:2000]}"
                )
        else:
            context_parts.append("No se encontró información relevante en los documentos del caso.")

        # Agregar contexto del corpus de leyes chilenas (S5.1 — 14 leyes
        # indexadas con embeddings reales). Habilita preguntas jurídicas
        # generales (e.g. causales de despido) que no aparecen en los
        # documentos del caso actual.
        if include_laws:
            try:
                law_results = search_laws_by_embedding(
                    query_embedding=query_embedding,
                    query_text=query,
                    top_k=4,
                    similarity_threshold=0.3,
                    legal_area=legal_area,
                )
                if law_results:
                    law_lines = []
                    for lr in law_results:
                        art = f" (art. {lr['article_number']})" if lr.get("article_number") else ""
                        law_lines.append(
                            f"- {lr['law_name']}{art} [similitud {lr['similarity']:.2f}]: "
                            f"{lr['content'][:1500]}"
                        )
                    context_parts.append(
                        "LEYES CHILENAS APLICABLES:\n" + "\n".join(law_lines)
                    )
            except Exception:
                pass  # Silencioso si falla búsqueda de leyes

        # Agregar contexto de precedentes judiciales
        if include_precedents:
            try:
                from app.services.precedent_rag import get_precedent_context as get_pc
                precedent_context = get_pc(
                    query=query,
                    organization_id=organization_id,
                    court=None,
                    year=None,
                    legal_area=legal_area.value if legal_area else None,
                    top_k=3
                )
                if precedent_context:
                    context_parts.append(f"PRECEDENTES JUDICIALES RELEVANTES:\n{precedent_context}")
            except Exception:
                pass  # Silencioso si falla búsqueda de precedentes

        return "\n\n---\n\n".join(context_parts)

    except Exception as e:
        return f"Error al recuperar contexto: {str(e)}"


def get_chat_history(session_id: int, limit: int = 10) -> list[dict]:
    db = SessionLocal()
    try:
        messages = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(limit).all()

        return [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in reversed(messages)
        ]
    finally:
        db.close()


def create_chat_session(matter_id: int, organization_id: int, user_id: int, title: str | None = None) -> ChatSession:
    db = SessionLocal()
    try:
        session = ChatSession(
            organization_id=organization_id,
            matter_id=matter_id,
            user_id=user_id,
            title=title or f"Chat - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        db.add(session)
        db.commit()

        session_id = session.id

        system_message = ChatMessage(
            chat_session_id=session_id,
            role="system",
            content="Sesión de chat iniciada. El asistente está listo para responder preguntas sobre los documentos del caso.",
            model_provider=settings.LLM_PROVIDER,
            model_name=settings.LLM_MODEL
        )
        db.add(system_message)
        db.commit()

        db.refresh(session)
        return session
    finally:
        db.close()


def get_session_messages(session_id: int) -> list[ChatMessage]:
    db = SessionLocal()
    try:
        messages = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()
        return messages
    finally:
        db.close()


def generate_chat_response(
    session_id: int,
    matter_id: int,
    organization_id: int,
    user_message: str,
    matter_type: str | None = None,
    legal_area_override: LegalArea | None = None,
    user_id: int | None = None,
) -> tuple[str, dict | None]:
    from app.services.llm import get_llm_provider

    # Determinar área legal a usar
    if legal_area_override is not None:
        legal_area = legal_area_override
    elif matter_type:
        legal_area = MATTER_TYPE_TO_LEGAL_AREA.get(matter_type.lower(), LegalArea.OTHER)
    else:
        legal_area = None

    context = get_relevant_context(
        matter_id, organization_id, user_message,
        top_k=5, legal_area=legal_area
    )

    provider = get_llm_provider()

    base_system_prompt = get_chat_system_prompt(matter_type, context, user_message, legal_area=legal_area)

    # Harvey-grade persistent memory: inject user facts + case snapshot if
    # we can identify the user. Failure to load memory is non-fatal — the
    # chat still works, it just forgets.
    memory_block = ""
    if user_id is not None:
        try:
            from app.services import memory as memory_service

            mem_db = SessionLocal()
            try:
                memory_block = memory_service.inject_into_prompt(
                    mem_db,
                    organization_id=organization_id,
                    user_id=user_id,
                    matter_id=matter_id,
                )
            finally:
                mem_db.close()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("memory.inject_into_prompt failed: %s", exc)

    system_prompt = (
        f"{memory_block}\n\n{base_system_prompt}" if memory_block else base_system_prompt
    )

    history = get_chat_history(session_id, limit=5)
    conversation = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])

    full_prompt = f"""Conversación anterior:
{conversation}

Nueva pregunta del usuario: {user_message}

Responde basándote únicamente en el contexto proporcionado arriba."""

    try:
        response = provider.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.5
        )

        return response, None

    except Exception as e:
        return f"Error al generar respuesta: {str(e)}", {"error": str(e)}


def save_chat_message(
    session_id: int,
    role: str,
    content: str,
    metadata: dict | None = None
) -> dict:
    """Guarda un mensaje de chat y retorna un dict con los valores necesarios."""
    db = SessionLocal()
    try:
        message = ChatMessage(
            chat_session_id=session_id,
            role=role,
            content=content,
            model_provider=settings.LLM_PROVIDER if role == "assistant" else None,
            model_name=settings.LLM_MODEL if role == "assistant" else None,
            metadata=metadata
        )
        db.add(message)
        db.commit()

        # Capture values before expunge
        result = {
            "id": message.id,
            "chat_session_id": message.chat_session_id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
            "model_provider": message.model_provider,
            "model_name": message.model_name,
        }

        # Update session timestamp
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = datetime.utcnow()
            db.commit()

        return result
    finally:
        db.close()


SNAPSHOT_MIN_MESSAGES = 4


def maybe_update_case_snapshot(
    session_id: int,
    last_assistant_message_id: int,
) -> None:
    """Refresh the rolling case_context_snapshot for the matter that owns
    this chat session. Runs as a fire-and-forget background task after
    each assistant message — does not block the streaming response.

    The snapshot generation is one extra LLM call. We only trigger it
    once the session has at least SNAPSHOT_MIN_MESSAGES (two full turns)
    so we are not spending tokens on a one-shot Q&A.

    All errors are logged and swallowed; if the snapshot update fails
    the chat must keep working.
    """
    from app.models.chat import ChatSession
    from app.services import memory as memory_service
    from app.services.llm import get_llm_provider

    own_db = SessionLocal()
    try:
        session = (
            own_db.query(ChatSession)
            .filter(ChatSession.id == session_id)
            .first()
        )
        if session is None:
            return
        matter_id = session.matter_id
        organization_id = session.organization_id

        msg_count = (
            own_db.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == session_id)
            .count()
        )
        if msg_count < SNAPSHOT_MIN_MESSAGES:
            return

        history = (
            own_db.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        transcript_lines = [
            f"{m.role.upper()}: {m.content}" for m in history[-20:]
        ]
        transcript = "\n".join(transcript_lines)

        prompt = (
            "Resume esta conversación legal en UNA sola frase ejecutiva (máx 30 palabras) "
            "y lista hasta 3 preguntas que el usuario aún no ha resuelto. "
            "Responde en JSON con el formato:\n"
            '{"summary": "...", "open_questions": ["...", "..."]}\n\n'
            f"TRANSCRIPCIÓN:\n{transcript[:6000]}"
        )

        provider = get_llm_provider()
        raw = provider.generate(
            prompt=prompt,
            system_prompt=(
                "Eres un asistente que produce resúmenes breves y precisos "
                "de conversaciones legales chilenas. Responde SOLO con JSON válido."
            ),
            max_tokens=400,
            temperature=0.2,
        )
        parsed = _safe_json_loads(raw)
        if not parsed:
            logger.warning("snapshot: LLM did not return parseable JSON")
            return
        summary = parsed.get("summary") or ""
        open_questions = parsed.get("open_questions") or []
        if not isinstance(open_questions, list):
            open_questions = []
        if not summary:
            return
        memory_service.update_case_snapshot(
            own_db,
            organization_id=organization_id,
            matter_id=matter_id,
            summary=summary[:1000],
            key_entities={},
            open_questions=[str(q)[:300] for q in open_questions[:8]],
            last_chat_message_id=last_assistant_message_id,
        )
        logger.info(
            "snapshot updated: matter=%s session=%s v=%s",
            matter_id, session_id, _current_snapshot_version(own_db, matter_id, organization_id),
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("maybe_update_case_snapshot failed: %s", exc)
    finally:
        own_db.close()


def _safe_json_loads(raw: str | None) -> dict | None:
    import json as _json
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        first_newline = text.find("\n")
        last_fence = text.rfind("```")
        if first_newline != -1 and last_fence != -1:
            text = text[first_newline + 1 : last_fence].strip()
    try:
        result = _json.loads(text)
        return result if isinstance(result, dict) else None
    except _json.JSONDecodeError:
        # Fallback: try to find a JSON object inside the response.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                result = _json.loads(text[start : end + 1])
                return result if isinstance(result, dict) else None
            except _json.JSONDecodeError:
                return None
        return None


def _current_snapshot_version(db, matter_id: int, organization_id: int) -> int | None:
    from app.models.memory import CaseContextSnapshot
    snap = (
        db.query(CaseContextSnapshot)
        .filter(
            CaseContextSnapshot.organization_id == organization_id,
            CaseContextSnapshot.matter_id == matter_id,
        )
        .first()
    )
    return snap.version if snap is not None else None
