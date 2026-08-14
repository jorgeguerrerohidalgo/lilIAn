"""Tests para endpoints /reviews (workflow draft -> pending -> approved/rejected).

S6-B5 / S6-29: covers the review workflow endpoints in
``app.api.endpoints.review``.

The ``review`` router is not yet included in ``app.main`` (Sprint 7+),
so we mount it directly on the app for the duration of each test using
FastAPI's ``include_router`` and a unique prefix.
"""
from __future__ import annotations

import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.analysis_report import AnalysisReport
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.review import Review, ReviewStatus
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


def _make_org(db) -> Organization:
    org = Organization(name="Org Review", type=OrganizationType.LAW_FIRM)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_analysis(db, org_id: int, user_id: int) -> AnalysisReport:
    ar = AnalysisReport(
        organization_id=org_id,
        matter_id=1,  # FK not enforced in SQLite test schema
        generated_by_user_id=user_id,
        report_type="preliminary_case_analysis",
        summary="x",
        status="generated",
    )
    db.add(ar)
    db.commit()
    db.refresh(ar)
    return ar


@pytest.fixture
def mounted_review_app(db):
    """Return a TestClient for a FastAPI app with the review router mounted.

    We re-use the same in-memory SQLite engine from conftest by mounting the
    router onto a fresh FastAPI instance that reuses ``app.main.app``'s
    dependency overrides via the ``get_db`` override pattern.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.endpoints import review as review_router
    from app.core.database import get_db

    from tests.conftest import _override_get_db

    app = FastAPI()
    app.include_router(review_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _override_get_db

    return TestClient(app)


@pytest.fixture
def org(db):
    return _make_org(db)


@pytest.fixture
def lawyer(db, org):
    return _make_user(db, "lawyer@review.com", org.id, MemberRole.LAWYER)


@pytest.fixture
def client_user(db, org):
    """A CLIENT role user — must not be allowed to review."""
    return _make_user(db, "client@review.com", org.id, MemberRole.CLIENT)


@pytest.fixture
def analysis(db, org, lawyer):
    return _make_analysis(db, org.id, lawyer.id)


# ===========================================================================
# Create / List pending
# ===========================================================================
class TestCreateReview:
    def test_create_review_starts_in_draft(self, mounted_review_app, db, lawyer, analysis):
        response = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id, "comments": "draft comments"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "draft"
        assert body["analysis_report_id"] == analysis.id
        assert body["created_by_user_id"] == lawyer.id
        # Persisted in DB
        review = db.query(Review).filter(Review.id == body["id"]).first()
        assert review is not None
        assert review.status == ReviewStatus.DRAFT

    def test_create_review_duplicate_active_returns_400(
        self, mounted_review_app, db, lawyer, analysis
    ):
        # First review succeeds
        r1 = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        )
        assert r1.status_code == 201

        # Second one blocked
        r2 = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        )
        assert r2.status_code == 400
        assert "ya existe" in r2.json()["detail"].lower()

    def test_create_review_for_missing_analysis_returns_404(
        self, mounted_review_app, lawyer
    ):
        response = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": 99999},
        )
        assert response.status_code == 404


class TestListPendingReviews:
    """The list endpoint /reviews/analysis/{id} surfaces pending reviews."""

    def test_list_pending_reviews_returns_recent(
        self, mounted_review_app, db, org, lawyer, analysis
    ):
        # Create a draft, submit it so it's pending, then list
        created = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        ).json()
        # submit -> pending
        submit_resp = mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/submit",
            headers=_auth_headers(lawyer),
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["status"] == "pending"

        # list
        list_resp = mounted_review_app.get(
            f"/api/v1/reviews/analysis/{analysis.id}",
            headers=_auth_headers(lawyer),
        )
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert len(body) == 1
        assert body[0]["status"] == "pending"


# ===========================================================================
# Approve / Reject
# ===========================================================================
class TestApproveReview:
    def _make_pending_review(self, mounted_review_app, db, lawyer, analysis):
        created = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        ).json()
        mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/submit",
            headers=_auth_headers(lawyer),
        )
        return created["id"]

    def test_approve_review_changes_status(
        self, mounted_review_app, db, lawyer, analysis, monkeypatch
    ):
        # Stub the missing update_analysis_review_status so we don't depend on
        # a function the current codebase hasn't implemented yet.
        import app.services.analysis as analysis_svc

        calls = []

        def _fake_update(report_id, new_status, db_session):
            calls.append((report_id, new_status))

        monkeypatch.setattr(
            analysis_svc, "update_analysis_review_status", _fake_update, raising=False
        )

        review_id = self._make_pending_review(mounted_review_app, db, lawyer, analysis)

        response = mounted_review_app.post(
            f"/api/v1/reviews/{review_id}/approve",
            headers=_auth_headers(lawyer),
            json={"comments": "LGTM"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "approved"
        assert body["reviewed_by_user_id"] == lawyer.id
        assert body["reviewed_at"] is not None

        # DB row reflects the change
        review = db.query(Review).filter(Review.id == review_id).first()
        assert review.status == ReviewStatus.APPROVED
        # Side effect: analysis was marked approved
        assert calls == [(analysis.id, "approved")]


class TestRejectReview:
    def _make_pending_review(self, mounted_review_app, db, lawyer, analysis):
        created = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        ).json()
        mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/submit",
            headers=_auth_headers(lawyer),
        )
        return created["id"]

    def test_reject_review_requires_reason_and_records_changes(
        self, mounted_review_app, db, lawyer, analysis, monkeypatch
    ):
        import app.services.analysis as analysis_svc

        calls = []

        def _fake_update(report_id, new_status, db_session):
            calls.append((report_id, new_status))

        monkeypatch.setattr(
            analysis_svc, "update_analysis_review_status", _fake_update, raising=False
        )

        review_id = self._make_pending_review(mounted_review_app, db, lawyer, analysis)

        response = mounted_review_app.post(
            f"/api/v1/reviews/{review_id}/reject",
            headers=_auth_headers(lawyer),
            json={"comments": "Datos insuficientes", "suggested_changes": "Agregar contrato"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "rejected"
        assert body["rejection_reason"] == "Datos insuficientes"
        assert body["suggested_changes"] == "Agregar contrato"

        review = db.query(Review).filter(Review.id == review_id).first()
        assert review.status == ReviewStatus.REJECTED
        assert calls == [(analysis.id, "rejected")]

    def test_reject_review_missing_reason_returns_422(
        self, mounted_review_app, db, lawyer, analysis
    ):
        review_id = self._make_pending_review(mounted_review_app, db, lawyer, analysis)

        response = mounted_review_app.post(
            f"/api/v1/reviews/{review_id}/reject",
            headers=_auth_headers(lawyer),
            json={},  # missing required `comments` field
        )
        # Pydantic validation -> 422
        assert response.status_code == 422


# ===========================================================================
# Role enforcement
# ===========================================================================
class TestReviewRequiresCorrectRole:
    def test_client_role_cannot_submit(
        self, mounted_review_app, db, org, lawyer, client_user, analysis
    ):
        # lawyer creates a draft
        created = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        ).json()

        # client tries to submit -> 403 (require_reviewer)
        response = mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/submit",
            headers=_auth_headers(client_user),
        )
        assert response.status_code == 403
        assert (
            "OWNER" in response.json()["detail"]
            or "ADMIN" in response.json()["detail"]
            or "LAWYER" in response.json()["detail"]
        )

    def test_client_role_cannot_approve(
        self, mounted_review_app, db, org, lawyer, client_user, analysis
    ):
        # Lawyer creates + submits to make it pending
        created = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        ).json()
        mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/submit",
            headers=_auth_headers(lawyer),
        )

        response = mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/approve",
            headers=_auth_headers(client_user),
            json={},
        )
        assert response.status_code == 403

    def test_viewer_role_cannot_reject(
        self, mounted_review_app, db, org, lawyer, analysis
    ):
        viewer = _make_user(db, "viewer@review.com", org.id, MemberRole.VIEWER)

        # Lawyer creates + submits
        created = mounted_review_app.post(
            "/api/v1/reviews",
            headers=_auth_headers(lawyer),
            json={"analysis_report_id": analysis.id},
        ).json()
        mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/submit",
            headers=_auth_headers(lawyer),
        )

        response = mounted_review_app.post(
            f"/api/v1/reviews/{created['id']}/reject",
            headers=_auth_headers(viewer),
            json={"comments": "no"},
        )
        assert response.status_code == 403
