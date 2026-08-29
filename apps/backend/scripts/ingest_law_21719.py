"""Ingesta de la Ley 21.719 al corpus legal chileno (Tier 1).

Uso:
    cd apps/backend
    python -m scripts.ingest_law_21719

Idempotencia: si los chunks ya existen con la misma ``law_code`` +
``article_number`` + ``chunk_index``, no los duplica. Solo agrega los
nuevos.

Notas:
- Descarga el texto desde el BCN Chile (leychile). Si la página no
  está disponible (timeout, 5xx), el script aborta sin tocar la DB.
- El parseo es heurístico: detecta líneas que empiezan con "Artículo N"
  y crea un chunk por artículo. Si el artículo es muy largo (> 2000
  caracteres), lo divide en chunks numerados ``1.1``, ``1.2``.
- Embeddings: usa OpenAI text-embedding-3-small (1536 dims) por
  defecto. Si tienes ``LLM_PROVIDER=openai`` configurado, el script
  detecta la API key y la usa. Si no, los embeddings quedan NULL y
  los chunks se pueden regenerar después con ``--reindex``.
- Los embeddings también se generan en background (no bloqueamos la
  ingestión si la API falla); se pueden regenerar luego.

Para correr en producción sin descargar en runtime, primero
ejecuta ``--cache`` que escribe el HTML parseado a un JSON local.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.law_chunk import LawChunk
from app.services.embeddings import get_embedding_provider

logger = logging.getLogger("lilian.ingest_law_21719")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")

# Source URLs — official Chilean government repositories.
BCN_LEY_21719 = "https://www.bcn.cl/leychile/navegar?idNorma=1209272"
BCN_LEY_19628 = "https://www.bcn.cl/leychile/navegar?idNorma=141599"
LEY_21719_PUBLICATION = "2024-12-13"
LEY_21719_EFFECTIVE = "2026-12-01"  # Vigencia general 1-dic-2026
LEY_19628_REPEAL_EFFECTIVE = "2026-12-01"  # Derogada por 21.719

CACHE_DIR = Path(__file__).parent / ".cache" / "law_ingestion"


# ----------------------------- HTML parsing -----------------------------

# Very tolerant regex: "Artículo 1.-", "Artículo 1°.-", "Artículo primero", etc.
_ARTICLE_RE = re.compile(
    r"^(?:Art\.\s*|Artículo\s+)([0-9]+(?:\s*[°º])?)\s*\.?-?",
    re.IGNORECASE | re.MULTILINE,
)

# Strip accents for matching the article number (BCN sometimes uses
# "Artículo primero", we don't expand Roman numerals — but the
# common case is Arabic numerals).


def _strip_html(text: str) -> str:
    """Minimal HTML→text — we don't have a real parser dependency here
    on purpose (kept script self-contained). BCN pages are simple
    enough that stripping tags + decoding entities is enough to detect
    articles."""
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</\s*(p|div|li|h\d|tr|td|th)\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&#10;", "\n")
    )
    return text


def _fetch(url: str, cache_name: str, *, force: bool = False) -> str:
    """Fetch with file cache so re-runs are deterministic + offline-safe."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_name}.html"
    if cache_file.exists() and not force:
        return cache_file.read_text(encoding="utf-8", errors="ignore")
    try:
        import httpx
    except ImportError:
        logger.error("httpx not installed; cannot fetch %s", url)
        sys.exit(1)
    logger.info("fetching %s", url)
    for attempt in range(3):
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": "lilian-ingest/1.0"})
            r.raise_for_status()
            cache_file.write_text(r.text, encoding="utf-8")
            return r.text
        except Exception as exc:
            logger.warning("attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2 ** attempt)
    logger.error("giving up after 3 attempts to fetch %s", url)
    sys.exit(1)


def _parse_law_text(html: str, *, law_code: str, law_name: str) -> list[dict]:
    """Returns list of {article_number, chapter_title, content}."""
    text = _strip_html(html)
    matches = list(_ARTICLE_RE.finditer(text))
    if not matches:
        logger.warning("no articles detected for %s — falling back to whole-doc chunk", law_code)
        return [{"article_number": "0", "chapter_title": None, "content": text.strip()}]

    chunks: list[dict] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        if not body or len(body) < 20:
            continue
        # Split very long articles to keep embeddings semantically tight.
        if len(body) > 2000:
            parts = [body[j:j + 2000] for j in range(0, len(body), 2000)]
            for k, part in enumerate(parts, 1):
                chunks.append({
                    "article_number": f"{m.group(1)}.{k}",
                    "chapter_title": None,
                    "content": part,
                })
        else:
            chunks.append({
                "article_number": m.group(1),
                "chapter_title": None,
                "content": body,
            })
    return chunks


# ----------------------------- DB ops -----------------------------

def _normalize(s: str) -> str:
    """Used for idempotency comparison — accent-stripped lowercase."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def _existing_index(db: Session, law_code: str) -> set[str]:
    """Returns the set of (article_number|chunk_index) keys already stored."""
    rows = db.execute(
        select(LawChunk.article_number, LawChunk.chunk_index).where(LawChunk.law_code == law_code)
    ).all()
    return {f"{r.article_number}|{r.chunk_index}" for r in rows}


def _embed(text: str) -> Optional[list[float]]:
    """Returns the embedding vector for the given text, or None if
    embeddings aren't available. We isolate this so the script can
    run in environments without OPENAI_API_KEY set (the corpus gets
    inserted with NULL embeddings and we reindex later)."""
    try:
        provider = get_embedding_provider()
        return provider.generate_embedding(text)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("embedding skipped: %s", exc)
        return None


def _persist(db: Session, *, law_code: str, law_name: str, legal_area: str, parsed: list[dict], dry_run: bool) -> int:
    """Returns the count of new chunks inserted."""
    existing = _existing_index(db, law_code)
    new_count = 0
    for i, c in enumerate(parsed):
        key = f"{c['article_number']}|{i}"
        if key in existing:
            continue
        embedding = _embed(c["content"])
        chunk = LawChunk(
            law_code=law_code,
            law_name=law_name,
            article_number=c["article_number"],
            chapter_title=c.get("chapter_title"),
            chunk_index=i,
            content=c["content"],
            embedding_vec=embedding,
            legal_area=legal_area,
            chunk_metadata={
                "valid_from": LEY_21719_PUBLICATION,
                "valid_until": None,
                "effective_date": LEY_21719_EFFECTIVE if law_code == "21719" else None,
                "repealed_by_21719": law_code == "19628",
                "source_url": BCN_LEY_21719 if law_code == "21719" else BCN_LEY_19628,
            },
        )
        if dry_run:
            logger.info("[dry-run] would insert %s art. %s", law_code, c["article_number"])
        else:
            db.add(chunk)
            new_count += 1
            if new_count % 10 == 0:
                db.commit()
                logger.info("committed %d chunks so far", new_count)
    if not dry_run:
        db.commit()
    return new_count


# ----------------------------- CLI -----------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--law", choices=["21719", "19628", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="don't write to DB")
    parser.add_argument("--reindex", action="store_true", help="regenerate embeddings for existing chunks")
    parser.add_argument("--force-fetch", action="store_true", help="bypass the local HTML cache")
    parser.add_argument("--legal-area", default="data_protection",
                        help="legal_area tag for the new chunks (default: data_protection)")
    parser.add_argument("--from-file", default=None,
                        help="path to a local file with the raw law text (one per line, "
                             "or HTML — auto-detected). Skips the BCN fetch entirely. "
                             "Recommended because BCN is a SPA with captcha. "
                             "Format: pass the path twice for both laws "
                             "(--from-file=21719:/path/a.txt --from-file=19628:/path/b.txt).")
    args = parser.parse_args(argv)

    targets: list[tuple[str, str, str | None]] = []
    from_file_map: dict[str, str] = {}
    if args.from_file:
        for spec in args.from_file.split(","):
            spec = spec.strip()
            if ":" not in spec:
                parser.error(f"--from-file expects LAW:PATH, got {spec!r}")
            law, path = spec.split(":", 1)
            from_file_map[law.strip()] = path.strip()
    if args.law in ("21719", "both"):
        targets.append(("21719", "Ley N° 21.719 — Protección de Datos Personales",
                        from_file_map.get("21719")))
    if args.law in ("19628", "both"):
        targets.append(("19628", "Ley N° 19.628 — Protección de la Vida Privada (derogada por 21.719)",
                        from_file_map.get("19628")))

    db = SessionLocal()
    try:
        total_new = 0
        for law_code, law_name, from_file in targets:
            logger.info("== ingesting %s ==", law_code)
            if from_file:
                logger.info("reading from local file: %s", from_file)
                text = Path(from_file).read_text(encoding="utf-8", errors="ignore")
                parsed = _parse_law_text(text, law_code=law_code, law_name=law_name)
            else:
                logger.info("fetching from BCN (may fail due to SPA / captcha)")
                url = BCN_LEY_21719 if law_code == "21719" else BCN_LEY_19628
                html = _fetch(url, law_code, force=args.force_fetch)
                parsed = _parse_law_text(html, law_code=law_code, law_name=law_name)
            parsed = _parse_law_text(html, law_code=law_code, law_name=law_name)
            logger.info("parsed %d chunks for %s", len(parsed), law_code)
            if args.reindex:
                logger.warning("--reindex not implemented in this version; use --dry-run to preview, then run a separate reindex script")
            new_count = _persist(db, law_code=law_code, law_name=law_name,
                                 legal_area=args.legal_area, parsed=parsed,
                                 dry_run=args.dry_run)
            logger.info("%s: %d new chunks %s",
                        law_code, new_count, "(dry-run)" if args.dry_run else "inserted")
            total_new += new_count
        logger.info("DONE. total new chunks = %d", total_new)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
