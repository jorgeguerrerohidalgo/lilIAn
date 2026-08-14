"""Tests for /alerts/* endpoints — list, update, isolation.

Covers S6-22:
- list filtered by org
- update status (acknowledge / resolve / dismiss)
- due_date / matter_id cross-tenant isolation

Note: the deadline_alerts router exposes GET and PATCH endpoints; alerts
themselves are created by the deadline_generator service, not by a POST
endpoint. The tests below seed ``DeadlineAlert`` rows directly via the
SQLAlchemy session and exercise the HTTP surface.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.deadline_alert import DeadlineAlert
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


def _make_matter(db, org_id: int, user_id: int, title: str = "Caso") -> Matter:
    matter = Matter(
        organization_id=org_id,
        created_by_user_id=user_id,
        title=title,
        matter_type="other",
        status=MatterStatus.NEW,
        urgency=MatterUrgency.MEDIUM,
    )
    db.add(matter)
    db.commit()
    db.refresh(matter)
    return matter


def _make_alert(
    db,
    org_id: int,
    matter_id: int,
    title: str = "Plazo X",
    due_date: date | None = None,
    urgency: str = "medium",
    status: str = "pending",
    is_overdue: bool = False,
) -> DeadlineAlert:
    alert = DeadlineAlert(
        organization_id=org_id,
        matter_id=matter_id,
        title=title,
        description="Detalle",
        event_type="judicial_deadline",
        due_date=due_date or (date.today() + timedelta(days=10)),
        days_remaining=10,
        is_overdue=is_overdue,
        urgency=urgency,
        importance_score=50,
        status=status,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@pytest.fixture
def org_a(db):
    org = _make_org(db, "Org A")
    user = _make_user(db, "lawyer.a@example.com", org.id, MemberRole.LAWYER)
    matter = _make_matter(db, org.id, user.id, "Caso A")
    return {"org": org, "user": user, "matter": matter}


@pytest.fixture
def org_b(db):
    org = _make_org(db, "Org B")
    user = _make_user(db, "lawyer.b@example.com", org.id, MemberRole.LAWYER)
    matter = _make_matter(db, org.id, user.id, "Caso B")
    return {"org": org, "user": user, "matter": matter}


# ===========================================================================
# S6-22: list — filtered by org
# ===========================================================================
class TestListAlerts:
    def test_list_alerts_filtered_by_org(self, client, org_a, org_b, db):
        _make_alert(db, org_a["org"].id, org_a["matter"].id, title="A-Alert")
        _make_alert(db, org_b["org"].id, org_b["matter"].id, title="B-Alert")

        resp_a = client.get("/api/v1/alerts/", headers=_auth_headers(org_a["user"]))
        assert resp_a.status_code == 200
        titles_a = [a["title"] for a in resp_a.json()]
        assert titles_a == ["A-Alert"]

        resp_b = client.get("/api/v1/alerts/", headers=_auth_headers(org_b["user"]))
        titles_b = [a["title"] for a in resp_b.json()]
        assert titles_b == ["B-Alert"]

    def test_list_alerts_unauthenticated_returns_401(self, client):
        resp = client.get("/api/v1/alerts/")
        assert resp.status_code == 401

    def test_list_alerts_without_org_returns_403(self, client, db):
        orphan = User(
            email="orphan@a.com",
            password_hash=get_password_hash("Test1234!Abcd"),
            full_name="Orphan",
        )
        db.add(orphan)
        db.commit()
        db.refresh(orphan)

        resp = client.get("/api/v1/alerts/", headers=_auth_headers(orphan))
        assert resp.status_code == 403

    def test_list_alerts_filter_by_status(self, client, org_a, db):
        _make_alert(db, org_a["org"].id, org_a["matter"].id,
                    title="Pendiente", status="pending")
        _make_alert(db, org_a["org"].id, org_a["matter"].id,
                    title="Resuelto", status="resolved")

        resp = client.get(
            "/api/v1/alerts/?status=resolved",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        titles = [a["title"] for a in resp.json()]
        assert titles == ["Resuelto"]

    def test_list_alerts_filter_by_matter(self, client, org_a, db):
        matter2 = _make_matter(db, org_a["org"].id, org_a["user"].id, "Caso 2")
        _make_alert(db, org_a["org"].id, org_a["matter"].id, title="M1-Alert")
        _make_alert(db, org_a["org"].id, matter2.id, title="M2-Alert")

        resp = client.get(
            f"/api/v1/alerts/?matter_id={matter2.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        titles = [a["title"] for a in resp.json()]
        assert titles == ["M2-Alert"]


# ===========================================================================
# S6-22: create via direct DB seed + assert appears in list
# ===========================================================================
class TestCreateAlert:
    """The router does not expose POST /alerts — alerts are seeded by
    the deadline_generator service. This test seeds one via the
    SQLAlchemy session (mirroring how production creates them) and
    verifies the GET endpoint exposes it.
    """

    def test_create_alert_via_seed(self, client, org_a, db):
        alert = _make_alert(
            db,
            org_a["org"].id,
            org_a["matter"].id,
            title="Nuevo Plazo",
            due_date=date.today() + timedelta(days=3),
            urgency="high",
        )

        resp = client.get(
            f"/api/v1/alerts/{alert.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Nuevo Plazo"
        assert body["urgency"] == "high"
        assert body["status"] == "pending"
        assert body["organization_id"] == org_a["org"].id


# ===========================================================================
# S6-22: update status
# ===========================================================================
class TestUpdateAlertStatus:
    def test_acknowledge_alert_sets_acknowledged_at(self, client, org_a, db):
        alert = _make_alert(db, org_a["org"].id, org_a["matter"].id, status="pending")

        resp = client.patch(
            f"/api/v1/alerts/{alert.id}",
            headers=_auth_headers(org_a["user"]),
            json={"status": "acknowledged"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "acknowledged"
        assert body["acknowledged_at"] is not None
        assert body["acknowledged_by"] == org_a["user"].id

    def test_resolve_alert_sets_resolved_at(self, client, org_a, db):
        alert = _make_alert(db, org_a["org"].id, org_a["matter"].id, status="pending")

        resp = client.patch(
            f"/api/v1/alerts/{alert.id}",
            headers=_auth_headers(org_a["user"]),
            json={"status": "resolved"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["resolved_at"] is not None
        assert body["resolved_by"] == org_a["user"].id

    def test_dismiss_alert_does_not_set_timestamps(self, client, org_a, db):
        """``dismissed`` is a valid status but the endpoint only stamps
        timestamps for ``acknowledged`` / ``resolved``.
        """
        alert = _make_alert(db, org_a["org"].id, org_a["matter"].id, status="pending")

        resp = client.patch(
            f"/api/v1/alerts/{alert.id}",
            headers=_auth_headers(org_a["user"]),
            json={"status": "dismissed"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "dismissed"
        assert body["acknowledged_at"] is None
        assert body["resolved_at"] is None

    def test_update_alert_cross_org_returns_404(self, client, org_a, org_b, db):
        """Org A cannot patch an alert owned by Org B."""
        alert_b = _make_alert(db, org_b["org"].id, org_b["matter"].id, status="pending")

        resp = client.patch(
            f"/api/v1/alerts/{alert_b.id}",
            headers=_auth_headers(org_a["user"]),
            json={"status": "acknowledged"},
        )
        assert resp.status_code == 404

    def test_update_nonexistent_alert_returns_404(self, client, org_a):
        resp = client.patch(
            "/api/v1/alerts/999999",
            headers=_auth_headers(org_a["user"]),
            json={"status": "acknowledged"},
        )
        assert resp.status_code == 404


# ===========================================================================
# S6-22: due_date validation + matter existence
# ===========================================================================
class TestAlertDueDateAndMatter:
    def test_alert_due_date_validation(self, client, org_a, db):
        """``due_date`` is required (NOT NULL column) and accepts any
        ISO date. We seed an alert with a past due_date and assert it
        is still readable through the API.
        """
        past = date.today() - timedelta(days=30)
        alert = _make_alert(
            db,
            org_a["org"].id,
            org_a["matter"].id,
            title="Vencido",
            due_date=past,
            is_overdue=True,
        )

        resp = client.get(
            f"/api/v1/alerts/{alert.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        # due_date is serialized as ISO string
        assert body["due_date"] == past.isoformat()
        assert body["is_overdue"] is True

    def test_get_alerts_for_matter_filters_by_matter(self, client, org_a, db):
        matter2 = _make_matter(db, org_a["org"].id, org_a["user"].id, "Caso 2")
        _make_alert(db, org_a["org"].id, org_a["matter"].id, title="M1")
        _make_alert(db, org_a["org"].id, matter2.id, title="M2")

        resp = client.get(
            f"/api/v1/alerts/matters/{matter2.id}",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        titles = [a["title"] for a in resp.json()]
        assert titles == ["M2"]

    def test_get_alerts_for_unknown_matter_returns_404(self, client, org_a):
        resp = client.get(
            "/api/v1/alerts/matters/999999",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 404


# ===========================================================================
# /alerts/summary smoke
# ===========================================================================
class TestAlertsSummary:
    def test_summary_counts_only_own_org(self, client, org_a, org_b, db):
        # org_a: 1 active critical, 1 resolved (should NOT count as active)
        _make_alert(
            db, org_a["org"].id, org_a["matter"].id,
            title="Crit-A", urgency="critical", status="pending",
        )
        _make_alert(
            db, org_a["org"].id, org_a["matter"].id,
            title="Res-A", urgency="high", status="resolved",
        )
        # org_b: 1 high pending
        _make_alert(
            db, org_b["org"].id, org_b["matter"].id,
            title="High-B", urgency="high", status="pending",
        )

        resp = client.get(
            "/api/v1/alerts/summary",
            headers=_auth_headers(org_a["user"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2  # both A alerts
        assert body["critical"] == 1
        assert body["high"] == 0  # the high one in A is resolved, not active
        # org_b's high alert must NOT leak into A's summary
        assert body["high"] != 1 or body["total"] != 3