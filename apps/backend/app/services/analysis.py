import json
import re
from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.analysis_report import AnalysisReport
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.matter import Matter
from app.models.review import Review, ReviewStatus
from app.models.risk_item import RiskItem

# S1-06: phrases that strongly suggest the upstream document (or the LLM
# itself) tried to break out of the analysis sandbox. When detected, the
# analysis is automatically flagged for human review.
_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore (all )?previous instructions", re.IGNORECASE),
    re.compile(r"ignore (all )?above instructions", re.IGNORECASE),
    re.compile(r"disregard (the )?(system|previous) prompt", re.IGNORECASE),
    re.compile(r"you are now (?!a legal)", re.IGNORECASE),
    re.compile(r"new instructions?:", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE),
)

# Allowed string fields and their character sets. Anything outside these
# bounds is rejected as malformed output.
_MAX_STRING_LEN = 8_000
_MAX_LIST_ITEMS = 200


def _detect_prompt_injection(payload: Any) -> bool:
    """Walk the LLM output looking for injection patterns."""
    if isinstance(payload, str):
        return any(p.search(payload) for p in _PROMPT_INJECTION_PATTERNS)
    if isinstance(payload, list):
        return any(_detect_prompt_injection(item) for item in payload)
    if isinstance(payload, dict):
        return any(_detect_prompt_injection(v) for v in payload.values())
    return False


def _shape_is_acceptable(payload: Any) -> bool:
    """Cheap shape check that prevents runaway responses from being persisted.

    Enforces soft caps on string length, list length and nesting depth.
    """
    def _walk(value: Any, depth: int = 0) -> bool:
        if depth > 8:
            return False
        if isinstance(value, str):
            return len(value) <= _MAX_STRING_LEN
        if isinstance(value, list):
            if len(value) > _MAX_LIST_ITEMS:
                return False
            return all(_walk(item, depth + 1) for item in value)
        if isinstance(value, dict):
            if len(value) > 50:
                return False
            return all(_walk(v, depth + 1) for v in value.values())
        return True

    return _walk(payload)


def _validate_llm_output(raw: Any) -> dict[str, Any]:
    """S1-06: validate an LLM structured output before persisting.

    Returns a normalized dict that ALWAYS has ``requires_human_review``
    and a ``warnings`` list so callers can branch on trust.
    """
    warnings: list[str] = []
    requires_human_review = False

    if raw is None:
        warnings.append("El LLM devolvió una respuesta vacía")
        requires_human_review = True
        normalized: dict[str, Any] = {
            "resumen_ejecutivo": "",
            "puntos_criticos": [],
            "risks": [],
            "confidence": "low",
            "warnings": warnings,
            "requires_human_review": True,
        }
        return normalized

    if not isinstance(raw, dict):
        warnings.append("El LLM no devolvió un objeto JSON válido")
        requires_human_review = True
        return {
            "resumen_ejecutivo": str(raw)[:_MAX_STRING_LEN],
            "puntos_criticos": [],
            "risks": [],
            "confidence": "low",
            "warnings": warnings,
            "requires_human_review": True,
        }

    if _detect_prompt_injection(raw):
        warnings.append(
            "El contenido del documento contenía instrucciones potencialmente "
            "adversarias; el análisis fue marcado para revisión humana."
        )
        requires_human_review = True

    if not _shape_is_acceptable(raw):
        warnings.append(
            "La respuesta del LLM excedió los límites esperados; se marcó "
            "para revisión humana."
        )
        requires_human_review = True

    # Coerce string fields into bounded strings so downstream code is safe.
    def _bounded(value: Any) -> Any:
        if isinstance(value, str):
            return value[:_MAX_STRING_LEN]
        if isinstance(value, list):
            return [item for item in (_bounded(v) for v in value) if item is not None][:_MAX_LIST_ITEMS]
        if isinstance(value, dict):
            return {str(k)[:120]: _bounded(v) for k, v in value.items()}
        return value

    normalized = _bounded(raw)
    normalized.setdefault("warnings", [])
    normalized["warnings"] = list(normalized.get("warnings", [])) + warnings
    normalized["requires_human_review"] = bool(
        normalized.get("requires_human_review", False) or requires_human_review
    )
    return normalized


# ==================== QUERIES RAG DINÁMICAS POR TIPO DE MATERIA ====================

QUERIES_RAG_POR_TIPO = {
    "laboral": "Código del Trabajo Chile obligaciones derechos trabajadores plazos despido Artículos 7 8 9 10",
    "contract_review": "Código Civil Chile obligaciones contratos arrendamiento Arts. 1915 1916 1917",
    "lease": "Ley 18.802 arrendamiento bienes raíces Chile obligaciones arrendador arrendatario",
    "company": "Código Comercio Chile sociedades obligaciones mercantiles representantes legales",
    "data_protection": "Ley 19.628 protección datos personales Chile derechos titular",
    "consumer": "Ley 19.496 consumidor cláusulas abusivas derechos obligaciones proveedor",
    "family": "Ley 19.968 tribunales familia pensiones medidas protección plazos",
    "debt": "Código Civil Chile obligaciones deudas prescripción Arts. 2514 2515",
    "other": "legislación chilena vigente contratos obligaciones generales"
}


# ==================== QUERIES RAG DE PRECEDENTES POR TIPO DE MATERIA ====================

QUERIES_PRECEDENT_POR_TIPO = {
    "laboral": "despido injustificado tutela laboral negociaciones colectivas fuero maternal",
    "contract_review": "incumplimiento contractual responsabilidad civil daños y perjuicios",
    "lease": "arrendamiento desalojo morosidad garantías",
    "company": "responsabilidad social anónima",
    "consumer": "cláusulas abusivas consumidores garantía legales",
    "family": "divorcio custodia alimentos régimen relación",
    "debt": "cobro deudas prescripción obligación",
    "penal": "delitos investigación criminal procedimiento",
    "other": "fallos judiciales jurisprudencia chilena"
}


# ==================== SECCIÓN COMÚN PARA TIMELINE Y CITAS ====================

SECTION_TIMELINE_CITAS = """

SECCIÓN ADICIONAL - TIMELINE Y CITAS LEGALES:

IDENTIFICACIÓN DE PLAZOS Y TIMELINE:
1. Identifica TODAS las fechas mencionadas en el documento (celebración, vigencia, término)
2. Para cada fecha con plazo asociado, indica:
   - Número exacto de días del plazo
   - Fecha de inicio del cómputo
   - Consecuencia de no cumplir (nulidad, multa, término anticipado, prescripción)
   - Artículo legal que fundamenta el plazo
3. Calcula la fecha límite si el plazo está corriendo desde una fecha específica

EXTRACCIÓN DE CITAS LEGALES DEL DOCUMENTO:
1. Extrae TODOS los artículos y leyes mencionados EXPLÍCITAMENTE en el texto
2. Para cada cita indica:
   - El texto EXACTO donde aparece el artículo citado
   - Si se refiere a una obligación o derecho
3. SOLO incluye citas que aparezcan en el documento, NO inventes artículos
4. Si el documento no menciona artículos específicos, indica que no hay citas documentales

"""


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
- Plazos y fechas relevantes (timeline con fechas límite)
- Artículos citados en el documento (citas documentales exactas)
- Riesgos detectados con nivel y fundamento legal
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
- Plazos y condiciones (timeline con fechas límite)
- Artículos citados en el documento (citas documentales exactas)
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
- Plazos y timeline (fechas límite relevantes)
- Artículos citados en el documento (citas documentales exactas)
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
- Plazos procesales importantes (timeline con fechas límite)
- Artículos citados en el documento (citas documentales exactas)
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
- Plazos y timeline (fechas límite relevantes)
- Artículos citados en el documento (citas documentales exactas)
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
- Plazos procesales importantes (timeline con fechas límite)
- Artículos citados en el documento (citas documentales exactas)
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
- Plazos relevantes (timeline con fechas límite)
- Artículos citados en el documento (citas documentales exactas)
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
        "timeline": {
            "type": "array",
            "description": "Timeline estructurado de plazos y fechas importantes",
            "items": {
                "type": "object",
                "properties": {
                    "evento": {"type": "string", "description": "Nombre del evento o plazo"},
                    "fecha_contrato": {"type": "string", "description": "Fecha mencionada en el contrato"},
                    "plazo_dias": {"type": "integer", "description": "Número de días del plazo"},
                    "fecha_limite": {"type": "string", "description": "Fecha límite calculada (hoy + plazo)"},
                    "consecuencia": {"type": "string", "description": "Consecuencia de no cumplir"},
                    "articulo_legal": {"type": "string", "description": "Artículo que fundamenta el plazo"}
                }
            }
        },
        "citas_documentales": {
            "type": "array",
            "description": "Artículos y leyes mencionados explícitamente en el documento",
            "items": {
                "type": "object",
                "properties": {
                    "articulo_citado": {"type": "string", "description": "Artículo citado (ej: 'Art. 123 Código del Trabajo')"},
                    "contexto_exacto": {"type": "string", "description": "Texto exacto donde aparece la cita"},
                    "obligacion_derecho": {"type": "string", "description": "Obligación o derecho que establece"}
                }
            }
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
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "normative_conflicts": {
            "type": "object",
            "description": "Conflictos detectados entre cláusulas del contrato y legislación chilena",
            "properties": {
                "conflicts": {
                    "type": "array",
                    "description": "Cláusulas que contradicen directamente la ley",
                    "items": {
                        "type": "object",
                        "properties": {
                            "clause": {"type": "string"},
                            "issue": {"type": "string"},
                            "law": {"type": "string"},
                            "severity": {"type": "string", "enum": ["high", "medium", "low"]}
                        }
                    }
                },
                "observations": {
                    "type": "array",
                    "description": "Cláusulas en observación",
                    "items": {
                        "type": "object",
                        "properties": {
                            "clause": {"type": "string"},
                            "concern": {"type": "string"},
                            "recommendation": {"type": "string"}
                        }
                    }
                },
                "summary": {"type": "string"},
                "confidence": {"type": "string"}
            }
        }
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


def get_laws_context_for_rag(matter_type: str, organization_id: int) -> str:
    """Obtiene contexto de leyes chilenas indexadas en RAG si están disponibles.

    Usa queries específicas según el tipo de materia (laboral, civil, etc.)
    """
    try:
        from app.services.embeddings import get_embedding_provider
        from app.services.rag import hybrid_search

        provider = get_embedding_provider()

        # Normalizar tipo de materia
        mt = matter_type.lower() if matter_type else "other"

        # Mapear tipo de materia a query RAG
        # Por defecto usa "legislación chilena vigente" si no hay mapping específico
        query = QUERIES_RAG_POR_TIPO.get(mt, "legislación chilena vigente contratos obligaciones")

        provider.generate_embedding(query)

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
                # Incluir el nombre de la ley y artículo si está disponible
                source = r.get('section_title', 'Fuente legal')
                context_parts.append(f"- [{source}]\n  {r['content'][:1000]}")
            return "\n\n".join(context_parts)
        return ""
    except Exception:
        return ""


def get_precedents_context_for_rag(matter_type: str, organization_id: int, top_k: int = 3) -> str:
    """Obtiene contexto de precedentes judiciales para el análisis."""
    try:
        from app.services.precedent_rag import get_precedent_context

        mt = matter_type.lower() if matter_type else "other"
        query = QUERIES_PRECEDENT_POR_TIPO.get(mt, "fallos judiciales jurisprudencia chilena")

        context = get_precedent_context(
            query=query,
            court=None,
            year=None,
            legal_area=None,
            top_k=top_k
        )
        return context if context else ""
    except Exception:
        return ""


def _empty_conflicts_result(summary: str, warnings: list) -> dict:
    """Helper for the early-return paths in ``detect_normative_conflicts``."""
    return {
        "conflicts": [],
        "observations": [],
        "confidence": "low",
        "summary": summary,
        "warnings": warnings,
        "requires_human_review": True,
    }


def _parse_conflicts_response(raw: str) -> dict:
    """Extract a JSON object from the LLM response and normalize its fields."""
    import json as _json
    import re as _re

    json_match = _re.search(r"\\{.*\\}", raw, _re.DOTALL)
    if not json_match:
        return _empty_conflicts_result(
            "No se pudo parsear el análisis de conflictos",
            ["Error al parsear respuesta del LLM"],
        )
    result = _json.loads(json_match.group(0))
    return {
        "conflicts": result.get("conflicts", []),
        "observations": result.get("observations", []),
        "confidence": "high",
        "summary": result.get("summary", "Análisis completado"),
    }


CONFLICTS_PROMPT_TEMPLATE = """Analiza el siguiente contrato y detecta conflictos con la legislación chilena.

Identifica:
1. CONFLICTOS: Cláusulas que contradicen directamente una ley o regulation chilena vigente
2. OBSERVACIONES: Cláusulas que podrían ser problematicas o estar en zona gris legal

CONTRATO:
{documents}

LEYES RELEVANTES:
{laws}

Responde SOLO con JSON válido siguiendo este esquema:
{{
    "conflicts": [
        {{
            "clause": "Texto o resumen de la cláusula",
            "law_reference": "Ley o artículo específico",
            "severity": "high|medium|low",
            "explanation": "Por qué hay conflicto",
            "concern": "Motivo de preocupación",
            "recommendation": "Recomendación"
        }}
    ],
    "observations": [
        {{
            "clause": "Texto o resumen de la cláusula",
            "law_reference": "Ley relacionada",
            "concern": "Motivo de preocupación",
            "recommendation": "Recomendación"
        }}
    ],
    "summary": "Resumen ejecutivo del análisis"
}}"""


def detect_normative_conflicts(
    documents_text: str,
    matter_type: str,
    organization_id: int,
) -> dict:
    """Detecta conflictos entre cláusulas del contrato y la legislación chilena vigente.

    S4-03: split into helpers (``CONFLICTS_PROMPT_TEMPLATE``,
    ``_parse_conflicts_response``, ``_empty_conflicts_result``) so this
    orchestrator only owns the flow.
    """
    from app.services.llm import get_llm_provider

    if not documents_text or len(documents_text.strip()) < 200:
        return _empty_conflicts_result(
            "Texto insuficiente para análisis de conflictos normativos",
            ["Documento con texto insuficiente para análisis de conflictos"],
        )

    try:
        laws_context = get_laws_context_for_rag(matter_type, organization_id)
        if not laws_context:
            return _empty_conflicts_result(
                "No se encontró contexto legal para comparar",
                ["Contexto legal no disponible - análisis de conflictos limitado"],
            )

        prompt = CONFLICTS_PROMPT_TEMPLATE.format(
            documents=documents_text[:15000],
            laws=laws_context[:5000],
        )

        provider = get_llm_provider()
        response = provider.generate(
            prompt=prompt,
            system_prompt=None,
            max_tokens=2048,
            temperature=0.3,
        )
        return _parse_conflicts_response(response)

    except Exception as exc:
        return _empty_conflicts_result(
            f"Error en análisis de conflictos: {exc}",
            [f"Error en análisis de conflictos: {exc}"],
        )



def analyze_contract(documents_text: str, matter_type: str, organization_id: int) -> dict:
    from app.services.llm import get_llm_provider

    if not documents_text or len(documents_text.strip()) < 100:
        return {
            "error": "No hay suficiente texto para analizar",
            "resumen_ejecutivo": "Información insuficiente para realizar análisis.",
            "puntos_criticos": [],
            "risks": [],
            "confidence": "low",
            "warnings": ["Documento sin texto suficiente para análisis completo"],
            "requires_human_review": True
        }

    provider = get_llm_provider()

    system_prompt = get_system_prompt_for_matter_type(matter_type)

    # Obtener contexto de leyes si está disponible
    laws_context = get_laws_context_for_rag(matter_type, organization_id)
    if laws_context:
        system_prompt += f"\n\nCONSULTA DE LEGISLACIÓN:\n{laws_context}"

    # Obtener contexto de precedentes judiciales si están disponibles
    precedents_context = get_precedents_context_for_rag(matter_type, organization_id)
    if precedents_context:
        system_prompt += f"\n\nPRECEDENTES JUDICIALES RELEVANTES:\n{precedents_context}"

    prompt = f"""Analiza el siguiente documento legal y proporciona un informe estructurado según el esquema JSON solicitado.

DOCUMENTO:
{documents_text[:30000]}

Proporciona el análisis en formato JSON siguiendo exactamente el esquema especificado."""

    try:
        raw_result = provider.generate_structured(prompt, system_prompt, RISK_ANALYSIS_SCHEMA)

        # S1-06: validate, shape-check and flag for human review when the
        # upstream document contains prompt-injection patterns.
        result = _validate_llm_output(raw_result)

        # Detectar conflictos normativos si hay suficiente contexto legal
        if laws_context:
            try:
                conflicts_result = detect_normative_conflicts(documents_text, matter_type, organization_id)
                if conflicts_result and (conflicts_result.get("conflicts") or conflicts_result.get("observations")):
                    result["normative_conflicts"] = conflicts_result
            except Exception:
                pass  # No bloquear análisis por error en detección de conflictos

        return result
    except Exception as e:
        return {
            "error": str(e),
            "resumen_ejecutivo": f"Error al generar análisis: {str(e)}",
            "puntos_criticos": [],
            "risks": [],
            "confidence": "low",
            "warnings": [f"Error en generación de análisis: {str(e)}"],
            "requires_human_review": True
        }


def create_analysis_report(
    matter_id: int,
    organization_id: int,
    user_id: int,
    analysis_result: dict,
    validation_summary: dict = None
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
            status="generated",
            validation_summary=json.dumps(validation_summary) if validation_summary else None
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

        # Ejecutar validación de documentos antes del análisis
        validation_result = None
        try:
            import asyncio

            from app.services.document_validator import validate_matter_documents

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                validation_result = loop.run_until_complete(
                    validate_matter_documents(matter_id, organization_id)
                )
            finally:
                loop.close()

            validation_summary = validation_result.validation_summary if validation_result else None
        except Exception:
            validation_summary = None

        analysis_result = analyze_contract(documents_text, matter_type_value, organization_id)

        if "error" in analysis_result and not analysis_result.get("resumen_ejecutivo"):
            matter.status = "missing_information"
            db.commit()
            return analysis_result

        report = create_analysis_report(
            matter_id, organization_id, user_id, analysis_result,
            validation_summary=validation_summary
        )

        return {
            "report_id": report.id,
            "status": "completed",
            "confidence": report.confidence,
            "risk_count": len(analysis_result.get("risks", []))
        }

    finally:
        db.close()


# =============================================================================
# GATE DE REVISIÓN - Análisis no aprobado no debe usarse para decisiones
# =============================================================================

def can_use_analysis_for_automated_decisions(
    analysis_report_id: int, db
) -> dict[str, Any]:
    """Verifica si un análisis puede ser usado para decisiones automatizadas.

    Política explícita (S0-13):
    - Si ``requires_human_review=True``, el gate SOLO se abre cuando
      ``review_approved=True``.
    - Si ``requires_human_review=False``, el análisis puede usarse sin
      revisión con ``review_status="auto_approved"`` para que la UI
      pueda distinguir.
    - Por defecto (sin información suficiente), el gate se mantiene
      cerrado para evitar decisiones legales sin auditoría.

    S4-17: previously a 99-line function with a chain of review-status
    branches and dict comprehensions inline. Refactor into per-status
    gate decisions so the top-level is a small switch-style flow.
    """
    report = (
        db.query(AnalysisReport)
        .filter(AnalysisReport.id == analysis_report_id)
        .first()
    )
    if not report:
        return _missing_report_response()

    if not report.requires_human_review:
        return _auto_approved_response()

    # requires_human_review=True path: gate opens only on approved review.
    if report.review_approved:
        return _approved_response()

    latest_review = _latest_review_for(db, analysis_report_id)
    if latest_review is None:
        return _no_review_response()

    return _evaluate_review_status(latest_review)


def _missing_report_response() -> dict:
    return {
        "can_use": False,
        "requires_review": False,
        "reason": "Analysis not found",
        "review_status": None,
    }


def _auto_approved_response() -> dict:
    """Returned when the report doesn't require human review.

    The gate is open (``can_use=True``) but the response is annotated
    ``review_status="auto_approved"`` so the UI can communicate this
    distinction to the user.
    """
    return {
        "can_use": True,
        "requires_review": False,
        "reason": None,
        "review_status": "auto_approved",
    }


def _approved_response() -> dict:
    return {
        "can_use": True,
        "requires_review": True,
        "reason": None,
        "review_status": "approved",
    }


def _no_review_response() -> dict:
    return {
        "can_use": False,
        "requires_review": True,
        "reason": "Analysis requires human review but no review has been submitted",
        "review_status": None,
    }


def _latest_review_for(db, analysis_report_id: int):
    return (
        db.query(Review)
        .filter(Review.analysis_report_id == analysis_report_id)
        .order_by(Review.created_at.desc())
        .first()
    )


def _evaluate_review_status(latest_review) -> dict:
    status = latest_review.status
    if status == ReviewStatus.PENDING:
        return {
            "can_use": False,
            "requires_review": True,
            "reason": "Analysis is pending review",
            "review_status": "pending",
        }
    if status == ReviewStatus.REJECTED:
        return {
            "can_use": False,
            "requires_review": True,
            "reason": f"Analysis was rejected: {latest_review.rejection_reason}",
            "review_status": "rejected",
            "suggested_changes": latest_review.suggested_changes,
        }
    if status == ReviewStatus.DRAFT:
        return {
            "can_use": False,
            "requires_review": True,
            "reason": "Analysis review is still in draft state",
            "review_status": "draft",
        }
    # Default conservative: deny.
    return {
        "can_use": False,
        "requires_review": True,
        "reason": "Analysis cannot be used for automated decisions",
        "review_status": status,
    }


