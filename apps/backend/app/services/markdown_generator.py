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
    """
    Convert a DocumentAnalysis to a formatted markdown string.

    Args:
        analysis: DocumentAnalysis model instance
        document: Optional Document model for additional metadata
        include_raw_content: Whether to include indexed_content

    Returns:
        Markdown-formatted string
    """
    lines = []

    doc_type = getattr(analysis, 'document_type', None) or "Desconocido"
    lines.append(f"# Analisis de Documento: {doc_type}")
    lines.append("")

    if document:
        filename = getattr(document, 'original_filename', 'Unknown')
        lines.append(f"**Archivo:** {filename}")
        if hasattr(analysis, 'created_at') and analysis.created_at:
            lines.append(f"**Fecha de analisis:** {analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

    participants = _parse_json_field(getattr(analysis, 'participants', None), [])
    financial_terms = _parse_json_field(getattr(analysis, 'financial_terms', None), {})
    obligations = _parse_json_field(getattr(analysis, 'obligations', None), [])
    clauses_by_type = _parse_json_field(getattr(analysis, 'clauses_by_type', None), {})
    unusual_clauses = _parse_json_field(getattr(analysis, 'unusual_clauses', None), [])
    risk_assessment = _parse_json_field(getattr(analysis, 'risk_assessment', None), [])
    contract_timeline = _parse_json_field(getattr(analysis, 'contract_timeline', None), [])
    legal_references = _parse_json_field(getattr(analysis, 'legal_references', None), [])

    if participants:
        lines.append("## Participantes")
        lines.append("")
        for p in participants:
            company = p.get('company', 'N/A')
            role = p.get('role', 'N/A')
            lines.append(f"- **{company}** ({role})")
            if p.get('rut'):
                lines.append(f"  - RUT: {p.get('rut')}")
            if p.get('representative'):
                lines.append(f"  - Representante: {p.get('representative')}")
            if p.get('representative_rut'):
                lines.append(f"  - RUT Representante: {p.get('representative_rut')}")
        lines.append("")

    if financial_terms:
        lines.append("## Terminos Financieros")
        lines.append("")
        if financial_terms.get('dates'):
            lines.append("**Fechas:**")
            for d in financial_terms['dates']:
                lines.append(f"- {d}")
        if financial_terms.get('amounts'):
            lines.append("**Montos:**")
            for a in financial_terms['amounts']:
                lines.append(f"- {a}")
        if financial_terms.get('terms'):
            lines.append("**Terminos:**")
            for t in financial_terms['terms']:
                lines.append(f"- {t}")
        lines.append("")

    if obligations:
        lines.append("## Obligaciones")
        lines.append("")
        for ob in obligations:
            party = ob.get('party', 'Parte')
            ob_type = ob.get('type', 'Obligacion')
            lines.append(f"### {party} - {ob_type}")
            lines.append("")
            lines.append(ob.get('description', 'Sin descripcion'))
            lines.append("")
        lines.append("")

    if clauses_by_type:
        lines.append("## Clausulas por Tipo")
        lines.append("")
        for clause_type, clauses in clauses_by_type.items():
            if clauses:
                display_type = clause_type.replace('_', ' ').title()
                lines.append(f"### {display_type}")
                lines.append("")
                for clause in clauses[:5]:
                    if len(clause) > 200:
                        lines.append(f"- {clause[:200]}...")
                    else:
                        lines.append(f"- {clause}")
                lines.append("")
        lines.append("")

    if unusual_clauses:
        lines.append("## Clausulas Inusuales / Alertas de Riesgo")
        lines.append("")
        for idx, uc in enumerate(unusual_clauses, 1):
            risk_level = uc.get('risk_level', 'unknown')
            risk_score = uc.get('risk_score', 0)
            lines.append(f"### {idx}. Nivel de Riesgo: {risk_level.upper()} (Score: {risk_score}/100)")
            lines.append("")
            lines.append(f"**Clausula:** {uc.get('clause', 'N/A')}")
            lines.append("")
            if uc.get('explanation'):
                lines.append(f"**Explicacion:** {uc.get('explanation')}")
            if uc.get('recommendation'):
                lines.append(f"**Recomendacion:** {uc.get('recommendation')}")
            lines.append("")
        lines.append("")

    if risk_assessment:
        lines.append("## Evaluacion de Riesgos")
        lines.append("")
        for idx, risk in enumerate(risk_assessment, 1):
            level = risk.get('risk_level', 'unknown')
            if level:
                level = level.upper()
            else:
                level = 'UNKNOWN'
            score = risk.get('risk_score', 0)
            clause_type = risk.get('clause_type', 'Riesgo sin tipo')
            clause_text = risk.get('clause_text', 'N/A')
            if len(clause_text) > 300:
                clause_text = clause_text[:300] + "..."

            lines.append(f"### {idx}. [{level}] {clause_type} (Score: {score}/100)")
            lines.append("")
            lines.append(f"**Clausula:** {clause_text}")
            lines.append("")
            lines.append(f"**Explicacion:** {risk.get('explanation', 'Sin explicacion')}")
            if risk.get('industry_standard'):
                lines.append(f"**Estandar del sector:** {risk.get('industry_standard')}")
            if risk.get('suggested_clause'):
                lines.append(f"**Clausula sugerida:** {risk.get('suggested_clause')}")
            lines.append("")
        lines.append("")

    if contract_timeline:
        lines.append("## Linea de Tiempo del Contrato")
        lines.append("")
        lines.append("| Evento | Fecha | Dias | Tipo | Consecuencia | Referencia |")
        lines.append("|--------|-------|------|------|--------------|-------------|")
        for event in contract_timeline:
            event_name = event.get('event', 'N/A')
            date = event.get('date', 'N/A')
            days = event.get('days_from_signing', 'N/A')
            event_type = event.get('type', 'N/A')
            consequence = event.get('consequence', 'Sin consecuencias')
            if len(consequence) > 50:
                consequence = consequence[:50] + "..."
            legal_ref = event.get('legal_reference', 'N/A')
            lines.append(f"| {event_name} | {date} | {days} | {event_type} | {consequence} | {legal_ref} |")
        lines.append("")

    if legal_references:
        lines.append("## Referencias Legales Citadas")
        lines.append("")
        for ref in legal_references:
            article = ref.get('article', 'N/A')
            context = ref.get('context', 'Sin contexto')
            lines.append(f"- **{article}**: {context}")
        lines.append("")

    indexed_content = getattr(analysis, 'indexed_content', None)
    if indexed_content and include_raw_content:
        lines.append("## Contenido Indexado")
        lines.append("")
        lines.append(indexed_content[:1000])
        if len(indexed_content) > 1000:
            lines.append("")
            lines.append(f"... (contenido truncado, total: {len(indexed_content)} caracteres)")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Este analisis es generado automaticamente y no reemplaza la revision profesional de un abogado habilitado en Chile.*")

    return "\n".join(lines)


def _parse_json_field(value: Any, default: Any) -> Any:
    """Parse a JSON field that might be a string or already parsed."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def generate_document_markdown_filename(document) -> str:
    """Generate a markdown filename from a document."""
    safe_name = getattr(document, 'original_filename', 'document')
    safe_name = safe_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    base_name = safe_name.rsplit('.', 1)[0] if '.' in safe_name else safe_name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{base_name}_analysis_{timestamp}.md"
