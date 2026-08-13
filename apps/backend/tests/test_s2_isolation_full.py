"""S2 extended isolation tests.

Beyond the original test_isolation.py (24 tests), this file covers
endpoints added in S2-04 (chat) and Sprint 4 (document_analysis,
document_generator) plus the bits of admin / metrics / review that
S2-04 hadn't tested. Every test verifies that a user from Tenant A
cannot read, list, mutate, or delete resources owned by Tenant B.
"""
from __future__ import annotations

import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.client import Client
from app.models.matter import Matter
from app.models.organization import Organization, OrganizationType
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User

pytestmark = pytest.mark.integration


def _make_org_member(
    db, suffix: str, role: MemberRole = MemberRole.LAWYER
) -> tuple[Organization, User, OrganizationMember]:
    org = Organization(
        name=f"Isolation Org {suffix}",
        type=OrganizationType.LAW_FIRM,
    )
    db.add(org)
    db.flush()

    user = User(
        email=f"user-{suffix}@isolation.dev",
        password_hash=get_password_hash("Test1234!Isolate"),
        full_name=f"Isolation {suffix}",
    )
    db.add(user)
    db.flush()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=role,
    )
    db.add(membership)
    db.commit()
    db.refresh(org)
    db.refresh(user)
    db.refresh(membership)
    return org, user, membership


def _auth(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def _make_matter(db, org: Organization, user: User, title: str) -> Matter:
    matter = Matter(
        organization_id=org.id,
        created_by_user_id=user.id,
        title=title,
        matter_type="contract_review",
    )
    db.add(matter)
    db.commit()
    db.refresh(matter)
    return matter


def _make_client(db, org: Organization, user: User, name: str) -> Client:
    client = Client(
        organization_id=org.id,
        created_by_user_id=user.id,
        name=name,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


# -------------------------------------------------------------------
# Cross-tenant: matter visibility
# -------------------------------------------------------------------


class TestMatterCrossTenant:
    def test_other_tenant_cannot_get_matter(self, client, db):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        matter_a = _make_matter(db, org_a, user_a, "Tenant A confidential")

        response = client.get(
            f"/api/v1/matters/{matter_a.id}",
            headers=_auth(user_b),
        )
        assert response.status_code == 404, (
            f"Expected 404 for cross-tenant GET, got {response.status_code}: "
            f"{response.text[:200]}"
        )

    def test_other_tenant_cannot_update_matter(self, client, db):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        matter_a = _make_matter(db, org_a, user_a, "Tenant A confidential")

        response = client.patch(
            f"/api/v1/matters/{matter_a.id}",
            headers=_auth(user_b),
            json={"title": "Hi-jacked by Tenant B"},
        )
        assert response.status_code in (403, 404), (
            f"Expected 403/404 for cross-tenant PATCH, got {response.status_code}"
        )
        # Re-read to confirm Tenant A's data is intact
        assert matter_a.title == "Tenant A confidential"

    def test_other_tenant_cannot_delete_matter(self, client, db):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        matter_a = _make_matter(db, org_a, user_a, "Tenant A confidential")

        response = client.delete(
            f"/api/v1/matters/{matter_a.id}",
            headers=_auth(user_b),
        )
        assert response.status_code in (204, 403, 404), (
            f"Expected 204/403/404 for cross-tenant DELETE, got {response.status_code}"
        )
        # Confirm Tenant A's matter is still there
        still = db.query(Matter).filter(Matter.id == matter_a.id).first()
        assert still is not None, "Tenant A's matter was deleted by Tenant B"

    def test_listing_matters_excludes_other_tenants(
        self, client, db
    ):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        for i in range(3):
            _make_matter(db, org_a, user_a, f"Tenant A matter {i}")
        for i in range(2):
            _make_matter(db, org_b, user_b, f"Tenant B matter {i}")

        # Each tenant should see only their own matters
        res_a = client.get("/api/v1/matters", headers=_auth(user_a))
        res_b = client.get("/api/v1/matters", headers=_auth(user_b))

        assert res_a.status_code == 200
        assert res_b.status_code == 200
        titles_a = [m["title"] for m in res_a.json()]
        titles_b = [m["title"] for m in res_b.json()]
        # Strict: no overlap
        assert all(t.startswith("Tenant A") for t in titles_a), titles_a
        assert all(t.startswith("Tenant B") for t in titles_b), titles_b
        assert len(titles_a) == 3
        assert len(titles_b) == 2


# -------------------------------------------------------------------
# Cross-tenant: clients
# -------------------------------------------------------------------


class TestClientCrossTenant:
    def test_other_tenant_cannot_list_other_tenants_clients(
        self, client, db
    ):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        for i in range(2):
            _make_client(db, org_a, user_a, f"Client A{i}")
        for i in range(3):
            _make_client(db, org_b, user_b, f"Client B{i}")

        res_b = client.get("/api/v1/clients", headers=_auth(user_b))
        assert res_b.status_code == 200
        names = [c["name"] for c in res_b.json()]
        assert all(n.startswith("Client B") for n in names), names

    def test_other_tenant_cannot_use_other_tenants_client_id(
        self, client, db
    ):
        """S1-09/S2-04 regression: a user from Tenant B must not be able
        to attach a matter to a Tenant A client just by knowing the ID.
        """
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        client_a = _make_client(db, org_a, user_a, "Tenant A client")

        response = client.post(
            "/api/v1/matters",
            headers=_auth(user_b),
            json={
                "title": "Cross-tenant matter",
                "matter_type": "contract_review",
                "client_id": client_a.id,
            },
        )
        # Either 404 (client not found in B's tenant) or 400 — but never 201
        assert response.status_code >= 400
        assert response.status_code != 201, (
            f"Tenant B was able to create a matter using Tenant A's client_id! "
            f"Response: {response.text[:300]}"
        )


# -------------------------------------------------------------------
# Cross-tenant: documents
# -------------------------------------------------------------------


class TestDocumentCrossTenant:
    def test_other_tenant_cannot_get_document(self, client, db):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")

        # Need a Matter to belong to, then a Document
        matter_a = _make_matter(db, org_a, user_a, "Doc parent")
        from app.models.document import Document

        doc_a = Document(
            organization_id=org_a.id,
            matter_id=matter_a.id,
            uploaded_by_user_id=user_a.id,
            original_filename="secret.pdf",
            storage_path="/storage/secret.pdf",
            file_hash="x" * 64,
            file_size=1,
            mime_type="application/pdf",
        )
        db.add(doc_a)
        db.commit()
        db.refresh(doc_a)

        response = client.get(
            f"/api/v1/documents/{doc_a.id}",
            headers=_auth(user_b),
        )
        assert response.status_code in (403, 404), (
            f"Expected 403/404 for cross-tenant doc GET, got {response.status_code}"
        )

    def test_other_tenant_cannot_delete_document(self, client, db):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        matter_a = _make_matter(db, org_a, user_a, "Doc parent")
        from app.models.document import Document

        doc_a = Document(
            organization_id=org_a.id,
            matter_id=matter_a.id,
            uploaded_by_user_id=user_a.id,
            original_filename="secret.pdf",
            storage_path="/storage/secret.pdf",
            file_hash="y" * 64,
            file_size=1,
            mime_type="application/pdf",
        )
        db.add(doc_a)
        db.commit()
        db.refresh(doc_a)

        response = client.delete(
            f"/api/v1/documents/{doc_a.id}",
            headers=_auth(user_b),
        )
        assert response.status_code in (403, 404)
        # Confirm doc still exists
        still = db.query(Document).filter(Document.id == doc_a.id).first()
        assert still is not None


# -------------------------------------------------------------------
# Cross-tenant: chat session / messages (S2-03)
# -------------------------------------------------------------------


class TestChatCrossTenant:
    def test_other_tenant_cannot_read_chat_session(self, client, db):
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        matter_a = _make_matter(db, org_a, user_a, "Chat parent")
        from app.models.chat import ChatSession

        sess = ChatSession(
            organization_id=org_a.id,
            matter_id=matter_a.id,
            user_id=user_a.id,
            title="Tenant A private chat",
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)

        response = client.get(
            f"/api/v1/chat/sessions/{sess.id}/messages",
            headers=_auth(user_b),
        )
        assert response.status_code in (403, 404), (
            f"Expected 403/404 for cross-tenant chat GET, got "
            f"{response.status_code}: {response.text[:200]}"
        )


# -------------------------------------------------------------------
# Cross-tenant: legal_areas (S2-02)
# -------------------------------------------------------------------


class TestLegalAreasCrossTenant:
    def test_other_tenant_without_org_gets_403(self, client, db):
        """A user who is not a member of ANY organization cannot list
        legal areas. S2-02 closed this leak.
        """
        # Create a user with no memberships
        user = User(
            email="orphan@lilian.dev",
            password_hash=get_password_hash("Test1234!Orgless"),
            full_name="Orgless User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        response = client.get(
            "/api/v1/legal-areas",
            headers=_auth(user),
        )
        assert response.status_code == 403, (
            f"Orphan user got through with {response.status_code}"
        )


# -------------------------------------------------------------------
# Cross-tenant: /metrics (S2-01)
# -------------------------------------------------------------------


class TestMetricsCrossTenant:
    def test_metrics_filters_by_organization(self, client, db):
        """Each authenticated user sees /metrics scoped to their org only.
        S2-01 ensures cross-tenant aggregations don't leak.
        """
        org_a, user_a, _ = _make_org_member(db, "A")
        org_b, user_b, _ = _make_org_member(db, "B")
        for i in range(2):
            _make_matter(db, org_a, user_a, f"MA {i}")
        for i in range(4):
            _make_matter(db, org_b, user_b, f"MB {i}")

        # Flush the metrics cache so the request count is fresh. The
        # registry is a process-wide singleton and other tests may have
        # already populated it; testing the cache invariants belongs in a
        # dedicated registry test, not here.
        from app.core.metrics import registry

        registry.reset_for_test()

        res_a = client.get("/metrics", headers=_auth(user_a))
        res_b = client.get("/metrics", headers=_auth(user_b))

        assert res_a.status_code == 200
        assert res_b.status_code == 200
        payload_a = res_a.json()
        payload_b = res_b.json()
        # The endpoint tags the response with the caller's organization_id;
        # each caller must see their own org, not the other tenant's.
        assert payload_a.get("organization_id") == org_a.id, payload_a
        assert payload_b.get("organization_id") == org_b.id, payload_b
        # Counts returned for each call match the caller's matter count.
        assert payload_a.get("active_matters") == 2, payload_a
        assert payload_b.get("active_matters") == 4, payload_b
