"""Batched reindex for ``law_chunks.embedding_vec``.

Drops in for :mod:`scripts.reindex_chunks` when the corpus is large
(>5.000 NULL embeddings): the single-text path is rate-limited to
~1 chunk/sec, but OpenAI's batched endpoint accepts up to 2.048 inputs
per call and returns ~10x faster throughput in practice.

Behaviour:
- Reads all rows where ``embedding_vec IS NULL`` and chunks them
  into batches of ``--batch-size`` (default 100 — well under the
  2.048 OpenAI limit, leaving room for long texts).
- Calls ``OpenAIEmbedding.generate_embeddings(texts)`` once per batch.
- Writes the resulting vectors back via a single ``UPDATE ... FROM
  (VALUES ...)`` per batch (one round-trip per 100 chunks instead of
  per chunk).
- Resumable: re-running picks up only the remaining NULL rows.

Usage::

    cd apps/backend
    .venv_test/bin/python -m scripts.reindex_chunks_batched \\
        --batch-size 100 --sleep 0.1
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import SessionLocal

logger = logging.getLogger("lilian.reindex_chunks_batched")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")

    from app.services.embeddings import get_embedding_provider

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Chunks per OpenAI API call (max 2048)")
    parser.add_argument("--sleep", type=float, default=0.1,
                        help="Seconds to sleep between batches (rate-limit politeness)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stop after N total chunks (smoke test)")
    args = parser.parse_args(argv)

    provider = get_embedding_provider()
    if provider.provider_name == "dummy":
        logger.error(
            "refusing to reindex with the dummy provider — "
            "configure OPENAI_API_KEY / LLM_API_KEY with a real key first."
        )
        return 2

    session = SessionLocal()
    try:
        rows = session.execute(text(
            "SELECT id, content FROM law_chunks "
            "WHERE embedding_vec IS NULL "
            "ORDER BY id"
        )).all()
        if args.limit:
            rows = rows[: args.limit]

        total = len(rows)
        if total == 0:
            logger.info("nothing to do — all chunks already have embeddings")
            return 0
        logger.info("reindexing %d chunks (batch=%d, provider=%s)",
                    total, args.batch_size, provider.provider_name)

        updated = 0
        start = time.monotonic()
        # Process in fixed-size batches.
        for batch_start in range(0, total, args.batch_size):
            batch = rows[batch_start:batch_start + args.batch_size]
            ids = [r[0] for r in batch]
            texts = [(r[1] or "")[:8000] for r in batch]
            # Skip empty texts (would waste an API slot).
            non_empty_idx = [i for i, t in enumerate(texts) if t.strip()]
            if not non_empty_idx:
                continue
            try:
                vectors = provider.generate_embeddings([texts[i] for i in non_empty_idx])
            except Exception as exc:
                logger.warning("batch embedding failed at offset=%d: %s",
                               batch_start, exc)
                continue
            if len(vectors) != len(non_empty_idx):
                logger.warning("batch returned %d vectors for %d inputs (offset=%d) — skipping",
                               len(vectors), len(non_empty_idx), batch_start)
                continue
            # Build a single UPDATE … FROM (VALUES …) that writes every
            # vector in one round-trip. The pgvector literal is ``[v1,v2,...]``
            # which pgvector's ``::vector`` cast accepts.
            value_rows = []
            for j, idx in enumerate(non_empty_idx):
                vec_str = "[" + ",".join(f"{x:.7f}" for x in vectors[j]) + "]"
                value_rows.append(f"({ids[idx]}::bigint, '{vec_str}'::vector)")
            if not value_rows:
                continue
            update_sql = (
                "UPDATE law_chunks AS lc SET embedding_vec = v.vec "
                "FROM (VALUES " + ",".join(value_rows) + ") AS v(id, vec) "
                "WHERE lc.id = v.id"
            )
            session.execute(text(update_sql))
            session.commit()
            updated += len(value_rows)
            elapsed = time.monotonic() - start
            rate = updated / elapsed if elapsed > 0 else 0
            eta = (total - updated) / rate if rate > 0 else 0
            logger.info("progress %d/%d (%.1f chunks/sec, ETA %.0fs)",
                        updated, total, rate, eta)
            if args.sleep > 0:
                time.sleep(args.sleep)

        elapsed = time.monotonic() - start
        logger.info("done: %d/%d chunks updated in %.1fs (%.1f chunks/sec)",
                    updated, total, elapsed, updated / elapsed if elapsed else 0)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
