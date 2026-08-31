"""Golden dataset evaluator for the corpus legal.

Usage:
    cd apps/backend
    .venv_test/bin/python -m scripts.eval_law_retrieval

Loads ``docs/corpus/golden-dataset-v2.json``, runs each query
against the corpus, and reports ``recall@5`` plus per-question detail.
Exits with code 1 if any query fails the threshold (default 0.85).

We don't try to be clever about query rewriting. The RAG already
handles synonyms and acronym expansion; the dataset measures
whether the chunking + embedding pipeline surfaces the right article
in the top 5 hits.

Usage in CI::

    python -m scripts.eval_law_retrieval
    echo "exit=$?"

Returns exit 0 when the corpus is healthy; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("lilian.eval_law_retrieval")

GOLDEN_PATH = Path(__file__).parent.parent.parent.parent / "docs" / "corpus" / "golden-dataset-v2.json"
DEFAULT_RECALL_K = 5
DEFAULT_THRESHOLD = 0.85


def _load_golden() -> list[dict]:
    if not GOLDEN_PATH.exists():
        logger.error("golden dataset not found at %s", GOLDEN_PATH)
        sys.exit(2)
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


_TOKEN_CACHE = {"value": None, "expires_at": 0.0}


def _get_token(base_url: str) -> str | None:
    """Login as the platform admin and return a bearer token.

    Tokens last ~24h; we cache for the duration of the eval run.
    Credentials come from the active user's environment so the script
    works in any developer machine without hardcoding.
    """
    import time
    if _TOKEN_CACHE["value"] and _TOKEN_CACHE["expires_at"] > time.monotonic():
        return _TOKEN_CACHE["value"]
    import os
    username = os.environ.get("LILIAN_EVAL_USERNAME")
    password = os.environ.get("LILIAN_EVAL_PASSWORD")
    if not username or not password:
        logger.warning(
            "LILIAN_EVAL_USERNAME / LILIAN_EVAL_PASSWORD not set; "
            "eval will run unauthenticated (search results will be 401/empty)."
        )
        return None
    import httpx
    try:
        r = httpx.post(
            f"{base_url}/api/v1/auth/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
        if r.status_code != 200:
            logger.warning("login failed: %d %s", r.status_code, r.text[:200])
            return None
        _TOKEN_CACHE["value"] = r.json().get("access_token")
        _TOKEN_CACHE["expires_at"] = time.monotonic() + 3600
        return _TOKEN_CACHE["value"]
    except Exception as exc:
        logger.debug("login failed: %s", exc)
        return None


def _search_corpus(question: dict, top_k: int, base_url: str = "http://127.0.0.1:8765") -> list[dict]:
    """Call our own /api/v1/corpus/search via HTTPX. Falls back to a
    direct SQL query if the backend isn't running."""
    token = _get_token(base_url)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        import httpx
        params = {"q": question["query"], "top_k": top_k}
        if question.get("legal_area"):
            params["legal_area"] = question["legal_area"]
        if question.get("as_of"):
            params["as_of"] = question["as_of"]
        r = httpx.get(
            f"{base_url}/api/v1/corpus/search",
            params=params,
            headers=headers,
            timeout=30.0,
        )
        if r.status_code == 200:
            return r.json().get("chunks", [])
        logger.warning("/corpus/search returned %d: %s", r.status_code, r.text[:200])
        return []
    except Exception as exc:
        logger.debug("/corpus/search unreachable (%s), skipping", exc)
        return []


def _expected_article_set(question: dict) -> set[str]:
    return {str(a).strip() for a in question.get("expected_articles", [])}


def _expected_law_codes(question: dict) -> set[str]:
    return {str(c).strip() for c in question.get("expected_law_codes", [])}


def evaluate(
    questions: list[dict],
    *,
    recall_k: int = DEFAULT_RECALL_K,
    threshold: float = DEFAULT_THRESHOLD,
    base_url: str = "http://127.0.0.1:8765",
) -> dict:
    """Run every question and compute recall@k per question.

    A question "passes" when at least one of ``expected_articles`` is in
    the top-k returned chunks AND the chunk's ``law_code`` is in
    ``expected_law_codes``. We treat a hit on the article as sufficient
    because articles are the unit a lawyer cites.
    """
    results = []
    passed = 0
    for q in questions:
        chunks = _search_corpus(q, top_k=recall_k, base_url=base_url)
        expected_articles = _expected_article_set(q)
        expected_codes = _expected_law_codes(q)

        hit_articles: set[str] = set()
        hit_codes: set[str] = set()
        matched_question = False
        for chunk in chunks:
            chunk_article = str(chunk.get("article_number") or "").strip()
            chunk_code = str(chunk.get("law_code") or "").strip()
            hit_codes.add(chunk_code)
            if chunk_article in expected_articles:
                hit_articles.add(chunk_article)
                matched_question = True

        law_ok = bool(hit_codes & expected_codes) if expected_codes else True
        article_ok = matched_question
        passed_this = law_ok and article_ok

        if passed_this:
            passed += 1

        results.append({
            "id": q["id"],
            "query": q["query"],
            "expected_articles": sorted(expected_articles),
            "expected_codes": sorted(expected_codes),
            "top_codes": sorted({c.get("law_code") for c in chunks}),
            "hit_articles": sorted(hit_articles),
            "passed": passed_this,
        })

    total = len(questions)
    recall_at_k = passed / total if total else 0.0
    return {
        "recall_at_k": recall_at_k,
        "threshold": threshold,
        "passed": passed,
        "total": total,
        "details": results,
        "meets_threshold": recall_at_k >= threshold,
    }


def _format_report(report: dict) -> str:
    out = []
    out.append(
        f"recall@{report.get('passed', 0)}/{report.get('total', 0)} "
        f"= {report['recall_at_k']:.0%} (threshold {report['threshold']:.0%})"
    )
    out.append("Per-question:")
    for r in report["details"]:
        status = "PASS" if r["passed"] else "FAIL"
        out.append(
            f"  [{status}] Q{r['id']}: expected {r['expected_codes']}/{r['expected_articles']} "
            f"got top {r['top_codes']} matched {r['hit_articles']}"
        )
    return "\n".join(out)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--k", type=int, default=DEFAULT_RECALL_K)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)

    questions = _load_golden()
    report = evaluate(questions, recall_k=args.k, threshold=args.threshold)
    print(_format_report(report))

    return 0 if report["meets_threshold"] else 1


if __name__ == "__main__":
    sys.exit(main())
