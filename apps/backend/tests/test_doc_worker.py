"""Tests for document_processor worker (S6-27).

The worker is a thin RQ wrapper around
``app.services.document_processor.process_document`` — these tests cover
the wrapper's behavior by importing the function directly without the
RQ dependencies that the production worker entrypoint requires.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.matter import Matter, MatterStatus, MatterType, MatterUrgency
from app.models.organization import Organization, OrganizationType

# ---------------------------------------------------------------------------
# Fixture: load doc_worker module with stand-ins for rq/redis.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def doc_worker():
    """Import ``doc_worker`` while skipping its top-level rq/redis imports.

    The production module pulls in ``rq`` and a Redis connection at
    module load time. Those packages aren't installed in the test venv,
    so we synthesize the missing modules before importing. The worker
    exposes a single ``process_document`` function, which is all these
    tests need.

    Scoped at the module level so the fake modules stay registered for
    the duration of this test module only.
    """
    # Insert fake modules for rq and rq sub-modules so the import succeeds.
    for name in ("rq", "rq.Queue", "rq.Worker"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    sys.modules["rq"].Queue = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    sys.modules["rq"].Worker = lambda *args, **kwargs: None  # type: ignore[attr-defined]

    # `from redis import Redis` — provide a stand-in class.
    # IMPORTANT: We save and restore the real `redis` module to avoid
    # silently breaking other tests that rely on the real `RedisError`
    # and friends. A previous version of this fixture replaced the
    # global `redis` module and caused 30+ test_isolation failures.
    saved_redis = sys.modules.get("redis")

    class _FakeRedis:
        @staticmethod
        def from_url(url, **kwargs):
            return None

    stub = types.ModuleType("redis")
    stub._doc_worker_stub = True  # type: ignore[attr-defined]
    stub.Redis = _FakeRedis  # type: ignore[attr-defined]
    sys.modules["redis"] = stub

    worker_path = (
        Path(__file__).resolve().parents[1]
        / "workers" / "document_processor" / "doc_worker.py"
    )
    try:
        spec = importlib.util.spec_from_file_location("doc_worker_under_test", worker_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if saved_redis is not None:
            sys.modules["redis"] = saved_redis
        else:
            sys.modules.pop("redis", None)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_org(db) -> Organization:
    org = Organization(name="Worker Org", type=OrganizationType.LAW_FIRM)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_matter(db, org: Organization) -> Matter:
    matter = Matter(
        organization_id=org.id,
        created_by_user_id=1,
        title="Worker matter",
        matter_type=MatterType.LABOR,
        status=MatterStatus.NEW,
        urgency=MatterUrgency.MEDIUM,
    )
    db.add(matter)
    db.commit()
    db.refresh(matter)
    return matter


def _make_doc(db, organization_id: int, matter_id: int, **kwargs) -> Document:
    defaults = {
        "organization_id": organization_id,
        "matter_id": matter_id,
        "uploaded_by_user_id": 1,
        "original_filename": "doc.pdf",
        "storage_path": "1/1/doc.pdf",
        "mime_type": "application/pdf",
        "file_size": 1024,
        "status": "uploaded",
    }
    defaults.update(kwargs)
    doc = Document(**defaults)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# Worker delegates to canonical process_document
# ---------------------------------------------------------------------------

def test_worker_processes_pending_documents(db, doc_worker):
    """S6-27: the worker successfully processes a pending document."""
    org = _make_org(db)
    matter = _make_matter(db, org)
    doc = _make_doc(db, org.id, matter.id, status="uploaded")
    sample = "--- PDF (1 páginas) ---\n\nContract text. " * 20

    session_factory = lambda: db  # noqa: E731
    with patch("app.services.document_processor.SessionLocal", side_effect=session_factory), \
         patch("app.services.document_processor.extract_text_from_file",
               return_value=sample), \
         patch("app.services.storage.get_file_path",
               return_value="/tmp/fake.pdf"), \
         patch("app.services.document_processor._classify_document_async"), \
         patch("app.services.document_processor.create_chunks_for_document",
               return_value={"created": 2, "skipped": False,
                             "status": "created", "content_hash": "deadbeef"}):
        result = doc_worker.process_document(doc.id)

    assert result["status"] == "processed"
    assert result["document_id"] == doc.id
    assert result["chunks_created"] == 2


def test_worker_handles_failure_gracefully(db, doc_worker):
    """S6-27: a failing document returns a failure payload (does not raise)."""
    org = _make_org(db)
    matter = _make_matter(db, org)
    doc = _make_doc(db, org.id, matter.id, status="uploaded")
    doc_id = doc.id

    # Storage resolution returns None so the pipeline records the failure.
    session_factory = lambda: db  # noqa: E731
    with patch("app.services.document_processor.SessionLocal", side_effect=session_factory), \
         patch("app.services.storage.get_file_path", return_value=None), \
         patch("app.services.document_processor._classify_document_async"):
        result = doc_worker.process_document(doc_id)

    # Should NOT raise; returns the failure dict
    assert result["status"] == "failed"
    assert "error" in result
    assert "Storage path no encontrado" in result["error"] or "storage" in result["error"].lower()

    db.expire_all()
    refreshed = db.get(Document, doc_id)
    assert refreshed.status == "failed"


def test_worker_skips_already_processed(db, doc_worker):
    """S6-27: already-processed docs are returned as skipped."""
    org = _make_org(db)
    matter = _make_matter(db, org)
    doc = _make_doc(db, org.id, matter.id, status="processed")
    existing = DocumentChunk(
        document_id=doc.id,
        organization_id=org.id,
        matter_id=matter.id,
        chunk_index=0,
        content="prior chunk",
    )
    db.add(existing)
    db.commit()

    session_factory = lambda: db  # noqa: E731
    with patch("app.services.document_processor.SessionLocal", side_effect=session_factory), \
         patch("app.services.document_processor._classify_document_async") as classify, \
         patch("app.services.document_processor.create_chunks_for_document") as chunks, \
         patch("app.services.document_processor.extract_text_from_file") as extract:
        result = doc_worker.process_document(doc.id)

    assert result["status"] == "already_processed"
    assert result["skipped"] is True
    # The pipeline short-circuits before any of these helpers fire.
    classify.assert_not_called()
    chunks.assert_not_called()
    extract.assert_not_called()
