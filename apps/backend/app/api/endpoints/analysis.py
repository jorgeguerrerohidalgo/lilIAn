from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import json

from app.core.database import get_db
from app.models.analysis_report import AnalysisReport
from app.models.risk_item import RiskItem
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.analysis import (
    AnalysisReportResponse,
    AnalysisReportDetailResponse,
    RiskItemResponse,
    GenerateAnalysisRequest
)
from app.api.deps.auth import get_current_user, require_organization

router = APIRouter(prefix="/analysis", tags=["analysis"])


def run_analysis_task(matter_id: int, organization_id: int, user_id: int):
    from app.services.analysis import generate_analysis_for_matter
    generate_analysis_for_matter(matter_id, organization_id, user_id)


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

    background_tasks.add_task(
        run_analysis_task,
        analysis_request.matter_id,
        membership.organization_id,
        current_user.id
    )

    return {
        "message": "Análisis iniciado en segundo plano",
        "matter_id": analysis_request.matter_id,
        "status": "processing"
    }


@router.get("/matters/{matter_id}", response_model=List[AnalysisReportResponse])
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
    response_data["risks"] = risk_responses

    return AnalysisReportDetailResponse(**response_data)


@router.get("/matters/{matter_id}/risks", response_model=List[RiskItemResponse])
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
