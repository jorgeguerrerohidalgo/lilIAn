"""Migration: add password reset fields to users (Phase 1b).

Adds two columns to the ``users`` table to support self-service password
recovery shipped in Phase 1b (plan: ``cosmic-roaming-wozniak``):
  - ``password_reset_token``: optional opaque token (``secrets.token_urlsafe(32)``).
    Generated on ``POST /auth/forgot-password``, consumed by
    ``POST /auth/reset-password`` when the user clicks the link in the
    recovery email. Cleared on success to prevent replay.
  - ``password_reset_expires_at``: optional ``TIMESTAMP`` marking the
    hard TTL (1 hour). Reset endpoints reject tokens past this.

Both columns are nullable so the change is additive — no existing row
needs backfill. Old users with NULL tokens simply have no pending reset.

Usage
-----
    python -m migrations.add_password_reset_fields

Safe to re-run: every ``ADD COLUMN IF NOT EXISTS`` is idempotent.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import SessionLocal, engine

logger = logging.getLogger(__name__)


def _add_columns() -> None:
    """Idempotent ALTER TABLE statements — both ``ADD COLUMN`` use
    Postgres 9.6+ ``IF NOT EXISTS`` so they are safe to re-run after
    the columns have already been added.
    """
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(128)"
        ))
        conn.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMP"
        ))
        # Index used by POST /auth/reset-password to look up the user
        # from the opaque token in O(log n).
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_users_password_reset_token "
            "ON users (password_reset_token)"
        ))
    logger.info("ALTER TABLE users (password_reset_*) OK")


def _print_summary() -> None:
    """Verify the columns actually exist by reading information_schema."""
    db = SessionLocal()
    try:
        cur = db.execute(text(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'users'
              AND column_name IN (
                'password_reset_token',
                'password_reset_expires_at'
              )
            ORDER BY column_name
            """
        ))
        rows = list(cur)
    finally:
        db.close()
    for row in rows:
        print(f"  {row[0]}: {row[1]} nullable={row[2]} default={row[3]}")
    if not rows:
        print("  (no rows matched — columns still missing?)")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print("[add_password_reset_fields] starting", flush=True)

    _add_columns()
    _print_summary()

    print("[add_password_reset_fields] done", flush=True)


if __name__ == "__main__":
    main()
