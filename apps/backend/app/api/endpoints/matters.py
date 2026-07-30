from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.matter import Matter, MatterStatus
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.matter import MatterCreate, MatterUpdate, MatterResponse
from app.api.deps.auth import get_current_user, require_organization

router = APIRouter(prefix="/matters", tags=["matters"])


@router.get("", response_model=List[MatterResponse])
def list_matters(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    status_filter: str = None,
    client_id: int = None
):
    query = db.query(Matter).filter(Matter.organization_id == membership.organization_id)

    if status_filter:
        query = query.filter(Matter.status == status_filter)

    if client_id:
        query = query.filter(Matter.client_id == client_id)

    matters = query.order_by(Matter.created_at.desc()).offset(skip).limit(limit).all()
    return matters


@router.post("", response_model=MatterResponse, status_code=status.HTTP_201_CREATED)
def create_matter(
    matter_data: MatterCreate,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = Matter(
        organization_id=membership.organization_id,
        created_by_user_id=current_user.id,
        client_id=matter_data.client_id,
        title=matter_data.title,
        matter_type=matter_data.matter_type,
        description=matter_data.description,
        urgency=matter_data.urgency,
        counterparty_name=matter_data.counterparty_name,
        relevant_date=matter_data.relevant_date,
        source_channel=matter_data.source_channel,
    )
    db.add(matter)
    db.commit()
    db.refresh(matter)

    return matter


@router.get("/{matter_id}", response_model=MatterResponse)
def get_matter(
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

    return matter


@router.patch("/{matter_id}", response_model=MatterResponse)
def update_matter(
    matter_id: int,
    matter_data: MatterUpdate,
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

    update_data = matter_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(matter, field, value)

    db.commit()
    db.refresh(matter)

    return matter


@router.delete("/{matter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_matter(
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

    db.delete(matter)
    db.commit()


@router.get("/{matter_id}/participants")
def get_matter_participants(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Obtiene todos los participantes del caso con sus documentos."""
    from app.services.document_analyzer import get_all_participants_from_matter
    from app.services.required_documents import REQUIRED_DOCUMENTS, DOCUMENT_TYPE_LABELS
    import json

    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    # Obtener participantes de todos los análisis
    participants = get_all_participants_from_matter(matter_id)

    # Obtener requisitos del tipo de matter
    matter_type_value = matter.matter_type.value if hasattr(matter.matter_type, 'value') else matter.matter_type
    requirements = REQUIRED_DOCUMENTS.get(matter_type_value, REQUIRED_DOCUMENTS.get("other", {}))

    # Para cada participante, calcular completitud
    result = []
    for p in participants:
        rut = p.get("rut")
        doc_ids = p.get("documents", [])

        # Obtener tipos de documentos que tiene este participante
        from app.models.document import Document
        docs = db.query(Document).filter(
            Document.id.in_(doc_ids)
        ).all() if doc_ids else []

        doc_types = [d.detected_document_type for d in docs if d.detected_document_type]

        # Calcular faltantes
        required = requirements.get("required", [])
        missing = [dt for dt in required if dt not in doc_types]

        result.append({
            **p,
            "documents_types": doc_types,
            "documents_count": len(docs),
            "required_documents": required,
            "missing_documents": missing,
            "completeness_score": round((len(required) - len(missing)) / max(len(required), 1), 2)
        })

    return {
        "matter_id": matter_id,
        "participants": result,
        "requirements": {
            "required": requirements.get("required", []),
            "recommended": requirements.get("recommended", [])
        }
    }
