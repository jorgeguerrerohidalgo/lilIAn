import json
import logging
from datetime import datetime

import fitz
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.legal_area import get_legal_area_from_matter_type
from app.models.matter import Matter

# S1-07: hard caps on PDF processing to avoid DoS / memory exhaustion.
MAX_PDF_PAGES = 500
MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB aligned with MAX_FILE_SIZE
MAX_DOCX_BYTES = 50 * 1024 * 1024


class DocumentTooLargeError(Exception):
    """Raised when a document exceeds the configured size or page limits."""


def extract_text_from_file(file_path: str, mime_type: str | None) -> str:
    logger.info(f"[EXTRACT] extract_text_from_file: path={file_path}, mime={mime_type}")  # S4-05
    if not file_path or not mime_type:
        logger.info("[EXTRACT] ERROR: Missing file_path or mime_type")  # S4-05
        return ""

    try:
        if mime_type == "application/pdf":
            result = extract_text_from_pdf(file_path)
            logger.info(f"[EXTRACT] PDF extraction result length: {len(result)}")  # S4-05
            return result
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword"
        ]:
            result = extract_text_from_docx(file_path)
            logger.info(f"[EXTRACT] DOCX extraction result length: {len(result)}")  # S4-05
            return result
        elif mime_type == "text/plain":
            result = extract_text_from_txt(file_path)
            logger.info(f"[EXTRACT] TXT extraction result length: {len(result)}")  # S4-05
            return result
        else:
            logger.info(f"[EXTRACT] ERROR: Unsupported mime_type: {mime_type}")  # S4-05
            return ""
    except DocumentTooLargeError as exc:
        logger.warning("Document rejected: %s", exc)
        return f"Error extracting text: {exc}"
    except Exception as e:
        logger.info(f"[EXTRACT] ERROR: {type(e).__name__}: {str(e)}")  # S4-05
        return f"Error extracting text: {str(e)}"


def _safe_open_pdf(file_path: str) -> fitz.Document:
    """Open a PDF enforcing size and page caps before handing it to PyMuPDF."""
    import os

    try:
        size = os.path.getsize(file_path)
    except OSError:
        size = 0
    if size > MAX_PDF_BYTES:
        raise DocumentTooLargeError(
            f"PDF excede el tamaño máximo ({size} bytes)"
        )

    doc = fitz.open(file_path)
    if len(doc) > MAX_PDF_PAGES:
        page_count = len(doc)
        doc.close()
        raise DocumentTooLargeError(
            f"PDF excede el máximo de {MAX_PDF_PAGES} páginas ({page_count} detectadas)"
        )
    return doc


def extract_text_from_pdf(file_path: str) -> str:
    logger.info(f"[EXTRACT] extract_text_from_pdf: path={file_path}")  # S4-05
    text_parts = []
    page_count = 0
    try:
        doc = _safe_open_pdf(file_path)
        page_count = len(doc)
        logger.info(f"[EXTRACT] PDF opened, {page_count} pages")  # S4-05
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
    except DocumentTooLargeError:
        raise
    except Exception as e:
        logger.info(f"[EXTRACT] ERROR opening PDF: {type(e).__name__}: {str(e)}")  # S4-05
        return ""

    full_text = "\n\n".join(text_parts)
    logger.info(f"[EXTRACT] PDF text extracted, length={len(full_text)}")  # S4-05
    # Si no se extrajo texto o es muy poco, usar OCR
    if len(full_text.strip()) < 100:
        logger.info("[EXTRACT] Text too short, attempting OCR")  # S4-05
        ocr_text = extract_text_from_pdf_ocr(file_path)
        if ocr_text:
            return f"--- PDF ({page_count} páginas - OCR) ---\n\n{ocr_text}"

    return f"--- PDF ({page_count} páginas) ---\n\n{full_text}"


def extract_text_from_pdf_ocr(file_path: str) -> str:
    """Extrae texto de PDFs escaneados usando Tesseract OCR"""
    logger.info(f"[EXTRACT] extract_text_from_pdf_ocr: path={file_path}")  # S4-05
    try:
        import pytesseract
        from PIL import Image

        doc = _safe_open_pdf(file_path)
        text_parts = []

        for _page_num, page in enumerate(doc):
            # Convertir página a imagen
            pix = page.get_pixmap(dpi=200)
            img_data = pix.tobytes("png")

            # Abrir como imagen PIL
            from io import BytesIO
            img = Image.open(BytesIO(img_data))

            # OCR con español
            text = pytesseract.image_to_string(img, lang='spa+eng')
            text_parts.append(text)

            img.close()

        doc.close()
        return "\n\n".join(text_parts)
    except DocumentTooLargeError:
        raise
    except Exception as e:
        logger.info(f"[EXTRACT] OCR ERROR: {str(e)}")  # S4-05
        return f"[OCR Error: {str(e)}]"


def extract_text_from_docx(file_path: str) -> str:
    logger.info(f"[EXTRACT] extract_text_from_docx: path={file_path}")  # S4-05
    try:
        doc = DocxDocument(file_path)
        text = "\n\n".join([para.text for para in doc.paragraphs])
        logger.info(f"[EXTRACT] DOCX extracted, length={len(text)}")  # S4-05
        return f"--- DOCX ---\n\n{text}"
    except Exception as e:
        logger.info(f"[EXTRACT] DOCX ERROR: {type(e).__name__}: {str(e)}")  # S4-05
        return ""


def extract_text_from_txt(file_path: str) -> str:
    logger.info(f"[EXTRACT] extract_text_from_txt: path={file_path}")  # S4-05
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            logger.info(f"[EXTRACT] TXT (utf-8) extracted, length={len(content)}")  # S4-05
            return content
    except Exception as e:
        logger.info(f"[EXTRACT] TXT utf-8 failed: {e}, trying latin-1")  # S4-05
        try:
            with open(file_path, encoding="latin-1") as f:
                content = f.read()
                logger.info(f"[EXTRACT] TXT (latin-1) extracted, length={len(content)}")  # S4-05
                return content
        except Exception as e2:
            logger.error(f"[EXTRACT] TXT latin-1 also failed: {e2}")
            return ""


def _normalize_extracted_text(value: object) -> str:
    """Coerce None / non-str input into a safe empty string."""
    if not value:
        return ""
    if not isinstance(value, str):
        return str(value)
    return value


def _existing_content_hash(db, document_id: int) -> str | None:
    """Read the content_hash stored on the first chunk, if any."""
    first_chunk = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .first()
    )
    if not first_chunk or not first_chunk.chunk_metadata:
        return None
    try:
        return json.loads(first_chunk.chunk_metadata).get("content_hash")
    except Exception:
        return None


def _should_skip_chunking(db, document_id: int, content_hash: str, force: bool) -> dict | None:
    """Idempotency guard. Returns a skip-result dict when nothing needs to be done."""
    existing_chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .first()
    )

    if existing_chunks is not None and not force:
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .count()
        )
        return {
            "created": 0,
            "skipped": True,
            "status": "skipped",
            "message": f"Chunks ya existen ({chunk_count}), usa force=True para recrear",
        }

    previous_hash = _existing_content_hash(db, document_id)
    if previous_hash == content_hash and not force:
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .count()
        )
        return {
            "created": 0,
            "skipped": True,
            "status": "skipped",
            "message": f"Contenido no cambió (hash: {content_hash}), usa force=True para recrear",
        }
    return None


def _delete_existing_chunks(db, document_id: int) -> None:
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).delete()


def _persist_chunks(
    db,
    raw_chunks: list,
    document_id: int,
    organization_id: int,
    matter_id: int,
    legal_area: str | None,
    content_hash: str,
    embedding_provider,
) -> int:
    created = 0
    for raw_chunk in raw_chunks:
        chunk = DocumentChunk(
            document_id=document_id,
            organization_id=organization_id,
            matter_id=matter_id,
            chunk_index=raw_chunk["chunk_index"],
            content=raw_chunk["content"],
            page_number=raw_chunk["page_number"],
            section_title=raw_chunk.get("section_title"),
            legal_area=legal_area,
            chunk_metadata=json.dumps({
                "content_hash": content_hash,
                "created_at": datetime.utcnow().isoformat(),
            }),
        )
        if embedding_provider:
            try:
                embedding = embedding_provider.generate_embedding(raw_chunk["content"])
                chunk.embedding = json.dumps(embedding)
            except Exception:
                pass
        db.add(chunk)
        created += 1
    db.commit()
    return created


def create_chunks_for_document(
    document_id: int,
    extracted_text: str,
    organization_id: int,
    matter_id: int,
    db,
    legal_area: str | None = None,
    force: bool = False,
) -> dict:
    """
    Crea chunks para un documento de forma idempotente.

    S4-06: split into helpers (``_should_skip_chunking``,
    ``_persist_chunks``, ``_existing_content_hash``,
    ``_normalize_extracted_text``) so this orchestrator only owns the
    control flow.
    """
    extracted_text = _normalize_extracted_text(extracted_text)

    import hashlib

    from app.services.chunker import split_text_into_chunks
    from app.services.embeddings import get_embedding_provider

    content_hash = hashlib.sha256(extracted_text.encode()).hexdigest()[:16]

    skip_result = _should_skip_chunking(db, document_id, content_hash, force)
    if skip_result is not None:
        return skip_result

    try:
        embedding_provider = get_embedding_provider()
    except Exception:
        embedding_provider = None

    raw_chunks = split_text_into_chunks(extracted_text)
    _delete_existing_chunks(db, document_id)
    created = _persist_chunks(
        db,
        raw_chunks,
        document_id=document_id,
        organization_id=organization_id,
        matter_id=matter_id,
        legal_area=legal_area,
        content_hash=content_hash,
        embedding_provider=embedding_provider,
    )

    return {
        "created": created,
        "skipped": False,
        "status": "created",
        "content_hash": content_hash,
    }


def process_document(document_id: int, force: bool = False) -> dict:
    """
    Procesa un documento de forma idempotente.

    Args:
        document_id: ID del documento a procesar
        force: Si True, fuerza el reprocesamiento incluso si ya fue procesado

    Returns:
        dict con estado del procesamiento
    """
    logger.info(f"[PROCESS] START document_id={document_id}, force={force}")  # S4-05
    db = SessionLocal()
    try:
        # S1-08: acquire a pessimistic row lock so two workers (RQ + the
        # in-process BackgroundTasks fallback) cannot process the same
        # document concurrently. The lock is released automatically when
        # the transaction commits or rolls back below.
        document = (
            db.query(Document)
            .filter(Document.id == document_id)
            .with_for_update()
            .first()
        )

        if not document:
            logger.info(f"[PROCESS] ERROR: Document {document_id} not found")  # S4-05
            return {"error": "Documento no encontrado", "status": "error"}

        logger.info(f"[PROCESS] Doc {document_id}: status={document.status}, mime={document.mime_type}, path={document.storage_path}")  # S4-05
        # Verificar si ya fue procesado (y no es forzado)
        if document.status == "processed" and not force:
            existing_chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).count()
            if existing_chunks > 0:
                logger.info(f"[PROCESS] Doc {document_id} already processed, skipping")  # S4-05
                return {
                    "document_id": document_id,
                    "status": "already_processed",
                    "skipped": True,
                    "message": "Documento ya fue procesado, usa force=True para reprocesar",
                    "chunk_count": existing_chunks
                }

        document.status = "processing"
        db.commit()
        logger.info(f"[PROCESS] Doc {document_id} status -> processing")  # S4-05
        # Inferir legal_area desde el matter
        legal_area = None
        if document.matter_id:
            matter = db.query(Matter).filter(Matter.id == document.matter_id).first()
            if matter and matter.matter_type:
                legal_area = get_legal_area_from_matter_type(matter.matter_type.value)
                logger.info(f"[PROCESS] Doc {document_id}: legal_area={legal_area}")  # S4-05
        if document.storage_path:
            from app.services.storage import get_file_path
            file_path = get_file_path(document.storage_path)
            logger.info(f"[PROCESS] Doc {document_id}: file_path={file_path}")  # S4-05
            if file_path:
                logger.info(f"[PROCESS] Doc {document_id}: Calling extract_text_from_file")  # S4-05
                extracted_text = extract_text_from_file(file_path, document.mime_type)
                document.extracted_text = extracted_text
                logger.info(f"[PROCESS] Doc {document_id}: extracted_text length={len(extracted_text) if extracted_text else 0}")  # S4-05
                logger.info(f"[PROCESS] Doc {document_id}: === EXTRACTED TEXT START ===")  # S4-05
                logger.debug(extracted_text[:3000] if extracted_text else "EMPTY")  # S4-05
                logger.info(f"[PROCESS] Doc {document_id}: === EXTRACTED TEXT END (total: {len(extracted_text) if extracted_text else 0} chars) ===")  # S4-05
                if document.mime_type == "application/pdf":
                    try:
                        doc = fitz.open(file_path)
                        document.page_count = len(doc)
                        doc.close()
                        logger.info(f"[PROCESS] Doc {document_id}: PDF page_count={document.page_count}")  # S4-05
                    except Exception as e:
                        logger.info(f"[PROCESS] Doc {document_id}: Error getting page count: {e}")  # S4-05
                document.status = "processed"
                document.processed_at = datetime.utcnow()
                db.commit()
                logger.info(f"[PROCESS] Doc {document_id}: status -> processed, extracted_text saved ({len(extracted_text) if extracted_text else 0} chars)")  # S4-05
                # Crear chunks de forma idempotente
                logger.info(f"[PROCESS] Doc {document_id}: Creating chunks")  # S4-05
                chunk_result = create_chunks_for_document(
                    document_id=document.id,
                    extracted_text=extracted_text,
                    organization_id=document.organization_id,
                    matter_id=document.matter_id,
                    db=db,
                    legal_area=legal_area,
                    force=force
                )
                logger.info(f"[PROCESS] Doc {document_id}: chunk_result={chunk_result}")  # S4-05
                # Clasificar documento de forma async (no bloquea procesamiento)
                logger.info(f"[PROCESS] Doc {document_id}: Calling _classify_document_async")  # S4-05
                _classify_document_async(document.id)

                logger.info(f"[PROCESS] Doc {document_id}: COMPLETED SUCCESSFULLY")  # S4-05
                return {
                    "document_id": document_id,
                    "status": document.status,
                    "extracted_length": len(document.extracted_text) if document.extracted_text else 0,
                    "legal_area": legal_area.value if legal_area else None,
                    "chunks_created": chunk_result.get("created", 0),
                    "chunks_skipped": chunk_result.get("skipped", False),
                    "content_hash": chunk_result.get("content_hash")
                }

            else:
                logger.info(f"[PROCESS] Doc {document_id}: ERROR file_path is None")  # S4-05
                document.status = "failed"
                db.commit()
                return {"error": "Storage path no encontrado", "status": "failed"}
        else:
            logger.info(f"[PROCESS] Doc {document_id}: ERROR storage_path is None")  # S4-05
            document.status = "failed"
            db.commit()
            return {"error": "No tiene storage_path", "status": "failed"}

    except Exception as e:
        logger.info(f"[PROCESS] Doc {document_id}: EXCEPTION {type(e).__name__}: {str(e)}")  # S4-05
        try:
            document.status = "failed"
            db.commit()
        except Exception:
            pass
        return {"error": str(e), "status": "failed"}
    finally:
        db.close()
        logger.info(f"[PROCESS] Doc {document_id}: Finished, db closed")  # S4-05
def _classify_document_async(document_id: int) -> None:
    """Clasifica un documento de forma asíncrona."""
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    try:
        from app.services.document_classifier import classify_document

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(classify_document(document_id))
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"Classification failed for document {document_id}: {e}")
