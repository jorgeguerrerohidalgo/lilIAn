from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from redis import Redis
from rq import Queue
import json

from app.core.database import get_db
from app.core.config import settings
from app.models.document import Document
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.api.deps.auth import get_current_user, require_organization
from app.services import storage

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
]

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

redis_conn = Redis.from_url(settings.REDIS_URL)
document_queue = Queue("document_processing", connection=redis_conn)


@router.post("/matters/{matter_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    matter_id: int,
    file: UploadFile = File(...),
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

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Tipos válidos: PDF, DOCX, DOC, TXT"
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    storage_path, file_hash, file_size = storage.save_file(
        content,
        file.filename,
        membership.organization_id,
        matter_id
    )

    document = Document(
        organization_id=membership.organization_id,
        matter_id=matter_id,
        uploaded_by_user_id=current_user.id,
        original_filename=file.filename,
        storage_path=storage_path,
        mime_type=file.content_type,
        file_size=file_size,
        file_hash=file_hash,
        status="uploaded"
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        document_queue.enqueue(
            "app.services.document_processor.process_document",
            document.id,
            job_timeout="10m"
        )
    except Exception:
        pass

    return document


@router.get("/matters/{matter_id}/documents", response_model=List[DocumentResponse])
def list_matter_documents(
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

    documents = db.query(Document).filter(
        Document.matter_id == matter_id,
        Document.organization_id == membership.organization_id
    ).order_by(Document.created_at.desc()).all()

    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if document.storage_path:
        storage.delete_file(document.storage_path)

    db.delete(document)
    db.commit()


@router.post("/{document_id}/process")
def reprocess_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    document.status = "uploaded"
    document.processed_at = None
    db.commit()

    try:
        document_queue.enqueue(
            "app.services.document_processor.process_document",
            document.id,
            job_timeout="10m"
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Error al encolar procesamiento")

    return {"message": "Documento encolado para procesamiento", "document_id": document_id}
