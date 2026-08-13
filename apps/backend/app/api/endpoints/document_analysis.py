"""Endpoints for document analysis (analyze, get analysis, markdown, risk dashboard).

S4-04: split from ``documents.py`` so the basic CRUD router stays under
the 600-line mark. The URLs are unchanged because both routers share the
``/documents`` prefix in :mod:`app.main`.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.api.deps.auth import get_current_user, require_organization

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
        )


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


@router.get("/matters/{matter_id}/risk-dashboard")
def get_matter_risk_dashboard(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
    level: Optional[str] = Query(None, description="Filter by risk level (high, medium, low)"),
    risk_type: Optional[str] = Query(None, description="Filter by risk type (terminacion, penalidades, etc.)"),
    sort_by: Optional[str] = Query("score", description="Sort by: score, level, type"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc, desc"),
):
    """Obtiene dashboard agregado de riesgos de todos los documentos analizados de un matter."""
    from app.models.document_analysis import DocumentAnalysis

    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id,
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    analyses = (
        db.query(DocumentAnalysis)
        .join(Document)
        .filter(
            Document.matter_id == matter_id,
            Document.organization_id == membership.organization_id,
        )
        .all()
    )

    all_risks = []
    risk_summary = {"high": 0, "medium": 0, "low": 0}
    documents_analyzed = 0
    risk_types: set[str] = set()

    for analysis in analyses:
        if not analysis.risk_assessment:
            continue
        risks = (
            json.loads(analysis.risk_assessment)
            if isinstance(analysis.risk_assessment, str)
            else analysis.risk_assessment
        )
        for risk in risks:
            risk_copy = {**risk, "document_id": analysis.document_id}
            risk_copy["document_name"] = (
                analysis.document.original_filename
                if analysis.document
                else f"Documento {analysis.document_id}"
            )
            all_risks.append(risk_copy)
            risk_level = risk.get("risk_level", "low")
            if risk_level in risk_summary:
                risk_summary[risk_level] += 1
            risk_type_val = risk.get("clause_type", "unknown")
            if risk_type_val:
                risk_types.add(risk_type_val)
        documents_analyzed += 1

    if level:
        all_risks = [r for r in all_risks if r.get("risk_level") == level]
    if risk_type:
        all_risks = [r for r in all_risks if r.get("clause_type") == risk_type]

    reverse = sort_order == "desc"
    if sort_by == "score":
        all_risks.sort(key=lambda x: x.get("risk_score", 0), reverse=reverse)
    elif sort_by == "level":
        level_order = {"high": 0, "medium": 1, "low": 2}
        all_risks.sort(key=lambda x: level_order.get(x.get("risk_level", "low"), 3), reverse=reverse)
    elif sort_by == "type":
        all_risks.sort(key=lambda x: x.get("clause_type", ""), reverse=reverse)

    return {
        "matter_id": matter_id,
        "documents_analyzed": documents_analyzed,
        "total_risks": len(all_risks),
        "risk_summary": risk_summary,
        "risk_types": sorted(risk_types),
        "risks": all_risks,
    }