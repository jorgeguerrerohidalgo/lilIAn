from datetime import datetime
from typing import Optional
import fitz
from docx import Document as DocxDocument
import json

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.matter import Matter
from app.models.legal_area import get_legal_area_from_matter_type


def extract_text_from_file(file_path: str, mime_type: Optional[str]) -> str:
    if not file_path or not mime_type:
        return ""

    try:
        if mime_type == "application/pdf":
            return extract_text_from_pdf(file_path)
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword"
        ]:
            return extract_text_from_docx(file_path)
        elif mime_type == "text/plain":
            return extract_text_from_txt(file_path)
        else:
            return ""
    except Exception as e:
        return f"Error extracting text: {str(e)}"


def extract_text_from_pdf(file_path: str) -> str:
    text_parts = []
    page_count = 0
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
    except Exception:
        return ""
    return f"--- PDF ({page_count} páginas) ---\n\n" + "\n\n".join(text_parts)


def extract_text_from_docx(file_path: str) -> str:
    try:
        doc = DocxDocument(file_path)
        text = "\n\n".join([para.text for para in doc.paragraphs])
        return f"--- DOCX ---\n\n{text}"
    except Exception:
        return ""


def extract_text_from_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception:
            return ""


def create_chunks_for_document(
    document_id: int,
    extracted_text: str,
    organization_id: int,
    matter_id: int,
    db,
    legal_area: Optional[str] = None
) -> int:
    from app.services.chunker import split_text_into_chunks
    from app.services.embeddings import get_embedding_provider

    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()

    raw_chunks = split_text_into_chunks(extracted_text)

    # Get embedding provider
    try:
        embedding_provider = get_embedding_provider()
    except Exception:
        embedding_provider = None

    for raw_chunk in raw_chunks:
        chunk = DocumentChunk(
            document_id=document_id,
            organization_id=organization_id,
            matter_id=matter_id,
            chunk_index=raw_chunk["chunk_index"],
            content=raw_chunk["content"],
            page_number=raw_chunk["page_number"],
            section_title=raw_chunk.get("section_title"),
            legal_area=legal_area
        )

        # Generate embedding if provider is available
        if embedding_provider:
            try:
                embedding = embedding_provider.generate_embedding(raw_chunk["content"])
                chunk.embedding = json.dumps(embedding)
            except Exception:
                pass

        db.add(chunk)

    db.commit()
    return len(raw_chunks)


def process_document(document_id: int) -> dict:
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()

        if not document:
            return {"error": "Documento no encontrado"}

        document.status = "processing"
        db.commit()

        # Inferir legal_area desde el matter
        legal_area = None
        if document.matter_id:
            matter = db.query(Matter).filter(Matter.id == document.matter_id).first()
            if matter and matter.matter_type:
                legal_area = get_legal_area_from_matter_type(matter.matter_type.value)

        if document.storage_path:
            from app.services.storage import get_file_path
            file_path = get_file_path(document.storage_path)

            if file_path:
                extracted_text = extract_text_from_file(file_path, document.mime_type)
                document.extracted_text = extracted_text

                if document.mime_type == "application/pdf":
                    try:
                        doc = fitz.open(file_path)
                        document.page_count = len(doc)
                        doc.close()
                    except Exception:
                        pass

                document.status = "processed"
                document.processed_at = datetime.utcnow()
                db.commit()

                chunk_count = create_chunks_for_document(
                    document_id=document.id,
                    extracted_text=extracted_text,
                    organization_id=document.organization_id,
                    matter_id=document.matter_id,
                    db=db,
                    legal_area=legal_area
                )

            else:
                document.status = "failed"
                db.commit()
        else:
            document.status = "failed"
            db.commit()

        return {
            "document_id": document_id,
            "status": document.status,
            "extracted_length": len(document.extracted_text) if document.extracted_text else 0,
            "legal_area": legal_area.value if legal_area else None
        }

    except Exception as e:
        try:
            document.status = "failed"
            db.commit()
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        db.close()
