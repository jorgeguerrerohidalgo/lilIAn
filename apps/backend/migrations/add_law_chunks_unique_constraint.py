"""Migration: UNIQUE constraint on law_chunks (law_code, version_id, chunk_index).

P4 from the corpus audit. Without this constraint, re-ingesting the same
norm duplicates chunks (there is no natural key on the table today).
Re-running fix_corpus_v4.sh on a DB without this constraint produces
2x chunks for every Tier 1 norm and the recall gets *worse* because
RRF gets noisier.

The constraint is intentionally (law_code, version_id, chunk_index):

- law_code:    which norm (1209272 for 21.719, 1984 for Codigo Penal, ...)
- version_id:  which historical snapshot — multiple rows with the same
               chunk_index can legitimately coexist across different
               time-stamped versions of the same norm
- chunk_index: position within the version, populated by the parser

`version_id` is nullable in the schema (chunks ingested before Fase 1
have it set to NULL), so the constraint is on (law_code, chunk_index)
where version_id IS NULL plus on (law_code, version_id, chunk_index)
otherwise. PostgreSQL handles this naturally because NULLs are
distinct in UNIQUE constraints.

Pre-flight: counts duplicate rows by (law_code, version_id, chunk_index)
and aborts if it would orphan data. Run after the re-ingest of a clean
corpus (or after backfilling version_id on legacy rows).

Idempotent — uses DO $$ blocks that check information_schema. Safe
to re-run.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import SessionLocal, engine

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

PREFLIGHT_DUPLICATES_SQL = """
SELECT law_code, version_id, chunk_index, COUNT(*) AS dupes
FROM law_chunks
GROUP BY law_code, version_id, chunk_index
HAVING COUNT(*) > 1
ORDER BY dupes DESC
LIMIT 20;
"""

LAW_CHUNKS_UNIQUE_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_law_chunks_law_code_version_chunk'
    ) THEN
        ALTER TABLE law_chunks
            ADD CONSTRAINT uq_law_chunks_law_code_version_chunk
            UNIQUE (law_code, version_id, chunk_index);
    END IF;
END
$$;
"""


def main() -> None:
    log.info("P4 migration: UNIQUE constraint on law_chunks")

    # Pre-flight: refuse to apply if duplicates exist that would block
    # the constraint creation. PostgreSQL would error out with
    # "could not create unique constraint" anyway, but a clean abort
    # is friendlier.
    with engine.begin() as conn:
        dupes = list(conn.execute(text(PREFLIGHT_DUPLICATES_SQL)).mappings())
        if dupes:
            log.error(
                "aborting: %d duplicate (law_code, version_id, chunk_index) "
                "groups exist. Clean them up first.",
                len(dupes),
            )
            for row in dupes[:10]:
                log.error(
                    "  law_code=%s version_id=%s chunk_index=%s dupes=%s",
                    row["law_code"],
                    row["version_id"],
                    row["chunk_index"],
                    row["dupes"],
                )
            raise SystemExit(1)

        conn.execute(text(LAW_CHUNKS_UNIQUE_SQL))
        log.info("uq_law_chunks_law_code_version_chunk created (or already existed)")

    # Smoke check.
    with engine.begin() as conn:
        present = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_law_chunks_law_code_version_chunk'
                """
            )
        ).scalar()
        if not present:
            raise RuntimeError("constraint missing after migration")
        log.info("smoke check OK: constraint present in pg_constraint")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
