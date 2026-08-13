"""
Markdown Generator for Document Analysis

Generates human-readable markdown reports from document analysis results.
"""
import json
from datetime import datetime
from typing import Any


def analysis_to_markdown(
    analysis,
    document=None,
    include_raw_content: bool = False
) -> str:
    """Render a structured DocumentAnalysis as a Markdown report.

    S4-11: previously a single 183-line function with nine `if section:
    add_section(...)` branches inlined. Split into per-section helpers so
    the top-level is a linear sequence of `_render_X(analysis)` calls
    and each section's format is testable independently.
    """
    md = _render_header(analysis, document)
    md += _render_summary(analysis)
    md += _render_metadata(analysis, document)
    md += _render_participants(analysis)
    md += _render_financial_terms(analysis)
    md += _render_obligations(analysis)
    md += _render_clauses(analysis)
    md += _render_unusual_clauses(analysis)
    md += _render_risk_assessment(analysis)
    md += _render_timeline(analysis)
    md += _render_legal_references(analysis)
    if include_raw_content:
        md += _render_raw_content(analysis)
    return md


# ---------------------------------------------------------------------------
# S4-11: markdown section renderers
# ---------------------------------------------------------------------------
def _md_h(level: int, text: str) -> str:
    """Header prefix at the requested markdown level."""
    return f"{'#' * level} {text}\n\n"


def _decode_json_field(value: Any) -> Any:
    """Decode a possibly-stringified-JSON column; pass dicts/list through."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return []
    return value or []


def _render_header(analysis, document) -> str:
    md = _md_h(1, "Análisis del Documento")
    md += f"**Tipo de documento:** {analysis.document_type or 'No determinado'}\n\n"
    if document and getattr(document, "original_filename", None):
        md += f"**Archivo:** {document.original_filename}\n\n"
    if document and getattr(document, "matter_id", None):
        md += f"**Caso (matter) ID:** {document.matter_id}\n\n"
    return md


def _render_summary(analysis) -> str:
    if not analysis.indexed_content:
        return ""
    md = _md_h(2, "Resumen")
    md += f"{analysis.indexed_content.strip()}\n\n"
    return md


def _render_metadata(analysis, document) -> str:
    md = _md_h(2, "Información del Análisis")
    raw_meta = getattr(analysis, "analysis_metadata", None) or {}
    if isinstance(raw_meta, str):
        try:
            raw_meta = json.loads(raw_meta)
        except (ValueError, TypeError):
            raw_meta = {}
    if isinstance(raw_meta, dict):
        if raw_meta.get("model"):
            md += f"- **Modelo usado:** {raw_meta['model']}\n"
        if raw_meta.get("analyzed_at"):
            md += f"- **Fecha de análisis:** {raw_meta['analyzed_at']}\n"
    return md


def _render_participants(analysis) -> str:
    participants = _decode_json_field(analysis.participants)
    if not participants:
        return ""
    md = _md_h(2, "Participantes Identificados")
    for p in participants:
        name = p.get("name", "N/A")
        role = p.get("role", "")
        identifier = p.get("rut") or p.get("tax_id") or ""
        line = f"- **{name}**"
        if role:
            line += f" ({role})"
        if identifier:
            line += f" — {identifier}"
        md += line + "\n"
    return md + "\n"


def _render_financial_terms(analysis) -> str:
    terms = _decode_json_field(analysis.financial_terms)
    if not terms or not any(terms.values()):
        return ""
    md = _md_h(2, "Términos Financieros")
    if terms.get("amounts"):
        md += "**Montos:**\n"
        for amount in terms["amounts"]:
            md += f"- {amount}\n"
        md += "\n"
    if terms.get("dates"):
        md += "**Fechas:**\n"
        for date_str in terms["dates"]:
            md += f"- {date_str}\n"
        md += "\n"
    if terms.get("terms"):
        md += "**Otros términos:**\n"
        for term in terms["terms"]:
            md += f"- {term}\n"
        md += "\n"
    return md


def _render_obligations(analysis) -> str:
    obls = _decode_json_field(analysis.obligations)
    if not obls:
        return ""
    md = _md_h(2, "Obligaciones")
    for obl in obls:
        party = obl.get("party", "N/A")
        obl_type = obl.get("type", "")
        description = obl.get("description", "")
        line = f"- **{party}**"
        if obl_type:
            line += f" — {obl_type}"
        md += line + "\n"
        if description:
            md += f"  - {description}\n"
    return md + "\n"


def _render_clauses(analysis) -> str:
    clauses = _decode_json_field(analysis.clauses_by_type)
    if not clauses:
        return ""
    md = _md_h(2, "Cláusulas por Tipo")
    for clause_type, items in clauses.items():
        md += _md_h(3, clause_type)
        for item in items:
            md += f"- {item}\n"
        md += "\n"
    return md


def _render_unusual_clauses(analysis) -> str:
    unusual = _decode_json_field(analysis.unusual_clauses)
    if not unusual:
        return ""
    md = _md_h(2, "⚠️ Cláusulas Inusuales o Riesgosos")
    for clause in unusual:
        risk = clause.get("risk_level") or clause.get("level") or ""
        clause_type = clause.get("clause_type") or clause.get("type") or "Riesgo"
        explanation = clause.get("explanation") or clause.get("description") or ""
        line = f"- **{clause_type}**"
        if risk:
            line += f" [{risk}]"
        md += line + "\n"
        if explanation:
            md += f"  - {explanation}\n"
    return md + "\n"


def _render_risk_assessment(analysis) -> str:
    risks = _decode_json_field(analysis.risk_assessment)
    if not risks:
        return ""
    md = _md_h(2, "Evaluación de Riesgos")
    for risk in risks:
        level = risk.get("level", "Desconocido")
        description = risk.get("description") or risk.get("risk") or ""
        line = f"- **{level}**"
        md += line + "\n"
        if description:
            md += f"  - {description}\n"
    return md + "\n"


def _render_timeline(analysis) -> str:
    timeline = _decode_json_field(analysis.contract_timeline)
    if not timeline:
        return ""
    md = _md_h(2, "Cronología Contractual")
    for event in timeline:
        event_date = event.get("date") or event.get("fecha_contrato") or "Sin fecha"
        event_type = event.get("type") or event.get("evento") or "Evento"
        days_from_signing = event.get("days_from_signing") or event.get("plazo_dias")
        days_str = f" ({days_from_signing} días desde firma)" if days_from_signing else ""
        md += f"- **{event_date}** — {event_type}{days_str}\n"
        if event.get("description"):
            md += f"  - {event['description']}\n"
        if event.get("consequence"):
            md += f"  - Consecuencia: {event['consequence']}\n"
    return md + "\n"


def _render_legal_references(analysis) -> str:
    refs = _decode_json_field(analysis.legal_references)
    if not refs:
        return ""
    md = _md_h(2, "Referencias Legales")
    for ref in refs:
        law = ref.get("law") or ref.get("name") or ""
        article = ref.get("article") or ref.get("articulo") or ""
        line = f"- **{law}**"
        if article:
            line += f" — {article}"
        md += line + "\n"
    return md + "\n"


def _render_raw_content(analysis) -> str:
    md = _md_h(2, "Contenido Indexado")
    if analysis.indexed_content:
        md += f"```\n{analysis.indexed_content[:5000]}\n```\n\n"
    return md

def generate_document_markdown_filename(document) -> str:
    """Generate a markdown filename from a document."""
    safe_name = getattr(document, 'original_filename', 'document')
    safe_name = safe_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    base_name = safe_name.rsplit('.', 1)[0] if '.' in safe_name else safe_name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{base_name}_analysis_{timestamp}.md"
