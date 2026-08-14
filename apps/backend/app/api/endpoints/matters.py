
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.analysis_report import AnalysisReport
from app.models.chat import ChatMessage, ChatSession
from app.models.client import Client
from app.models.deadline_alert import DeadlineAlert
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_chunk import DocumentChunk
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.risk_item import RiskItem
from app.models.user import User
from app.schemas.matter import MatterCreate, MatterResponse, MatterUpdate

router = APIRouter(prefix="/matters", tags=["matters"])

logger = logging.getLogger(__name__)


@router.get("", response_model=list[MatterResponse])
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
    """Crea un nuevo caso para la organización del usuario actual.

    Valida que el ``client_id`` opcional (cuando se proporciona) perte-
    nezca a la misma organización, evitando leaks cross-tenant.

    Args:
        matter_data: Payload validado (``MatterCreate``).
        current_user: Usuario autenticado que crea el caso.
        membership: Membresía activa (inyecta ``organization_id``).
        db: Sesión de SQLAlchemy inyectada por dependencia.

    Returns:
        ``MatterResponse`` con el caso recién creado.

    Raises:
        HTTPException: 404 si ``client_id`` no pertenece a la org.
    """
    # S1-09: validate that client_id (when provided) belongs to the same
    # organization. Without this check, a user could attach a case to a
    # client from another organization, leaking its existence across tenants.
    if matter_data.client_id is not None:
        client = db.query(Client).filter(
            Client.id == matter_data.client_id,
            Client.organization_id == membership.organization_id,
        ).first()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado en esta organización",
            )

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
    """Actualiza parcialmente un caso existente.

    Aplica únicamente los campos presentes en el payload (partial update).
    Si se modifica ``client_id`` se revalida que pertenezca a la misma
    organización para evitar asignación cross-tenant.

    Args:
        matter_id: ID del caso a actualizar.
        matter_data: Payload parcial validado (``MatterUpdate``).
        current_user: Usuario autenticado.
        membership: Membresía activa (inyecta ``organization_id``).
        db: Sesión de SQLAlchemy inyectada por dependencia.

    Returns:
        ``MatterResponse`` con el caso actualizado.

    Raises:
        HTTPException: 404 si el caso no existe en la org o el nuevo
            ``client_id`` no pertenece a la org.
    """
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    update_data = matter_data.model_dump(exclude_unset=True)

    # S1-09: same client validation as create — preventing cross-tenant
    # assignment when the client_id is updated post-creation.
    if "client_id" in update_data and update_data["client_id"] is not None:
        client = db.query(Client).filter(
            Client.id == update_data["client_id"],
            Client.organization_id == membership.organization_id,
        ).first()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado en esta organización",
            )

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
    """Elimina un caso y todos sus recursos asociados (cascade cleanup).

    Borra en orden hijos→padre para evitar FK violations:
    ``RiskItem`` → ``DocumentChunk`` → ``DocumentAnalysis`` →
    ``AnalysisReport`` → ``DeadlineAlert`` → ``ChatMessage`` →
    ``ChatSession`` → ``Document`` → ``Matter``. Los archivos físicos
    se eliminan DESPUÉS del commit de la DB para que un fallo de
    storage no haga rollback de la limpieza de metadatos.

    Args:
        matter_id: ID del caso a eliminar.
        current_user: Usuario autenticado.
        membership: Membresía activa (inyecta ``organization_id``).
        db: Sesión de SQLAlchemy inyectada por dependencia.

    Returns:
        ``Response`` 204 No Content en éxito.

    Raises:
        HTTPException: 404 si el caso no existe en la org.
    """
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    # S1-02: snapshot storage paths BEFORE we touch the DB. We need them
    # to call storage.delete_file() after the transaction commits, because
    # once Documents are deleted the storage_path column is gone.
    # NOTE: the model column is `storage_path`, not `file_path`.
    storage_paths: list[tuple[int, str | None]] = [
        (d.id, d.storage_path)
        for d in db.query(Document).filter(Document.matter_id == matter_id).all()
    ]

    # S1-11: explicit cascade cleanup so we don't leak orphans in the DB
    # or in storage. Order matters — child rows before the parent matter.
    # DocumentAnalysis doesn't have a matter_id column — its link to a
    # matter is indirect via Document. We resolve the document ids first
    # and delete by subquery (SQLAlchemy forbids .delete() after .join()).
    db.query(RiskItem).filter(RiskItem.matter_id == matter_id).delete(synchronize_session=False)
    db.query(DocumentChunk).filter(DocumentChunk.matter_id == matter_id).delete(synchronize_session=False)
    doc_ids = [doc_id for doc_id, _ in storage_paths]
    if doc_ids:
        db.query(DocumentAnalysis).filter(DocumentAnalysis.document_id.in_(doc_ids)).delete(synchronize_session=False)
    db.query(AnalysisReport).filter(AnalysisReport.matter_id == matter_id).delete(synchronize_session=False)
    db.query(DeadlineAlert).filter(DeadlineAlert.matter_id == matter_id).delete(synchronize_session=False)
    # ChatMessage's link to a matter is indirect via ChatSession.matter_id;
    # same SQLAlchemy restriction on .delete() after .join() applies.
    session_ids = [s.id for s in db.query(ChatSession.id).filter(ChatSession.matter_id == matter_id).all()]
    if session_ids:
        db.query(ChatMessage).filter(ChatMessage.chat_session_id.in_(session_ids)).delete(synchronize_session=False)
    db.query(ChatSession).filter(ChatSession.matter_id == matter_id).delete(synchronize_session=False)
    db.query(Document).filter(Document.matter_id == matter_id).delete(synchronize_session=False)

    db.delete(matter)
    db.commit()

    # S1-02: delete physical files AFTER the DB commit so a storage
    # failure does not roll back the DB cleanup (orphaned metadata is
    # recoverable; orphan files are tracked separately for janitor jobs).
    from app.services.storage import delete_file as storage_delete_file

    for doc_id, storage_path in storage_paths:
        if not storage_path:
            continue
        try:
            if not storage_delete_file(storage_path):
                logger.warning(
                    "storage_delete_returned_false",
                    extra={"matter_id": matter_id, "doc_id": doc_id, "storage_path": storage_path},
                )
        except Exception as exc:
            logger.error(
                "storage_delete_raised",
                extra={
                    "matter_id": matter_id,
                    "doc_id": doc_id,
                    "storage_path": storage_path,
                    "error": str(exc),
                },
            )


@router.get("/{matter_id}/participants")
def get_matter_participants(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Obtiene todos los participantes del caso con sus documentos."""

    from app.services.document_analyzer import get_all_participants_from_matter
    from app.services.required_documents import REQUIRED_DOCUMENTS

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
        p.get("rut")
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
