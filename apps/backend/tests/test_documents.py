"""Tests para endpoints /documents (upload, list, get, delete, process, analyze).

S6-B5 / S6-28: covers the document CRUD endpoints in
``app.api.endpoints.documents`` and ``app.api.endpoints.document_analysis``.

These tests use the in-memory SQLite fixture from ``conftest.py`` so they
do not need a live database or storage backend.
"""
from __future__ import annotations

import io
import json

import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.client import Client
from app.models.document import Document
from app.models.matter import Matter, MatterStatus, MatterUrgency
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers (kept local to this module to avoid cross-test coupling).
# ---------------------------------------------------------------------------
def _auth_headers(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def _make_user(db, email: str, org_id: int, role: MemberRole) -> User:
    user = User(
        email=email,
        password_hash=get_password_hash("Test1234!"),
        full_name=email.split("@")[0],
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=role))
    db.commit()
    db.refresh(user)
    return user


def _make_org(db, name: str = "Org Test") -> Organization:
    org = Organization(name=name, type=OrganizationType.LAW_FIRM)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_matter(db, org_id: int, user_id: int) -> Matter:
    matter = Matter(
        organization_id=org_id,
        created_by_user_id=user_id,
        title="Caso prueba documentos",
        urgency=MatterUrgency.MEDIUM,
        status=MatterStatus.NEW,
    )
    db.add(matter)
    db.commit()
    db.refresh(matter)
    return matter


def _pdf_bytes() -> bytes:
    """Minimal valid PDF signature for magic-byte detection."""
    return b"%PDF-1.4\n%fake pdf content for testing\n%%EOF\n"


def _txt_bytes(text: str = "hola mundo") -> bytes:
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# Fixtures scoped to this file.
# ---------------------------------------------------------------------------
@pytest.fixture
def org(db):
    return _make_org(db)


@pytest.fixture
def lawyer(db, org):
    return _make_user(db, "lawyer@test.com", org.id, MemberRole.LAWYER)


@pytest.fixture
def matter(db, org, lawyer):
    return _make_matter(db, org.id, lawyer.id)


# ===========================================================================
# Upload endpoint
# ===========================================================================
class TestUploadDocument:
    """POST /documents/matters/{matter_id}/documents"""

    def test_upload_document_pdf_returns_201(self, client, db, org, lawyer, matter, monkeypatch):
        """Valid PDF upload succeeds and creates a Document row."""
        from app.services import storage

        def _fake_save(content, filename, org_id, m_id):
            return (f"org{org_id}/matter{m_id}/{filename}", "fakehash", len(content))

        monkeypatch.setattr(storage, "save_file", _fake_save)

        response = client.post(
            f"/api/v1/documents/matters/{matter.id}/documents",
            headers=_auth_headers(lawyer),
            files={"file": ("contract.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["original_filename"] == "contract.pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["matter_id"] == matter.id
        assert data["organization_id"] == org.id
        assert data["status"] == "uploaded"

    def test_upload_document_invalid_mime_type_returns_400(
        self, client, db, org, lawyer, matter, monkeypatch
    ):
        """Binary that doesn't match any accepted signature is rejected."""
        from app.services import storage

        def _fake_save(content, filename, org_id, m_id):
            return (f"org{org_id}/matter{m_id}/{filename}", "h", len(content))

        monkeypatch.setattr(storage, "save_file", _fake_save)

        # Random bytes that decode as neither PDF nor valid UTF-8 text.
        bogus = b"\x00\x01\x02\x03\xff\xfe\xfd"
        response = client.post(
            f"/api/v1/documents/matters/{matter.id}/documents",
            headers=_auth_headers(lawyer),
            files={"file": ("bad.bin", io.BytesIO(bogus), "application/octet-stream")},
        )

        assert response.status_code == 400
        assert "Tipo de archivo no permitido" in response.json()["detail"]

    def test_upload_document_oversized_returns_400(
        self, client, db, org, lawyer, matter, monkeypatch
    ):
        """File larger than 50MB is rejected before saving."""
        from app.api.endpoints import documents as docs_mod
        from app.services import storage

        called = {"n": 0}

        def _fake_save(content, filename, org_id, m_id):
            called["n"] += 1
            return (f"org{org_id}/matter{m_id}/{filename}", "h", len(content))

        monkeypatch.setattr(storage, "save_file", _fake_save)

        # Patch the size check on the endpoint module: the route reads the
        # whole upload then compares against ``MAX_FILE_SIZE``. We patch
        # the constant to a tiny threshold so we don't have to actually
        # send 50MB through the test client.
        monkeypatch.setattr(docs_mod, "MAX_FILE_SIZE", 4)

        response = client.post(
            f"/api/v1/documents/matters/{matter.id}/documents",
            headers=_auth_headers(lawyer),
            files={"file": ("big.pdf", io.BytesIO(b"%PDF-too-much-content"), "application/pdf")},
        )

        assert response.status_code == 400, response.text
        detail = response.json()["detail"].lower()
        assert "excede" in detail or "tam" in detail
        assert called["n"] == 0, "storage.save_file must not be called for oversized uploads"


# ===========================================================================
# Listing
# ===========================================================================
class TestGetDocumentsByMatter:
    """GET /documents/matters/{matter_id}/documents"""

    def test_get_documents_by_matter_returns_only_matching(
        self, client, db, org, lawyer, matter
    ):
        # Two docs in this matter
        for i in range(2):
            db.add(
                Document(
                    organization_id=org.id,
                    matter_id=matter.id,
                    uploaded_by_user_id=lawyer.id,
                    original_filename=f"doc-{i}.txt",
                    mime_type="text/plain",
                    file_size=10,
                    file_hash=f"hash-{i}",
                    status="uploaded",
                )
            )
        # And one doc in another matter for isolation check.
        other_matter = _make_matter(db, org.id, lawyer.id)
        db.add(
            Document(
                organization_id=org.id,
                matter_id=other_matter.id,
                uploaded_by_user_id=lawyer.id,
                original_filename="other.txt",
                mime_type="text/plain",
                file_size=5,
                file_hash="hash-other",
                status="uploaded",
            )
        )
        db.commit()

        response = client.get(
            f"/api/v1/documents/matters/{matter.id}/documents",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 200
        ids = [d["id"] for d in response.json()]
        assert len(ids) == 2
        for d in response.json():
            assert d["matter_id"] == matter.id

    def test_get_documents_for_missing_matter_returns_404(self, client, db, org, lawyer):
        response = client.get(
            "/api/v1/documents/matters/99999/documents",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 404


# ===========================================================================
# Delete cascade
# ===========================================================================
class TestDeleteDocument:
    """DELETE /documents/{document_id}"""

    def test_delete_document_cascade_removes_row(
        self, client, db, org, lawyer, matter, monkeypatch
    ):
        from app.services import storage

        deleted_paths = []

        def _fake_delete(path):
            deleted_paths.append(path)
            return True

        monkeypatch.setattr(storage, "delete_file", _fake_delete)

        doc = Document(
            organization_id=org.id,
            matter_id=matter.id,
            uploaded_by_user_id=lawyer.id,
            original_filename="to-delete.pdf",
            mime_type="application/pdf",
            file_size=100,
            file_hash="abc",
            storage_path="org1/matter1/to-delete.pdf",
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        response = client.delete(
            f"/api/v1/documents/{doc.id}",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 204
        # Row gone from DB
        assert db.query(Document).filter(Document.id == doc.id).first() is None
        # Storage cleanup was invoked
        assert deleted_paths == ["org1/matter1/to-delete.pdf"]

    def test_delete_document_missing_returns_404(self, client, db, org, lawyer):
        response = client.delete(
            "/api/v1/documents/424242",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 404


# ===========================================================================
# Process document endpoint
# ===========================================================================
class TestProcessDocument:
    """POST /documents/{document_id}/process"""

    def test_process_document_endpoint_marks_queued(
        self, client, db, org, lawyer, matter, monkeypatch
    ):
        # Patch the document processor to avoid touching real storage/extraction.
        from app.services import document_processor

        def _fake_process(document_id, force=False):
            return {"status": "processed", "document_id": document_id}

        monkeypatch.setattr(document_processor, "process_document", _fake_process)

        # And patch the background function reference inside the endpoint module.
        import app.api.endpoints.documents as docs_mod

        called = {"n": 0}

        def _fake_bg(doc_id):
            called["n"] += 1
            from app.services.document_processor import process_document

            process_document(doc_id)

        monkeypatch.setattr(docs_mod, "_process_document_background", _fake_bg)

        doc = Document(
            organization_id=org.id,
            matter_id=matter.id,
            uploaded_by_user_id=lawyer.id,
            original_filename="x.txt",
            mime_type="text/plain",
            file_size=4,
            file_hash="h",
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        response = client.post(
            f"/api/v1/documents/{doc.id}/process",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["document_id"] == doc.id
        assert body["status"] == "queued"

        db.refresh(doc)
        assert doc.status == "queued"

    def test_process_missing_document_returns_404(self, client, db, org, lawyer):
        response = client.post(
            "/api/v1/documents/7777/process",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 404


# ===========================================================================
# Analyze endpoint
# ===========================================================================
class TestAnalyzeDocument:
    """POST /documents/{document_id}/analyze and GET /documents/{id}/analysis"""

    def test_analyze_document_endpoint(
        self, client, db, org, lawyer, matter, monkeypatch
    ):
        from app.services import document_analyzer

        def _fake_analyze(doc_id):
            return {"ok": True}

        monkeypatch.setattr(document_analyzer, "analyze_document_full", _fake_analyze)

        doc = Document(
            organization_id=org.id,
            matter_id=matter.id,
            uploaded_by_user_id=lawyer.id,
            original_filename="contract.pdf",
            mime_type="application/pdf",
            file_size=42,
            file_hash="h",
            extracted_text="some extracted text",
            status="processed",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        response = client.post(
            f"/api/v1/documents/{doc.id}/analyze",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 200, response.text
        assert response.json()["has_analysis"] is True

    def test_analyze_without_extracted_text_returns_400(
        self, client, db, org, lawyer, matter
    ):
        doc = Document(
            organization_id=org.id,
            matter_id=matter.id,
            uploaded_by_user_id=lawyer.id,
            original_filename="empty.pdf",
            mime_type="application/pdf",
            file_size=10,
            file_hash="h",
            extracted_text=None,
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        response = client.post(
            f"/api/v1/documents/{doc.id}/analyze",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 400
        assert "texto extra" in response.json()["detail"].lower()

    def test_get_document_analysis_no_analysis_returns_false_flag(
        self, client, db, org, lawyer, matter
    ):
        from app.services import document_analyzer

        monkey = pytest.MonkeyPatch()
        monkey.setattr(document_analyzer, "get_document_analysis", lambda _id: None)
        doc = Document(
            organization_id=org.id,
            matter_id=matter.id,
            uploaded_by_user_id=lawyer.id,
            original_filename="noanalysis.txt",
            mime_type="text/plain",
            file_size=1,
            file_hash="h",
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        response = client.get(
            f"/api/v1/documents/{doc.id}/analysis",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["has_analysis"] is False
        monkey.undo()

    def test_get_document_analysis_returns_decoded_payload(
        self, client, db, org, lawyer, matter
    ):
        """When an analysis row exists, the endpoint decodes JSON-as-text fields."""
        from app.models.document_analysis import DocumentAnalysis
        from app.services import document_analyzer

        doc = Document(
            organization_id=org.id,
            matter_id=matter.id,
            uploaded_by_user_id=lawyer.id,
            original_filename="withanalysis.pdf",
            mime_type="application/pdf",
            file_size=10,
            file_hash="h",
            extracted_text="x",
            status="processed",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        analysis = DocumentAnalysis(
            document_id=doc.id,
            organization_id=org.id,
            document_type="contrato",
            participants=json.dumps(["Alice", "Bob"]),
            financial_terms=json.dumps({"monto": 1000}),
            obligations=json.dumps(["pago"]),
            clauses_by_type=json.dumps({"terminacion": []}),
            unusual_clauses=json.dumps([]),
            risk_assessment=json.dumps([{"risk_level": "high", "score": 9}]),
            contract_timeline=json.dumps([]),
            legal_references=json.dumps([]),
            indexed_content="full text",
        )
        db.add(analysis)
        db.commit()

        monkey = pytest.MonkeyPatch()
        monkey.setattr(
            document_analyzer,
            "get_document_analysis",
            lambda _id: analysis,
        )

        response = client.get(
            f"/api/v1/documents/{doc.id}/analysis",
            headers=_auth_headers(lawyer),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["has_analysis"] is True
        assert body["document_type"] == "contrato"
        assert body["participants"] == ["Alice", "Bob"]
        assert body["financial_terms"] == {"monto": 1000}
        monkey.undo()
