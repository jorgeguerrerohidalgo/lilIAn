"""Endpoints for document analysis (analyze, get analysis, markdown, risk dashboard).

S4-04: split from ``documents.py`` so the basic CRUD router stays under
the 600-line mark. The URLs are unchanged because both routers share the
``/documents`` prefix in :mod:`app.main`.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.document import Document
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["documents"])

logger = logging.getLogger(__name__)


@router.post("/{document_id}/analyze")
def analyze_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Analiza un documento y extrae datos estructurados estilo Harvey.ai."""
    from app.services.document_analyzer import analyze_document_full

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if not document.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="El documento aún no tiene texto extraído. Procesa primero.",
        )

    try:
        analyze_document_full(document_id)
        return {
            "message": "Documento analizado exitosamente",
            "document_id": document_id,
            "has_analysis": True,
        }
    except Exception as exc:
        logger.error(
            "Error analyzing document %s: %s: %s",
            document_id, type(exc).__name__, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error en análisis: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/{document_id}/analysis")
def get_document_analysis(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Obtiene el análisis estructurado de un documento."""
    from app.services.document_analyzer import get_document_analysis as fetch_analysis

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    analysis = fetch_analysis(document_id)

    if not analysis:
        return {"has_analysis": False, "document_id": document_id}

    def _decode(field: str):
        raw = getattr(analysis, field)
        return json.loads(raw) if raw else ([] if field.endswith("s") or field.startswith("clauses") or field in {"unusual_clauses", "risk_assessment", "contract_timeline", "legal_references", "participants", "obligations"} else {})

    return {
        "has_analysis": True,
        "document_id": document_id,
        "document_type": analysis.document_type,
        "participants": _decode("participants"),
        "financial_terms": _decode("financial_terms"),
        "obligations": _decode("obligations"),
        "clauses_by_type": _decode("clauses_by_type"),
        "unusual_clauses": _decode("unusual_clauses"),
        "risk_assessment": _decode("risk_assessment"),
        "contract_timeline": _decode("contract_timeline"),
        "legal_references": _decode("legal_references"),
        "indexed_content": analysis.indexed_content,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }


@router.get("/{document_id}/analysis/markdown")
def get_document_analysis_markdown(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Obtiene el análisis de un documento en formato markdown."""
    from app.services.document_analyzer import get_document_analysis as fetch_analysis
    from app.services.markdown_generator import analysis_to_markdown

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    analysis = fetch_analysis(document_id)

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="El documento no tiene análisis disponible",
        )

    markdown_content = analysis_to_markdown(analysis, document)
    return {
        "document_id": document_id,
        "filename": f"{document.original_filename.rsplit('.', 1)[0]}_analysis.md",
        "content": markdown_content,
        "content_type": "text/markdown",
    }


_RISK_LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}


@router.get("/matters/{matter_id}/risk-dashboard")
def get_matter_risk_dashboard(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
    level: str | None = Query(None, description="Filter by risk level (high, medium, low)"),
    risk_type: str | None = Query(None, description="Filter by risk type (terminacion, penalidades, etc.)"),
    sort_by: str | None = Query("score", description="Sort by: score, level, type"),
    sort_order: str | None = Query("desc", description="Sort order: asc, desc"),
):
    """Obtiene dashboard agregado de riesgos de todos los documentos analizados de un matter.

    S4-20: previously an 82-line function that did 5 things inline (matter
    lookup, analyses fetch, risk extraction, summary aggregation, filter
    and sort). Refactored into focused helpers so the top-level is a
    readable pipeline of intent.
    """
    _load_matter(db, matter_id, membership.organization_id)  # validates 404
    analyses = _load_analyses(db, matter_id, membership.organization_id)

    all_risks, risk_summary, risk_types, documents_analyzed = _aggregate_risks(analyses)

    all_risks = _apply_risk_filters(all_risks, level, risk_type)
    all_risks = _apply_risk_sort(all_risks, sort_by, sort_order)

    return {
        "matter_id": matter_id,
        "documents_analyzed": documents_analyzed,
        "total_risks": len(all_risks),
        "risk_summary": risk_summary,
        "risk_types": sorted(risk_types),
        "risks": all_risks,
    }


# ---------------------------------------------------------------------------
# S4-20: risk-dashboard helpers
# ---------------------------------------------------------------------------
def _load_matter(db, matter_id: int, organization_id: int) -> Matter:
    matter = (
        db.query(Matter)
        .filter(
            Matter.id == matter_id,
            Matter.organization_id == organization_id,
        )
        .first()
    )
    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return matter


def _load_analyses(db, matter_id: int, organization_id: int) -> list:
    from app.models.document_analysis import DocumentAnalysis

    return (
        db.query(DocumentAnalysis)
        .join(Document)
        .filter(
            Document.matter_id == matter_id,
            Document.organization_id == organization_id,
        )
        .all()
    )


def _parse_risk_assessment(raw) -> list:
    """risk_assessment is JSON-as-text on the row; tolerate both shapes."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return []
    return raw


def _risk_document_name(analysis) -> str:
    if analysis.document:
        return analysis.document.original_filename
    return f"Documento {analysis.document_id}"


def _aggregate_risks(analyses) -> tuple[list[dict], dict, set, int]:
    """Walk analyses once, return (all_risks, summary, types, document_count)."""
    all_risks: list[dict] = []
    risk_summary = {"high": 0, "medium": 0, "low": 0}
    risk_types: set[str] = set()
    documents_analyzed = 0

    for analysis in analyses:
        risks = _parse_risk_assessment(analysis.risk_assessment)
        if not risks:
            continue
        for risk in risks:
            risk_copy = {**risk, "document_id": analysis.document_id}
            risk_copy["document_name"] = _risk_document_name(analysis)
            all_risks.append(risk_copy)

            risk_level = risk.get("risk_level", "low")
            if risk_level in risk_summary:
                risk_summary[risk_level] += 1

            risk_type_val = risk.get("clause_type", "unknown")
            if risk_type_val:
                risk_types.add(risk_type_val)
        documents_analyzed += 1

    return all_risks, risk_summary, risk_types, documents_analyzed


def _apply_risk_filters(risks: list[dict], level: str | None, risk_type: str | None) -> list[dict]:
    if level:
        risks = [r for r in risks if r.get("risk_level") == level]
    if risk_type:
        risks = [r for r in risks if r.get("clause_type") == risk_type]
    return risks


def _apply_risk_sort(
    risks: list[dict], sort_by: str | None, sort_order: str | None
) -> list[dict]:
    reverse = sort_order == "desc"
    if sort_by == "score":
        return sorted(risks, key=lambda x: x.get("risk_score", 0), reverse=reverse)
    if sort_by == "level":
        return sorted(
            risks,
            key=lambda x: _RISK_LEVEL_ORDER.get(x.get("risk_level", "low"), 3),
            reverse=reverse,
        )
    if sort_by == "type":
        return sorted(
            risks, key=lambda x: x.get("clause_type", ""), reverse=reverse
        )
    return risks


