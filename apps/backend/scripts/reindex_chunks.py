"""Reindex embeddings for law_chunks rows with NULL embedding_vec.

Idempotent: only updates rows where ``embedding_vec IS NULL``. Designed
to run after the embeddings provider config is fixed (real OpenAI key,
1536-dim output) so legacy NULL chunks get real vectors.

Usage::

    cd apps/backend
    .venv_test/bin/python -m scripts.reindex_chunks [--batch=100] [--sleep=0.1]

Emits progress every 50 chunks and a final summary. Exits non-zero if
the embeddings provider is the dummy (i.e. the operator forgot to
configure a real key) — fail loud so we don't burn 30 minutes for
nothing.

Estimated runtime: ~5-10 minutes for ~8.000 chunks (3 chunks/sec
with rate limiting + retry). Cost: ~$0.10 USD at OpenAI's
text-embedding-3-small pricing.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

logger = logging.getLogger("lilian.reindex_chunks")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")

    from app.core.database import SessionLocal
    from app.services.embeddings import get_embedding_provider
    from app.models.law_chunk import LawChunk
    from sqlalchemy import text

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", type=int, default=50, help="Commit every N chunks")
    parser.add_argument("--sleep", type=float, default=0.05,
                        help="Seconds to sleep between API calls (rate-limit politeness)")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N chunks (smoke test)")
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
        # Pull the IDs + content first so we don't hold a long-running
        # query while we make API calls. The chunk count is small
        # enough (~8k) that loading all rows in memory is fine.
        rows = session.execute(text(
            "SELECT id, content FROM law_chunks "
            "WHERE embedding_vec IS NULL "
            "ORDER BY id"
        )).all()
        if args.limit:
            rows = rows[: args.limit]

        total = len(rows)
        logger.info("reindexing %d chunks (provider=%s, batch=%d)",
                    total, provider.provider_name, args.batch)

        if total == 0:
            logger.info("nothing to do — all chunks already have embeddings")
            return 0

        updated = 0
        start = time.monotonic()
        for chunk_id, content in rows:
            text_to_embed = (content or "")[:8000]
            if not text_to_embed.strip():
                continue
            try:
                vec = provider.generate_embedding(text_to_embed)
            except Exception as exc:
                logger.warning("embedding failed for chunk %d: %s", chunk_id, exc)
                continue

            if vec is None or len(vec) != 1536:
                logger.warning("chunk %d produced %s-dim vector, skipping", chunk_id,
                               len(vec) if vec else 0)
                continue

            # Direct UPDATE — avoids loading the row into the ORM session.
            session.execute(
                text("UPDATE law_chunks SET embedding_vec = CAST(:v AS vector) WHERE id = :id"),
                {"v": vec, "id": chunk_id},
            )
            updated += 1

            if updated % args.batch == 0:
                session.commit()
                elapsed = time.monotonic() - start
                rate = updated / elapsed if elapsed > 0 else 0
                eta = (total - updated) / rate if rate > 0 else 0
                logger.info("progress %d/%d (%.1f chunks/sec, ETA %.0fs)",
                            updated, total, rate, eta)

            if args.sleep > 0:
                time.sleep(args.sleep)

        session.commit()
        elapsed = time.monotonic() - start
        logger.info("done: %d/%d chunks updated in %.1fs (%.1f chunks/sec)",
                    updated, total, elapsed, updated / elapsed if elapsed else 0)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
