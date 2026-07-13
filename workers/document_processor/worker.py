import os
import sys

from redis import Redis
from rq import Queue, Worker

# Add backend app to path for imports
sys.path.insert(0, '/app')

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.services.storage import get_file_path
from app.services.document_processor import extract_text_from_file, create_chunks_for_document
from datetime import datetime


redis_conn = Redis.from_url(settings.REDIS_URL)
queue = Queue("document_processing", connection=redis_conn)


def process_document(document_id: int) -> dict:
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()

        if not document:
            return {"error": "Documento no encontrado"}

        document.status = "processing"
        db.commit()

        if document.storage_path:
            # Get absolute path using storage service
            file_path = get_file_path(document.storage_path)

            if file_path and os.path.exists(file_path):
                extracted_text = extract_text_from_file(file_path, document.mime_type)
                document.extracted_text = extracted_text
                document.status = "processed"
                document.processed_at = datetime.utcnow()

                # Create chunks for RAG
                create_chunks_for_document(
                    document_id=document.id,
                    extracted_text=extracted_text,
                    organization_id=document.organization_id,
                    matter_id=document.matter_id,
                    db=db
                )
            else:
                document.status = "failed"
                return {"error": f"File not found: {document.storage_path}"}
        else:
            document.status = "failed"

        db.commit()

        return {"document_id": document_id, "status": document.status}

    except Exception as e:
        try:
            document.status = "failed"
            db.commit()
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    worker = Worker(["document_processing"], connection=redis_conn)
    worker.work()
