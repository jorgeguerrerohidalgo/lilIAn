"""Tests para endpoints /admin (audit logs, org listing, platform stats).

S6-B5 / S6-30: covers the platform-admin endpoints in
``app.api.endpoints.admin``.

The admin router depends on ``get_platform_admin_membership`` which
checks ``MemberRole.PLATFORM_ADMIN`` — so the fixtures create one
admin user per tenant.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.audit_log import AuditLog
from app.models.matter import Matter, MatterStatus, MatterUrgency
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
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


def _make_org(db, name: str) -> Organization:
    org = Organization(name=name, type=OrganizationType.LAW_FIRM)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_audit_log(db, *, org_id, user_id, action, entity_type=None, entity_id=None,
                    ip=None, metadata=None, days_ago=0):
    log = AuditLog(
        organization_id=org_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip,
        log_metadata=str(metadata) if metadata else None,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def org_a(db):
    return _make_org(db, "Org A")


@pytest.fixture
def org_b(db):
    return _make_org(db, "Org B")


@pytest.fixture
def platform_admin(db):
    """PLATFORM_ADMIN user — has no tenant-scoped membership role.

    Per ``get_platform_admin_membership`` we only need a row with
    ``role == MemberRole.PLATFORM_ADMIN``; the ``organization_id`` is
    the host organization the admin operates from.
    """
    org = _make_org(db, "Internal Platform Org")
    user = User(
        email="admin@platform.com",
        password_hash=get_password_hash("Test1234!"),
        full_name="Platform Admin",
    )
    db.add(user)
    db.flush()
    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=MemberRole.PLATFORM_ADMIN,
        )
    )
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_lawyer(db, org_a):
    return _make_user(db, "lawyer@a.com", org_a.id, MemberRole.LAWYER)


@pytest.fixture
def audit_logs_seeded(db, org_a, org_b, regular_lawyer):
    """A small batch of audit logs across both orgs and a few actions."""
    return [
        _make_audit_log(
            db, org_id=org_a.id, user_id=regular_lawyer.id,
            action="login", entity_type="user", entity_id=regular_lawyer.id,
            ip="127.0.0.1", days_ago=0,
        ),
        _make_audit_log(
            db, org_id=org_a.id, user_id=regular_lawyer.id,
            action="matter.create", entity_type="matter", entity_id=1,
            ip="127.0.0.1", days_ago=1,
        ),
        _make_audit_log(
            db, org_id=org_b.id, user_id=None,
            action="login", entity_type="user", entity_id=2,
            ip="10.0.0.1", days_ago=2,
        ),
        _make_audit_log(
            db, org_id=org_b.id, user_id=None,
            action="matter.create", entity_type="matter", entity_id=2,
            ip="10.0.0.1", days_ago=10,  # outside default 7-day window
        ),
    ]


# ===========================================================================
# Authorization
# ===========================================================================
class TestAdminRequiresAdmin:
    def test_admin_endpoints_require_admin(self, client, db, org_a, regular_lawyer):
        """A regular LAWYER cannot access platform-admin endpoints."""
        # /admin/audit-logs
        r1 = client.get(
            "/api/v1/admin/audit-logs",
            headers=_auth_headers(regular_lawyer),
        )
        assert r1.status_code == 403

        # /admin/organizations
        r2 = client.get(
            "/api/v1/admin/organizations",
            headers=_auth_headers(regular_lawyer),
        )
        assert r2.status_code == 403

        # /admin/stats
        r3 = client.get(
            "/api/v1/admin/stats",
            headers=_auth_headers(regular_lawyer),
        )
        assert r3.status_code == 403

    def test_admin_endpoints_require_authentication(self, client):
        r = client.get("/api/v1/admin/audit-logs")
        assert r.status_code == 401


# ===========================================================================
# Audit log listing
# ===========================================================================
class TestListAuditLogs:
    def test_list_audit_logs_returns_recent(self, client, platform_admin, audit_logs_seeded):
        """Default 7-day window picks up the last 3 logs but not the 10-day-old one."""
        response = client.get(
            "/api/v1/admin/audit-logs",
            headers=_auth_headers(platform_admin),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # 3 of 4 logs are within the default 7-day window
        assert len(body) == 3
        # Most recent first
        assert body[0]["created_at"] >= body[-1]["created_at"]

    def test_audit_log_filtered_by_org(self, client, platform_admin, audit_logs_seeded, org_a):
        """``organization_id`` query parameter narrows results to one tenant."""
        response = client.get(
            "/api/v1/admin/audit-logs",
            params={"organization_id": org_a.id},
            headers=_auth_headers(platform_admin),
        )
        assert response.status_code == 200
        body = response.json()
        assert all(log["organization_id"] == org_a.id for log in body)
        assert len(body) >= 1

    def test_audit_log_filtered_by_action(self, client, platform_admin, audit_logs_seeded):
        response = client.get(
            "/api/v1/admin/audit-logs",
            params={"action_filter": "matter.create", "days": 30},
            headers=_auth_headers(platform_admin),
        )
        assert response.status_code == 200
        body = response.json()
        assert all(log["action"] == "matter.create" for log in body)
        assert len(body) == 2

    def test_audit_log_filtered_by_entity_type(self, client, platform_admin, audit_logs_seeded):
        response = client.get(
            "/api/v1/admin/audit-logs",
            params={"entity_type": "user"},
            headers=_auth_headers(platform_admin),
        )
        assert response.status_code == 200
        body = response.json()
        assert all(log["entity_type"] == "user" for log in body)

    def test_audit_log_extends_window(self, client, platform_admin, audit_logs_seeded):
        """Increasing the ``days`` parameter picks up the 10-day-old entry."""
        response = client.get(
            "/api/v1/admin/audit-logs",
            params={"days": 30},
            headers=_auth_headers(platform_admin),
        )
        assert response.status_code == 200
        assert len(response.json()) == 4


# ===========================================================================
# Organizations / stats
# ===========================================================================
class TestOrganizationAdminData:
    def test_get_organization_admin_data_returns_all_orgs_with_counts(
        self, client, platform_admin, org_a, org_b, regular_lawyer, db
    ):
        # Seed some users + matters to exercise the counters.
        _make_user(db, "lawyer2@a.com", org_a.id, MemberRole.LAWYER)
        matter = Matter(
            organization_id=org_a.id,
            created_by_user_id=regular_lawyer.id,
            title="Caso A",
            urgency=MatterUrgency.MEDIUM,
            status=MatterStatus.NEW,
        )
        db.add(matter)
        db.commit()

        response = client.get(
            "/api/v1/admin/organizations",
            headers=_auth_headers(platform_admin),
        )
        assert response.status_code == 200
        body = response.json()
        org_ids = {o["id"] for o in body}
        assert org_a.id in org_ids
        assert org_b.id in org_ids

        a_data = next(o for o in body if o["id"] == org_a.id)
        # org_a has at least the regular_lawyer + lawyer2 + admin = 3 members
        assert a_data["user_count"] >= 2
        assert a_data["matter_count"] == 1
        assert a_data["type"] in {"law_firm", "LAW_FIRM"}

    def test_suspend_and_activate_organization(
        self, client, platform_admin, org_a
    ):
        # Suspend
        r1 = client.post(
            f"/api/v1/admin/organizations/{org_a.id}/suspend",
            headers=_auth_headers(platform_admin),
        )
        assert r1.status_code == 200
        assert r1.json()["org_id"] == org_a.id

        # Activate
        r2 = client.post(
            f"/api/v1/admin/organizations/{org_a.id}/activate",
            headers=_auth_headers(platform_admin),
        )
        assert r2.status_code == 200

    def test_platform_stats_endpoint_returns_counts(
        self, client, platform_admin, org_a, org_b, regular_lawyer
    ):
        response = client.get(
            "/api/v1/admin/stats",
            headers=_auth_headers(platform_admin),
        )
        assert response.status_code == 200
        body = response.json()
        # All required keys present
        for key in (
            "total_organizations",
            "total_users",
            "total_matters",
            "total_documents",
            "active_subscriptions",
            "recent_logins",
        ):
            assert key in body
        assert body["total_organizations"] >= 2
        assert body["total_users"] >= 1
