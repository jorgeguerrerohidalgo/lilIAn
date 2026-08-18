import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.document import Document
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services import storage

router = APIRouter(prefix="/documents", tags=["documents"])

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Map magic-byte signatures to the canonical MIME type we accept.
MAGIC_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/msword"),
)

_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


def _detect_mime_from_content(content: bytes) -> str | None:
    """Detect MIME type from the actual file bytes (magic numbers).

    Returning ``None`` means we could not positively identify the file as
    one of the formats we accept.
    """
    for signature, mime in MAGIC_SIGNATURES:
        if content.startswith(signature):
            return mime
    # text/plain: require ASCII/UTF-8 decodable without errors.
    try:
        content.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return None


def _sanitize_filename(name: str | None) -> str:
    """Return a filesystem- and HTML-safe filename stripped of path components
    and control characters. Falls back to ``"upload"`` if nothing usable remains.
    """
    if not name:
        return "upload"
    # Strip any directory components (basename only).
    name = name.replace("\\", "/").split("/")[-1]
    name = _FILENAME_SAFE_RE.sub("_", name)
    name = name.strip("._") or "upload"
    return name[:255]


def process_document_background(document_id: int) -> None:
    """Background task that runs after response is sent."""
    from app.services.document_processor import process_document as process_doc

    try:
        logger.info(f"Starting background processing for document {document_id}")
        result = process_doc(document_id)
        logger.info(f"Background processing completed: {result.get('status')}")
    except Exception as e:
        logger.error(f"Background processing failed: {type(e).__name__}: {str(e)}", exc_info=True)


@router.post("/matters/{matter_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    matter_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    detected_mime = _detect_mime_from_content(content)
    if detected_mime is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no permitido. El contenido no coincide con un formato aceptado (PDF, DOCX, DOC, TXT)."
        )

    # Reject mismatched Content-Type headers unless they fall in the allowed set.
    declared_mime = file.content_type
    if declared_mime and declared_mime not in ALLOWED_MIME_TYPES:
        logger.warning(
            "Rejected upload with disallowed declared mime type",
            extra={"matter_id": matter_id, "declared_mime": declared_mime, "user_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no permitido. Tipos válidos: PDF, DOCX, DOC, TXT"
        )

    safe_filename = _sanitize_filename(file.filename)

    storage_path, file_hash, file_size = storage.save_file(
        content,
        safe_filename,
        membership.organization_id,
        matter_id
    )

    document = Document(
        organization_id=membership.organization_id,
        matter_id=matter_id,
        uploaded_by_user_id=current_user.id,
        original_filename=safe_filename,
        storage_path=storage_path,
        mime_type=detected_mime,
        file_size=file_size,
        file_hash=file_hash,
        status="uploaded"
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # NOTE: Background processing removed - user must click "Procesar" manually
    # background_tasks.add_task(process_document_background, document.id)

    return document


@router.get("/matters/{matter_id}/documents", response_model=list[DocumentResponse])
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

    # Eliminar chunks asociados primero
    from app.models.document_chunk import DocumentChunk
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).delete()

    if document.storage_path:
        storage.delete_file(document.storage_path)

    db.delete(document)
    db.commit()


@router.get("/{document_id}/debug")
def debug_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Diagnostic endpoint for stuck documents.

    Returns the document's status, storage_path, whether the file
    actually exists on disk, and the document's timestamps. Used to
    figure out why a document is stuck in "processing" — almost always
    a storage issue (Railway's ephemeral filesystem wiped the file on
    the latest deploy).
    """
    import os
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    file_exists = False
    resolved_path = None
    if document.storage_path:
        from app.services.storage import get_file_path
        resolved_path = get_file_path(document.storage_path)
        if resolved_path:
            file_exists = os.path.exists(resolved_path)

    return {
        "document_id": document.id,
        "status": document.status,
        "original_filename": document.original_filename,
        "storage_path": document.storage_path,
        "resolved_path": resolved_path,
        "file_exists_on_disk": file_exists,
        "has_extracted_text": bool(document.extracted_text),
        "extracted_text_length": len(document.extracted_text) if document.extracted_text else 0,
        "file_size_bytes": document.file_size,
        "page_count": document.page_count,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "hint": (
            "El archivo no existe en disco. Railway borra /app/storage/documents "
            "en cada redeploy. Solución: re-subir el documento."
        ) if not file_exists and document.storage_path else None,
    }


@router.post("/{document_id}/process")
def reprocess_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Procesa un documento en background, retorna inmediatamente."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    document.status = "queued"
    document.processed_at = None
    db.commit()

    # Procesar en background si BackgroundTasks está disponible
    if background_tasks:
        background_tasks.add_task(_process_document_background, document_id)

    return {
        "message": "Documento encolado para procesamiento",
        "document_id": document_id,
        "status": "queued"
    }


def _process_document_background(document_id: int) -> None:
    """Función que se ejecuta en background para procesar documentos.

    S3-05: FastAPI's ``BackgroundTasks`` scheduler runs tasks in a
    threadpool (not the event loop), so it's safe to use the sync
    SQLAlchemy session here. If you ever need to call this from
    ``async def`` code, dispatch through ``run_in_threadpool`` to
    keep the event loop unblocked.
    """
    from app.core.database import SessionLocal
    from app.services.document_processor import process_document

    db = SessionLocal()
    try:
        # Actualizar estado a processing
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = "processing"
            db.commit()

        # Procesar
        result = process_document(document_id, force=True)

        # Actualizar estado final
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            if result.get("status") == "error":
                document.status = "failed"
            else:
                document.status = "processed"
            db.commit()
        logger.info(f"Document {document_id} processed: {result.get('status')}")
    except Exception as e:
        logger.error(f"Background processing failed: {type(e).__name__}: {str(e)}", exc_info=True)
        # Marcar como failed
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
