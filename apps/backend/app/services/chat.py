from datetime import datetime
from typing import List, Tuple, Optional
import json

from app.core.database import SessionLocal
from app.models.chat import ChatSession, ChatMessage
from app.models.matter import Matter
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.core.config import settings


SYSTEM_PROMPT_CHAT = """Eres un asistente legal chileno especializado en análisis documental y apoyo jurídico preliminar.

Tu función es responder preguntas sobre los documentos del caso, basándote únicamente en la información disponible.

REGLAS OBLIGATORIAS:
1. Solo responde basado en los fragmentos de documentos proporcionados en el contexto.
2. NO inventes normas, artículos, jurisprudencia ni hechos no presentes en los documentos.
3. Si la información no está en los documentos proporcionados, indica claramente que no tienes esa información.
4. Si detectas riesgos relevantes en la información, recomiéndanos revisión profesional humana.
5. Cuando cites información de un documento, indica de cuál documento proviene.
6. Mantén un tono profesional y formal apropiado para contexto legal chileno.
7. Incluye siempre la advertencia: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile."

CONtexto PROPORCIONADO:
{context}

Pregunta del usuario: {question}"""


def get_relevant_context(matter_id: int, organization_id: int, query: str, top_k: int = 5) -> str:
    from app.services.rag import hybrid_search
    from app.services.embeddings import get_embedding_provider

    try:
        provider = get_embedding_provider()
        query_embedding = provider.generate_embedding(query)

        results = hybrid_search(
            query=query,
            organization_id=organization_id,
            matter_id=matter_id,
            top_k=top_k,
            embedding_weight=0.7
        )

        if not results:
            return "No se encontró información relevante en los documentos del caso."

        context_parts = []
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

        return "\n\n---\n\n".join(context_parts)

    except Exception as e:
        return f"Error al recuperar contexto: {str(e)}"


def get_chat_history(session_id: int, limit: int = 10) -> List[dict]:
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


def create_chat_session(matter_id: int, organization_id: int, user_id: int, title: Optional[str] = None) -> ChatSession:
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
        db.refresh(session)

        system_message = ChatMessage(
            chat_session_id=session.id,
            role="system",
            content="Sesión de chat iniciada. El asistente está listo para responder preguntas sobre los documentos del caso.",
            model_provider=settings.LLM_PROVIDER,
            model_name=settings.LLM_MODEL
        )
        db.add(system_message)
        db.commit()

        return session
    finally:
        db.close()


def get_session_messages(session_id: int) -> List[ChatMessage]:
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
    user_message: str
) -> Tuple[str, Optional[dict]]:
    from app.services.llm import get_llm_provider

    context = get_relevant_context(matter_id, organization_id, user_message)

    provider = get_llm_provider()

    system_prompt = SYSTEM_PROMPT_CHAT.format(context=context, question=user_message)

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
    metadata: Optional[dict] = None
) -> ChatMessage:
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
        db.refresh(message)

        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = datetime.utcnow()
            db.commit()

        return message
    finally:
        db.close()
