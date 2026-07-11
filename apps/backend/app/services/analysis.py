from datetime import datetime
from typing import List, Dict, Any, Optional
import json

from app.core.database import SessionLocal
from app.models.analysis_report import AnalysisReport
from app.models.risk_item import RiskItem
from app.models.matter import Matter
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.core.config import settings


SYSTEM_PROMPT_CONTRACT_REVIEW = """Eres un asistente legal chileno especializado en análisis documental y revisión de contratos.

Tu función es asistir en el análisis preliminar de documentos legales, identificando riesgos, obligaciones y cláusulas relevantes.

REGLAS OBLIGATORIAS:
1. Solo analiza basado en la información proporcionada en los documentos.
2. NO inventes normas, artículos, jurisprudencia ni antecedentes.
3. Si no encuentras información suficiente, indícalo claramente.
4. Si detectas riesgos relevantes, recomiéndanos revisión profesional humana.
5. Clasifica los riesgos en: verde (sin alerta), amarillo (requiere revisión), rojo (riesgo alto), gris (info insuficiente).
6. Toda respuesta debe incluir la advertencia: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile."

FORMATO DE SALIDA:
- Resumen ejecutivo del contrato.
- Partes identificadas.
- Obligaciones principales.
- Fechas y plazos relevantes.
- Montos mencionados.
- Riesgos detectados con su nivel.
- Cláusulas relevantes.
- Información faltante.
- Preguntas sugeridas.
- Próximos pasos.
"""

SYSTEM_PROMPT_GENERAL = """Eres un asistente legal chileno especializado en análisis preliminar de casos legales.

Tu función es asistir en la organización de antecedentes, identificación de riesgos y preparación para revisión profesional.

REGLAS OBLIGATORIAS:
1. Solo analiza basado en la información proporcionada.
2. NO inventes hechos, normas ni jurisprudencia.
3. Si falta información, indícalo claramente.
4. Si detectas riesgos relevantes, recomiéndanos revisión profesional humana.
5. Clasifica los riesgos en: verde, amarillo, rojo o gris según corresponda.
6. Incluye siempre la advertencia legal estándar.

El análisis debe ser claro, estructurado y útil tanto para el cliente como para el abogado que revisará el caso."""


RISK_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Resumen ejecutivo del análisis"},
        "document_type": {"type": "string", "description": "Tipo de documento identificado"},
        "parties": {"type": "array", "items": {"type": "string"}, "description": "Partes identificadas"},
        "key_obligations": {"type": "array", "items": {"type": "string"}, "description": "Obligaciones principales"},
        "dates_and_deadlines": {"type": "array", "items": {"type": "string"}, "description": "Fechas y plazos relevantes"},
        "amounts": {"type": "array", "items": {"type": "string"}, "description": "Montos mencionados"},
        "relevant_clauses": {"type": "array", "items": {"type": "string"}, "description": "Cláusulas relevantes"},
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["green", "yellow", "red", "gray"]},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "source_fragment": {"type": "string"},
                    "impact": {"type": "string"},
                    "recommendation": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
                }
            }
        },
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
    },
    "required": ["summary", "risks"]
}


def get_documents_text_for_analysis(matter_id: int, organization_id: int) -> str:
    db = SessionLocal()
    try:
        documents = db.query(Document).filter(
            Document.matter_id == matter_id,
            Document.organization_id == organization_id,
            Document.status == "processed"
        ).all()

        text_parts = []
        for doc in documents:
            if doc.extracted_text:
                text_parts.append(f"=== Documento: {doc.original_filename} ===\n{doc.extracted_text}")

        return "\n\n".join(text_parts)
    finally:
        db.close()


def get_chunks_text_for_analysis(matter_id: int, organization_id: int, max_chars: int = 50000) -> str:
    db = SessionLocal()
    try:
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.matter_id == matter_id,
            DocumentChunk.organization_id == organization_id
        ).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).all()

        text_parts = []
        total_chars = 0
        for chunk in chunks:
            if total_chars + len(chunk.content) <= max_chars:
                text_parts.append(chunk.content)
                total_chars += len(chunk.content)
            else:
                break

        return "\n\n---\n\n".join(text_parts)
    finally:
        db.close()


def analyze_contract(documents_text: str, matter_type: str) -> dict:
    from app.services.llm import get_llm_provider

    if not documents_text or len(documents_text.strip()) < 100:
        return {
            "error": "No hay suficiente texto para analizar",
            "summary": "Información insuficiente para realizar análisis.",
            "risks": [],
            "confidence": "low"
        }

    provider = get_llm_provider()

    system_prompt = SYSTEM_PROMPT_CONTRACT_REVIEW if matter_type == "contract_review" else SYSTEM_PROMPT_GENERAL

    prompt = f"""Analiza el siguiente documento legal y proporciona un informe estructurado según el esquemaJSON solicitado.

DOCUMENTO:
{documents_text[:30000]}

Proporciona el análisis en formato JSON siguiendo exactamente el esquema especificado."""

    try:
        result = provider.generate_structured(prompt, system_prompt, RISK_ANALYSIS_SCHEMA)
        return result
    except Exception as e:
        return {
            "error": str(e),
            "summary": f"Error al generar análisis: {str(e)}",
            "risks": [],
            "confidence": "low"
        }


def create_analysis_report(
    matter_id: int,
    organization_id: int,
    user_id: int,
    analysis_result: dict
) -> AnalysisReport:
    db = SessionLocal()
    try:
        report = AnalysisReport(
            organization_id=organization_id,
            matter_id=matter_id,
            generated_by_user_id=user_id,
            model_provider=settings.LLM_PROVIDER,
            model_name=settings.LLM_MODEL,
            report_type="preliminary_case_analysis",
            summary=analysis_result.get("summary", ""),
            facts=json.dumps(analysis_result.get("facts", [])),
            missing_information=json.dumps(analysis_result.get("missing_information", [])),
            next_steps=json.dumps(analysis_result.get("next_steps", [])),
            disclaimer="Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile.",
            confidence=analysis_result.get("confidence", "medium"),
            status="generated"
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        risks = analysis_result.get("risks", [])
        for risk_data in risks:
            risk = RiskItem(
                analysis_report_id=report.id,
                matter_id=matter_id,
                organization_id=organization_id,
                level=risk_data.get("level", "gray"),
                title=risk_data.get("title", "Riesgo sin título"),
                description=risk_data.get("description"),
                source_fragment=risk_data.get("source_fragment"),
                impact=risk_data.get("impact"),
                recommendation=risk_data.get("recommendation"),
                confidence=risk_data.get("confidence", "medium"),
                review_status="pending"
            )
            db.add(risk)

        matter = db.query(Matter).filter(Matter.id == matter_id).first()
        if matter:
            matter.status = "analysis_ready"

        db.commit()
        db.refresh(report)

        return report

    finally:
        db.close()


def generate_analysis_for_matter(matter_id: int, organization_id: int, user_id: int) -> dict:
    db = SessionLocal()
    try:
        matter = db.query(Matter).filter(
            Matter.id == matter_id,
            Matter.organization_id == organization_id
        ).first()

        if not matter:
            return {"error": "Caso no encontrado"}

        matter.status = "processing"
        db.commit()

        documents_text = get_chunks_text_for_analysis(matter_id, organization_id)

        if not documents_text or len(documents_text.strip()) < 100:
            matter.status = "missing_information"
            db.commit()
            return {"error": "No hay documentos procesados para analizar"}

        analysis_result = analyze_contract(documents_text, matter.matter_type.value if hasattr(matter.matter_type, 'value') else matter.matter_type)

        if "error" in analysis_result and not analysis_result.get("summary"):
            matter.status = "missing_information"
            db.commit()
            return analysis_result

        report = create_analysis_report(matter_id, organization_id, user_id, analysis_result)

        return {
            "report_id": report.id,
            "status": "completed",
            "confidence": report.confidence,
            "risk_count": len(analysis_result.get("risks", []))
        }

    finally:
        db.close()
