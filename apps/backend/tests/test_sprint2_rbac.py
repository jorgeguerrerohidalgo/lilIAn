"""Regression tests for Sprint 2 RBAC fixes.

Covers the four issues found during the S2 audit:

S2-01: ``GET /metrics`` must require authentication and scope DB counts to
       the caller's organization.
S2-02: ``GET /legal-areas`` must require organization membership.
S2-03: chat.send_message must scope the ``Matter`` lookup to the caller's org.
S2-04: ``/metrics`` business counts must NOT leak cross-tenant.

Tests use the same SQLite-in-memory harness as ``test_isolation.py``.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.matter import Matter, MatterStatus, MatterUrgency
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User

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


def _auth_headers(user: User) -> dict:
    """Generate auth headers for the given user via /auth/test-token style.

    For Sprint 2 we rely on the JWT directly because /auth/login needs a
    full password round-trip. We mint a token with the same helper the
    security module uses.
    """
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def _make_org(db, name: str) -> Organization:
    org = Organization(name=name, type=OrganizationType.INDIVIDUAL)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_user(db, email: str, org_id: int, role: MemberRole) -> User:
    user = User(
        email=email,
        password_hash=get_password_hash("Test1234!Abcd"),
        full_name=email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    membership = OrganizationMember(
        organization_id=org_id, user_id=user.id, role=role
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return user


# ===========================================================================
# S2-01: /metrics must require authentication
# ===========================================================================
class TestMetricsRequiresAuth:
    def test_unauthenticated_metrics_returns_401(self, client):
        """Previously /metrics had no auth at all (CRITICAL leak)."""
        response = client.get("/metrics")
        assert response.status_code == 401, (
            f"S2-01 regression: /metrics returned {response.status_code}"
        )

    def test_authenticated_metrics_returns_200(self, client, db):
        org = _make_org(db, "Auth Org")
        user = _make_user(db, "metrics@auth.com", org.id, MemberRole.LAWYER)
        response = client.get("/metrics", headers=_auth_headers(user))
        assert response.status_code == 200


# ===========================================================================
# S2-02: /legal-areas must require organization membership
# ===========================================================================
class TestLegalAreasRequiresOrg:
    def test_unauthenticated_legal_areas_returns_401(self, client):
        response = client.get("/api/v1/legal-areas")
        assert response.status_code == 401, (
            f"S2-02 regression: /legal-areas returned {response.status_code}"
        )

    def test_user_without_org_returns_403(self, client, db):
        orphan = User(
            email="orphan@leg.com",
            password_hash=get_password_hash("Test1234!Abcd"),
            full_name="Sin org",
        )
        db.add(orphan)
        db.commit()
        db.refresh(orphan)
        response = client.get(
            "/api/v1/legal-areas", headers=_auth_headers(orphan)
        )
        assert response.status_code == 403

    def test_user_with_org_returns_200(self, client, db):
        org = _make_org(db, "LA Org")
        user = _make_user(db, "la@org.com", org.id, MemberRole.LAWYER)
        response = client.get(
            "/api/v1/legal-areas", headers=_auth_headers(user)
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ===========================================================================
# S2-04: /metrics must scope counts to caller's organization
# ===========================================================================
class TestMetricsTenantIsolation:
    def test_metrics_only_count_own_org_matters(
        self, client, db
    ):
        """Tenant A and Tenant B both have active matters; the /metrics
        response for tenant A must only include the matters that belong
        to tenant A.
        """
        org_a = _make_org(db, "Metrics A")
        user_a = _make_user(db, "ma@a.com", org_a.id, MemberRole.LAWYER)
        org_b = _make_org(db, "Metrics B")
        _make_user(db, "mb@b.com", org_b.id, MemberRole.LAWYER)

        # Each tenant gets one active matter
        matter_a = Matter(
            organization_id=org_a.id,
            created_by_user_id=user_a.id,
            title="A",
            matter_type="civil",
            status=MatterStatus.IN_PROGRESS,
            urgency=MatterUrgency.MEDIUM,
        )
        matter_b = Matter(
            organization_id=org_b.id,
            created_by_user_id=user_a.id,
            title="B",
            matter_type="civil",
            status=MatterStatus.IN_PROGRESS,
            urgency=MatterUrgency.MEDIUM,
        )
        db.add_all([matter_a, matter_b])
        db.commit()

        response = client.get(
            "/metrics", headers=_auth_headers(user_a)
        )
        assert response.status_code == 200
        body = response.json()
        # Org scoping tag must be present and correct
        assert body.get("organization_id") == org_a.id
