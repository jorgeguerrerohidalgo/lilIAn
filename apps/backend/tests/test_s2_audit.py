"""S2 audit regression tests for search, precedents, and saas endpoints.

This test file is the regression gate for the S2 cross-tenant audit. It
locks in the property that:

- GET/POST /search/* filters document chunks by the caller's org.
- GET/POST /precedents/* filters precedents by the caller's org.
- GET /saas/metrics, /saas/subscription, /saas/usage/events filter
  counts and rows by the caller's org.

The audit found no active leaks (the endpoints were already correctly
scoped); this test exists to prevent future regressions and to serve as
living documentation of the expected isolation contract.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.matter import Matter, MatterStatus, MatterType, MatterUrgency
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.precedent import Precedent
from app.models.subscription import Plan, Subscription, UsageEvent
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


def _make_plan(db, name: str = "starter") -> Plan:
    plan = Plan(
        name=name,
        display_name=name.title(),
        is_active=True,
        documents_limit=10,
        analyses_limit=10,
        users_limit=2,
        monthly_price=100,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


# ===========================================================================
# S2: precedents endpoint isolation
# ===========================================================================
class TestPrecedentsTenantIsolation:
    def test_list_precedents_excludes_other_org(
        self, client, db
    ):
        """list_precedents (via /precedents/{id}) must return 404 for a
        precedent owned by another tenant.
        """
        org_a = _make_org(db, "Prec A")
        user_a = _make_user(db, "pa@a.com", org_a.id, MemberRole.LAWYER)
        org_b = _make_org(db, "Prec B")
        _make_user(db, "pb@b.com", org_b.id, MemberRole.LAWYER)

        prec_b = Precedent(
            organization_id=org_b.id,
            court="Corte Suprema",
            tribunal="Corte Suprema",
            year=2024,
            roll_number="1234-2024",
            legal_area="civil",
            summary="Sentencia de tenant B",
        )
        db.add(prec_b)
        db.commit()
        db.refresh(prec_b)

        response = client.get(
            f"/api/v1/precedents/{prec_b.id}",
            headers=_auth_headers(user_a),
        )
        assert response.status_code == 404, (
            "S2 regression: tenant A was able to read tenant B's precedent"
        )

    def test_courts_list_scoped_to_caller_org(
        self, client, db
    ):
        """GET /precedents/courts must only return courts that have
        precedents belonging to the caller's organization.
        """
        org_a = _make_org(db, "Courts A")
        user_a = _make_user(db, "ca@a.com", org_a.id, MemberRole.LAWYER)
        org_b = _make_org(db, "Courts B")
        _make_user(db, "cb@b.com", org_b.id, MemberRole.LAWYER)

        db.add(Precedent(
            organization_id=org_a.id,
            court="Corte de Apelaciones de Santiago",
            tribunal="Corte de Apelaciones de Santiago",
            year=2024, roll_number="1-2024", legal_area="civil",
            summary="x",
        ))
        db.add(Precedent(
            organization_id=org_b.id,
            court="Corte Suprema",
            tribunal="Corte Suprema",
            year=2024, roll_number="2-2024", legal_area="civil",
            summary="y",
        ))
        db.commit()

        response = client.get(
            "/api/v1/precedents/courts", headers=_auth_headers(user_a)
        )
        assert response.status_code == 200
        courts = response.json()["courts"]
        assert "Corte de Apelaciones de Santiago" in courts
        assert "Corte Suprema" not in courts, (
            "S2 regression: tenant A's /precedents/courts leaked "
            "tenant B's court name"
        )


# ===========================================================================
# S2: saas endpoint isolation
# ===========================================================================
class TestSaasTenantIsolation:
    def test_subscription_returns_404_for_other_org(
        self, client, db
    ):
        """A subscription belonging to org B must not be visible to a
        user from org A. /saas/subscription must return null in that
        case (no subscription found for org A) — never the org B row.
        """
        _make_plan(db, "starter")

        org_a = _make_org(db, "Sub A")
        user_a = _make_user(db, "sa@a.com", org_a.id, MemberRole.LAWYER)
        org_b = _make_org(db, "Sub B")

        sub_b = Subscription(
            organization_id=org_b.id,
            plan_name="starter",
            status="active",
            documents_limit=10,
            analyses_limit=10,
            users_limit=2,
            monthly_price=100,
        )
        db.add(sub_b)
        db.commit()

        response = client.get(
            "/api/v1/saas/subscription", headers=_auth_headers(user_a)
        )
        assert response.status_code == 200
        assert response.json() is None, (
            "S2 regression: tenant A saw tenant B's subscription via "
            "/saas/subscription"
        )

    def test_metrics_counts_only_caller_org(
        self, client, db
    ):
        """Total counts in /saas/metrics must reflect only the caller's
        organization (no cross-tenant aggregation).
        """
        org_a = _make_org(db, "Metrics A")
        user_a = _make_user(db, "ma@a.com", org_a.id, MemberRole.LAWYER)
        org_b = _make_org(db, "Metrics B")
        _make_user(db, "mb@b.com", org_b.id, MemberRole.LAWYER)

        # 2 matters for A, 5 for B
        for i in range(2):
            db.add(Matter(
                organization_id=org_a.id,
                created_by_user_id=user_a.id,
                title=f"A {i}",
                matter_type=MatterType.OTHER,
                status=MatterStatus.IN_PROGRESS,
                urgency=MatterUrgency.MEDIUM,
            ))
        for i in range(5):
            db.add(Matter(
                organization_id=org_b.id,
                created_by_user_id=user_a.id,
                title=f"B {i}",
                matter_type=MatterType.OTHER,
                status=MatterStatus.IN_PROGRESS,
                urgency=MatterUrgency.MEDIUM,
            ))
        db.commit()

        response = client.get(
            "/api/v1/saas/metrics", headers=_auth_headers(user_a)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_matters"] == 2, (
            f"S2 regression: /saas/metrics leaked cross-tenant matters "
            f"(expected 2 for org A, got {body['total_matters']})"
        )

    def test_usage_events_scoped_to_caller_org(
        self, client, db
    ):
        """GET /saas/usage/events must only return events belonging to
        the caller's organization.
        """
        org_a = _make_org(db, "Usage A")
        user_a = _make_user(db, "ua@a.com", org_a.id, MemberRole.LAWYER)
        org_b = _make_org(db, "Usage B")
        _make_user(db, "ub@b.com", org_b.id, MemberRole.LAWYER)

        db.add(UsageEvent(
            organization_id=org_a.id, user_id=user_a.id,
            event_type="document_uploaded", quantity=1,
        ))
        db.add(UsageEvent(
            organization_id=org_b.id, user_id=user_a.id,
            event_type="document_uploaded", quantity=1,
        ))
        db.commit()

        response = client.get(
            "/api/v1/saas/usage/events", headers=_auth_headers(user_a)
        )
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1, (
            f"S2 regression: /saas/usage/events leaked cross-tenant "
            f"events (expected 1, got {len(events)})"
        )
        assert all(e["user_id"] == user_a.id for e in events)


# ===========================================================================
# S2: search endpoint isolation (matter lookup must reject cross-tenant ids)
# ===========================================================================
class TestSearchTenantIsolation:
    def test_search_rejects_other_org_matter(
        self, client, db
    ):
        """POST /search must return 404 when the requested matter_id
        belongs to a different organization.
        """
        org_a = _make_org(db, "Search A")
        user_a = _make_user(db, "sea@a.com", org_a.id, MemberRole.LAWYER)
        org_b = _make_org(db, "Search B")
        _make_user(db, "seb@b.com", org_b.id, MemberRole.LAWYER)

        matter_b = Matter(
            organization_id=org_b.id,
            created_by_user_id=user_a.id,
            title="B matter",
            matter_type=MatterType.OTHER,
            status=MatterStatus.IN_PROGRESS,
            urgency=MatterUrgency.MEDIUM,
        )
        db.add(matter_b)
        db.commit()
        db.refresh(matter_b)

        response = client.post(
            "/api/v1/search",
            json={
                "query": "arrendamiento",
                "matter_id": matter_b.id,
                "top_k": 5,
                "use_embeddings": False,
            },
            headers=_auth_headers(user_a),
        )
        assert response.status_code == 404, (
            "S2 regression: tenant A was able to search inside tenant B's "
            "matter via /search"
        )
