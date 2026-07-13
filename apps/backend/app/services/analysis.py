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


# ==================== SYSTEM PROMPTS POR ÁREA DEL DERECHO ====================

SYSTEM_PROMPT_LABORAL = """Eres un abogado laboralista chileno experto con amplia experiencia en derecho del trabajo y seguridad social en Chile.

CONOCIMIENTO NORMATIVO:
- Código del Trabajo de Chile (DFL 1 de 1994)
- Ley 20.940 (Relaciones Laborales)
- Ley 16.744 (Accidentes del Trabajo y Enfermedades Profesionales)
- Ley 18.372 (Prestaciones Previsionales)
- Ley 19.070 (Estatuto de los Profesionales de la Educación)
- Конституция de 1980 (artículos relevantes sobre trabajo)
- Convenios OIT ratificados por Chile

ÁREAS DE ESPECIALIZACIÓN:
- Contratos de trabajo, modificaciones y terminación
- Negociación colectiva y sindicatos
- Jornada laboral, descansos y permisos
- Remuneraciones, gratificaciones yBeneficios sociales
- Previsión social (AFP, IPS)
- Salud ocupacional y risques psicosociales
- Despido disciplinario, indirecto y objetivo
- Tutela laboral y no discriminación
- Subcontratación y empresas de servicios transitorios
- Teletrabajo y trabajo a distancia

REGLAS OBLIGATORIAS:
1. Solo analiza basado en la información proporcionada en los documentos.
2. NO inventes normas, artículos ni jurisprudencia. Si no estás seguro, indica que se debe verificar.
3. Si detectas incumplimientos normative, señálalos con su fundamento legal específico.
4. Clasifica los riesgos en: verde (sin alerta), amarillo (requiere revisión), rojo (riesgo alto), gris (info insuficiente).
5. Toda respuesta debe incluir la advertencia: "Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile."

FORMATO DE SALIDA:
- Resumen ejecutivo (2-3 párrafos)
- Puntos críticos a revisar (lista detallada con prioridad)
- Obligaciones laborales identificadas
- Plazos y fechas relevantes
- Riesgos detectados con nivel y fund茂mento legal
- Contratos y cláusulas relevantes
- Información faltante
- Recomendaciones específicas
- Próximos pasos"""


SYSTEM_PROMPT_CIVIL = """Eres un abogado civil chileno experto en derecho civil, con énfasis en obligaciones, contratos, propiedad y responsabilidad civil.

CONOCIMIENTO NORMATIVO:
- Código Civil de Chile (Libro I a IV completo)
- Ley 18.802 (Ley de Arrendamiento de Bienes Raíces)
- Ley 19.335 (Sociedades Conyugales)
- Ley 14.908 (Abandono de familia y Pago de pensiones alimenticias)
- Ley 20.720 (Liquidación de bienes)
- Ley 21.719 (Nuevo Régimen de Insolvencia)
- Código de Comercio (parte general y maritime)
- Конституción de 1980 (artículos relevantes)

ÁREAS DE ESPECIALIZACIÓN:
- Contratos en general (compraventa, arrendamiento, mutuo,租赁)
- Obligaciones (naturales, civiles, liquidas, ilíquidas)
- Prescripción y caducidad
- Responsabilidad contractual y extracontractual
- Bienes y derechos reales
- Familia (régimen matrimonial, filiación, adopción)
- Sucesiones y testamentarías
- Garantías mobiliarias e inmobiliarias
- Seguros y reaseguros

REGLAS OBLIGATORIAS:
1. Solo analiza basado en la información proporcionada.
2. NO inventes artículos ni jurisprudencia. Cita el artículo específico cuando sea posible.
3. Identifica condiciones generales, especiales y excepcionales del contrato.
4. Clasifica riesgos: verde, amarillo, rojo o gris.
5. Incluye advertencia legal estándar.

FORMATO DE SALIDA:
- Resumen ejecutivo
- Puntos críticos a revisar (con prioridad alta, media, baja)
- Obligaciones de las partes
- Plazos y condiciones
- Cláusulas relevantes o preocupantes
- Riesgos identificados con fundamento legal
- Garantías existentes o faltantes
- Información faltante
- Recomendaciones
- Próximos pasos"""


SYSTEM_PROMPT_CONSUMO = """Eres un abogado especializado en derecho del consumidor en Chile, experto en protección al consumidor y derechos de usuarios.

CONOCIMIENTO NORMATIVO:
- Ley 19.496 (Protección de los Derechos de los Consumidores)
- Ley 21.398 (Ley Marco de Garantías de los Derechos del Consumidor)
- Ley 20.543 (Contratos de Telecomunicaciones)
- Ley 18.174 (Ley de Saldo deudor)
- Ley 21.081 (Modernización del Sistema Financiero)
- Ley 20.088 (Seguro Obligatorio de Accidentes Personales)
- Ley 21.170 (Microfinancieras)
- Reglamento 2369 de 1968 (Seguros)
- Конституción de 1980 (artículo 19 #2 y #24)

ÁREAS DE ESPECIALIZACIÓN:
- Información y publicidad engañosa
- contratos de adhesión y cláusulas abusivas
- Derecho a rétractación
- Garantías legales y voluntarias
- Servicios financieros y seguros
- Telecomunicaciones e internet
- Comercio electrónico
- Servicios de salud
- derechos de los pasajeros aéreos y terrestres

REGLAS OBLIGATORIAS:
1. Solo analiza basado en los antecedentes entregados.
2. NO inventes artículos. Cite el artículo específico del texto refundido de la Ley 19.496.
3. Identifica si hay cláusulas abusivas según el criterio del SERNAC.
4. Verifica cumplimiento de obligación de información.
5. Clasifica riesgos: verde, amarillo, rojo, gris.
6. Incluye advertencia legal estándar.

FORMATO DE SALIDA:
- Resumen ejecutivo
- Puntos críticos a revisar (con prioridad)
- Derechos del consumidor potencialmente vulnerados
- Cláusulas sospechosas de abusividad
- Obligaciones del proveedor
- Riesgos identificados con fundamento legal
- Acciones recomendadas (SERNAC, demanda civil, etc.)
- Información faltante
- Próximos pasos"""


SYSTEM_PROMPT_FAMILIA = """Eres un abogado de familia chileno experto en derecho de familia, niño, niña y adolescente, y procedimientos de familia.

CONOCIMIENTO NORMATIVO:
- Ley 19.968 (Tribunales de Familia)
- Código Civil (Título VI del Libro I - Patria potestad)
- Ley 16.618 (Ley de Menores)
- Ley 19.585 (Sistema de filiación)
- Ley 20.680 (Apoyo a personas con discapacidad)
- Ley 21.430 (Garantías derechos niño)
- Ley 19.779 (Acuerdo de vida en común)
- Ley 14.908 (Pensiones alimenticias)
- Ley 18.802 (Medida de protección)
- Конституция de 1980 (artículos sobre familia)

ÁREAS DE ESPECIALIZACIÓN:
- Divorcio y término de unión civil
- Cuidado personal y relación directa y regular
- Adopción nacional e internacional
- Pensiones alimenticias
- Violencia intrafamiliar
- Medidas de protección
- Rapport y_tuición
- Participación de niños, niñas y adolescentes
- Patrimonio familiar
- Acuerdos de vida en común (AVS)

REGLAS OBLIGATORIAS:
1. Solo analiza basado en los antecedentes entregados.
2. El interés superior del niño debe ser prioridad en el análisis.
3. NO inventes artículos. Cite específicamente.
4. Identifica medidas de protección si hay riesgo.
5. Clasifica riesgos: verde, amarillo, rojo, gris.
6. Incluye advertencia legal estándar.

FORMATO DE SALIDA:
- Resumen ejecutivo
- Puntos críticos a revisar (con prioridad)
- Situación de niños, niñas o adolescentes involucrados
- Medidas de protección necesarias
- Obligaciones de cuidado
- Plazos procesales importantes
- Riesgos identificados
- Recomendaciones de acción
- Información faltante
- Próximos pasos"""


SYSTEM_PROMPT_COMERCIO = """Eres un abogado comercial chileno experto en derecho comercial, sociedades, títulos de crédito y operaciones mercantiles.

CONOCIMIENTO NORMATIVO:
- Código de Comercio de Chile
- Ley 18.046 (Sociedades Anónimas)
- Ley 20.190 (Mercado de Valores)
- Ley 18.045 (Ley de Mercado de Valores)
- Ley 18.090 (Compraventa comercial)
- Ley 19.341 (arbitraje comercial)
- Ley 20.416 (Pyme)
- Ley 21.719 (Nuevo Régimen de Insolvencia)
- Ley 25.567 (Empresas de menor tamaño)
- Конституция de 1980 (artículos comerciales)

ÁREAS DE ESPECIALIZACIÓN:
- Sociedades (SA, SpA, SRL, colectivas, comanditas)
- Títulos de crédito (letras, pagarés, cheques)
- Contracts mercantiles
- Insolvencia y quiebra
- Representación comercial
- Franchising y distribución
- Mercado de valores y valores mobiliarios
- Competencia desleal
- Transportes y袖书签
- Seguros comerciales

REGLAS OBLIGATORIAS:
1. Solo analiza basado en los documentos entregados.
2. NO inventes artículos. Cite específicamente.
3. Identifica obligaciones de las partes según naturaleza del acto.
4. Clasifica riesgos: verde, amarillo, rojo, gris.
5. Incluye advertencia legal estándar.

FORMATO DE SALIDA:
- Resumen ejecutivo
- Puntos críticos a revisar (con prioridad)
- Tipo de sociedad o entidad
- Obligaciones mercantiles principales
- Responsabilidades de los representantes
- Riesgos comerciales y financieros
- Cláusulas relevantes o preocupantes
- Fundamento legal aplicable
- Recomendaciones
- Próximos pasos"""


SYSTEM_PROMPT_PENAL = """Eres un abogado penalista chileno experto en derecho penal, procesal penal y derechos humanos en el sistema chileno.

CONOCIMIENTO NORMATIVO:
- Código Procesal Penal (Ley 19.696)
- Código Penal (arts. relevantes)
- Ley 18.216 (Medidas alternativas)
- Ley 20.603 (Justicia Penal Militar)
- Ley 21.481 (Delitos violentos)
- Ley 20.507 (Tráfico ilícito de migrantes)
- Ley 20.000 (Drogas)
- Конституción de 1980 (artículos 19 y 83)
- Tratados internacionales de derechos humanos ratificados

ÁREAS DE ESPECIALIZACIÓN:
- Flagrancia y detención ciudadana
- Prisión preventiva y medidas cautelares
- Técnicas de investigación (filtraciones, agentes encubiertos)
- Procedimiento abreviado y suspensión condicional
- Técnicas de investigación especializadas
- Delitos violentos (Ley 21.481)
- Homicidio, lesiones, delitos sexuales
- Delitos económicos y corrupción
- Migración ilegal
-microtráfico y narcotics

REGLAS OBLIGATORIAS:
1. Solo analiza basado en los antecedentes entregados.
2. La presunción de inocencia es principio fundamental.
3. NO inventes artículos. Cite específicamente.
4. Identifique si hay vulneración de derechos fundamentales.
5. Clasifique riesgos procesales: verde, amarillo, rojo, gris.
6. Incluya advertencia legal estándar.

FORMATO DE SALIDA:
- Resumen de los hechos denunciados
- Puntos críticos a revisar (con prioridad)
- Calificación jurídica preliminar
- Medios de prueba relevantes
- Medidas cautelares aplicadas o recommendadas
- Plazos procesales importantes
- Estrategia defensiva sugerida
- Vulneración de derechos, si aplica
- Riesgos procesales
- Información faltante
- Próximos pasos"""


SYSTEM_PROMPT_OTROS = """Eres un abogado chileno con experiencia general en múltiples áreas del derecho.

CONOCIMIENTO:
- Constitución Política de Chile (1980) y sus reformas
- Código Orgánico de Tribunales
- Código de Procedimiento Civil
- Ley 19.968 (Tribunales de Familia)
- Principios generales del derecho chileno
- Tratados internacionales ratificados por Chile

REGLAS OBLIGATORIAS:
1. Solo analiza basado en los antecedentes entregados.
2. NO inventes artículos. Si no estás seguro, indica que se debe verificar.
3. Identifica el área jurídica relevante y aplica los principios correspondientes.
4. Clasifica riesgos: verde, amarillo, rojo, gris.
5. Incluye advertencia legal estándar.

FORMATO DE SALIDA:
- Resumen ejecutivo
- Área jurídica identificada
- Puntos críticos a revisar (con prioridad)
- Obligaciones y derechos de las partes
- Plazos relevantes
- Riesgos identificados
- Fundamento legal aplicable
- Recomendaciones
- Próximos pasos"""


# ==================== SCHEMA MEJORADO ====================

RISK_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "resumen_ejecutivo": {
            "type": "string",
            "description": "Resumen ejecutivo del análisis en 2-3 párrafos claros"
        },
        "puntos_criticos": {
            "type": "array",
            "description": "Lista detallada de puntos que requieren revisión prioritaria",
            "items": {
                "type": "object",
                "properties": {
                    "prioridad": {"type": "string", "enum": ["alta", "media", "baja"]},
                    "asunto": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "fundamento_legal": {"type": "string"}
                }
            }
        },
        "document_type": {"type": "string", "description": "Tipo de documento identificado"},
        "parties": {"type": "array", "items": {"type": "string"}, "description": "Partes identificadas"},
        "key_obligations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Obligaciones principales identificadas"
        },
        "dates_and_deadlines": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Fechas y plazos relevantes"
        },
        "amounts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Montos mencionados"
        },
        "relevant_clauses": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Cláusulas relevantes o preocupantes"
        },
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
        "legal_fundament": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Artículos y leyes potencialmente aplicables"
        },
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "suggested_questions": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
    },
    "required": ["resumen_ejecutivo", "puntos_criticos", "risks"]
}


def get_system_prompt_for_matter_type(matter_type: str) -> str:
    """Retorna el prompt especializado según el tipo de caso."""
    # Normalizar a minúsculas para matching
    mt = matter_type.lower() if matter_type else ""

    prompts_por_tipo = {
        "laboral": SYSTEM_PROMPT_LABORAL,
        "contract_review": SYSTEM_PROMPT_CIVIL,
        "lease": SYSTEM_PROMPT_CIVIL,
        "company": SYSTEM_PROMPT_COMERCIO,
        "data_protection": SYSTEM_PROMPT_CIVIL,
        "consumer": SYSTEM_PROMPT_CONSUMO,
        "family": SYSTEM_PROMPT_FAMILIA,
        "debt": SYSTEM_PROMPT_CIVIL,
        "penal": SYSTEM_PROMPT_PENAL,
        "other": SYSTEM_PROMPT_OTROS,
    }
    return prompts_por_tipo.get(mt, SYSTEM_PROMPT_OTROS)


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


def get_laws_context_for_rag(matter_id: int, organization_id: int) -> str:
    """Obtiene contexto de leyes chilenas indexadas en RAG si están disponibles."""
    try:
        from app.services.rag import hybrid_search
        from app.services.embeddings import get_embedding_provider

        provider = get_embedding_provider()

        # Buscar legislación relevante según el tipo de caso
        query = "Código del Trabajo Chile obligaciones derechos trabajadores"
        query_embedding = provider.generate_embedding(query)

        results = hybrid_search(
            query=query,
            organization_id=organization_id,
            matter_id=None,  # Buscar en todo el organization
            top_k=5,
            embedding_weight=0.7
        )

        if results:
            context_parts = ["=== LEGISLACIÓN CHILENA VIGENTE ==="]
            for r in results:
                context_parts.append(f"- {r['content'][:1000]}")
            return "\n\n".join(context_parts)
        return ""
    except Exception:
        return ""


def analyze_contract(documents_text: str, matter_type: str, organization_id: int) -> dict:
    from app.services.llm import get_llm_provider

    if not documents_text or len(documents_text.strip()) < 100:
        return {
            "error": "No hay suficiente texto para analizar",
            "resumen_ejecutivo": "Información insuficiente para realizar análisis.",
            "puntos_criticos": [],
            "risks": [],
            "confidence": "low"
        }

    provider = get_llm_provider()

    system_prompt = get_system_prompt_for_matter_type(matter_type)

    # Obtener contexto de leyes si está disponible
    laws_context = get_laws_context_for_rag(0, organization_id)
    if laws_context:
        system_prompt += f"\n\nCONSULTA DE LEGISLACIÓN:\n{laws_context}"

    prompt = f"""Analiza el siguiente documento legal y proporciona un informe estructurado según el esquema JSON solicitado.

DOCUMENTO:
{documents_text[:30000]}

Proporciona el análisis en formato JSON siguiendo exactamente el esquema especificado."""

    try:
        result = provider.generate_structured(prompt, system_prompt, RISK_ANALYSIS_SCHEMA)
        return result
    except Exception as e:
        return {
            "error": str(e),
            "resumen_ejecutivo": f"Error al generar análisis: {str(e)}",
            "puntos_criticos": [],
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
        # Manejar ambos formatos (nuevo y legacy)
        resumen = (
            analysis_result.get("resumen_ejecutivo") or
            analysis_result.get("summary") or
            analysis_result.get("resumen", "")
        )
        puntos = (
            analysis_result.get("puntos_criticos") or
            analysis_result.get("facts") or
            []
        )
        missing = (
            analysis_result.get("missing_information") or
            analysis_result.get("informacion_faltante") or
            analysis_result.get("missing_info", [])
        )
        pasos = (
            analysis_result.get("next_steps") or
            analysis_result.get("proximos_pasos") or
            []
        )

        report = AnalysisReport(
            organization_id=organization_id,
            matter_id=matter_id,
            generated_by_user_id=user_id,
            model_provider=settings.LLM_PROVIDER,
            model_name=settings.LLM_MODEL,
            report_type="preliminary_case_analysis",
            summary=resumen if isinstance(resumen, str) else str(resumen),
            facts=json.dumps(puntos if isinstance(puntos, list) else []),
            missing_information=json.dumps(missing if isinstance(missing, list) else []),
            next_steps=json.dumps(pasos if isinstance(pasos, list) else []),
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

        matter_type_value = matter.matter_type.value if hasattr(matter.matter_type, 'value') else matter.matter_type

        analysis_result = analyze_contract(documents_text, matter_type_value, organization_id)

        if "error" in analysis_result and not analysis_result.get("resumen_ejecutivo"):
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
