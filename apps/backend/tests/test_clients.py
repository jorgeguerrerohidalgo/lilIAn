"""Tests for /clients/* endpoints — CRUD + RBAC + soft-delete.

Covers S6-20: happy-path CRUD, RBAC isolation (another org can't see),
and soft-delete behavior (``is_active=False``).
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
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User

# ---------------------------------------------------------------------------
# Engine / fixtures (same pattern as test_isolation.py)
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
# S6-20: create
# ===========================================================================
class TestCreateClient:
    def test_create_client_success(self, client, org_a):
        response = client.post(
            "/api/v1/clients",
            headers=_auth_headers(org_a["user"]),
            json={
                "name": "Juan Pérez",
                "company_name": "Pérez SpA",
                "rut": "12.345.678-9",
                "email": "juan@example.com",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Juan Pérez"
        assert body["company_name"] == "Pérez SpA"
        assert body["rut"] == "12.345.678-9"
        assert body["email"] == "juan@example.com"
        assert body["organization_id"] == org_a["org"].id
        assert body["is_active"] is True
        assert "id" in body

    def test_create_client_minimal_payload(self, client, org_a):
        """Only name is required; everything else is optional."""
        response = client.post(
            "/api/v1/clients",
            headers=_auth_headers(org_a["user"]),
            json={"name": "Solo Nombre"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["name"] == "Solo Nombre"

    def test_create_client_without_auth_returns_401(self, client):
        response = client.post(
            "/api/v1/clients",
            json={"name": "Sin auth"},
        )
        assert response.status_code == 401

    def test_create_client_without_org_returns_403(self, client, db):
        """User without OrganizationMember cannot access the endpoint."""
        orphan = User(
            email="orphan@c.com",
            password_hash=get_password_hash("Test1234!Abcd"),
            full_name="Orphan",
        )
        db.add(orphan)
        db.commit()
        db.refresh(orphan)

        response = client.post(
            "/api/v1/clients",
            headers=_auth_headers(orphan),
            json={"name": "X"},
        )
        assert response.status_code == 403


# ===========================================================================
# S6-20: list filtered by org
# ===========================================================================
class TestListClients:
    def test_list_clients_filtered_by_org(self, client, org_a, org_b, db):
        # Create clients in each org directly
        db.add(Client(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            name="A-Client",
        ))
        db.add(Client(
            organization_id=org_b["org"].id,
            created_by_user_id=org_b["user"].id,
            name="B-Client",
        ))
        db.commit()

        # Org A sees only its client
        resp_a = client.get("/api/v1/clients", headers=_auth_headers(org_a["user"]))
        assert resp_a.status_code == 200
        names_a = [c["name"] for c in resp_a.json()]
        assert names_a == ["A-Client"]

        # Org B sees only its client
        resp_b = client.get("/api/v1/clients", headers=_auth_headers(org_b["user"]))
        names_b = [c["name"] for c in resp_b.json()]
        assert names_b == ["B-Client"]

    def test_list_clients_excludes_soft_deleted(self, client, org_a, db):
        c1 = Client(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            name="Activo",
            is_active=True,
        )
        c2 = Client(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            name="Borrado",
            is_active=False,
        )
        db.add_all([c1, c2])
        db.commit()

        resp = client.get("/api/v1/clients", headers=_auth_headers(org_a["user"]))
        names = [c["name"] for c in resp.json()]
        assert "Activo" in names
        assert "Borrado" not in names


# ===========================================================================
# S6-20: update
# ===========================================================================
class TestUpdateClient:
    def test_update_client(self, client, org_a, db):
        target = Client(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            name="Original",
            email="original@example.com",
        )
        db.add(target)
        db.commit()
        db.refresh(target)

        resp = client.put(
            f"/api/v1/clients/{target.id}",
            headers=_auth_headers(org_a["user"]),
            json={"name": "Actualizado", "email": "nuevo@example.com"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "Actualizado"
        assert body["email"] == "nuevo@example.com"
        # Fields not sent stay the same
        assert body["organization_id"] == org_a["org"].id

    def test_update_client_cross_org_returns_404(self, client, org_a, org_b, db):
        """Org A cannot update a client that belongs to Org B."""
        target = Client(
            organization_id=org_b["org"].id,
            created_by_user_id=org_b["user"].id,
            name="B-Client",
        )
        db.add(target)
        db.commit()
        db.refresh(target)

        resp = client.put(
            f"/api/v1/clients/{target.id}",
            headers=_auth_headers(org_a["user"]),
            json={"name": "Hackeado"},
        )
        assert resp.status_code == 404


# ===========================================================================
# S6-20: delete (soft delete)
# ===========================================================================
class TestDeleteClient:
    def test_delete_client_soft_delete(self, client, org_a, db):
        target = Client(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            name="Para Borrar",
            is_active=True,
        )
        db.add(target)
        db.commit()
        db.refresh(target)

        resp = client.delete(
            f"/api/v1/clients/{target.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 204

        # Row still exists but is_active=False
        db.refresh(target)
        assert target.is_active is False

    def test_delete_client_disappears_from_list(self, client, org_a, db):
        target = Client(
            organization_id=org_a["org"].id,
            created_by_user_id=org_a["user"].id,
            name="Invisible",
            is_active=True,
        )
        db.add(target)
        db.commit()
        db.refresh(target)

        client.delete(
            f"/api/v1/clients/{target.id}",
            headers=_auth_headers(org_a["user"]),
        )

        list_resp = client.get(
            "/api/v1/clients",
            headers=_auth_headers(org_a["user"]),
        )
        ids = [c["id"] for c in list_resp.json()]
        assert target.id not in ids

    def test_delete_client_cross_org_returns_404(self, client, org_a, org_b, db):
        target = Client(
            organization_id=org_b["org"].id,
            created_by_user_id=org_b["user"].id,
            name="B-Client",
        )
        db.add(target)
        db.commit()
        db.refresh(target)

        resp = client.delete(
            f"/api/v1/clients/{target.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_client_returns_404(self, client, org_a):
        resp = client.delete(
            "/api/v1/clients/999999",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 404
