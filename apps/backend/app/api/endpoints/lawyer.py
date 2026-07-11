from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.matter import Matter, MatterStatus
from app.models.template import MatterNote, MatterStatusHistory
from app.models.organization_member import OrganizationMember, MemberRole
from app.models.user import User
from app.models.analysis_report import AnalysisReport
from app.models.risk_item import RiskItem
from app.api.deps.auth import get_current_user, require_organization

router = APIRouter(prefix="/lawyer", tags=["lawyer"])


class MatterNoteCreate(BaseModel):
    matter_id: int
    content: str


class MatterNoteResponse(BaseModel):
    id: int
    matter_id: int
    user_id: int
    content: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MatterStatusUpdate(BaseModel):
    matter_id: int
    new_status: str
    notes: Optional[str] = None


class LawyerMatterResponse(BaseModel):
    id: int
    title: str
    matter_type: str
    status: str
    urgency: str
    description: Optional[str]
    counterparty_name: Optional[str]
    created_at: str
    updated_at: str
    risk_count: int
    has_analysis: bool
    created_by_name: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/cases", response_model=List[LawyerMatterResponse])
def list_lawyer_cases(
    status_filter: Optional[str] = None,
    urgency_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role not in [MemberRole.LAWYER, MemberRole.ADMIN, MemberRole.OWNER]:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = db.query(Matter).filter(
        Matter.organization_id == membership.organization_id
    )

    if status_filter:
        query = query.filter(Matter.status == status_filter)

    if urgency_filter:
        query = query.filter(Matter.urgency == urgency_filter)

    query = query.filter(
        Matter.status.in_([
            MatterStatus.NEW,
            MatterStatus.ANALYSIS_READY,
            MatterStatus.PENDING_HUMAN_REVIEW,
            MatterStatus.MISSING_INFORMATION,
            MatterStatus.CONTACT_CLIENT
        ])
    )

    matters = query.order_by(Matter.created_at.desc()).all()

    result = []
    for matter in matters:
        risk_count = db.query(RiskItem).filter(
            RiskItem.matter_id == matter.id,
            RiskItem.level.in_(["red", "yellow"])
        ).count()

        has_analysis = db.query(AnalysisReport).filter(
            AnalysisReport.matter_id == matter.id
        ).first() is not None

        creator = db.query(User).filter(User.id == matter.created_by_user_id).first()

        result.append(LawyerMatterResponse(
            id=matter.id,
            title=matter.title,
            matter_type=matter.matter_type.value if hasattr(matter.matter_type, 'value') else matter.matter_type,
            status=matter.status.value if hasattr(matter.status, 'value') else matter.status,
            urgency=matter.urgency.value if hasattr(matter.urgency, 'value') else matter.urgency,
            description=matter.description,
            counterparty_name=matter.counterparty_name,
            created_at=matter.created_at.isoformat(),
            updated_at=matter.updated_at.isoformat(),
            risk_count=risk_count,
            has_analysis=has_analysis,
            created_by_name=creator.full_name if creator else None
        ))

    return result


@router.post("/matters/{matter_id}/notes", response_model=MatterNoteResponse, status_code=201)
def add_matter_note(
    matter_id: int,
    note_data: MatterNoteCreate,
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

    note = MatterNote(
        matter_id=matter_id,
        user_id=current_user.id,
        content=note_data.content
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    return MatterNoteResponse(
        id=note.id,
        matter_id=note.matter_id,
        user_id=note.user_id,
        content=note.content,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat()
    )


@router.get("/matters/{matter_id}/notes", response_model=List[MatterNoteResponse])
def get_matter_notes(
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

    notes = db.query(MatterNote).filter(
        MatterNote.matter_id == matter_id
    ).order_by(MatterNote.created_at.desc()).all()

    return [
        MatterNoteResponse(
            id=n.id,
            matter_id=n.matter_id,
            user_id=n.user_id,
            content=n.content,
            created_at=n.created_at.isoformat(),
            updated_at=n.updated_at.isoformat()
        )
        for n in notes
    ]


@router.patch("/matters/{matter_id}/status")
def update_matter_status(
    matter_id: int,
    status_data: MatterStatusUpdate,
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

    try:
        new_status = MatterStatus(status_data.new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Estado no válido")

    old_status = matter.status

    history = MatterStatusHistory(
        matter_id=matter_id,
        changed_by_user_id=current_user.id,
        old_status=old_status.value if hasattr(old_status, 'value') else old_status,
        new_status=new_status.value,
        notes=status_data.notes
    )
    db.add(history)

    matter.status = new_status
    db.commit()

    return {
        "message": "Estado actualizado",
        "matter_id": matter_id,
        "old_status": old_status.value if hasattr(old_status, 'value') else old_status,
        "new_status": new_status.value
    }


@router.post("/matters/{matter_id}/assign")
def assign_matter_to_lawyer(
    matter_id: int,
    lawyer_user_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if membership.role not in [MemberRole.LAWYER, MemberRole.ADMIN, MemberRole.OWNER]:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    lawyer_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == lawyer_user_id,
        OrganizationMember.organization_id == membership.organization_id,
        OrganizationMember.role.in_([MemberRole.LAWYER, MemberRole.ADMIN, MemberRole.OWNER])
    ).first()

    if not lawyer_member:
        raise HTTPException(status_code=400, detail="Usuario no es abogado válido")

    matter.assigned_lawyer_id = lawyer_user_id
    db.commit()

    return {"message": "Abogado asignado", "matter_id": matter_id, "lawyer_id": lawyer_user_id}


@router.get("/matters/{matter_id}/summary")
def get_matter_lawyer_summary(
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

    latest_report = db.query(AnalysisReport).filter(
        AnalysisReport.matter_id == matter_id
    ).order_by(AnalysisReport.created_at.desc()).first()

    risks = db.query(RiskItem).filter(
        RiskItem.matter_id == matter_id
    ).all()

    notes = db.query(MatterNote).filter(
        MatterNote.matter_id == matter_id
    ).order_by(MatterNote.created_at.desc()).limit(10).all()

    return {
        "matter": {
            "id": matter.id,
            "title": matter.title,
            "status": matter.status.value if hasattr(matter.status, 'value') else matter.status,
            "urgency": matter.urgency.value if hasattr(matter.urgency, 'value') else matter.urgency,
            "created_at": matter.created_at.isoformat()
        },
        "analysis": {
            "exists": latest_report is not None,
            "summary": latest_report.summary if latest_report else None,
            "confidence": latest_report.confidence if latest_report else None,
            "created_at": latest_report.created_at.isoformat() if latest_report else None
        } if latest_report else None,
        "risks": {
            "total": len(risks),
            "red": len([r for r in risks if r.level == "red"]),
            "yellow": len([r for r in risks if r.level == "yellow"]),
            "green": len([r for r in risks if r.level == "green"]),
            "gray": len([r for r in risks if r.level == "gray"])
        },
        "recent_notes": [
            {
                "id": n.id,
                "content": n.content,
                "created_at": n.created_at.isoformat()
            }
            for n in notes
        ]
    }
