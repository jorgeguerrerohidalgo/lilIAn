"""
Endpoints para workflow de revisión de análisis.

Workflow: draft → pending → approved/rejected
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewStatus(str):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewCreate(BaseModel):
    analysis_report_id: int
    comments: str | None = None


class ReviewUpdate(BaseModel):
    comments: str | None = None


class ReviewApprove(BaseModel):
    comments: str | None = None


class ReviewReject(BaseModel):
    comments: str  # Required - must provide reason for rejection
    suggested_changes: str | None = None


class ReviewResponse(BaseModel):
    id: int
    analysis_report_id: int
    status: str
    created_by_user_id: int
    reviewed_by_user_id: int | None
    comments: str | None
    rejection_reason: str | None
    suggested_changes: str | None
    created_at: str
    reviewed_at: str | None

    class Config:
        from_attributes = True


def require_reviewer(membership: OrganizationMember) -> None:
    """Verifica que el usuario tenga rol de reviewer."""
    allowed_roles = {MemberRole.OWNER, MemberRole.ADMIN, MemberRole.LAWYER}
    if membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo OWNER, ADMIN o LAWYER pueden revisar análisis"
        )


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """
    Crea un review en estado draft.

    El análisis se crea en estado 'draft' para revisión.
    """
    from app.models.analysis_report import AnalysisReport

    # Verificar que el análisis existe y pertenece a la org
    analysis = db.query(AnalysisReport).filter(
        AnalysisReport.id == review_data.analysis_report_id,
        AnalysisReport.organization_id == membership.organization_id
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análisis no encontrado"
        )

    # Verificar que no existe ya un review pendiente
    from app.models.review import Review
    existing = db.query(Review).filter(
        Review.analysis_report_id == review_data.analysis_report_id,
        Review.status.in_([ReviewStatus.DRAFT, ReviewStatus.PENDING])
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un review activo para este análisis"
        )

    review = Review(
        analysis_report_id=review_data.analysis_report_id,
        organization_id=membership.organization_id,
        created_by_user_id=current_user.id,
        status=ReviewStatus.DRAFT,
        comments=review_data.comments
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    return ReviewResponse(
        id=review.id,
        analysis_report_id=review.analysis_report_id,
        status=review.status,
        created_by_user_id=review.created_by_user_id,
        reviewed_by_user_id=review.reviewed_by_user_id,
        comments=review.comments,
        rejection_reason=review.rejection_reason,
        suggested_changes=review.suggested_changes,
        created_at=review.created_at.isoformat(),
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None
    )


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Obtiene un review por ID."""
    from app.models.review import Review

    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == membership.organization_id
    ).first()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review no encontrado"
        )

    return ReviewResponse(
        id=review.id,
        analysis_report_id=review.analysis_report_id,
        status=review.status,
        created_by_user_id=review.created_by_user_id,
        reviewed_by_user_id=review.reviewed_by_user_id,
        comments=review.comments,
        rejection_reason=review.rejection_reason,
        suggested_changes=review.suggested_changes,
        created_at=review.created_at.isoformat(),
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None
    )


@router.get("/analysis/{analysis_report_id}", response_model=list[ReviewResponse])
def get_reviews_for_analysis(
    analysis_report_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Obtiene todos los reviews para un análisis."""
    from app.models.review import Review

    reviews = db.query(Review).filter(
        Review.analysis_report_id == analysis_report_id,
        Review.organization_id == membership.organization_id
    ).order_by(Review.created_at.desc()).all()

    return [
        ReviewResponse(
            id=r.id,
            analysis_report_id=r.analysis_report_id,
            status=r.status,
            created_by_user_id=r.created_by_user_id,
            reviewed_by_user_id=r.reviewed_by_user_id,
            comments=r.comments,
            rejection_reason=r.rejection_reason,
            suggested_changes=r.suggested_changes,
            created_at=r.created_at.isoformat(),
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None
        )
        for r in reviews
    ]


@router.post("/{review_id}/submit", response_model=ReviewResponse)
def submit_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """
    Cambia estado de draft a pending.

    El review pasa a estado 'pending' para ser revisado por un reviewer.
    """
    require_reviewer(membership)

    from app.models.review import Review

    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == membership.organization_id
    ).first()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review no encontrado"
        )

    if review.status != ReviewStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede submeter un review en estado {review.status}"
        )

    review.status = ReviewStatus.PENDING
    db.commit()
    db.refresh(review)

    return ReviewResponse(
        id=review.id,
        analysis_report_id=review.analysis_report_id,
        status=review.status,
        created_by_user_id=review.created_by_user_id,
        reviewed_by_user_id=review.reviewed_by_user_id,
        comments=review.comments,
        rejection_reason=review.rejection_reason,
        suggested_changes=review.suggested_changes,
        created_at=review.created_at.isoformat(),
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None
    )


@router.post("/{review_id}/approve", response_model=ReviewResponse)
def approve_review(
    review_id: int,
    approve_data: ReviewApprove,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """
    Aprueba un review pending.

    El análisis queda aprobado para uso.
    """
    require_reviewer(membership)

    from app.models.review import Review

    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == membership.organization_id
    ).first()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review no encontrado"
        )

    if review.status != ReviewStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede aprobar un review en estado {review.status}"
        )

    review.status = ReviewStatus.APPROVED
    review.reviewed_by_user_id = current_user.id
    review.reviewed_at = datetime.utcnow()
    if approve_data.comments:
        review.comments = (review.comments or "") + f"\n\n--- Approve ---\n{approve_data.comments}"

    db.commit()
    db.refresh(review)

    # Actualizar status del análisis
    from app.services.analysis import update_analysis_review_status
    update_analysis_review_status(review.analysis_report_id, "approved", db)

    return ReviewResponse(
        id=review.id,
        analysis_report_id=review.analysis_report_id,
        status=review.status,
        created_by_user_id=review.created_by_user_id,
        reviewed_by_user_id=review.reviewed_by_user_id,
        comments=review.comments,
        rejection_reason=review.rejection_reason,
        suggested_changes=review.suggested_changes,
        created_at=review.created_at.isoformat(),
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None
    )


@router.post("/{review_id}/reject", response_model=ReviewResponse)
def reject_review(
    review_id: int,
    reject_data: ReviewReject,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """
    Rechaza un review pending.

    El análisis queda rechazado. Se debe proporcionar razón.
    """
    require_reviewer(membership)

    from app.models.review import Review

    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == membership.organization_id
    ).first()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review no encontrado"
        )

    if review.status != ReviewStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede rechazar un review en estado {review.status}"
        )

    review.status = ReviewStatus.REJECTED
    review.reviewed_by_user_id = current_user.id
    review.reviewed_at = datetime.utcnow()
    review.rejection_reason = reject_data.comments
    review.suggested_changes = reject_data.suggested_changes

    db.commit()
    db.refresh(review)

    # Actualizar status del análisis
    from app.services.analysis import update_analysis_review_status
    update_analysis_review_status(review.analysis_report_id, "rejected", db)

    return ReviewResponse(
        id=review.id,
        analysis_report_id=review.analysis_report_id,
        status=review.status,
        created_by_user_id=review.created_by_user_id,
        reviewed_by_user_id=review.reviewed_by_user_id,
        comments=review.comments,
        rejection_reason=review.rejection_reason,
        suggested_changes=review.suggested_changes,
        created_at=review.created_at.isoformat(),
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None
    )
