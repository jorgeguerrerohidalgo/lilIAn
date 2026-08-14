"""Tests for document_processor service (S6-23).

Covers:
- text extraction from PDF / DOCX
- document classification routing
- process_document happy path & idempotency
- chunk creation with size handling
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.matter import Matter, MatterStatus, MatterType, MatterUrgency
from app.models.organization import Organization, OrganizationType
from app.services import document_processor
from app.services.document_processor import (
    create_chunks_for_document,
    extract_text_from_docx,
    extract_text_from_pdf,
    process_document,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_org(db) -> Organization:
    org = Organization(name="Test Org", type=OrganizationType.LAW_FIRM)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_matter(db, org: Organization, matter_type=MatterType.CONTRACT_REVIEW) -> Matter:
    matter = Matter(
        organization_id=org.id,
        created_by_user_id=1,
        title="Test matter",
        matter_type=matter_type,
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
        "original_filename": "test.pdf",
        "storage_path": "1/1/file.pdf",
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
# extract_text_from_pdf
# ---------------------------------------------------------------------------

def test_extract_text_pdf(tmp_path):
    """S6-23: PDF extraction returns text wrapped with the page-count header."""
    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 stub")

    page1 = MagicMock(get_text=MagicMock(return_value="page 1 text " * 30))
    page2 = MagicMock(get_text=MagicMock(return_value="page 2 text " * 30))
    fake_doc = MagicMock()
    fake_doc.__iter__ = MagicMock(return_value=iter([page1, page2]))
    fake_doc.__len__ = MagicMock(return_value=2)
    fake_doc.__enter__ = MagicMock(return_value=fake_doc)
    fake_doc.__exit__ = MagicMock(return_value=False)
    fake_doc.close = MagicMock()

    # Force enough text so the OCR fallback is NOT triggered.
    with patch("app.services.document_processor.fitz.open", return_value=fake_doc), \
         patch("os.path.getsize", return_value=1024):
        result = extract_text_from_pdf(str(pdf_path))

    assert "page 1 text" in result
    assert "page 2 text" in result
    assert "PDF" in result
    assert "2 páginas" in result


# ---------------------------------------------------------------------------
# extract_text_from_docx
# ---------------------------------------------------------------------------

def test_extract_text_docx(tmp_path):
    """S6-23: DOCX extraction concatenates paragraphs into a single string."""
    docx_path = tmp_path / "fake.docx"
    docx_path.write_bytes(b"PK stub")

    para1 = MagicMock(text="First paragraph")
    para2 = MagicMock(text="Second paragraph")
    fake_doc = MagicMock()
    fake_doc.paragraphs = [para1, para2]

    with patch("app.services.document_processor.DocxDocument", return_value=fake_doc):
        result = extract_text_from_docx(str(docx_path))

    assert "First paragraph" in result
    assert "Second paragraph" in result
    assert result.startswith("--- DOCX")


# ---------------------------------------------------------------------------
# _infer_legal_area routing
# ---------------------------------------------------------------------------

def test_classify_document_contract_review(db):
    """S6-23: contract_review matters are inferred to CIVIL legal area."""
    org = _make_org(db)
    matter = _make_matter(db, org, matter_type=MatterType.CONTRACT_REVIEW)
    doc = _make_doc(db, org.id, matter.id)

    legal_area = document_processor._infer_legal_area(db, doc)

    assert legal_area is not None
    assert legal_area.value == "civil"


def test_classify_document_labor(db):
    """S6-23: labor matters are inferred to LABOR legal area."""
    org = _make_org(db)
    matter = _make_matter(db, org, matter_type=MatterType.LABOR)
    doc = _make_doc(db, org.id, matter.id)

    legal_area = document_processor._infer_legal_area(db, doc)

    assert legal_area is not None
    assert legal_area.value == "labor"


# ---------------------------------------------------------------------------
# process_document happy path & idempotency
# ---------------------------------------------------------------------------

def test_process_document_happy_path(db):
    """S6-23: process_document extracts text, marks processed, returns success."""
    org = _make_org(db)
    matter = _make_matter(db, org, matter_type=MatterType.CONTRACT_REVIEW)
    doc = _make_doc(db, org.id, matter.id, status="uploaded")

    sample_text = "--- PDF (1 páginas) ---\n\nSample contract text." * 10

    # process_document creates its own SessionLocal(); swap it for the test session.
    session_factory = lambda: db  # noqa: E731
    with patch("app.services.document_processor.SessionLocal", side_effect=session_factory), \
         patch("app.services.document_processor.extract_text_from_file",
               return_value=sample_text), \
         patch("app.services.storage.get_file_path",
               return_value="/tmp/fake.pdf"), \
         patch("app.services.document_processor._classify_document_async"), \
         patch("app.services.document_processor.create_chunks_for_document",
               return_value={"created": 3, "skipped": False, "status": "created",
                             "content_hash": "abc123"}):
        result = process_document(doc.id)

    assert result["status"] == "processed"
    assert result["document_id"] == doc.id
    assert result["chunks_created"] == 3
    assert result["chunks_skipped"] is False
    assert result["extracted_length"] > 0
    assert result["legal_area"] == "civil"

    db.expire_all()
    refreshed = db.query(Document).filter(Document.id == doc.id).first()
    assert refreshed.status == "processed"
    assert refreshed.extracted_text is not None


def test_process_document_skip_already_processed(db):
    """S6-23: idempotency guard — already processed docs are skipped."""
    org = _make_org(db)
    matter = _make_matter(db, org)
    doc = _make_doc(db, org.id, matter.id, status="processed")

    existing_chunk = DocumentChunk(
        document_id=doc.id,
        organization_id=org.id,
        matter_id=matter.id,
        chunk_index=0,
        content="previous content",
    )
    db.add(existing_chunk)
    db.commit()

    session_factory = lambda: db  # noqa: E731
    with patch("app.services.document_processor.SessionLocal", side_effect=session_factory), \
         patch("app.services.document_processor._classify_document_async") as mock_classify, \
         patch("app.services.document_processor.create_chunks_for_document") as mock_chunks:
        result = process_document(doc.id)

    assert result["status"] == "already_processed"
    assert result["skipped"] is True
    assert result["chunk_count"] == 1
    mock_classify.assert_not_called()
    mock_chunks.assert_not_called()


# ---------------------------------------------------------------------------
# create_chunks_for_document
# ---------------------------------------------------------------------------

def test_create_chunks_for_document_size(db):
    """S6-23: large text yields multiple chunks with sane sizes and content_hash metadata."""
    org = _make_org(db)
    matter = _make_matter(db, org)
    doc = _make_doc(db, org.id, matter.id, status="uploaded")

    long_text = "--- PDF (3 páginas) ---\n\n" + (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 50
    )

    with patch("app.services.embeddings.get_embedding_provider",
               side_effect=RuntimeError("embeddings disabled")):
        result = create_chunks_for_document(
            document_id=doc.id,
            extracted_text=long_text,
            organization_id=org.id,
            matter_id=matter.id,
            db=db,
            legal_area=None,
            force=False,
        )

    assert result["status"] == "created"
    assert result["created"] >= 1
    assert "content_hash" in result

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    assert len(chunks) == result["created"]
    for chunk in chunks:
        assert chunk.content
        assert chunk.organization_id == org.id
        assert chunk.matter_id == matter.id
        meta = json.loads(chunk.chunk_metadata) if chunk.chunk_metadata else {}
        assert meta.get("content_hash") == result["content_hash"]