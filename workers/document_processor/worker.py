import os
import sys

from redis import Redis
from rq import Queue, Worker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.services.extractor import extract_text_from_file
from datetime import datetime


redis_conn = Redis.from_url(settings.REDIS_URL)
queue = Queue("document_processing", connection=redis_conn)


def process_document(document_id: int):
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()

        if not document:
            return {"error": "Documento no encontrado"}

        document.status = "processing"
        db.commit()

        if document.storage_path:
            extracted_text = extract_text_from_file(document.storage_path, document.mime_type)

            document.extracted_text = extracted_text
            document.status = "processed"
            document.processed_at = datetime.utcnow()
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
