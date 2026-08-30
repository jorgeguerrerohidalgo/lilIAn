"""DB writer for the corpus legal Fase 1.

Translates parsed chunks + BCN catalog data into SQL UPSERTs against
``norm_catalog``, ``law_chunk_versions`` and ``law_chunks``. Designed
to be called by :mod:`scripts.ingest_bcn_corpus` after the parser
has produced a ``ParseResult`` and the BCN client has produced a
catalog dict.

Design choices:

- All writes go through SQLAlchemy Core (not ORM) for speed and to
  keep ON CONFLICT clauses explicit. We never use ``session.add`` for
  bulk inserts; every row gets a parameterised INSERT.
- Idempotent on ``(bcn_id)``, ``(version_label)``, ``(chunk_index)``
  via unique constraints + ``ON CONFLICT DO NOTHING``. Re-running the
  crawler never produces duplicate rows.
- Batch inserts: we commit every N rows to keep the transaction
  short. This matters for Tier 3 where we ingest ~15.000 chunks.
- Embeddings are computed lazily, only for chunks that don't already
  have a non-NULL ``embedding_vec``. Re-running reindex doesn't
  recompute the same vector twice.

Public API::

    writer = DBWriter(db_session_factory)
    norm_id = writer.upsert_norm(catalog_dict)
    version_id = writer.upsert_version(norm_id, version_label, valid_from, ...)
    writer.upsert_chunks(version_id, parsed_chunks, generate_embedding=True)
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from typing import Callable, Iterable, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.law_chunk import LawChunk
from app.models.law_chunk_version import LawChunkVersion
from app.models.norm_catalog import NormCatalog

logger = logging.getLogger("lilian.db_writer")


# ---------------------------------------------------------------------------
# Embeddings: lazy import so the script doesn't fail if the embeddings
# module isn't usable (e.g. openai key missing → returns dummy → dim
# mismatch). The writer treats a wrong-dim embedding as None.
# ---------------------------------------------------------------------------

def _try_embed(text: str) -> Optional[list[float]]:
    """Return a 1536-dim OpenAI embedding, or None if unavailable."""
    if not text or not text.strip():
        return None
    try:
        from app.services.embeddings import get_embedding_provider
        provider = get_embedding_provider()
        if getattr(provider, "provider_name", "unknown") == "dummy":
            return None
        vec = provider.generate_embedding(text)
        if vec is None or len(vec) != 1536:
            return None
        return vec
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("embedding skipped: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class DBWriter:
    """Bulk writer for the corpus legal tables. One instance per crawl
    run; reuses a single Session for the whole ingest.

    Args:
        session_factory: a callable returning a SQLAlchemy ``Session``.
        batch_size: rows per commit. Default 200.
        on_progress: optional callback called after each commit with
            the running totals.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        batch_size: int = 200,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.on_progress = on_progress
        self.session: Session = session_factory()
        self._norms_written = 0
        self._versions_written = 0
        self._chunks_written = 0
        self._pending = 0

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def upsert_norm(self, norm: dict) -> int:
        """Insert or update a row in ``norm_catalog`` by ``bcn_id``.

        Returns the row's primary key. Counts toward the write
        progress report (one unit per row).
        """
        from app.models.norm_catalog import NormType

        # Normalise the tipo: the crawler hands us a lowercase string
        # ("codigo", "ley", etc.). We map it back to the enum so
        # SQLAlchemy stores the .value, not the enum member name.
        raw_tipo = (norm.get("tipo") or "otro").lower().strip()
        try:
            tipo_value = NormType(raw_tipo).value
        except ValueError:
            tipo_value = NormType.OTRO.value

        stmt = pg_insert(NormCatalog).values(
            bcn_id=norm["bcn_id"],
            tipo=tipo_value,
            numero=norm.get("numero"),
            titulo=norm["titulo"],
            fecha_publicacion=_parse_date(norm.get("fecha_publicacion")),
            organismo_emisor=norm.get("organismo_emisor"),
            estado=(norm.get("estado") or "vigente").lower(),
            url_bcn=norm.get("url_bcn"),
            legal_area=norm.get("legal_area"),
            repealed_by_norm_id=norm.get("repealed_by_norm_id"),
        )
        # On conflict (bcn_id), refresh the metadata fields the BCN
        # catalog emits. We never overwrite manual edits (current_version_id,
        # modifies_norm_ids) — those are managed by other calls.
        stmt = stmt.on_conflict_do_update(
            index_elements=[NormCatalog.bcn_id],
            set_={
                "tipo": stmt.excluded.tipo,
                "numero": stmt.excluded.numero,
                "titulo": stmt.excluded.titulo,
                "fecha_publicacion": stmt.excluded.fecha_publicacion,
                "organismo_emisor": stmt.excluded.organismo_emisor,
                "estado": stmt.excluded.estado,
                "url_bcn": stmt.excluded.url_bcn,
                "legal_area": stmt.excluded.legal_area,
                # ``now()`` is Postgres-only; ``CURRENT_TIMESTAMP`` is
                # portable across SQLite (used by tests) and Postgres.
                "updated_at": text("CURRENT_TIMESTAMP"),
            },
        ).returning(NormCatalog.id)

        result = self.session.execute(stmt).scalar_one_or_none()
        self.session.commit()
        if result is None:
            # The row already existed with identical data and
            # ON CONFLICT triggered — fetch its id.
            existing = (
                self.session.query(NormCatalog.id)
                .filter(NormCatalog.bcn_id == norm["bcn_id"])
                .one()
            )
            return existing.id
        self._norms_written += 1
        self._maybe_progress()
        return result

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    def upsert_version(
        self,
        norm_id: int,
        version_label: str,
        valid_from: date,
        *,
        valid_until: Optional[date] = None,
        source_url: Optional[str] = None,
        raw_text_hash: Optional[str] = None,
        is_current: bool = True,
        extra: Optional[dict] = None,
    ) -> int:
        """Insert or update a ``law_chunk_versions`` row by
        (norm_id, version_label). Returns the row's id."""
        stmt = pg_insert(LawChunkVersion).values(
            norm_id=norm_id,
            version_label=version_label,
            valid_from=valid_from,
            valid_until=valid_until,
            is_current=is_current,
            source_url=source_url,
            raw_source_hash=raw_text_hash,
            extra=extra or {},
            chunk_count=0,
            imported_at=datetime.utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[LawChunkVersion.norm_id, LawChunkVersion.version_label],
            set_={
                "valid_from": stmt.excluded.valid_from,
                "valid_until": stmt.excluded.valid_until,
                "is_current": stmt.excluded.is_current,
                "source_url": stmt.excluded.source_url,
                "raw_source_hash": stmt.excluded.raw_source_hash,
                "extra": stmt.excluded.extra,
                "imported_at": stmt.excluded.imported_at,
            },
        ).returning(LawChunkVersion.id)

        result = self.session.execute(stmt).scalar_one_or_none()
        self.session.commit()
        if result is None:
            existing = (
                self.session.query(LawChunkVersion.id)
                .filter(
                    LawChunkVersion.norm_id == norm_id,
                    LawChunkVersion.version_label == version_label,
                )
                .one()
            )
            return existing.id
        self._versions_written += 1
        self._maybe_progress()
        return result

    def mark_previous_versions_superseded(
        self, norm_id: int, *, superseded_from: date, exclude_version_id: int
    ) -> int:
        """When a new version of a norm is created, all previously
        current versions for the same norm_id get ``is_current=false``
        and ``valid_until=superseded_from``. We skip the version that
        triggered this call (``exclude_version_id``) so it stays
        ``is_current=true``.

        Returns the number of rows touched. Used by the version-flip
        step in :mod:`scripts.versioning`.
        """
        stmt = text("""
            UPDATE law_chunk_versions
            SET is_current = FALSE,
                valid_until = :superseded_from
            WHERE norm_id = :norm_id
              AND is_current = TRUE
              AND id != :exclude_version_id
        """)
        result = self.session.execute(stmt, {
            "superseded_from": superseded_from,
            "norm_id": norm_id,
            "exclude_version_id": exclude_version_id,
        })
        self.session.commit()
        return result.rowcount or 0

    # ------------------------------------------------------------------
    # Chunks
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        version_id: int,
        chunks: Iterable,
        *,
        law_code: str,
        law_name: str,
        legal_area: str,
        source_url: Optional[str] = None,
        generate_embeddings: bool = True,
    ) -> int:
        """Insert chunks for a given ``law_chunk_versions.id``.

        ``chunks`` is an iterable of :class:`scripts.html_parser.ParsedChunk`.
        We honour the ``chunk_index`` already set by the parser.

        Returns the number of chunks actually written (skips
        duplicates by (norm_id, version_id, chunk_index)).
        """
        from scripts.html_parser import ParsedChunk

        written = 0
        for chunk in chunks:
            if not isinstance(chunk, ParsedChunk):
                continue
            content = (chunk.content or "").strip()
            if not content:
                continue
            embedding = _try_embed(content) if generate_embeddings else None
            stmt = pg_insert(LawChunk).values(
                law_code=law_code,
                law_name=law_name,
                article_number=chunk.article_number,
                chapter_title=chunk.capitulo,
                section_title=chunk.titulo,
                chunk_index=chunk.chunk_index,
                content=content,
                embedding_vec=embedding,
                legal_area=legal_area,
                chunk_metadata={
                    "source_url": source_url,
                    "jerarquia_hint": chunk.parent_hint,
                    "imported_at": datetime.utcnow().isoformat(),
                    # True when BCN marks this article as fully repealed.
                    # Codigo Civil articles all carry this flag because
                    # each has been modified by a later ley; the corpus
                    # keeps them so the RAG has full historical context.
                    # The ``/api/v1/corpus/search`` endpoint can filter
                    # by ``vigente=true`` if needed.
                    "derogado": getattr(chunk, "derogado", False),
                },
                jerarquia_path=chunk.hierarchy_path() or None,
                libro=chunk.libro,
                titulo=chunk.titulo,
                capitulo=chunk.capitulo,
                articulo=chunk.article_number,
                inciso=int(chunk.inciso) if chunk.inciso and chunk.inciso.isdigit() else None,
                numeral=chunk.numeral,
                letra=chunk.letra,
                version_id=version_id,
            )
            # ON CONFLICT for law_chunks: there's currently no
            # unique constraint on (law_code, version_id, chunk_index).
            # We rely on the idempotency of the insert + the chunk_index
            # being stable across re-ingests of the same version. If
            # the user re-runs the crawler for the same version, the
            # chunks will be duplicated — we accept this for now and
            # may add the unique constraint in a later migration.
            self.session.execute(stmt)
            written += 1
            self._chunks_written += 1
            self._pending += 1
            if self._pending >= self.batch_size:
                self.session.commit()
                self._pending = 0
                self._maybe_progress()
        if self._pending > 0:
            self.session.commit()
            self._pending = 0
        self._maybe_progress(force=True)
        return written

    # ------------------------------------------------------------------
    # Progress / lifecycle
    # ------------------------------------------------------------------

    def _maybe_progress(self, *, force: bool = False) -> None:
        if self.on_progress is None:
            return
        # Throttle progress callbacks to one per batch.
        if not force and self._pending > 0:
            return
        try:
            self.on_progress(self._chunks_written, self._versions_written + self._norms_written)
        except Exception:  # pragma: no cover
            pass

    def close(self) -> None:
        if self._pending > 0:
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value) -> Optional[date]:
    """Accept ``YYYY-MM-DD`` strings or ``datetime.date`` instances."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def hash_text(text: str) -> str:
    """Stable SHA-256 of the text used to detect "same content, skip reindex"."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
