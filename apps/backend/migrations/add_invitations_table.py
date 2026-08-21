"""Migration: add ``invitations`` table for S6.3.

Creates the table backing ``app.models.invitation.Invitation`` so the
``POST /api/v1/organizations/me/invitations`` endpoint can persist pending
team-invite records.

Idempotent — uses ``CREATE TABLE IF NOT EXISTS``. Safe to re-run.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import SessionLocal, engine

log = logging.getLogger(__name__)

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS invitations (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    invited_by_user_id INTEGER NOT NULL REFERENCES users(id),
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'LAWYER',
    token VARCHAR(128) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    expires_at TIMESTAMP NOT NULL,
    accepted_at TIMESTAMP
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_invitations_organization_id ON invitations(organization_id);",
    "CREATE INDEX IF NOT EXISTS ix_invitations_email ON invitations(email);",
    "CREATE INDEX IF NOT EXISTS ix_invitations_token ON invitations(token);",
]


def main() -> None:
    """Run the migration against the configured database."""
    log.info("S6.3 migration: create invitations table")
    with engine.begin() as conn:
        conn.execute(text(CREATE_SQL))
        for stmt in INDEX_SQL:
            conn.execute(text(stmt))

    # Quick smoke check — open a session and count rows.
    session = SessionLocal()
    try:
        from app.models.invitation import Invitation

        count = session.query(Invitation).count()
        log.info("S6.3 migration: invitations table ready (existing rows=%d)", count)
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
