"""Migration: widen law_chunks.article_number and law_chunks.articulo.

The Codigo Civil (idNorma 172986) has an article whose full name is
'7 (LEY SOBRE ABANDONO DE FAMILIA Y PAGO DE PENSIONES ALIMENTICIAS)'
— 67 characters. The previous schema declared both columns as
VARCHAR(50) (article_number) and VARCHAR(64) (articulo), so the
re-ingest of Tier 1 (fix_corpus_v4.sh) failed on this row with
``value too long for type character varying(64)``.

Long article names are semantically meaningful for the BCN parser
(e.g. they encode the parent law that an article consolidates), so
truncating in the parser would lose information. We widen both
columns to VARCHAR(255) — comfortably larger than the longest BCN
article name we've seen (~70 chars) and still indexed.

Idempotent — uses ALTER TABLE ... TYPE VARCHAR(255) which is a no-op
when the type already matches. Safe to re-run.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import SessionLocal, engine

log = logging.getLogger(__name__)


LAW_CHUNKS_WIDEN_ARTICLE_SQL = """
DO $$
BEGIN
    -- article_number: VARCHAR(50) -> VARCHAR(255)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'law_chunks'
          AND column_name = 'article_number'
          AND character_maximum_length < 255
    ) THEN
        ALTER TABLE law_chunks
            ALTER COLUMN article_number TYPE VARCHAR(255);
    END IF;

    -- articulo: VARCHAR(64) -> VARCHAR(255)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'law_chunks'
          AND column_name = 'articulo'
          AND character_maximum_length < 255
    ) THEN
        ALTER TABLE law_chunks
            ALTER COLUMN articulo TYPE VARCHAR(255);
    END IF;
END
$$;
"""


def main() -> None:
    log.info("widening law_chunks.article_number and law_chunks.articulo to VARCHAR(255)")

    with engine.begin() as conn:
        conn.execute(text(LAW_CHUNKS_WIDEN_ARTICLE_SQL))

    # Smoke check
    with engine.begin() as conn:
        rows = list(
            conn.execute(
                text(
                    """
                    SELECT column_name, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = 'law_chunks'
                      AND column_name IN ('article_number', 'articulo')
                    """
                )
            )
        )
        for name, length in rows:
            log.info("  law_chunks.%s = VARCHAR(%s)", name, length)
            if length < 255:
                raise RuntimeError(f"column {name} not widened: {length}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
