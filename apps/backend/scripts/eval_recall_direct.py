"""SQL-direct recall eval for the corpus legal.

Bypasses the FastAPI /corpus/search endpoint (which needs a JWT and
gets rate-limited at 10 logins/minute) and calls the same RAG
functions directly. Produces the same per-question breakdown as
``scripts.eval_law_retrieval`` so the numbers are comparable to the
baseline 45% (9/20) from 2026-09-01.

Usage::

    cd apps/backend
    .venv_test/bin/python -m scripts.eval_recall_direct [--k=20] [--data=docs/corpus/golden-dataset-v2.json]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.embeddings import get_embedding_provider
from app.services.rag import (
    search_laws_by_embedding,
    search_laws_by_keyword,
)

logger = logging.getLogger("lilian.eval_recall_direct")


def _expected_article_set(q: dict) -> set[str]:
    return {str(a).strip() for a in q.get("expected_articles", [])}


def _expected_law_codes(q: dict) -> set[str]:
    return {str(c).strip() for c in q.get("expected_law_codes", [])}


def _chunk_law_codes(chunk: dict) -> set[str]:
    """Map a chunk dict returned by rag.search_laws_by_* to the set of
    law_codes it could count as a hit for. Some Tier 1 questions
    expected both idNorma (``1209272``) and idLey (``21719``) for the
    same refundida, so we expose both via the corpus row."""
    codes = set()
    raw = chunk.get("law_code") or chunk.get("law_codes") or []
    if isinstance(raw, str):
        codes.add(raw)
    elif isinstance(raw, list):
        codes.update(str(c) for c in raw)
    return {c for c in codes if c}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--data", type=str,
                        default="docs/corpus/golden-dataset-v2.json",
                        help="Path to the golden JSON list of questions")
    args = parser.parse_args(argv)

    provider = get_embedding_provider()
    if provider.provider_name == "dummy":
        logger.error("refusing to evaluate with dummy embedding provider")
        return 2

    # Resolve data path relative to project root.
    data_path = Path(args.data)
    if not data_path.exists():
        data_path = Path("/home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian") / args.data
    with open(data_path) as f:
        questions = json.load(f)
    logger.info("loaded %d questions from %s", len(questions), data_path)

    # Pre-compute embeddings once (OpenAI call per query).
    embeddings: dict[int, list[float]] = {}
    t0 = time.monotonic()
    for q in questions:
        embeddings[q["id"]] = provider.generate_embedding(q["query"])
    elapsed = time.monotonic() - t0
    logger.info("embedded %d queries in %.1fs", len(questions), elapsed)

    # Run per-question search + scoring.
    results = []
    passed = 0
    for q in questions:
        try:
            emb_hits = search_laws_by_embedding(
                embeddings[q["id"]],
                top_k=args.k * 3,
                legal_area=q.get("legal_area") or q.get("category"),
                query_text=q["query"],
                as_of=q.get("as_of"),
                similarity_threshold=-0.4,
            )
        except Exception as exc:
            logger.warning("embedding search failed for Q%d: %s", q["id"], exc)
            emb_hits = []
        try:
            kw_hits = search_laws_by_keyword(
                q["query"],
                top_k=args.k * 3,
                legal_area=q.get("legal_area") or q.get("category"),
                as_of=q.get("as_of"),
            )
        except Exception as exc:
            logger.warning("keyword search failed for Q%d: %s", q["id"], exc)
            kw_hits = []

        # Replicate the RRF merge from app/api/endpoints/corpus.py.
        RRF_K = 60
        merged: dict[int, dict] = {}
        for rank, r in enumerate(emb_hits, 1):
            cid = r["chunk_id"]
            merged[cid] = {
                **r,
                "rrf_score": 1.0 / (RRF_K + rank),
                "embedding_rank": rank,
                "keyword_rank": None,
                "source": "embedding",
            }
        for rank, r in enumerate(kw_hits, 1):
            cid = r["chunk_id"]
            if cid in merged:
                merged[cid]["rrf_score"] += 1.0 / (RRF_K + rank)
                merged[cid]["keyword_rank"] = rank
                merged[cid]["source"] = "both"
            else:
                merged[cid] = {
                    **r,
                    "rrf_score": 1.0 / (RRF_K + rank),
                    "embedding_rank": None,
                    "keyword_rank": rank,
                    "source": "keyword",
                }
        ranked = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)[: args.k]

        # Compute recall: at least one expected article in top-k AND
        # its law_code is one of the expected law_codes. Mirrors the
        # eval_law_retrieval threshold (article hit on a correct law).
        expected_articles = _expected_article_set(q)
        expected_codes = _expected_law_codes(q)
        hit_articles: set[str] = set()
        hit_codes: set[str] = set()
        for r in ranked:
            art = str(r.get("article_number") or "").strip()
            for lc in _chunk_law_codes(r):
                hit_codes.add(lc)
            if art:
                hit_articles.add(art)
        article_hit = bool(expected_articles & hit_articles)
        law_hit = bool(expected_codes & hit_codes)
        ok = article_hit and law_hit
        passed += int(ok)
        results.append({
            "id": q["id"],
            "ok": ok,
            "expected_articles": sorted(expected_articles),
            "expected_codes": sorted(expected_codes),
            "got_articles": sorted(hit_articles & expected_articles) if ok else [],
            "top_codes": sorted(hit_codes)[:10],
        })

    total = len(questions)
    print(f"\nrecall@{args.k}/{total} = {passed}/{total} ({100*passed/total:.0f}%)")
    print(f"\nPer-question:")
    for r in results:
        marker = "PASS" if r["ok"] else "FAIL"
        print(f"  [{marker}] Q{r['id']}: expected {r['expected_codes']}/{r['expected_articles']} "
              f"got top {r['top_codes']} matched {r['got_articles']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
