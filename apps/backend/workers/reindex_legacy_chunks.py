"""Reindex legacy 512-dim document_chunks to 1536-dim pgvector.

The 034 migration skipped chunks whose stored ``embedding`` JSON had
512 dims — pgvector's vector(1536) column can't hold them. This
script walks the 192 legacy rows in batches, generates fresh
1536-dim embeddings via OpenAI, and stores them in
``embedding_vec``. Idempotent — rows that already have a vector are
left alone.

Run:
    DATABASE_URL=... \\
    LLM_API_KEY=sk-... \\
    EMBEDDING_PROVIDER=openai \\
    python -m workers.reindex_legacy_chunks

The script uses the venv's Python directly so it picks up the
``pgvector.sqlalchemy.Vector`` type registered with the same
SQLAlchemy version the runtime uses.
"""
from __future__ import annotations

import logging
import os
import sys
import time

sys.path.insert(0, "/app")

from sqlalchemy import select, text, update

from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.services.embeddings import get_embedding_provider

logger = logging.getLogger("lilian.reindex_legacy")


SHORT_PAD_THRESHOLD = 2000
BATCH_SIZE = 50
SLEEP_BETWEEN_BATCHES = 2.0  # seconds; stay under OpenAI tier-1 rate limit


def _pad_for_1536(text: str) -> str:
    if len(text) >= SHORT_PAD_THRESHOLD:
        return text
    return text + " " * (SHORT_PAD_THRESHOLD - len(text))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    provider = get_embedding_provider()

    db = SessionLocal()
    try:
        # Pull the IDs that need migration; we re-read each batch's
        # content fresh so the loop is safe to interrupt and resume.
        pending_ids = db.execute(
            select(DocumentChunk.id)
            .where(DocumentChunk.embedding_vec.is_(None))
            .order_by(DocumentChunk.id)
        ).scalars().all()
        total = len(pending_ids)
        logger.info("[reindex] %d legacy chunks need 1536-dim embeddings", total)

        if total == 0:
            logger.info("[reindex] nothing to do")
            return

        done = 0
        for batch_start in range(0, total, BATCH_SIZE):
            batch_ids = pending_ids[batch_start:batch_start + BATCH_SIZE]
            rows = db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.id.in_(batch_ids))
            ).scalars().all()
            texts = [_pad_for_1536(r.content) for r in rows]
            try:
                embeddings = provider.generate_embeddings(texts)
            except Exception as exc:
                logger.error("[reindex] batch %d failed: %s", batch_start, exc)
                continue
            for chunk, vec in zip(rows, embeddings):
                chunk.embedding_vec = vec
            db.commit()
            done += len(rows)
            logger.info(
                "[reindex] %d / %d done (batch_start=%d)",
                done, total, batch_start,
            )
            if batch_start + BATCH_SIZE < total:
                time.sleep(SLEEP_BETWEEN_BATCHES)

        logger.info("[reindex] complete: %d chunks migrated to 1536-dim", done)
    finally:
        db.close()


if __name__ == "__main__":
    main()
