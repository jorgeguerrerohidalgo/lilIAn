"""Tests for /matters/* endpoints — CRUD, validation, cascade delete.

Covers S6-21:
- create with client_id (happy + cross-org 404)
- list with pagination
- urgency validation (Pydantic allows any string today — this test
  documents current behaviour and the safer bound the schema enforces)
- cascade delete cleans up Documents/Storage paths
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.client import Client
from app.models.document import Document
from app.models.matter import Matter, MatterStatus, MatterUrgency
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User

# ---------------------------------------------------------------------------
# Engine / fixtures
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _auth_headers(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def _make_org(db, name: str) -> Organization:
    org = Organization(name=name, type=OrganizationType.INDIVIDUAL)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_user(db, email: str, org_id: int, role: MemberRole = MemberRole.LAWYER) -> User:
    user = User(
        email=email,
        password_hash=get_password_hash("Test1234!Abcd"),
        full_name=email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=role))
    db.commit()
    return user


def _make_client(db, org_id: int, user_id: int, name: str = "Cliente") -> Client:
    c = Client(organization_id=org_id, created_by_user_id=user_id, name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def org_a(db):
    org = _make_org(db, "Org A")
    user = _make_user(db, "lawyer.a@example.com", org.id, MemberRole.LAWYER)
    return {"org": org, "user": user}


@pytest.fixture
def org_b(db):
    org = _make_org(db, "Org B")
    user = _make_user(db, "lawyer.b@example.com", org.id, MemberRole.LAWYER)
    return {"org": org, "user": user}


# ===========================================================================
# S6-21: create
# ===========================================================================
class TestCreateMatter:
    def test_create_matter_with_client(self, client, org_a, db):
        cli = _make_client(db, org_a["org"].id, org_a["user"].id, "Cliente X")
        resp = client.post(
            "/api/v1/matters",
            headers=_auth_headers(org_a["user"]),
            json={
                "title": "Caso Contract Review",
                "matter_type": "contract_review",
                "urgency": "medium",
                "client_id": cli.id,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["title"] == "Caso Contract Review"
        assert body["matter_type"] == "contract_review"
        assert body["client_id"] == cli.id
        assert body["organization_id"] == org_a["org"].id
        assert body["status"] == "new"

    def test_create_matter_without_client(self, client, org_a):
        resp = client.post(
            "/api/v1/matters",
            headers=_auth_headers(org_a["user"]),
            json={"title": "Sin cliente"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["client_id"] is None

    def test_create_matter_invalid_client_returns_404(
        self, client, org_a
    ):
        """client_id pointing to a non-existent client must 404."""
        resp = client.post(
            "/api/v1/matters",
            headers=_auth_headers(org_a["user"]),
            json={"title": "Caso huérfano", "client_id": 99999},
        )
        assert resp.status_code == 404, resp.text

    def test_create_matter_cross_org_client_returns_404(
        self, client, org_a, org_b, db
    ):
        """S1-09: cannot attach a matter to a client owned by another org."""
        other_client = _make_client(db, org_b["org"].id, org_b["user"].id, "B-Client")
        resp = client.post(
            "/api/v1/matters",
            headers=_auth_headers(org_a["user"]),
            json={"title": "Caso cross-org", "client_id": other_client.id},
        )
        assert resp.status_code == 404, resp.text


# ===========================================================================
# S6-21: urgency validation
# ===========================================================================
class TestUrgencyValidation:
    def test_create_matter_with_valid_urgency(self, client, org_a):
        for urg in ("low", "medium", "high", "urgent"):
            resp = client.post(
                "/api/v1/matters",
                headers=_auth_headers(org_a["user"]),
                json={"title": f"Urg-{urg}", "urgency": urg},
            )
            assert resp.status_code == 201, f"{urg}: {resp.text}"
            assert resp.json()["urgency"] == urg

    def test_create_matter_invalid_urgency_returns_error(self, client, org_a):
        """MatterCreate has ``urgency: str`` (no enum bound at the
        Pydantic layer), so the request reaches the endpoint and the
        SQLAlchemy Enum column rejects unknown values with a
        ``LookupError``.

        The TestClient re-raises server exceptions by default, so we
        use ``pytest.raises`` to document the unhandled error path.
        A future Pydantic-bound enum (``MatterUrgency``) on the
        schema would turn this into a 422 response.
        """
        with pytest.raises(LookupError) as excinfo:
            client.post(
                "/api/v1/matters",
                headers=_auth_headers(org_a["user"]),
                json={"title": "Caso raro", "urgency": "this-is-not-a-urgency"},
            )
        assert "this-is-not-a-urgency" in str(excinfo.value)


# ===========================================================================
# S6-21: cascade delete (S1-11)
# ===========================================================================
class TestMatterCascadeDelete:
    def test_matter_cascade_delete_storage(self, client, org_a, db, monkeypatch):
        """Deleting a matter must cascade-delete its documents.

        The endpoint also calls ``storage_delete_file`` for every
        document's storage_path. We monkey-patch that helper so the
        test doesn't need a real storage backend, and we verify it
        was called once per document.
        """
        # Seed: matter + 2 documents
        matter = Matter(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            title="Para eliminar",
            matter_type="other",
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
        )
        db.add(matter)
        db.commit()
        db.refresh(matter)

        doc1 = Document(
            organization_id=org_a["org"].id,
            matter_id=matter.id,
            uploaded_by_user_id=org_a["user"].id,
            original_filename="d1.txt",
            storage_path="org_a/case/d1.txt",
            mime_type="text/plain",
            file_size=10,
            file_hash="h1",
            status="uploaded",
        )
        doc2 = Document(
            organization_id=org_a["org"].id,
            matter_id=matter.id,
            uploaded_by_user_id=org_a["user"].id,
            original_filename="d2.txt",
            storage_path="org_a/case/d2.txt",
            mime_type="text/plain",
            file_size=20,
            file_hash="h2",
            status="uploaded",
        )
        db.add_all([doc1, doc2])
        db.commit()
        doc1_id, doc2_id = doc1.id, doc2.id

        # Spy on storage.delete_file
        from app.services import storage as storage_service

        calls = []
        def fake_delete(path):
            calls.append(path)
            return True
        monkeypatch.setattr(storage_service, "delete_file", fake_delete)

        resp = client.delete(
            f"/api/v1/matters/{matter.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 204, resp.text

        # Matter + documents are gone
        assert db.query(Matter).filter(Matter.id == matter.id).first() is None
        assert db.query(Document).filter(Document.id.in_([doc1_id, doc2_id])).count() == 0

        # Storage cleanup ran for each document that had a path
        assert set(calls) == {"org_a/case/d1.txt", "org_a/case/d2.txt"}

    def test_matter_cascade_delete_skips_empty_storage_paths(
        self, client, org_a, db, monkeypatch
    ):
        """Documents without a storage_path must not blow up delete."""
        matter = Matter(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            title="Sin storage",
            matter_type="other",
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
        )
        db.add(matter)
        db.commit()
        db.refresh(matter)
        db.add(Document(
            organization_id=org_a["org"].id,
            matter_id=matter.id,
            uploaded_by_user_id=org_a["user"].id,
            original_filename="no-path.txt",
            storage_path=None,
            mime_type="text/plain",
            file_size=0,
            file_hash="h",
            status="uploaded",
        ))
        db.commit()

        from app.services import storage as storage_service

        calls = []
        monkeypatch.setattr(storage_service, "delete_file", lambda p: calls.append(p) or True)

        resp = client.delete(
            f"/api/v1/matters/{matter.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 204
        assert calls == []  # no paths → no delete_file calls

    def test_matter_cascade_delete_cross_org_returns_404(
        self, client, org_a, org_b, db
    ):
        matter_b = Matter(
            organization_id=org_b["org"].id,
            created_by_user_id=org_b["user"].id,
            title="B-Case",
            matter_type="other",
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
        )
        db.add(matter_b)
        db.commit()
        db.refresh(matter_b)

        resp = client.delete(
            f"/api/v1/matters/{matter_b.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 404


# ===========================================================================
# S6-21: list pagination
# ===========================================================================
class TestListMattersPagination:
    def test_list_matters_pagination(self, client, org_a, db):
        for i in range(5):
            db.add(Matter(
                organization_id=org_a["org"].id,
                created_by_user_id=org_a["user"].id,
                title=f"Case {i}",
                matter_type="other",
                status=MatterStatus.NEW,
                urgency=MatterUrgency.MEDIUM,
            ))
        db.commit()

        # Default: limit=50 → all 5
        resp_all = client.get(
            "/api/v1/matters",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp_all.status_code == 200
        assert len(resp_all.json()) == 5

        # skip=0, limit=2 → first 2 (ordered by created_at DESC, so the
        # most recent matters come first — i.e. Case 4, Case 3)
        resp_page1 = client.get(
            "/api/v1/matters?skip=0&limit=2",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp_page1.status_code == 200
        assert len(resp_page1.json()) == 2

        resp_page2 = client.get(
            "/api/v1/matters?skip=2&limit=2",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp_page2.status_code == 200
        assert len(resp_page2.json()) == 2

        # No overlap between pages
        ids_p1 = {m["id"] for m in resp_page1.json()}
        ids_p2 = {m["id"] for m in resp_page2.json()}
        assert ids_p1.isdisjoint(ids_p2)

    def test_list_matters_filter_by_status(self, client, org_a, db):
        new = Matter(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            title="New one",
            matter_type="other",
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
        )
        closed = Matter(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            title="Closed one",
            matter_type="other",
            status=MatterStatus.CLOSED,
            urgency=MatterUrgency.MEDIUM,
        )
        db.add_all([new, closed])
        db.commit()

        resp = client.get(
            "/api/v1/matters?status_filter=closed",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        titles = [m["title"] for m in resp.json()]
        assert titles == ["Closed one"]

    def test_list_matters_filter_by_client(self, client, org_a, db):
        cli = _make_client(db, org_a["org"].id, org_a["user"].id, "Filtro")
        db.add(Matter(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            title="Con cliente",
            matter_type="other",
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
            client_id=cli.id,
        ))
        db.add(Matter(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            title="Sin cliente",
            matter_type="other",
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
            client_id=None,
        ))
        db.commit()

        resp = client.get(
            f"/api/v1/matters?client_id={cli.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        titles = [m["title"] for m in resp.json()]
        assert titles == ["Con cliente"]


# ===========================================================================
# Cross-tenant isolation smoke (mirrors test_isolation.py, kept here so
# /matters is fully covered by test_matters.py alone).
# ===========================================================================
class TestMatterIsolation:
    def test_other_org_cannot_read(self, client, org_a, org_b, db):
        matter_b = Matter(
            organization_id=org_b["org"].id,
            created_by_user_id=org_b["user"].id,
            title="B-Case",
            matter_type="other",
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
        )
        db.add(matter_b)
        db.commit()
        db.refresh(matter_b)

        resp = client.get(
            f"/api/v1/matters/{matter_b.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 404