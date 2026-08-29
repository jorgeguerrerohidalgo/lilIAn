"""Versionado temporal de chunks legales (Ley 21.719-friendly).

Each row in ``law_chunk_versions`` is one historical snapshot of a
norm's text. The current snapshot for each ``norm_id`` has
``is_current=true`` and ``valid_until=NULL``. When the BCN publishes a
new version of a norm, the crawler:

1. Creates a new ``LawChunkVersion`` with ``is_current=true`` and
   ``valid_from=<publication_date>``.
2. Flips the previous current version to ``is_current=false`` and
   stamps ``valid_until=<new_publication_date>``.
3. Inserts the new chunks tagged with the new version_id.

A RAG query with ``as_of=2024-06-01`` filters to chunks whose
``valid_from <= as_of`` AND (``valid_until IS NULL`` OR
``valid_until > as_of``) AND ``is_current=true`` (at that point in
time). That lets us answer "¿qué establecía este artículo en X fecha?"
correctly even after a refundición deroga the old text.

Why a separate versions table (vs adding valid_from/until to law_chunks):

- Per-norm lifecycle events are atomic — a single new version can
  flip tens of chunks without updating each one.
- Validating "this snapshot was the law at date X" is a join on a
  small (versions) table, not a scan of all chunks.
- Historical chunks remain queryable for legal/discovery reasons even
  after the version is no longer current.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON as JSONType

from app.core.database import Base


class LawChunkVersion(Base):
    __tablename__ = "law_chunk_versions"

    id = Column(Integer, primary_key=True, index=True)
    norm_id = Column(
        Integer,
        ForeignKey("norm_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Human-readable label: "Versión vigente", "Ley 21.719 refundida",
    # "Texto original 1999". Used in UI and audit logs.
    version_label = Column(String(128), nullable=False)
    # The first day this version is/was in force. Required.
    valid_from = Column(Date, nullable=False, index=True)
    # The first day this version stopped being in force, or NULL if it
    # is the current version. The crawler flips NULL → publication_date
    # of the new version when a new snapshot arrives.
    valid_until = Column(Date, nullable=True, index=True)
    # True if this is the currently-active version. Maintained by the
    # versioning module — exactly one row per norm_id should have this.
    is_current = Column(Boolean, default=True, nullable=False, index=True)
    # URL where this version was sourced from (typically the BCN page
    # for that specific historical version).
    source_url = Column(String(500), nullable=True)
    # sha256 of the raw HTML/AKN downloaded for this version. Used by
    # the crawler to detect "same content as last time, skip the
    # reindex". Cheap to compute, immune to whitespace drift.
    raw_source_hash = Column(String(64), nullable=True, index=True)
    # Live counter so the dashboard can show "Código Civil vigente
    # tiene 2.596 chunks en 3 libros" without a join.
    chunk_count = Column(Integer, default=0)
    # Free-form metadata: {"deroga_a": "ley 19.628", "source_format":
    # "akoma-ntoso", "refundida_por": "21.719"}. Drives the grafo de
    # relaciones table ingestion.
    extra = Column(JSONType, default=dict)
    imported_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    norm = relationship(
        "NormCatalog",
        back_populates="versions",
        foreign_keys=[norm_id],
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<LawChunkVersion norm={self.norm_id} {self.version_label} {self.valid_from}→{self.valid_until or 'current'}>"
