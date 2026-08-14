"""Tests for /auth/* endpoints — register, login, me.

Covers S6-17 (positive register/login flows), S6-18 (negative
register/login flows: duplicates, weak passwords, wrong creds,
rate-limited login), and a smoke check for ``/auth/me``.

Uses SQLite-in-memory + ``dependency_overrides`` (same harness as
``test_isolation.py``) so tests run without PostgreSQL/Redis.
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
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User

# ---------------------------------------------------------------------------
# Engine SQLite en memoria compartido entre sesiones de test
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
_VALID_PASSWORD = "Test1234!Abcd"  # >=12 chars, upper/lower/digit/symbol


def _auth_headers(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def _make_user(db, email: str, password: str = _VALID_PASSWORD) -> User:
    """Create a User (no membership)."""
    user = User(
        email=email,
        password_hash=get_password_hash(password),
        full_name=email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_member(db, email: str, role: MemberRole = MemberRole.OWNER) -> tuple[User, Organization]:
    user = _make_user(db, email)
    org = Organization(name=f"Org {email}", type=OrganizationType.INDIVIDUAL)
    db.add(org)
    db.commit()
    db.refresh(org)
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=role))
    db.commit()
    return user, org


# ===========================================================================
# S6-17: register — happy path and validation
# ===========================================================================
class TestRegisterSuccess:
    """POST /auth/register returns 201 and creates User + Org + Membership."""

    def test_register_success(self, client):
        payload = {
            "email": "new@example.com",
            "password": _VALID_PASSWORD,
            "full_name": "New User",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["email"] == payload["email"]
        assert body["full_name"] == payload["full_name"]
        assert "id" in body
        assert "password" not in body
        assert "password_hash" not in body

    def test_register_creates_organization_and_membership(self, client, db):
        payload = {
            "email": "owner@example.com",
            "password": _VALID_PASSWORD,
            "full_name": "Owner",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        user = db.query(User).filter(User.email == payload["email"]).first()
        assert user is not None

        membership = (
            db.query(OrganizationMember)
            .filter(OrganizationMember.user_id == user.id)
            .first()
        )
        assert membership is not None
        assert membership.role == MemberRole.OWNER


# ===========================================================================
# S6-18: register — negative cases
# ===========================================================================
class TestRegisterFailures:
    def test_register_duplicate_email(self, client, db):
        _make_user(db, "dup@example.com")
        payload = {
            "email": "dup@example.com",
            "password": _VALID_PASSWORD,
            "full_name": "Dup",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400, response.text
        assert "ya está registrado" in response.json()["detail"].lower()

    def test_register_weak_password_too_short(self, client):
        # Password min length is 12 chars
        payload = {
            "email": "weak1@example.com",
            "password": "Short1!",  # 7 chars
            "full_name": "Weak",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422, response.text

    def test_register_weak_password_no_symbol(self, client):
        payload = {
            "email": "weak2@example.com",
            "password": "NoSymbol1234",  # valid length but no symbol
            "full_name": "Weak",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422, response.text

    def test_register_weak_password_no_uppercase(self, client):
        payload = {
            "email": "weak3@example.com",
            "password": "lowercase123!",  # no uppercase
            "full_name": "Weak",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422, response.text

    def test_register_missing_fields(self, client):
        # Missing password and full_name
        response = client.post("/api/v1/auth/register", json={"email": "x@x.com"})
        assert response.status_code == 422, response.text

    def test_register_invalid_email(self, client):
        payload = {
            "email": "not-an-email",
            "password": _VALID_PASSWORD,
            "full_name": "Bad",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422, response.text


# ===========================================================================
# S6-17: login — happy path
# ===========================================================================
class TestLoginSuccess:
    def test_login_success_returns_token(self, client, db):
        _make_user(db, "login@example.com", _VALID_PASSWORD)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "login@example.com", "password": _VALID_PASSWORD},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 20

        # Token should be set as cookie too
        assert "lilian_auth_token" in response.cookies

    def test_login_updates_last_login_at(self, client, db):
        user = _make_user(db, "active@example.com", _VALID_PASSWORD)
        assert user.last_login_at is None
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "active@example.com", "password": _VALID_PASSWORD},
        )
        assert response.status_code == 200
        db.refresh(user)
        assert user.last_login_at is not None


# ===========================================================================
# S6-18: login — negative cases
# ===========================================================================
class TestLoginFailures:
    def test_login_wrong_password(self, client, db):
        _make_user(db, "wrong@example.com", _VALID_PASSWORD)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "wrong@example.com", "password": "BadPass1!Wrong"},
        )
        assert response.status_code == 401, response.text
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "ghost@example.com", "password": _VALID_PASSWORD},
        )
        assert response.status_code == 401, response.text

    def test_login_rate_limited(self, client, db):
        """S1-05: /login is throttled at 10/minute by slowapi."""
        _make_user(db, "rl@example.com", _VALID_PASSWORD)
        # Make 11 attempts with the same wrong password — slowapi must
        # reject the last one with 429.
        last_status = None
        for _ in range(11):
            last_status = client.post(
                "/api/v1/auth/login",
                data={"username": "rl@example.com", "password": "Wrong1!"},
            ).status_code
        assert last_status == 429, f"expected 429, got {last_status}"


# ===========================================================================
# /auth/me — small smoke
# ===========================================================================
class TestAuthMe:
    def test_me_returns_current_user(self, client, db):
        user, _ = _make_member(db, "me@example.com")
        response = client.get("/api/v1/auth/me", headers=_auth_headers(user))
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"

    def test_me_without_token_returns_401(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401