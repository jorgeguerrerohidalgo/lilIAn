"""
Análisis Estructurado de Documentos - Estilo Harvey.ai

Este módulo analiza documentos legales y extrae datos estructurados SIN resumir.
El contenido completo permanece accesible, pero organizado y searchable.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_chunk import DocumentChunk
from app.core.config import settings

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
        from app.services.rag import hybrid_search
        from app.models.legal_area import LegalArea

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
    """Analiza un documento y genera estructura estilo Harvey.ai."""
    from app.services.llm import get_llm_provider

    db = SessionLocal()
    try:
        # Obtener documento
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Documento {document_id} no encontrado")

        # Verificar que tiene texto extraído
        if not document.extracted_text:
            raise ValueError("El documento no tiene texto extraído aún")

        # Asegurar que extracted_text es string
        extracted_text = str(document.extracted_text) if document.extracted_text else ""

        # Obtener contexto RAG basado en tipo de documento
        doc_type = document.detected_document_type or "unknown"
        rag_context = get_rag_context_for_document_type(doc_type, document.organization_id)

        # Generar análisis con LLM
        provider = get_llm_provider()
        base_prompt = PROMPT_ANALYSIS.replace("{text}", extracted_text[:50000] if extracted_text else "")

        # Incluir contexto RAG si está disponible
        if rag_context:
            prompt = base_prompt.replace(
                "El texto del documento es:",
                f"{rag_context}\n\nEl texto del documento es:"
            )
        else:
            prompt = base_prompt

        try:
            result = provider.generate_structured(prompt, "", DOCUMENT_ANALYSIS_SCHEMA)
        except Exception as e:
            # Si falla, crear análisis vacío
            result = {
                "document_type": document.detected_document_type or "unknown",
                "participants": [],
                "financial_terms": {"dates": [], "amounts": [], "terms": []},
                "obligations": [],
                "clauses_by_type": {},
                "unusual_clauses": [],
                "legal_references": [],
                "risk_assessment": [],
                "contract_timeline": [],
                "summary": f"Error en análisis: {str(e)}"
            }

        # Crear o actualizar análisis
        analysis = db.query(DocumentAnalysis).filter(
            DocumentAnalysis.document_id == document_id
        ).first()

        if not analysis:
            analysis = DocumentAnalysis(
                document_id=document_id,
                organization_id=document.organization_id
            )
            db.add(analysis)

        # Actualizar campos
        analysis.document_type = result.get("document_type", document.detected_document_type)
        analysis.participants = json.dumps(result.get("participants", []))
        analysis.financial_terms = json.dumps(result.get("financial_terms", {}))
        analysis.obligations = json.dumps(result.get("obligations", []))
        analysis.clauses_by_type = json.dumps(result.get("clauses_by_type", {}))
        analysis.unusual_clauses = json.dumps(result.get("unusual_clauses", []))
        analysis.risk_assessment = json.dumps(result.get("risk_assessment", []))
        analysis.contract_timeline = json.dumps(result.get("contract_timeline", []))
        analysis.legal_references = json.dumps(result.get("legal_references", []))
        analysis.indexed_content = result.get("summary", "")

        # Metadata
        analysis.analysis_metadata = json.dumps({
            "model": settings.LLM_MODEL,
            "analyzed_at": datetime.utcnow().isoformat()
        })

        db.commit()
        db.refresh(analysis)

        # Generate deadline alerts from contract_timeline
        try:
            from app.services.deadline_generator import generate_alerts_from_document
            import logging
            logger = logging.getLogger(__name__)
            alert_ids = generate_alerts_from_document(document_id)
            logger.info(f"Generated {len(alert_ids)} deadline alerts for document {document_id}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating deadline alerts: {e}", exc_info=True)
            pass  # Don't fail analysis if alerts fail

        # Compare clauses against templates to find deviations
        try:
            from app.services.clause_comparator import compare_contract_clauses_to_templates
            import logging
            logger = logging.getLogger(__name__)

            clauses_by_type = result.get("clauses_by_type", {})
            if clauses_by_type:
                contract_type = document.detected_document_type or "contract_review"
                deviations = compare_contract_clauses_to_templates(clauses_by_type, contract_type)
                if deviations:
                    logger.info(f"Found {len(deviations)} clause deviations in document {document_id}")

                    # Add deviations to unusual_clauses if significant
                    unusual_clauses = result.get("unusual_clauses", [])
                    for deviation in deviations:
                        if deviation.get("deviation_level") in ["major", "critical"]:
                            unusual_clauses.append({
                                "type": "template_deviation",
                                "clause_type": deviation.get("clause_type"),
                                "clause": deviation.get("clause_text"),
                                "risk_level": "medium" if deviation.get("deviation_level") == "major" else "high",
                                "explanation": deviation.get("description"),
                                "risk_score": 60 + deviation.get("risk_score_adjustment", 0),
                                "recommendation": f"Revisar vs estándar: {deviation.get('industry_default')}",
                                "industry_standard": deviation.get("standard_clause"),
                                "deviation_level": deviation.get("deviation_level")
                            })

                    # Update unusual_clauses in analysis
                    analysis.unusual_clauses = json.dumps(unusual_clauses)
                    db.commit()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error comparing clauses to templates: {e}", exc_info=True)
            pass  # Don't fail analysis if comparison fails

        # Generate and store markdown info in metadata
        try:
            from app.services.markdown_generator import analysis_to_markdown, generate_document_markdown_filename
            markdown_content = analysis_to_markdown(analysis, document)
            filename = generate_document_markdown_filename(document)
            raw_metadata = analysis.analysis_metadata
            if isinstance(raw_metadata, str):
                metadata = json.loads(raw_metadata) if raw_metadata else {}
            elif isinstance(raw_metadata, dict):
                metadata = raw_metadata
            else:
                metadata = {}
            metadata['markdown_filename'] = filename
            metadata['markdown_generated_at'] = datetime.utcnow().isoformat()
            metadata['markdown_size'] = len(markdown_content)
            analysis.analysis_metadata = metadata
            db.commit()
            logger.info(f"Generated markdown for document {document_id}: {filename}")
        except Exception as e:
            logger.warning(f"Failed to generate markdown for document {document_id}: {e}")

        return analysis

    finally:
        db.close()


def get_document_analysis(document_id: int) -> Optional[DocumentAnalysis]:
    """Obtiene el análisis de un documento si existe."""
    db = SessionLocal()
    try:
        return db.query(DocumentAnalysis).filter(
            DocumentAnalysis.document_id == document_id
        ).first()
    finally:
        db.close()


def get_all_participants_from_matter(matter_id: int) -> List[Dict]:
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
