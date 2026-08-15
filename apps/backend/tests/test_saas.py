"""Tests for SaaS endpoints and helpers (S6-26).

Covers:
- GET /saas/plans requires authentication
- POST /saas/subscription requires auth
- GET /saas/metrics scoped per organization
- record_usage_event helper persists UsageEvent
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints.saas import record_usage_event
from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.matter import Matter, MatterStatus, MatterType, MatterUrgency
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.subscription import Plan, Subscription, UsageEvent
from app.models.user import User

# ---------------------------------------------------------------------------
# Local test DB (separate from the conftest engine so we can mount state)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="function")
def client(db):
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db, email, org_id, role, full_name=None):
    user = User(
        email=email,
        password_hash=get_password_hash("Test1234!"),
        full_name=full_name or email.split("@")[0],
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=role))
    db.commit()
    db.refresh(user)
    return user


def _make_org(db, name):
    org = Organization(name=name, type=OrganizationType.LAW_FIRM)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _auth_headers(user):
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def _seed_plans(db):
    db.add(Plan(name="free", display_name="Free", documents_limit=10,
                analyses_limit=5, users_limit=2, monthly_price=0, is_active=True))
    db.add(Plan(name="pro", display_name="Pro", documents_limit=100,
                analyses_limit=50, users_limit=10, monthly_price=9990, is_active=True))
    db.add(Plan(name="hidden", display_name="Hidden", documents_limit=999,
                analyses_limit=999, users_limit=999, monthly_price=1, is_active=False))
    db.commit()


# ---------------------------------------------------------------------------
# /saas/plans
# ---------------------------------------------------------------------------

def test_list_plans_public(client, db):
    """S6-26: /saas/plans requires authentication; only active plans returned."""
    _seed_plans(db)
    org = _make_org(db, "acme")
    user = _make_user(db, "u@acme.cl", org.id, MemberRole.OWNER)

    # Without auth -> 401
    r = client.get("/api/v1/saas/plans")
    assert r.status_code == 401

    # With auth -> 200, list excludes the hidden plan
    r = client.get("/api/v1/saas/plans", headers=_auth_headers(user))
    assert r.status_code == 200
    data = r.json()
    names = [p["name"] for p in data]
    assert "free" in names
    assert "pro" in names
    assert "hidden" not in names


# ---------------------------------------------------------------------------
# POST /saas/subscription requires auth
# ---------------------------------------------------------------------------

def test_create_subscription_requires_auth(client, db):
    """S6-26: POST /saas/subscription is gated by auth and role check."""
    _seed_plans(db)
    org = _make_org(db, "acme")
    user = _make_user(db, "u@acme.cl", org.id, MemberRole.LAWYER)

    r = client.post("/api/v1/saas/subscription?plan_name=pro")
    assert r.status_code == 401

    # Authenticated but role=LAWYER -> 403
    r = client.post(
        "/api/v1/saas/subscription?plan_name=pro",
        headers=_auth_headers(user),
    )
    assert r.status_code == 403

    # OWNER can create a subscription
    owner = _make_user(db, "owner@acme.cl", org.id, MemberRole.OWNER, full_name="Owner")
    r = client.post(
        "/api/v1/saas/subscription?plan_name=pro",
        headers=_auth_headers(owner),
    )
    assert r.status_code == 200
    assert r.json()["plan"] == "pro"

    subs = db.query(Subscription).filter(Subscription.organization_id == org.id).all()
    assert any(s.plan_name == "pro" and s.status == "active" for s in subs)


# ---------------------------------------------------------------------------
# /saas/metrics filters by organization
# ---------------------------------------------------------------------------

def test_get_organization_metrics_filtered(client, db):
    """S6-26: /saas/metrics counts only the caller's organization."""
    org_a = _make_org(db, "org-a")
    org_b = _make_org(db, "org-b")
    user_a = _make_user(db, "a@a.cl", org_a.id, MemberRole.OWNER)
    _make_user(db, "b@b.cl", org_b.id, MemberRole.OWNER)

    # 2 matters in org_a, 5 matters in org_b
    for i in range(2):
        db.add(Matter(
            organization_id=org_a.id,
            created_by_user_id=user_a.id,
            title=f"matter a {i}",
            matter_type=MatterType.OTHER,
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
        ))
    for i in range(5):
        db.add(Matter(
            organization_id=org_b.id,
            created_by_user_id=user_a.id,
            title=f"matter b {i}",
            matter_type=MatterType.OTHER,
            status=MatterStatus.NEW,
            urgency=MatterUrgency.MEDIUM,
        ))
    db.commit()

    r = client.get("/api/v1/saas/metrics", headers=_auth_headers(user_a))
    assert r.status_code == 200
    metrics = r.json()
    assert metrics["total_matters"] == 2
    assert metrics["total_users"] == 1


# ---------------------------------------------------------------------------
# record_usage_event
# ---------------------------------------------------------------------------

def test_record_usage_event(db):
    """S6-26: record_usage_event persists an event with serialized metadata."""
    org = _make_org(db, "acme")
    user = _make_user(db, "u@acme.cl", org.id, MemberRole.OWNER)

    record_usage_event(
        organization_id=org.id,
        user_id=user.id,
        event_type="document.uploaded",
        quantity=1,
        metadata={"filename": "contract.pdf"},
        db=db,
    )

    events = db.query(UsageEvent).filter(UsageEvent.organization_id == org.id).all()
    assert len(events) == 1
    e = events[0]
    assert e.event_type == "document.uploaded"
    assert e.quantity == 1
    assert e.user_id == user.id
    assert json.loads(e.event_metadata) == {"filename": "contract.pdf"}
    assert isinstance(e.created_at, datetime)
