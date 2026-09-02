"""Verify the state of the corpus after a re-chunking or ingest.

Reports per-law chunk counts + chunk-size distribution + number of
chunks with embeddings. Use after running ``ingest_bcn_corpus
ingest-tier1/2 --max-chunk-chars=N --force`` to confirm the re-chunking
landed correctly.

Usage::

    cd apps/backend
    .venv_test/bin/python -m scripts.verify_corpus_chunks
    .venv_test/bin/python -m scripts.verify_corpus_chunks --law 172986
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import SessionLocal

logger = logging.getLogger("lilian.verify_corpus_chunks")


def _print_distribution(session, law_codes: list[str]) -> None:
    rows = session.execute(
        text("""
            SELECT
                law_code,
                COUNT(*)                            AS total,
                COUNT(embedding_vec)                AS with_emb,
                MIN(LENGTH(content))                AS min_len,
                (AVG(LENGTH(content)))::int         AS avg_len,
                MAX(LENGTH(content))                AS max_len,
                COUNT(*) FILTER (WHERE LENGTH(content) <= 800) AS under_800,
                COUNT(*) FILTER (WHERE LENGTH(content) > 800)  AS over_800
            FROM law_chunks
            WHERE law_code = ANY(:ids)
            GROUP BY law_code
            ORDER BY law_code
        """),
        {"ids": law_codes},
    ).all()
    if not rows:
        print("no chunks found for the given law_codes")
        return
    print(
        f"{'law_code':<10s} {'total':>6s} {'with_emb':>9s} "
        f"{'min':>6s} {'avg':>6s} {'max':>6s} "
        f"{'<=800':>6s} {'>800':>6s}"
    )
    for r in rows:
        print(
            f"{r.law_code:<10s} {r.total:>6d} {r.with_emb:>9d} "
            f"{r.min_len:>6d} {r.avg_len:>6d} {r.max_len:>6d} "
            f"{r.under_800:>6d} {r.over_800:>6d}"
        )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
    from scripts.ingest_bcn_corpus import TIER1_BCN_IDS

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--law", action="append", default=None,
        help="Filter to a specific law_code (can repeat). Default: Tier 1 only.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show every law_code in the corpus, not just Tier 1.",
    )
    args = parser.parse_args(argv)

    if args.law:
        laws = args.law
    elif args.all:
        session = SessionLocal()
        try:
            rows = session.execute(
                text("SELECT DISTINCT law_code FROM law_chunks ORDER BY law_code")
            ).all()
            laws = [r[0] for r in rows]
        finally:
            session.close()
    else:
        laws = list(TIER1_BCN_IDS)

    session = SessionLocal()
    try:
        _print_distribution(session, laws)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
