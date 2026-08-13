"""
Análisis Estructurado de Documentos - Estilo Harvey.ai

Este módulo analiza documentos legales y extrae datos estructurados SIN resumir.
El contenido completo permanece accesible, pero organizado y searchable.
"""

import json
import logging
from datetime import datetime

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


# Schema para análisis estructurado
DOCUMENT_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "description": "Tipo de documento detectado"
        },
        "participants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Razón social de la empresa o entidad"},
                    "rut": {"type": "string", "description": "RUT de la empresa (ej: 76.123.456-7)"},
                    "representative": {"type": "string", "description": "Nombre del representante legal"},
                    "representative_rut": {"type": "string", "description": "RUT del representante legal"},
                    "role": {"type": "string", "description": "Rol: 'contratante', 'contratista', 'proveedor', 'cliente', etc."},
                    "verified": {"type": "boolean"}
                }
            }
        },
        "financial_terms": {
            "type": "object",
            "properties": {
                "dates": {"type": "array", "items": {"type": "string"}},
                "amounts": {"type": "array", "items": {"type": "string"}},
                "terms": {"type": "array", "items": {"type": "string"}}
            }
        },
        "obligations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "party": {"type": "string"},
                    "type": {"type": "string"},
                    "description": {"type": "string"}
                }
            }
        },
        "clauses_by_type": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "unusual_clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause": {"type": "string"},
                    "risk_level": {"type": "string"},
                    "explanation": {"type": "string"},
                    "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "recommendation": {"type": "string"}
                }
            }
        },
        "legal_references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "article": {"type": "string"},
                    "context": {"type": "string"}
                }
            }
        },
        "summary": {
            "type": "string",
            "description": "Resumen ejecutivo breve (max 200 palabras)"
        },
        "risk_assessment": {
            "type": "array",
            "description": "Evaluación detallada de riesgo por cláusula",
            "items": {
                "type": "object",
                "properties": {
                    "clause_type": {"type": "string", "description": "Tipo de cláusula: penalidad, terminacion, garantia, confidencialidad, etc."},
                    "clause_text": {"type": "string", "description": "Texto exacto de la cláusula relevante"},
                    "risk_level": {"type": "string", "enum": ["high", "medium", "low"], "description": "Nivel de riesgo: HIGH (≥70), MEDIUM (40-69), LOW (<40)"},
                    "risk_score": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Score de 0-100"},
                    "explanation": {"type": "string", "description": "Por qué esta cláusula es riesgosa"},
                    "industry_standard": {"type": "string", "description": "Cuál es el estándar en contratos similares en Chile"},
                    "recommendation": {"type": "string", "description": "Qué debería negociarse para reducir el riesgo"},
                    "suggested_clause": {"type": "string", "description": "Texto alternativo sugerido más equilibrado"}
                }
            }
        },
        "contract_timeline": {
            "type": "array",
            "description": "Línea de tiempo de fechas clave del contrato",
            "items": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "Nombre del evento (ej: Inicio del contrato, Término, Aviso previo)"},
                    "date": {"type": "string", "description": "Fecha exacta o referencia (ej: 15 de marzo de 2024, o Día 30 desde la firma)"},
                    "days_from_signing": {"type": "integer", "description": "Días desde la firma del contrato"},
                    "type": {"type": "string", "description": "Tipo: inicio, termino, aviso, renovacion, garantia, pago, firma, plazo_sin_penalidad"},
                    "description": {"type": "string", "description": "Descripción del evento y su implicancia"},
                    "consequence": {"type": "string", "description": "Consecuencia si no se cumple a tiempo. Si no hay penalidad contractual explícita, indica 'Sin penalidad contractual'"},
                    "legal_reference": {"type": "string", "description": "Referencia legal aplicable (ej: Artículo 177 Código del Trabajo)"}
                }
            }
        }
    }
}


PROMPT_ANALYSIS = """Eres un asistente legal chileno especializado en análisis documental estilo Harvey.ai.

Tu función es ANALIZAR y ESTRUCTURAR el documento, NO resumirlo.
Todo el contenido relevante debe permanecer, organizado por categorías.

INSTRUCCIONES:
1. IDENTIFICA a todos los participantes del contrato:
   - IMPORTANTE: El campo "company" es la RAZÓN SOCIAL de la empresa (ej: "Agrícola Ariztía Ltda"), NO el nombre de una persona
   - El campo "representative" es el NOMBRE de la persona que representa a la empresa
   - Si el contrato dice "entre [Empresa A] y [Empresa B]", cada una tiene su propia entrada con company=razón social
   - Si aparece "Representante: Juan Pérez", esa persona es el representative de la empresa mencionada
   - Para CADA parte del contrato extraer OBLIGATORIAMENTE estos campos:
     * "company": Nombre de la empresa (razón social completa, ej: "Agrícola Ariztía Ltda" o "Servicios ABC SpA")
     * "rut": RUT de la empresa (ej: "76.123.456-7")
     * "representative": Nombre de la persona representante (ej: "Cristian Guerra") - DEJAR VACÍO "" si no hay
     * "representative_rut": RUT de la persona (ej: "12.345.678-9") - DEJAR VACÍO "" si no hay
     * "role": "contratante" o "contratista" (basado en quién paga o quién provee el servicio)
   - NO pongas el nombre de la empresa en el campo "representative"
   - NO mezcles roles: si alguien es "Representante del Contratista", el role="contratista" y company es la empresa que representa
2. EXTRAE términos financieros (fechas, montos, plazos)
3. CATALOGA las cláusulas por tipo (penales, terminación, garantías, confidencialidad, etc.)
4. EVALUA cada cláusula importante con SCORING DE RIESGO (0-100):
   - HIGH (70-100): Cláusula muy desfavorable, requiere atención inmediata
   - MEDIUM (40-69): Cláusula riesgosa, debería negociarse
   - LOW (0-39): Cláusula razonable o favorable
5. COMPARA con estándares del sector en Chile
6. PROPORCIONA recomendación concreta de negociación
7. SUGIERE texto alternativo cuando sea posible
8. LISTA las referencias legales citadas en el texto
9. IDENTIFICA fechas clave del contrato (inicio, término, plazos de aviso, renovaciones, pagos, límites para firma)
   - IMPORTANTE: Detecta TODAS las fechas límite aunque NO tengan penalización contractual explícita
   - Si el contrato dice "debe firmarse antes del [fecha]" sin consecuencias, igual incluye la alerta
   - Usa type="firma" para límites de firma sin penalidad
   - Usa type="plazo_sin_penalidad" para plazos que vencen sin penalización
   - En consequence, indica "Sin penalidad contractual" si no hay castigo definido
10. GENERA un resumen ejecutivo BREVE (max 200 palabras)

CRITERIOS DE EVALUACIÓN EN CHILE:
- Contratos laborales: Código del Trabajo Chile, fuero maternal, jornada, remuneration
- Contratos comerciales: Código de Comercio, responsabilidad, penalidades usuales 1-5%
- Contratos de arriendo: Ley 18.101, plazos mínimos, incremento máximo
- Contratos de consumo: Ley 19.496, cláusulas abusivas, derecho a retracto

FORMATO JSON:
- participants: Array con las empresas del contrato
  EJEMPLO CORRECTO:
  [{"company": "Agrícola Ariztía Ltda", "rut": "76.123.456-7", "representative": "", "representative_rut": "", "role": "contratante"},
   {"company": "Servicios ABC SpA", "rut": "77.987.654-3", "representative": "Cristian Guerra", "representative_rut": "76.324.018-5", "role": "contratista"}]
- financial_terms: {dates: [], amounts: [], terms: []}
- obligations: [{party, type, description}]
- clauses_by_type: {penalidades: [], terminacion: [], garantias: [], confidencialidad: [], etc.}
- unusual_clauses: [{clause, risk_level, explanation, risk_score, recommendation}]
- legal_references: [{article, context}]
- summary: resumen breve
- risk_assessment: [{clause_type, clause_text, risk_level, risk_score, explanation, industry_standard, recommendation, suggested_clause}]
- contract_timeline: [{event, date, days_from_signing, type, description, consequence, legal_reference}]

El texto del documento es:
{text}

Responde SOLO con JSON válido."""


def get_document_chunks_text(document_id: int) -> str:
    """Obtiene todo el texto del documento desde los chunks."""
    db = SessionLocal()
    try:
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).order_by(DocumentChunk.chunk_index).all()

        return "\n\n---\n\n".join([c.content for c in chunks])
    finally:
        db.close()


def get_rag_context_for_document_type(document_type: str, organization_id: int) -> str:
    """Obtiene contexto legal relevante usando RAG según el tipo de documento."""
    try:
        from app.models.legal_area import LegalArea
        from app.services.rag import hybrid_search

        # Mapear tipo de documento a área legal y query de búsqueda
        type_to_query = {
            "contract": "cláusulas contractuales Chile responsabilidad penalidades términos",
            "labor": "contrato de trabajo Chile fuero jornada remuneración termination",
            "lease": "contrato de arriendo Chile ley 18.101 plazos incremento",
            "consumer": "protección al consumidor Chile cláusulas abusivas derechos",
            "company": "contrato comercial Chile sociedad responsabilidad Code Comercio",
            "unknown": "contrato Chile obligaciones partes"
        }

        query = type_to_query.get(document_type, type_to_query["unknown"])

        # Mapear a área legal
        type_to_legal_area = {
            "contract": "civil",
            "labor": "labor",
            "lease": "civil",
            "consumer": "consumer",
            "company": "commerce"
        }
        legal_area_str = type_to_legal_area.get(document_type, "civil")
        legal_area = LegalArea(legal_area_str) if legal_area_str in [e.value for e in LegalArea] else None

        # Hacer búsqueda RAG
        results = hybrid_search(
            query=query,
            organization_id=organization_id,
            matter_id=0,  # No matter específico para contexto general
            top_k=3,
            include_laws=True,
            legal_area=legal_area
        )

        if not results:
            return ""

        # Construir contexto
        context_parts = ["\n\nCONTEXTO LEGAL RELEVANTE (leyes chilenas):\n"]
        for i, r in enumerate(results[:3], 1):
            content = r.get("content", "")[:500]  # Limitar a 500 chars
            source = r.get("source", "document")
            law_ref = r.get("law_title", "")
            context_parts.append(f"{i}. [{source.upper()}] {law_ref}: {content}...")

        return "\n".join(context_parts)

    except Exception as e:
        logger.debug(f"Error getting RAG context: {e}")  # S4-05
        return ""


def analyze_document_full(document_id: int) -> DocumentAnalysis:
    """Analiza un documento y genera estructura estilo Harvey.ai.

    S4-08: previously a single 166-line function with three side-effects
    blocks (LLM call, deadline alerts, clause comparison) and three
    error-swallowing try/except. Now each stage is its own helper and
    the top-level reads as a linear pipeline.
    """
    db = SessionLocal()
    try:
        document = _load_document_for_analysis(document_id)
        extracted_text = _normalize_extracted_text(document)

        rag_context = get_rag_context_for_document_type(
            document.detected_document_type or "unknown",
            document.organization_id,
        )
        prompt = _build_analysis_prompt(extracted_text, rag_context)

        # Persist or update the analysis row once with a base shape; the
        # downstream enrichment steps (deadlines, clauses) can keep
        # writing to the same row without recreating it.
        analysis = _get_or_create_analysis(db, document_id, document)

        result = _call_llm_with_fallback(document, prompt)
        _persist_analysis_result(analysis, result)

        db.commit()
        db.refresh(analysis)

        # Downstream enrichments are best-effort — failure of one
        # shouldn't roll back the analysis itself.
        try:
            _enrich_with_deadline_alerts(document_id)
        except Exception as exc:
            logger.warning(
                f"Deadline alerts enrichment failed for {document_id}: {exc}"
            )
        try:
            _enrich_with_clause_comparisons(analysis, result, document)
            db.commit()
        except Exception as exc:
            logger.warning(
                f"Clause comparison enrichment failed for {document_id}: {exc}"
            )
        _attach_markdown_metadata(analysis, document)
        db.commit()

        return analysis
    finally:
        db.close()


# ---------------------------------------------------------------------------
# S4-08: analyze_document_full pipeline helpers
# ---------------------------------------------------------------------------
def _load_document_for_analysis(document_id: int) -> Document:
    """Return the document row or raise ValueError when missing or empty.

    Empty extracted_text is treated as "not yet analyzed" — the caller
    surfaces that as a 400 in the endpoint layer.
    """
    db = SessionLocal()
    try:
        document = (
            db.query(Document).filter(Document.id == document_id).first()
        )
    finally:
        db.close()
    if not document:
        raise ValueError(f"Documento {document_id} no encontrado")
    if not document.extracted_text:
        raise ValueError("El documento no tiene texto extraído aún")
    return document


def _normalize_extracted_text(document: Document) -> str:
    """Coerce extracted_text to string (defensive: column is JSON-backed)."""
    return str(document.extracted_text) if document.extracted_text else ""


def _build_analysis_prompt(extracted_text: str, rag_context: str | None) -> str:
    """Inject the document text (truncated to 50k chars) and optional RAG
    context into the analysis prompt template.
    """
    truncated = extracted_text[:50_000] if extracted_text else ""
    base_prompt = PROMPT_ANALYSIS.replace("{text}", truncated)
    if rag_context:
        return base_prompt.replace(
            "El texto del documento es:",
            f"{rag_context}\n\nEl texto del documento es:",
        )
    return base_prompt


def _call_llm_with_fallback(document: Document, prompt: str) -> dict:
    """Return the LLM-generated structured dict, or a graceful empty
    shape when the provider fails. Failure is logged but never raised
    because downstream code always needs SOMETHING to persist.
    """
    from app.services.llm import get_llm_provider

    try:
        provider = get_llm_provider()
        return provider.generate_structured(prompt, "", DOCUMENT_ANALYSIS_SCHEMA)
    except Exception as exc:
        logger.warning(
            f"LLM analysis failed for doc {document.id}: {exc}; "
            "persisting empty shape"
        )
        return _empty_analysis_result(document)


def _empty_analysis_result(document: Document) -> dict:
    """Last-resort structure when the LLM call fails. Keeps the JSON
    schema consistent so downstream consumers can rely on the shape.
    """
    return {
        "document_type": document.detected_document_type or "unknown",
        "participants": [],
        "financial_terms": {"dates": [], "amounts": [], "terms": []},
        "obligations": [],
        "clauses_by_type": {},
        "unusual_clauses": [],
        "legal_references": [],
        "risk_assessment": [],
        "contract_timeline": [],
        "summary": "",
    }


def _get_or_create_analysis(db, document_id: int, document: Document) -> DocumentAnalysis:
    """Return the existing DocumentAnalysis row or create one with sane defaults."""
    analysis = (
        db.query(DocumentAnalysis)
        .filter(DocumentAnalysis.document_id == document_id)
        .first()
    )
    if analysis is None:
        analysis = DocumentAnalysis(
            document_id=document_id,
            organization_id=document.organization_id,
        )
        db.add(analysis)
    return analysis


def _persist_analysis_result(analysis: DocumentAnalysis, result: dict) -> None:
    """Apply the LLM dict to the row. JSON columns are encoded here so
    the schema/export logic stays consistent.
    """
    analysis.document_type = result.get(
        "document_type", analysis.document_type or "unknown"
    )
    analysis.participants = json.dumps(result.get("participants", []))
    analysis.financial_terms = json.dumps(result.get("financial_terms", {}))
    analysis.obligations = json.dumps(result.get("obligations", []))
    analysis.clauses_by_type = json.dumps(result.get("clauses_by_type", {}))
    analysis.unusual_clauses = json.dumps(result.get("unusual_clauses", []))
    analysis.risk_assessment = json.dumps(result.get("risk_assessment", []))
    analysis.contract_timeline = json.dumps(result.get("contract_timeline", []))
    analysis.legal_references = json.dumps(result.get("legal_references", []))
    analysis.indexed_content = result.get("summary", "")


def _enrich_with_deadline_alerts(document_id: int) -> None:
    """Generate deadline alerts derived from contract_timeline."""
    from app.services.deadline_generator import generate_alerts_from_document

    alert_ids = generate_alerts_from_document(document_id)
    logger.info(
        f"Generated {len(alert_ids)} deadline alerts for document {document_id}"
    )


def _enrich_with_clause_comparisons(
    analysis: DocumentAnalysis, result: dict, document: Document
) -> None:
    """Compare clauses against the template library and append major/critical
    deviations to ``unusual_clauses``.
    """
    clauses_by_type = result.get("clauses_by_type", {})
    if not clauses_by_type:
        return
    from app.services.clause_comparator import (
        compare_contract_clauses_to_templates,
    )

    contract_type = document.detected_document_type or "contract_review"
    deviations = compare_contract_clauses_to_templates(
        clauses_by_type, contract_type
    )
    if not deviations:
        return

    logger.info(
        f"Found {len(deviations)} clause deviations in document {document.id}"
    )

    unusual = list(result.get("unusual_clauses", []))
    for deviation in deviations:
        level = deviation.get("deviation_level")
        if level not in {"major", "critical"}:
            continue
        unusual.append({
            "type": "template_deviation",
            "clause_type": deviation.get("clause_type"),
            "clause": deviation.get("clause_text"),
            "risk_level": "medium" if level == "major" else "high",
            "explanation": deviation.get("description"),
            "risk_score": 60 + deviation.get("risk_score_adjustment", 0),
            "recommendation": (
                f"Revisar vs estándar: {deviation.get('industry_default')}"
            ),
            "industry_standard": deviation.get("standard_clause"),
            "deviation_level": level,
        })
    analysis.unusual_clauses = json.dumps(unusual)


def _attach_markdown_metadata(analysis: DocumentAnalysis, document: Document) -> None:
    """Render the analysis to markdown and record filename + size in metadata
    so the export endpoint can serve it later without recomputing.
    """
    from app.services.markdown_generator import (
        analysis_to_markdown,
        generate_document_markdown_filename,
    )

    markdown_content = analysis_to_markdown(analysis, document)
    filename = generate_document_markdown_filename(document)

    raw_metadata = analysis.analysis_metadata
    if isinstance(raw_metadata, str):
        metadata = json.loads(raw_metadata) if raw_metadata else {}
    elif isinstance(raw_metadata, dict):
        metadata = raw_metadata
    else:
        metadata = {}

    metadata["markdown_filename"] = filename
    metadata["markdown_generated_at"] = datetime.utcnow().isoformat()
    metadata["markdown_size"] = len(markdown_content)
    analysis.analysis_metadata = metadata
    logger.info(
        f"Generated markdown for document {document.id}: {filename}"
    )



def get_document_analysis(document_id: int) -> DocumentAnalysis | None:
    """Obtiene el análisis de un documento si existe."""
    db = SessionLocal()
    try:
        return db.query(DocumentAnalysis).filter(
            DocumentAnalysis.document_id == document_id
        ).first()
    finally:
        db.close()


def get_all_participants_from_matter(matter_id: int) -> list[dict]:
    """Extrae todos los participantes de todos los documentos de un matter."""
    db = SessionLocal()
    try:
        # Obtener análisis de todos los documentos del matter
        analyses = db.query(DocumentAnalysis).join(Document).filter(
            Document.matter_id == matter_id
        ).all()

        all_participants = []
        seen_ruts = set()

        for analysis in analyses:
            participants = json.loads(analysis.participants) if analysis.participants else []
            for p in participants:
                rut = p.get("rut")
                if rut and rut not in seen_ruts:
                    seen_ruts.add(rut)
                    p["documents"] = [analysis.document_id]
                    all_participants.append(p)
                elif rut in seen_ruts:
                    # Agregar documento al participante existente
                    for existing in all_participants:
                        if existing.get("rut") == rut:
                            existing["documents"].append(analysis.document_id)

        return all_participants
    finally:
        db.close()
