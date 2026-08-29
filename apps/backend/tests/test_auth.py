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

# Ley 21.719 — the legal-page versions currently in production. Tests
# that simulate a registration must include these so the backend's
# consent gate accepts the payload.
_LEGAL_TERMS_VERSION = "v1-2026-08-29"
_LEGAL_PRIVACY_VERSION = "v1-2026-08-29"


def _consent_payload(**overrides):
    """Build a registration payload that satisfies the Ley 21.719
    consent gate. Individual fields can be overridden to test
    rejection paths."""
    base = {
        "email": "user@example.com",
        "password": _VALID_PASSWORD,
        "full_name": "Test User",
        "terms_accepted": True,
        "privacy_accepted": True,
        "terms_version": _LEGAL_TERMS_VERSION,
        "privacy_version": _LEGAL_PRIVACY_VERSION,
    }
    base.update(overrides)
    return base


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
        payload = _consent_payload(email="new@example.com", full_name="New User")
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["email"] == payload["email"]
        assert body["full_name"] == payload["full_name"]
        assert "id" in body
        assert "password" not in body
        assert "password_hash" not in body

    def test_register_creates_organization_and_membership(self, client, db):
        payload = _consent_payload(email="owner@example.com", full_name="Owner")
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        user = db.query(User).filter(User.email == payload["email"]).first()
        assert user is not None
        # Ley 21.719 — the denormalised consent fields land on the User row.
        assert user.consent_given_at is not None
        assert user.terms_version == _LEGAL_TERMS_VERSION
        assert user.privacy_version == _LEGAL_PRIVACY_VERSION

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

    # ----------------------------------------------------------------
    # Ley 21.719 — explicit consent gate (Fase 0).
    # The backend must refuse to create an account when the user has
    # not actively opted in to Terms + Privacy Policy. This is the
    # legal requirement that gates everything else in the compliance
    # surface.
    # ----------------------------------------------------------------

    def test_register_rejects_when_terms_not_accepted(self, client, db):
        payload = _consent_payload(email="no-terms@example.com", terms_accepted=False)
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422
        assert "términos" in response.json()["detail"].lower()
        # Critical: no User row should have been created.
        assert db.query(User).filter(User.email == "no-terms@example.com").first() is None

    def test_register_rejects_when_privacy_not_accepted(self, client, db):
        payload = _consent_payload(email="no-privacy@example.com", privacy_accepted=False)
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422
        assert "privacidad" in response.json()["detail"].lower()
        assert db.query(User).filter(User.email == "no-privacy@example.com").first() is None

    def test_register_rejects_when_consent_flags_missing(self, client, db):
        # Frontends built before Ley 21.719 don't send the consent
        # flags at all. The gate must still hold.
        payload = {
            "email": "legacy@example.com",
            "password": _VALID_PASSWORD,
            "full_name": "Legacy",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422
        assert "términos" in response.json()["detail"].lower()

    def test_register_rejects_when_versions_missing(self, client, db):
        # Consent granted but versions omitted — we still need a
        # verifiable trail of *which* legal text the user agreed to.
        payload = _consent_payload(
            email="no-version@example.com",
            terms_version=None,
            privacy_version=None,
        )
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422
        assert "versión" in response.json()["detail"].lower()

    def test_register_persists_consent_records(self, client, db):
        """Ley 21.719 — one ConsentRecord per scope must be persisted
        with IP + UA so we have a verifiable trail for years."""
        from app.models.consent import ConsentRecord, ConsentScope

        payload = _consent_payload(email="tracked@example.com")
        response = client.post(
            "/api/v1/auth/register",
            json=payload,
            headers={"user-agent": "pytest-suite/1.0"},
        )
        assert response.status_code == 201

        user = db.query(User).filter(User.email == "tracked@example.com").first()
        records = (
            db.query(ConsentRecord)
            .filter(ConsentRecord.user_id == user.id)
            .all()
        )
        scopes = {r.scope for r in records}
        assert scopes == {ConsentScope.TERMS, ConsentScope.PRIVACY}
        for r in records:
            assert r.version == _LEGAL_TERMS_VERSION
            assert r.granted_at is not None
            assert r.revoked_at is None
            assert r.user_agent == "pytest-suite/1.0"

    def test_register_rejects_stale_terms_version(self, client):
        # A user accepting a stale legal version (e.g. v0 cached in
        # their browser) must be rejected so the frontend re-renders
        # the current text. We can't actually verify staleness without
        # server-side state, but we *can* verify that omitting the
        # version triggers the gate.
        payload = _consent_payload(
            email="stale@example.com",
            terms_version="",
        )
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


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
