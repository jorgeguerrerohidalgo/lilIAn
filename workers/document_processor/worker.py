import sys

from redis import Redis
from rq import Queue, Worker

# Add backend app to path for imports
sys.path.insert(0, '/app')

from app.core.config import settings
from app.services.document_processor import process_document as backend_process_document

redis_conn = Redis.from_url(settings.REDIS_URL)
queue = Queue("document_processing", connection=redis_conn)


def process_document(document_id: int, force: bool = False) -> dict:
    """
    Wrapper del worker que delega al backend.
    Usa la función centralizada para garantizar idempotencia.
    """
    return backend_process_document(document_id, force=force)


if __name__ == "__main__":
    worker = Worker(["document_processing"], connection=redis_conn)
    worker.work()
