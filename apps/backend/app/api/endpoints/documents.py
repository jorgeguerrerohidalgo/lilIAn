from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging

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

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
]

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


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

    background_tasks.add_task(process_document_background, document.id)

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

    # Eliminar chunks asociados primero
    from app.models.document_chunk import DocumentChunk
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).delete()

    if document.storage_path:
        storage.delete_file(document.storage_path)

    db.delete(document)
    db.commit()


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
    """Función que se ejecuta en background para procesar documentos."""
    from app.services.document_processor import process_document
    from app.core.database import SessionLocal

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


@router.post("/{document_id}/analyze")
def analyze_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Analiza un documento y extrae datos estructurados estilo Harvey.ai."""
    import logging
    logger = logging.getLogger(__name__)

    from app.services.document_analyzer import analyze_document_full

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if not document.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="El documento aún no tiene texto extraído. Procesa primero."
        )

    try:
        analysis = analyze_document_full(document_id)
        return {
            "message": "Documento analizado exitosamente",
            "document_id": document_id,
            "has_analysis": True
        }
    except Exception as e:
        logger.error(f"Error analyzing document {document_id}: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en análisis: {type(e).__name__}: {str(e)}")


@router.get("/{document_id}/analysis")
def get_document_analysis(
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Obtiene el análisis estructurado de un documento."""
    from app.services.document_analyzer import get_document_analysis as get_doc_analysis
    import json

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == membership.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    analysis = get_doc_analysis(document_id)

    if not analysis:
        return {
            "has_analysis": False,
            "document_id": document_id
        }

    return {
        "has_analysis": True,
        "document_id": document_id,
        "document_type": analysis.document_type,
        "participants": json.loads(analysis.participants) if analysis.participants else [],
        "financial_terms": json.loads(analysis.financial_terms) if analysis.financial_terms else {},
        "obligations": json.loads(analysis.obligations) if analysis.obligations else [],
        "clauses_by_type": json.loads(analysis.clauses_by_type) if analysis.clauses_by_type else {},
        "unusual_clauses": json.loads(analysis.unusual_clauses) if analysis.unusual_clauses else [],
        "risk_assessment": json.loads(analysis.risk_assessment) if analysis.risk_assessment else [],
        "contract_timeline": json.loads(analysis.contract_timeline) if analysis.contract_timeline else [],
        "legal_references": json.loads(analysis.legal_references) if analysis.legal_references else [],
        "indexed_content": analysis.indexed_content,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None
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

    # Verificar que el matter existe
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    # Obtener todos los análisis de documentos del matter
    analyses = db.query(DocumentAnalysis).join(Document).filter(
        Document.matter_id == matter_id,
        Document.organization_id == membership.organization_id
    ).all()

    # Crear mapa de documentos para obtener nombres
    doc_map = {a.document_id: a for a in analyses}

    # Agregar riesgos
    all_risks = []
    risk_summary = {"high": 0, "medium": 0, "low": 0}
    documents_analyzed = 0
    risk_types = set()

    for analysis in analyses:
        if analysis.risk_assessment:
            risks = json.loads(analysis.risk_assessment) if isinstance(analysis.risk_assessment, str) else analysis.risk_assessment
            for risk in risks:
                risk_copy = {**risk, "document_id": analysis.document_id}
                # Incluir nombre del documento
                risk_copy["document_name"] = analysis.document.original_filename if analysis.document else f"Documento {analysis.document_id}"
                all_risks.append(risk_copy)
                level = risk.get("risk_level", "low")
                if level in risk_summary:
                    risk_summary[level] += 1
                # Track unique risk types
                risk_type_val = risk.get("clause_type", "unknown")
                if risk_type_val:
                    risk_types.add(risk_type_val)
            documents_analyzed += 1

    # Filtrar por nivel si se especifica
    if level:
        all_risks = [r for r in all_risks if r.get("risk_level") == level]

    # Filtrar por tipo si se especifica
    if risk_type:
        all_risks = [r for r in all_risks if r.get("clause_type") == risk_type]

    # Ordenar
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
        "risk_types": sorted(list(risk_types)),
        "risks": all_risks
    }
