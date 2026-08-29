"""Migration: Ley 21.719 (Chile) compliance tables.

Creates the four tables backing ``app.models.consent``:

- ``consent_records``           — verifiable per-scope user consent.
- ``data_processing_activities``— ROPA (art. 17) per tenant.
- ``rights_requests``           — ARCO + portability + blocking (art. 27).
- ``breach_incidents``          — security incidents (art. 29).

Also extends ``users`` with the denormalised consent fields used by
the fast auth path (``consent_given_at``, ``terms_version``,
``privacy_version``, ``deletion_requested_at``, ``last_export_at``).

Idempotent — uses ``CREATE TABLE IF NOT EXISTS`` and ``ADD COLUMN IF
NOT EXISTS``. Safe to re-run.

Wired into ``main._run_startup_migrations()`` so it runs on every
container boot regardless of builder (Dockerfile, Nixpacks, Railpack).
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import SessionLocal, engine

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

CONSENT_RECORDS_SQL = """
CREATE TABLE IF NOT EXISTS consent_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    scope VARCHAR(32) NOT NULL,
    version VARCHAR(32) NOT NULL,
    granted_at TIMESTAMP NOT NULL DEFAULT now(),
    revoked_at TIMESTAMP,
    ip_address VARCHAR(64),
    user_agent VARCHAR(512),
    extra JSONB
);
"""

# Postgres needs a separate CREATE INDEX for indexes declared on a model
# table_args — SQLAlchemy's ``Index(...)`` doesn't auto-create them when
# the table already exists.
CONSENT_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_consent_records_user_id ON consent_records(user_id);",
    "CREATE INDEX IF NOT EXISTS ix_consent_user_scope ON consent_records(user_id, scope);",
    "CREATE INDEX IF NOT EXISTS ix_consent_user_scope_version ON consent_records(user_id, scope, version);",
]

DATA_PROCESSING_ACTIVITIES_SQL = """
CREATE TABLE IF NOT EXISTS data_processing_activities (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    purpose TEXT NOT NULL,
    legal_basis VARCHAR(64) NOT NULL,
    data_categories VARCHAR(64)[] NOT NULL DEFAULT '{}',
    data_subjects VARCHAR(64)[] NOT NULL DEFAULT '{}',
    retention_days INTEGER,
    recipients VARCHAR(128)[] NOT NULL DEFAULT '{}',
    involves_sensitive_data INTEGER NOT NULL DEFAULT 0,
    involves_automated_decisions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    extra JSONB
);
"""

DATA_PROCESSING_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_data_processing_activities_organization_id ON data_processing_activities(organization_id);",
]

RIGHTS_REQUESTS_SQL = """
CREATE TABLE IF NOT EXISTS rights_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMP NOT NULL DEFAULT now(),
    completed_at TIMESTAMP,
    rejection_reason TEXT,
    response_payload_url TEXT,
    ip_address VARCHAR(64),
    user_agent VARCHAR(512)
);
"""

RIGHTS_REQUESTS_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_rights_requests_user_id ON rights_requests(user_id);",
    "CREATE INDEX IF NOT EXISTS ix_rights_user_status ON rights_requests(user_id, status);",
    "CREATE INDEX IF NOT EXISTS ix_rights_status_requested ON rights_requests(status, requested_at);",
]

BREACH_INCIDENTS_SQL = """
CREATE TABLE IF NOT EXISTS breach_incidents (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),
    discovered_at TIMESTAMP NOT NULL DEFAULT now(),
    severity VARCHAR(16) NOT NULL DEFAULT 'medium',
    description TEXT NOT NULL,
    mitigation TEXT,
    affected_user_ids INTEGER[] NOT NULL DEFAULT '{}',
    reported_to_agency_at TIMESTAMP,
    reported_to_users_at TIMESTAMP,
    agency_reference VARCHAR(255),
    extra JSONB
);
"""

BREACH_INCIDENTS_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_breach_incidents_organization_id ON breach_incidents(organization_id);",
    "CREATE INDEX IF NOT EXISTS ix_breach_org_discovered ON breach_incidents(organization_id, discovered_at);",
]

# ---------------------------------------------------------------------------
# Users extension (denormalised consent fields)
# ---------------------------------------------------------------------------

USER_COLUMNS_SQL = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_given_at TIMESTAMP;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_version VARCHAR(32);",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_version VARCHAR(32);",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMP;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_export_at TIMESTAMP;",
]


def main() -> None:
    """Run the migration against the configured database."""
    log.info("Ley 21.719 migration: create compliance tables + extend users")

    with engine.begin() as conn:
        # 1. New tables — order matters because of FKs (consent_records
        #    and rights_requests point at users; data_processing_activities
        #    and breach_incidents point at organizations).
        for ddl in (
            CONSENT_RECORDS_SQL,
            DATA_PROCESSING_ACTIVITIES_SQL,
            RIGHTS_REQUESTS_SQL,
            BREACH_INCIDENTS_SQL,
        ):
            conn.execute(text(ddl))

        # 2. Indexes.
        for ddl in (
            *CONSENT_INDEXES_SQL,
            *DATA_PROCESSING_INDEXES_SQL,
            *RIGHTS_REQUESTS_INDEXES_SQL,
            *BREACH_INCIDENTS_INDEXES_SQL,
        ):
            conn.execute(text(ddl))

        # 3. Extend users with denormalised consent fields.
        for ddl in USER_COLUMNS_SQL:
            conn.execute(text(ddl))

    # Smoke check — open a session and count rows in each new table.
    session = SessionLocal()
    try:
        from app.models.consent import (
            BreachIncident,
            ConsentRecord,
            DataProcessingActivity,
            RightsRequest,
        )
        from app.models.user import User
        from sqlalchemy import inspect

        inspector = inspect(engine)
        for table in ("consent_records", "data_processing_activities", "rights_requests", "breach_incidents"):
            assert inspector.has_table(table), f"missing table: {table}"
        # Verify the new columns landed on users.
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        for col in ("consent_given_at", "terms_version", "privacy_version", "deletion_requested_at", "last_export_at"):
            assert col in user_cols, f"missing users.{col}"

        log.info(
            "Ley 21.719 migration: tables ready (consent=%d, ropa=%d, rights=%d, breach=%d)",
            session.query(ConsentRecord).count(),
            session.query(DataProcessingActivity).count(),
            session.query(RightsRequest).count(),
            session.query(BreachIncident).count(),
        )
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
