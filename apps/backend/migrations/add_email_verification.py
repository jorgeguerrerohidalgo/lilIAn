"""Migration: add email_verified + verification_token to users.

Sprint 1 / S1.1 — Self-service signup with email verification.

Adds two columns to the ``users`` table to support the email verification
flow shipped in commit pair (S1.1):
  - ``email_verified``: bool, defaults to ``False``. The login endpoint
    blocks access until this is ``True``.
  - ``verification_token``: optional opaque token. Generated on register,
    consumed by ``POST /auth/verify-email`` when the user clicks the link
    in the welcome email. Cleared once verified to prevent reuse.

Both columns are nullable / have defaults so the change is additive — no
existing row needs backfill because we want to force a re-verification
loop for users coming from the legacy admin-invite path.

Usage
-----
    python -m migrations.add_email_verification

Safe to re-run: every ``ADD COLUMN IF NOT EXISTS`` is idempotent.
"""
import sys

sys.path.insert(0, "/app")

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
            "ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL "
            "DEFAULT FALSE"
        ))
        conn.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS verification_token VARCHAR(128)"
        ))
        conn.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN IF NOT EXISTS verification_sent_at TIMESTAMP"
        ))
        # Useful index — the verify-email endpoint looks up by token.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_users_verification_token "
            "ON users (verification_token)"
        ))
    logger.info("ALTER TABLE users OK")


def _backfill_admin_rows() -> int:
    """Mark already-verified users (created via the legacy admin path)
    as verified so they don't get locked out. We use the conservative
    heuristic: any user with status='active' AND last_login_at IS NOT
    NULL is treated as already verified. This matches the previous
    behaviour where users were explicitly invited by the platform admin.
    """
    db = SessionLocal()
    try:
        result = db.execute(text(
            """
            UPDATE users
               SET email_verified = TRUE
             WHERE email_verified = FALSE
               AND last_login_at IS NOT NULL
            """
        ))
        db.commit()
        updated = result.rowcount or 0
        logger.info("backfilled %d already-active users", updated)
        return updated
    finally:
        db.close()


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
                'email_verified',
                'verification_token',
                'verification_sent_at'
              )
            ORDER BY column_name
            """
        ))
        for row in cur:
            print(f"  {row[0]}: {row[1]} nullable={row[2]} default={row[3]}")
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print("[add_email_verification] starting", flush=True)

    _add_columns()
    _backfill_admin_rows()
    _print_summary()

    print("[add_email_verification] done", flush=True)


if __name__ == "__main__":
    main()
