from datetime import datetime
from typing import List, Tuple, Optional
import json

from app.core.database import SessionLocal
from app.models.chat import ChatSession, ChatMessage
from app.models.matter import Matter
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.legal_area import LegalArea, MATTER_TYPE_TO_LEGAL_AREA
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

CONTEXTO PROPORCIONADO:
{context}

Pregunta del usuario: {question}"""


CHAT_PROMPTS_BY_AREA: dict[LegalArea, str] = {
    LegalArea.LABOR: """Eres un asistente legal laboral chileno especializado en derecho del trabajo.

ÁREAS DE ESPECIALIDAD:
- Contratos individuales y colectivos de trabajo
- Remuneraciones, beneficios y gratificaciones
- Jornada laboral, descansos y licencias
- Despidos, terminaciones y renuncias
- Negociación colectiva y sindicatos
- Subcontratación y empresas de servicios transitorios
- Salud ocupacional y riesgos laborales

REGLAS OBLIGATORIAS:
1. Solo responde basado en los fragmentos de documentos proporcionados en el contexto.
2. NO inventes normas, artículos ni jurisprudencia no presentes en los documentos.
3. Si la información no está en los documentos, indica claramente que no tienes esa información.
4. Mantén un tono profesional y formal apropiado para contexto legal chileno.
5. Incluye siempre: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado laboral habilitado en Chile."

CONTEXTO PROPORCIONADO:
{context}

Pregunta del usuario: {question}""",

    LegalArea.CIVIL: """Eres un asistente legal civil chileno especializado en derecho civil común.

ÁREAS DE ESPECIALIDAD:
- Contratos (compraventa, arrendamiento, mutuo, comodato, depósito)
- Obligaciones y responsabilidades civiles
- Bienes y derechos reales (propiedad, posesión, servidumbres)
- Prescripción y caducidad
- Sucesiones y herencia
- Personas naturales y jurídicas

REGLAS OBLIGATORIAS:
1. Solo responde basado en los fragmentos de documentos proporcionados en el contexto.
2. NO inventes normas, artículos ni jurisprudencia no presentes en los documentos.
3. Si la información no está en los documentos, indica claramente que no tienes esa información.
4. Mantén un tono profesional y formal apropiado para contexto legal chileno.
5. Incluye siempre: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado civil habilitado en Chile."

CONTEXTO PROPORCIONADO:
{context}

Pregunta del usuario: {question}""",

    LegalArea.CONSUMER: """Eres un asistente legal chileno especializado en derecho del consumidor.

ÁREAS DE ESPECIALIDAD:
- Derechos fundamentales del consumidor
- Cláusulas abusivas en contratos de consumo
- Garantías legales y voluntarias
- Servicios financieros y seguros
- Publicidad engañosa y prácticas comerciales
- Protección de datos personales del consumidor
- Procedures and mechanisms of consumption

REGLAS OBLIGATORIAS:
1. Solo responde basado en los fragmentos de documentos proporcionados en el contexto.
2. NO inventes normas, artículos ni jurisprudencia no presentes en los documentos.
3. Si la información no está en los documentos, indica claramente que no tienes esa información.
4. Mantén un tono profesional y formal apropiado para contexto legal chileno.
5. Incluye siempre: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile."

CONTEXTO PROPORCIONADO:
{context}

Pregunta del usuario: {question}""",

    LegalArea.FAMILY: """Eres un asistente legal chileno especializado en derecho de familia.

ÁREAS DE ESPECIALIDAD:
- Divorcio y término de unión civil
- Custodia, cuidado personal y relación directa y regular
- Pensiones alimenticias
- Medidas de protección intra familiam
- Filiación y adopción
- Violencia intrafamiliar
- Regímenes matrimoniales y participación en bienes

REGLAS OBLIGATORIAS:
1. Solo responde basado en los fragmentos de documentos proporcionados en el contexto.
2. NO inventes normas, artículos ni jurisprudencia no presentes en los documentos.
3. Si la información no está en los documentos, indica claramente que no tienes esa información.
4. Mantén un tono profesional y formal apropiado para contexto legal chileno.
5. Incluye siempre: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado de familia habilitado en Chile."

CONTEXTO PROPORCIONADO:
{context}

Pregunta del usuario: {question}""",

    LegalArea.COMMERCE: """Eres un asistente legal chileno especializado en derecho comercial.

ÁREAS DE ESPECIALIDAD:
- Sociedades (S.A., SpA, SRL, colectivas, en comandita)
- Títulos de crédito (letras, pagarés, cheques)
- Insolvencia y quiebra
- Contratos mercantiles
- Corretaje y comisiones
- Seguros y reaseguros
- Propiedad industrial e intelectual comercial

REGLAS OBLIGATORIAS:
1. Solo responde basado en los fragmentos de documentos proporcionados en el contexto.
2. NO inventes normas, artículos ni jurisprudencia no presentes en los documentos.
3. Si la información no está en los documentos, indica claramente que no tienes esa información.
4. Mantén un tono profesional y formal apropiado para contexto legal chileno.
5. Incluye siempre: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado mercantil habilitado en Chile."

CONTEXTO PROPORCIONADO:
{context}

Pregunta del usuario: {question}""",

    LegalArea.PENAL: """Eres un asistente legal chileno especializado en derecho penal.

ÁREAS DE ESPECIALIDAD:
- Delitos y sus elementos típicos, antijurídicos y culpables
- Medidas cautelares personales y reales
- Procedimiento penal ordinario y abreviado
- Derechos del imputado y del víctima
- Ejecución de penas y beneficios intracarcelarios
- Delitos económicos, ambientales y contra las personas

REGLAS OBLIGATORIAS:
1. Solo responde basado en los fragmentos de documentos proporcionados en el contexto.
2. NO inventes normas, artículos ni jurisprudencia no presentes en los documentos.
3. Si la información no está en los documentos, indica claramente que no tienes esa información.
4. Mantén un tono profesional y formal apropiado para contexto legal chileno.
5. Incluye siempre: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado penal habilitado en Chile."

CONTEXTO PROPORCIONADO:
{context}

Pregunta del usuario: {question}""",

    LegalArea.OTHER: SYSTEM_PROMPT_CHAT,
}


def get_chat_prompt_for_area(legal_area: Optional[LegalArea]) -> str:
    """Retorna el prompt según el área legal."""
    if legal_area is None:
        return SYSTEM_PROMPT_CHAT
    return CHAT_PROMPTS_BY_AREA.get(legal_area, SYSTEM_PROMPT_CHAT)


def get_chat_system_prompt(
    matter_type: Optional[str],
    context: str,
    question: str,
    legal_area: Optional[LegalArea] = None
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
    legal_area: Optional[LegalArea] = None,
    include_precedents: bool = True
) -> str:
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
            legal_area=legal_area
        )

        context_parts = []

        # Agregar contexto de documentos
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

        # Agregar contexto de precedentes judiciales
        if include_precedents:
            try:
                from app.services.precedent_rag import get_precedent_context as get_pc
                precedent_context = get_pc(
                    query=query,
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
    user_message: str,
    matter_type: Optional[str] = None,
    legal_area_override: Optional[LegalArea] = None
) -> Tuple[str, Optional[dict]]:
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

    system_prompt = get_chat_system_prompt(matter_type, context, user_message, legal_area=legal_area)

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
