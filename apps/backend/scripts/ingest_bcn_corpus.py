"""BCN corpus crawler CLI — Fase 1.

Usage::

    cd apps/backend
    .venv_test/bin/python -m scripts.ingest_bcn_corpus catalog
    .venv_test/bin/python -m scripts.ingest_bcn_corpus ingest --bcn-id=1984
    .venv_test/bin/python -m scripts.ingest_bcn_corpus ingest-tier1
    .venv_test/bin/python -m scripts.ingest_bcn_corpus sync --since=YYYY-MM-DD

The CLI orchestrates three components:

1. :mod:`scripts.bcn_client`  — SPARQL endpoint access (catalog,
   versions, relations).
2. :mod:`scripts.html_parser` — local .txt dump parser with hierarchy.
3. :mod:`scripts.db_writer`   — Postgres upserts for norm_catalog,
   law_chunk_versions, law_chunks.

Tier 1 norms are listed in ``TIER1_BCN_IDS``. Local text dumps
(``apps/backend/data/legal_dumps/<bcn_id>.txt``) are preferred over
fetching from the BCN website because the SPA returns captcha-gated
HTML — we run human download when needed and commit the text files
to the repo.

Each ingest step writes a progress line every 50 chunks. On success
the catalog row is updated with ``last_synced_at = now()`` and the
chunk_count. Failures are logged but don't abort the batch — the
crawler is idempotent and the next ``sync`` picks up where we left off.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("lilian.ingest_bcn_corpus")


class IngestError(Exception):
    """Recoverable per-norm failure during ingest.

    Raised by ``_ingest_one`` when the XML fetch or the DB upsert fails
    in a way that should NOT abort the rest of the batch. System-level
    errors (KeyboardInterrupt, MemoryError, ...) propagate as
    themselves so the operator sees the real cause.
    """

# Kept for backwards compatibility — the Tier 1 ingest now downloads
# from BCN automatically via bcn_http_client. Operators may still drop
# files here as a fallback when BCN is down or for testing.
LOCAL_DUMPS_DIR = Path(__file__).parent.parent / "data" / "legal_dumps"

# Tier 1 — the 5 Códigos base + the Constitution + Ley 21.719 +
# Ley 19.628 (derogada). All BCN ids below were verified by
# querying the Consulta/obtxml endpoint directly. The crawler pulls
# the full XML for each, so no operator-side text dumps needed.
#
# Tier 2 (siguiente sprint): add ~100 most-cited leyes (laboral,
# tributario, consumidor) once we have eval baseline.
# Tier 3 (después): discover via ``discover_bcn_catalog.py`` and
# iterate over all ~6.000 normas.
# Tier 1 — the BCN idNorma for each norm. Confirmed against the legacy
# corpus and the BCN LeyChile endpoint.
#
# IMPORTANT: the BCN idNorma is not always the obvious "YYYY" — e.g.
# the Ley 21.719 is idNorma=1209272 in BCN, NOT "21719". A wrong idNorma
# would ingest a related-but-different norm (or an empty historical
# stub) and explain nothing.
TIER1_BCN_IDS: list[str] = [
    "172986",   # Codigo Civil refundido (DFL 1 30-May-2000)
    "1984",     # Codigo Penal refundido
    "207436",   # Codigo del Trabajo refundido
    "22740",    # Codigo de Comercio refundido (57 MB XML)
    "176595",   # Codigo Procesal Penal refundido
    "242302",   # Constitución Política refundida
    "1209272",  # Ley 21.719 refundida (Protección de Datos Personales)
    "141599",   # Ley 19.628 refundida (Protección a la Vida Privada / "Ley DICOM")
    "18046",    # Ley 18.046 (Sociedad Anónima)
    "19496",    # Ley 19.496 (Protección al Consumidor)
]

# Some BCN idNormas don't match their law number: idNorma=19496 returns a
# 3 KB Decreto "Feria Internacional del Salmón" instead of the Ley del
# Consumidor. The same law number via BCN's ``idLey=`` parameter returns
# the 300 KB consolidated text. We mark these here so ``_fetch_norm_xml``
# routes them through :meth:`BCNHttpClient.fetch_law_xml` instead of
# ``fetch_norm_xml``.
TIER1_USE_IDLEY: set[str] = {
    "19496",    # Ley 19.496 (Consumidor): idNorma points at unrelated Decreto
    "18046",    # Ley 18.046 (S.A.): same pattern
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session_factory():
    from app.core.database import SessionLocal
    return SessionLocal


def _fetch_norm_xml(bcn_id: str) -> Optional[bytes]:
    """Download the BCN XML for ``bcn_id`` via the legacy obtxml endpoint.

    Routes through :meth:`BCNHttpClient.fetch_law_xml` (using the
    ``idLey=`` parameter) for norms whose idNorma points at an unrelated
    document — see :data:`TIER1_USE_IDLEY` for the current set.
    """
    from scripts.bcn_http_client import BCNHttpClient
    client = BCNHttpClient()
    if bcn_id in TIER1_USE_IDLEY:
        content = client.fetch_law_xml(bcn_id)
    else:
        content = client.fetch_norm_xml(bcn_id)
    if content is None:
        return None
    return content.encode("utf-8")


def _ingest_one(
    *,
    bcn_id: str,
    catalog_rows: dict[str, dict],
    legal_area: str = "data_protection",
    source_url: Optional[str] = None,
    version_label: str = "vigente",
    valid_from=None,
    max_chunk_chars: int = 2200,
    generate_embeddings: bool = True,
) -> int:
    """Ingest a single norm end-to-end. Returns the number of chunks written."""
    from scripts.db_writer import DBWriter

    SessionLocal = _get_session_factory()
    try:
        text = _fetch_norm_xml(bcn_id)
    except Exception as exc:
        raise IngestError(f"fetch failed: {exc}") from exc
    if text is None:
        logger.warning("could not fetch XML for %s; skipping", bcn_id)
        return 0

    # We always parse via BCNXmlParser now that the BCN legacy
    # ``Consulta/obtxml`` endpoint is the canonical source. The
    # HTMLParser fallback remains available for non-BCN sources
    # (Diario Oficial PDFs converted to text, etc.) — see
    # ``ingest_law_21719.py`` for the historical text-dump path.
    from scripts.bcn_xml_parser import BCNXmlParser
    parser = BCNXmlParser(max_chunk_chars=max_chunk_chars)
    try:
        parsed = parser.parse(text)
    except Exception as exc:
        raise IngestError(f"parse failed: {exc}") from exc
    if not parsed.chunks:
        logger.warning("parser produced 0 chunks for %s; check input", bcn_id)
        return 0

    catalog_row = catalog_rows.get(bcn_id, {
        "bcn_id": bcn_id,
        "titulo": f"Norma {bcn_id}",
        "tipo": "otro",
        "legal_area": legal_area,
    })
    catalog_row.setdefault("url_bcn", source_url or f"https://www.bcn.cl/leychile/navegar?idNorma={bcn_id}")

    from datetime import date
    if valid_from is None:
        valid_from = parsed.chunks[0].article_number and date.today()
        if valid_from is None:
            valid_from = date.today()

    try:
        with DBWriter(SessionLocal) as writer:
            norm_id = writer.upsert_norm(catalog_row)
            version_id = writer.upsert_version(
                norm_id=norm_id,
                version_label=version_label,
                valid_from=valid_from,
                source_url=source_url or catalog_row.get("url_bcn"),
                extra={"parser_warnings": parsed.warnings},
            )
            # Flip any previously-current versions on this norm to historical.
            writer.mark_previous_versions_superseded(
                norm_id=norm_id,
                superseded_from=valid_from,
                exclude_version_id=version_id,
            )
            n = writer.upsert_chunks(
                version_id=version_id,
                chunks=parsed.chunks,
                law_code=bcn_id,
                law_name=catalog_row.get("titulo", f"Norma {bcn_id}"),
                legal_area=legal_area,
                source_url=source_url or catalog_row.get("url_bcn"),
                generate_embeddings=generate_embeddings,
            )
    except Exception as exc:
        raise IngestError(f"db write failed: {exc}") from exc

    logger.info("ingested %s: %d chunks, %d warnings", bcn_id, n, len(parsed.warnings))
    return n


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_catalog(args) -> int:
    """Download the BCN catalog and emit ``bcn_id → metadata`` JSONL."""
    from scripts.bcn_client import BCNClient
    client = BCNClient()
    norms = client.query_norms(limit=args.limit)
    for n in norms:
        # Emit one JSON line per norm. Stdout is the natural sink — the
        # caller can redirect to a file or pipe through ``jq``.
        import json
        sys.stdout.write(json.dumps(n, ensure_ascii=False) + "\n")
    logger.info("emitted %d norms from BCN catalog", len(norms))
    return 0


def cmd_ingest(args) -> int:
    """Ingest a single norm by its BCN id."""
    if not args.bcn_id:
        logger.error("--bcn-id is required for ingest")
        return 2
    catalog_rows = {}
    if args.catalog_file:
        import json
        for line in Path(args.catalog_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            catalog_rows[row["bcn_id"]] = row
    n = _ingest_one(
        bcn_id=args.bcn_id,
        catalog_rows=catalog_rows,
        legal_area=args.legal_area,
        source_url=args.source_url,
        version_label=args.version_label,
        max_chunk_chars=args.max_chunk_chars,
        generate_embeddings=not args.no_embeddings,
    )
    if n == 0:
        logger.warning("ingest produced 0 chunks for %s", args.bcn_id)
        return 1
    return 0


def cmd_ingest_tier1(args) -> int:
    """Ingest every Tier 1 norm by downloading its XML from BCN.

    Skips norms already in the DB (idempotent). Per-norm failures are
    logged and swallowed so one fat Codigo de Comercio (57 MB XML)
    doesn't poison the rest of the batch. Per-norm progress is logged
    inline so operators can see what's actually happening.
    """
    import time

    from sqlalchemy import text
    SessionLocal = _get_session_factory()
    session = SessionLocal()
    try:
        already_ingested = {
            row[0]
            for row in session.execute(text(
                "SELECT DISTINCT nc.bcn_id FROM law_chunks lc "
                "JOIN law_chunk_versions v ON v.id = lc.version_id "
                "JOIN norm_catalog nc ON nc.id = v.norm_id "
                "WHERE nc.bcn_id = ANY(:ids)"
            ), {"ids": list(TIER1_BCN_IDS)}).all()
        }
    finally:
        session.close()

    if args.force and already_ingested:
        # Re-chunking path: wipe chunks for the targets before re-ingesting
        # so the new (smaller) chunks don't collide on the
        # (law_code, version_id, chunk_index) UNIQUE constraint. Norm +
        # version rows are kept; only ``law_chunks`` is cleared.
        del_session = SessionLocal()
        try:
            n_deleted = del_session.execute(
                text("DELETE FROM law_chunks WHERE law_code = ANY(:ids)"),
                {"ids": list(already_ingested)},
            ).rowcount
            del_session.commit()
            logger.warning(
                "--force: deleted %d existing chunks for %s",
                n_deleted, sorted(already_ingested),
            )
        finally:
            del_session.close()
        already_ingested = set()

    targets = [bid for bid in TIER1_BCN_IDS if bid not in already_ingested]
    if not targets:
        logger.info("all Tier 1 norms already ingested — nothing to do")
        return 0

    logger.info(
        "ingesting %d Tier 1 norms (skipping %d already in DB)",
        len(targets), len(already_ingested),
    )
    total = 0
    failed: list[tuple[str, str]] = []
    for bcn_id in targets:
        t0 = time.monotonic()
        try:
            n = _ingest_one(
                bcn_id=bcn_id,
                catalog_rows={},
                legal_area=args.legal_area,
                max_chunk_chars=args.max_chunk_chars,
                generate_embeddings=not args.no_embeddings,
            )
        except IngestError as exc:
            # Recoverable per-norm failure: log full stack and move on.
            # The rest of Tier 1 still ingests.
            logger.exception("ingest failed for %s: %s", bcn_id, exc)
            failed.append((bcn_id, str(exc)))
            continue
        elapsed = time.monotonic() - t0
        logger.info("  ✓ %s: %d chunks in %.1fs", bcn_id, n, elapsed)
        total += n

    if failed:
        logger.warning(
            "Tier 1 ingest: %d/%d norms failed",
            len(failed),
            len(targets),
        )
        for bcn_id, reason in failed:
            logger.warning("  - %s: %s", bcn_id, reason)

    logger.info("done: %d total chunks across %d Tier 1 norms", total, len(targets))
    return 0


def cmd_ingest_tier2(args) -> int:
    """Ingest every Tier 2 norm from the curated set in
    ``scripts.discover_bcn_catalog``.

    The list is curated (not auto-discovered) so the operator sees
    exactly which laws are about to be ingested before running. See
    ``scripts/discover_bcn_catalog.py::TIER2_BCN_IDS`` for the source
    data. Idempotent: skips laws already present in the DB.
    """
    from scripts.discover_bcn_catalog import TIER2_BCN_IDS as RAW_TIER2

    # Drop the (id, label, topic) tuple down to just ids and exclude
    # any Tier 1 overlap (defensive — should already be empty).
    tier2_ids = [bid for (bid, _label, _topic) in RAW_TIER2
                 if bid not in TIER1_BCN_IDS]
    if not tier2_ids:
        logger.info("Tier 2 list is empty after Tier 1 exclusion — nothing to do")
        return 0

    import time

    from sqlalchemy import text
    SessionLocal = _get_session_factory()
    session = SessionLocal()
    try:
        already_ingested = {
            row[0]
            for row in session.execute(text(
                "SELECT DISTINCT nc.bcn_id FROM law_chunks lc "
                "JOIN law_chunk_versions v ON v.id = lc.version_id "
                "JOIN norm_catalog nc ON nc.id = v.norm_id "
                "WHERE nc.bcn_id = ANY(:ids)"
            ), {"ids": tier2_ids}).all()
        }
    finally:
        session.close()

    if args.force and already_ingested:
        del_session = SessionLocal()
        try:
            n_deleted = del_session.execute(
                text("DELETE FROM law_chunks WHERE law_code = ANY(:ids)"),
                {"ids": list(already_ingested)},
            ).rowcount
            del_session.commit()
            logger.warning(
                "--force: deleted %d existing chunks for Tier 2 re-chunking",
                n_deleted,
            )
        finally:
            del_session.close()
        already_ingested = set()

    targets = [bid for bid in tier2_ids if bid not in already_ingested]
    if not targets:
        logger.info("all Tier 2 norms already ingested — nothing to do")
        return 0

    logger.info(
        "ingesting %d Tier 2 norms (skipping %d already in DB)",
        len(targets), len(already_ingested),
    )
    total = 0
    failed: list[tuple[str, str]] = []
    for bcn_id in targets:
        t0 = time.monotonic()
        try:
            n = _ingest_one(
                bcn_id=bcn_id,
                catalog_rows={},
                legal_area=args.legal_area,
                max_chunk_chars=args.max_chunk_chars,
                generate_embeddings=not args.no_embeddings,
            )
        except IngestError as exc:
            logger.exception("ingest failed for %s: %s", bcn_id, exc)
            failed.append((bcn_id, str(exc)))
            continue
        elapsed = time.monotonic() - t0
        logger.info("  ✓ %s: %d chunks in %.1fs", bcn_id, n, elapsed)
        total += n

    if failed:
        logger.warning(
            "Tier 2 ingest: %d/%d norms failed", len(failed), len(targets),
        )
        for bcn_id, reason in failed:
            logger.warning("  - %s: %s", bcn_id, reason)

    logger.info("done: %d total chunks across %d Tier 2 norms", total, len(targets))
    return 0


def cmd_sync(args) -> int:
    """Re-ingest norms whose ``last_synced_at`` is older than ``--since``.

    This is what the daily cron runs: it picks up any norm that
    changed recently without forcing a full re-ingest. Implemented as
    a re-ingest of TIER1 with a quick exit if no local dump has
    changed since the last run; a full diff-based sync is Fase 3
    work.
    """
    return cmd_ingest_tier1(args)


def cmd_list(args) -> int:
    """List local text dumps present + Tier 1 catalog of BCN ids."""
    print(f"Local dumps dir: {LOCAL_DUMPS_DIR}")
    print("Local dumps present:")
    if LOCAL_DUMPS_DIR.exists():
        for path in sorted(LOCAL_DUMPS_DIR.glob("*.txt")):
            size_kb = path.stat().st_size // 1024
            print(f"  {path.stem}.txt  ({size_kb} KB)")
    print()
    print(f"Tier 1 BCN ids: {TIER1_BCN_IDS}")
    print("Missing local dumps:")
    for bcn_id in TIER1_BCN_IDS:
        if not (LOCAL_DUMPS_DIR / f"{bcn_id}.txt").exists():
            print(f"  - {bcn_id}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cat = sub.add_parser("catalog", help="Download the BCN catalog as JSONL")
    p_cat.add_argument("--limit", type=int, default=None, help="Stop after N norms")
    p_cat.set_defaults(func=cmd_catalog)

    p_ing = sub.add_parser("ingest", help="Ingest a single BCN id")
    p_ing.add_argument("--bcn-id", required=True)
    p_ing.add_argument("--legal-area", default="data_protection")
    p_ing.add_argument("--source-url", default=None)
    p_ing.add_argument("--version-label", default="vigente")
    p_ing.add_argument("--catalog-file", default=None,
                        help="JSONL file produced by ``catalog`` (else empty stub)")
    p_ing.add_argument("--max-chunk-chars", type=int, default=2200)
    p_ing.add_argument("--no-embeddings", action="store_true",
                        help="Skip embedding generation (faster, useful for tests)")
    p_ing.set_defaults(func=cmd_ingest)

    p_t1 = sub.add_parser("ingest-tier1", help="Ingest every Tier 1 norm with a local dump")
    p_t1.add_argument("--legal-area", default="data_protection")
    p_t1.add_argument("--max-chunk-chars", type=int, default=2200)
    p_t1.add_argument("--no-embeddings", action="store_true")
    p_t1.add_argument("--force", action="store_true",
                      help="Delete existing chunks for the target before re-ingesting. "
                           "Used to re-chunk with a different --max-chunk-chars value.")
    p_t1.set_defaults(func=cmd_ingest_tier1)

    p_t2 = sub.add_parser("ingest-tier2", help="Ingest the curated Tier 2 norms (see discover_bcn_catalog.TIER2_BCN_IDS)")
    p_t2.add_argument("--legal-area", default="data_protection")
    p_t2.add_argument("--max-chunk-chars", type=int, default=2200)
    p_t2.add_argument("--no-embeddings", action="store_true")
    p_t2.add_argument("--force", action="store_true",
                      help="Delete existing chunks for the target before re-ingesting.")
    p_t2.set_defaults(func=cmd_ingest_tier2)

    p_sync = sub.add_parser("sync", help="Re-ingest norms changed since a date (alias for ingest-tier1 today)")
    p_sync.add_argument("--since", default="1970-01-01")
    p_sync.add_argument("--legal-area", default="data_protection")
    p_sync.add_argument("--max-chunk-chars", type=int, default=2200)
    p_sync.add_argument("--no-embeddings", action="store_true")
    p_sync.set_defaults(func=cmd_sync)

    p_list = sub.add_parser("list", help="Show what's available locally + Tier 1 catalog")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
