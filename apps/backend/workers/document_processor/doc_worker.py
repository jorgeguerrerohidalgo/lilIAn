import os
import sys

from redis import Redis
from rq import Queue, Worker

# Add backend app to path for imports
sys.path.insert(0, '/app')

from app.core.config import settings
from app.services.document_processor import process_document as canonical_process_document


# S1-08: reuse the canonical ``process_document`` from
# ``app.services.document_processor`` instead of duplicating the logic.
# The canonical implementation owns the session lifecycle, status
# transitions, chunking and error handling. Keeping two copies caused
# race conditions because both copies could mutate the same Document row
# concurrently.
def process_document(document_id: int) -> dict:
    return canonical_process_document(document_id)


redis_conn = Redis.from_url(settings.REDIS_URL)
queue = Queue("document_processing", connection=redis_conn)


if __name__ == "__main__":
    worker = Worker(["document_processing"], connection=redis_conn)
    worker.work()
