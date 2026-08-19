
import logging as _logging
import threading
from contextlib import suppress

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.analysis_report import AnalysisReport
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.risk_item import RiskItem
from app.models.user import User
from app.schemas.analysis import (
    AnalysisReportDetailResponse,
    AnalysisReportResponse,
    GenerateAnalysisRequest,
    RiskItemResponse,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])

_logger = _logging.getLogger("lilian.analysis")

# Per-matter in-process lock so two concurrent POSTs for the same case do
# not race each other and corrupt the matter's status / DB rows.
_analysis_locks: dict[int, threading.Lock] = {}
_analysis_locks_guard = threading.Lock()


def _get_analysis_lock(matter_id: int) -> threading.Lock:
    with _analysis_locks_guard:
        lock = _analysis_locks.get(matter_id)
        if lock is None:
            lock = threading.Lock()
            _analysis_locks[matter_id] = lock
        return lock


def run_analysis_task(matter_id: int, organization_id: int, user_id: int):
    """Background-task entry point.

    Wraps the real orchestrator with a per-matter lock and a hard
    top-level ``try/except`` so a crash inside the analysis pipeline
    never bubbles back into the FastAPI threadpool as an unhandled
    exception (which is what was poisoning subsequent requests).
    """
    lock = _get_analysis_lock(matter_id)
    if not lock.acquire(blocking=False):
        _logger.warning(
            "analysis for matter %s already running, skipping duplicate dispatch",
            matter_id,
        )
        return
    try:
        from app.services.analysis import generate_analysis_for_matter
        try:
            generate_analysis_for_matter(matter_id, organization_id, user_id)
        except Exception:
            # Belt-and-braces: generate_analysis_for_matter already
            # swallows + persists the failure, but if a future change
            # leaks an exception we still must NOT let it bubble.
            _logger.exception(
                "background analysis task leaked exception for matter %s",
                matter_id,
            )
            with suppress(Exception):
                from app.services.analysis import _set_matter_error_status
                _set_matter_error_status(
                    matter_id, "background task crashed"
                )
    finally:
        lock.release()


@router.post("", status_code=202)
def generate_analysis(
    analysis_request: GenerateAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == analysis_request.matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    # Pre-flight checks surface common failures immediately so the user
    # does not have to wait for the background task to discover them.
    from app.models.document import Document
    doc_count = (
        db.query(Document)
        .filter(
            Document.matter_id == analysis_request.matter_id,
            Document.organization_id == membership.organization_id,
            Document.status.in_(["processed", "analyzed"]),
        )
        .count()
    )
    if doc_count == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No hay documentos procesados para analizar. Sube al menos "
                "un PDF/DOCX, espera a que se procese y vuelve a intentar."
            ),
        )

    background_tasks.add_task(
        run_analysis_task,
        analysis_request.matter_id,
        membership.organization_id,
        current_user.id
    )

    return {
        "message": "Análisis iniciado en segundo plano",
        "matter_id": analysis_request.matter_id,
        "status": "processing",
        "documents_to_analyze": doc_count,
    }


@router.get("/matters/{matter_id}", response_model=list[AnalysisReportResponse])
def list_matter_analyses(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    reports = db.query(AnalysisReport).filter(
        AnalysisReport.matter_id == matter_id,
        AnalysisReport.organization_id == membership.organization_id
    ).order_by(AnalysisReport.created_at.desc()).all()

    return reports


@router.get("/reports/{report_id}", response_model=AnalysisReportDetailResponse)
def get_analysis_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    report = db.query(AnalysisReport).filter(
        AnalysisReport.id == report_id,
        AnalysisReport.organization_id == membership.organization_id
    ).first()

    if not report:
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    risks = db.query(RiskItem).filter(
        RiskItem.analysis_report_id == report_id
    ).all()

    risk_responses = [RiskItemResponse.model_validate(r) for r in risks]

    response_data = AnalysisReportResponse.model_validate(report).model_dump()
    response_data["risks"] = risk_responses

    return AnalysisReportDetailResponse(**response_data)


@router.get("/matters/{matter_id}/status")
def get_matter_analysis_status(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Lightweight status endpoint so the frontend can detect analysis
    failures without waiting for the polling to time out. Returns
    ``{status, error}`` where ``status`` is the matter's current
    lifecycle status and ``error`` carries the failure message when
    the last attempt set ``status = "error:<reason>"``.
    """
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id,
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    status = matter.status or "new"
    error_message = None
    if isinstance(status, str) and status.startswith("error:"):
        error_message = status[len("error:"):].strip() or "Error desconocido"
        status = "failed"
    return {
        "matter_id": matter_id,
        "status": status,
        "error": error_message,
        "updated_at": matter.updated_at.isoformat() if matter.updated_at else None,
    }


@router.get("/matters/{matter_id}/latest", response_model=AnalysisReportDetailResponse)
def get_latest_analysis(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    report = db.query(AnalysisReport).filter(
        AnalysisReport.matter_id == matter_id,
        AnalysisReport.organization_id == membership.organization_id
    ).order_by(AnalysisReport.created_at.desc()).first()

    if not report:
        raise HTTPException(status_code=404, detail="No existe análisis para este caso")

    risks = db.query(RiskItem).filter(
        RiskItem.analysis_report_id == report.id
    ).all()

    risk_responses = [RiskItemResponse.model_validate(r) for r in risks]

    response_data = AnalysisReportResponse.model_validate(report).model_dump()

    # Deserialize validation_summary from JSON if present
    if report.validation_summary:
        import json
        try:
            response_data["validation_summary"] = json.loads(report.validation_summary)
        except (ValueError, TypeError):
            response_data["validation_summary"] = None

    response_data["risks"] = risk_responses

    return AnalysisReportDetailResponse(**response_data)


@router.get("/matters/{matter_id}/risks", response_model=list[RiskItemResponse])
def list_matter_risks(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    risks = db.query(RiskItem).filter(
        RiskItem.matter_id == matter_id,
        RiskItem.organization_id == membership.organization_id
    ).order_by(
        RiskItem.level.desc(),
        RiskItem.created_at.desc()
    ).all()

    return risks


@router.patch("/risks/{risk_id}/review")
def update_risk_review_status(
    risk_id: int,
    review_status: str,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if review_status not in ["pending", "reviewed", "accepted", "dismissed"]:
        raise HTTPException(status_code=400, detail="Estado de revisión no válido")

    risk = db.query(RiskItem).filter(
        RiskItem.id == risk_id,
        RiskItem.organization_id == membership.organization_id
    ).first()

    if not risk:
        raise HTTPException(status_code=404, detail="Riesgo no encontrado")

    risk.review_status = review_status
    db.commit()

    return {"message": "Estado actualizado", "risk_id": risk_id, "review_status": review_status}
