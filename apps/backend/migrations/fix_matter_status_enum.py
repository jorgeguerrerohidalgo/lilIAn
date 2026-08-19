"""One-shot migration: fix MatterStatus enum + repair bad rows.

Background
----------
The analysis pipeline (``app/services/analysis.py``) was writing
arbitrary error strings into ``matters.status`` with an ``"error:"``
prefix. Because the column is typed as ``Enum(MatterStatus)`` and
``MatterStatus`` never had a member covering those prefixes, any
read of the row raised ``LookupError`` and crashed the whole request,
which the unhandled-exception path turned into a 500. The 500 also
broke the SQLAlchemy session and pulled unrelated endpoints down
with it.

What this migration does
------------------------
1. Idempotently add the ``failed`` value to the ``matterstatus``
   PostgreSQL enum type so the new ``MatterStatus.FAILED`` member is
   accepted.
2. Coerce every existing row whose ``status`` starts with ``"error:"``
   into ``status='failed'`` so the database stops raising LookupErrors
   on the next read. The lost error detail is recoverable from the
   application logs (the analysis pipeline logged the full traceback
   via ``logger.exception`` before calling
   ``_set_matter_error_status``).
3. Idempotently add the ``last_error`` text column to capture future
   failure messages without breaking the enum.

Usage
-----
    python -m migrations.fix_matter_status_enum

Safe to run repeatedly. Each statement is wrapped in ``IF NOT EXISTS``
where Postgres supports it, and the data UPDATE is idempotent because
the ``LIKE 'error:%'`` predicate stops matching once the rows are
healed.
"""
import sys

sys.path.insert(0, "/app")

import logging

from sqlalchemy import text

from app.core.database import SessionLocal, engine

logger = logging.getLogger(__name__)


def _add_enum_value() -> None:
    """``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block,
    so we execute it against the raw DBAPI connection with
    ``AUTOCOMMIT`` isolation. Idempotent thanks to ``IF NOT EXISTS``.
    """
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(
            "ALTER TYPE matterstatus ADD VALUE IF NOT EXISTS 'failed'"
        ))
        logger.info("ALTER TYPE matterstatus ADD VALUE 'failed' OK")


def _ensure_last_error_column() -> None:
    """Add the ``last_error`` text column if it doesn't exist.

    We use ``ADD COLUMN IF NOT EXISTS`` (Postgres 9.6+) so the script is
    safe to re-run after the column has been added.
    """
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE matters ADD COLUMN IF NOT EXISTS last_error TEXT"
        ))
        logger.info("ALTER TABLE matters ADD COLUMN last_error OK")


def _heal_corrupt_status_rows() -> int:
    """Re-encode any rows whose ``status`` starts with ``"error:"`` so the
    enum validation stops raising ``LookupError``. Returns the number of
    rows updated.
    """
    db = SessionLocal()
    try:
        result = db.execute(text(
            """
            UPDATE matters
               SET status = 'failed',
                   last_error = SUBSTR(status, 7)
             WHERE status LIKE 'error:%'
               AND last_error IS NULL
            """
        ))
        db.commit()
        updated = result.rowcount or 0
        logger.info("healed %d corrupt matter rows", updated)
        return updated
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print("[fix_matter_status_enum] starting", flush=True)

    _add_enum_value()
    _ensure_last_error_column()
    healed = _heal_corrupt_status_rows()

    print(f"[fix_matter_status_enum] done — healed {healed} rows", flush=True)


if __name__ == "__main__":
    main()
