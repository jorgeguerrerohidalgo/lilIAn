"""Migration: add Stripe columns to subscriptions + organizations.

Sprint 2 / S2.01 — Stripe self-service checkout.

Adds the Stripe linkage columns that ``app/services/stripe_client.py``
and the webhook handler rely on:

  ``organizations``:
    - ``stripe_customer_id``: persisted after the first Checkout so we
      can open the Billing Portal without hitting Stripe on every page.

  ``subscriptions``:
    - ``stripe_customer_id``    — same value as above, denormalised.
    - ``stripe_subscription_id`` — ``sub_…`` for the active subscription.
    - ``stripe_status``          — current Stripe status (active, past_due,
                                    canceled, etc.).
    - ``cancel_at_period_end``   — surfaced on the billing page.
    - ``trial_ends_at``          — to schedule the trial-expiring email.
    - ``updated_at``             — used for change-detection on the row.

All columns are nullable or have defaults so this is a pure additive
change and no existing row needs a backfill.

Usage
-----
    python -m migrations.add_stripe_columns

Safe to re-run: every ``ADD COLUMN`` uses Postgres 9.6+ ``IF NOT EXISTS``
and every index uses ``CREATE INDEX IF NOT EXISTS``.
"""
import sys

sys.path.insert(0, "/app")

import logging

from sqlalchemy import text

from app.core.database import engine

logger = logging.getLogger(__name__)


def _add_columns() -> None:
    """Idempotent ALTER TABLE statements."""
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE organizations "
            "ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_organizations_stripe_customer_id "
            "ON organizations (stripe_customer_id)"
        ))

        conn.execute(text(
            "ALTER TABLE subscriptions "
            "ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_subscriptions_stripe_customer_id "
            "ON subscriptions (stripe_customer_id)"
        ))
        conn.execute(text(
            "ALTER TABLE subscriptions "
            "ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_subscriptions_stripe_subscription_id "
            "ON subscriptions (stripe_subscription_id)"
        ))
        conn.execute(text(
            "ALTER TABLE subscriptions "
            "ADD COLUMN IF NOT EXISTS stripe_status VARCHAR(50)"
        ))
        conn.execute(text(
            "ALTER TABLE subscriptions "
            "ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN "
            "NOT NULL DEFAULT FALSE"
        ))
        conn.execute(text(
            "ALTER TABLE subscriptions "
            "ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE subscriptions "
            "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"
        ))
    logger.info("ALTER TABLE OK (organizations + subscriptions)")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print("[add_stripe_columns] starting", flush=True)
    _add_columns()
    print("[add_stripe_columns] done", flush=True)


if __name__ == "__main__":
    main()
