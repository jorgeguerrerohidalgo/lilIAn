"""Chilean legal norm catalog (BCN Open Data).

The ``norm_catalog`` table is the single source of truth for *which*
laws exist in our corpus and *what state* each one is in. It is
populated by the BCN crawler (``scripts/bcn_client.py`` +
``ingest_bcn_corpus.py``) and drives the versionado temporal of the
chunks in ``law_chunks``: every chunk has a ``version_id`` pointing to a
``LawChunkVersion`` row that belongs to a specific historical snapshot
of the norm identified here.

Why a separate catalog table (instead of stuffing metadata into the
chunks themselves):

- A norm can have hundreds of chunks but a single canonical identity.
- Lifecycle events (deroga, refundición, rectificación) happen at the
  norm level, not the chunk level.
- The /precedents search UI needs to filter by ``tipo_norma`` /
  ``legal_area`` without joining across thousands of chunk rows.
- The relaciones table can FK to a single ID per norm without exploding
  the index cardinality.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON as JSONType

from app.core.database import Base


class NormType(str, enum.Enum):
    """Tipo de norma jurídica según la clasificación del BCN.

    Mantener estable: cambiar el valor de un enum existente rompe el
    catálogo. Agregar nuevos tipos si la BCN incorpora categorías nuevas.
    """

    CODIGO = "codigo"               # Código Civil, Penal, del Trabajo, etc.
    LEY = "ley"                     # Ley simple (ej. Ley 21.719)
    DECRETO = "decreto"             # Decreto Supremo / Decreto Ley
    DFL = "dfl"                     # Decreto con Fuerza de Ley
    DL = "dl"                       # Decreto Ley (histórico, pre-1973)
    CONSTITUCION = "constitucion"   # Constitución Política
    TRATADO = "tratado"             # Tratados internacionales
    REGLAMENTO = "reglamento"       # Reglamentos
    ORDENANZA = "ordenanza"         # Ordenanzas municipales
    OTRO = "otro"


class NormCatalog(Base):
    __tablename__ = "norm_catalog"

    id = Column(Integer, primary_key=True, index=True)
    # BCN identifier (URI slug) — what BCN uses to refer to this norm.
    # Examples: "1984" (Codigo Penal), "1209272" (Ley 21.719).
    bcn_id = Column(String(64), unique=True, index=True, nullable=False)
    # ``values_callable`` makes SQLAlchemy persist the enum's .value
    # ("codigo", "ley") instead of the Python member name
    # ("CODIGO", "LEY"). The crawler and the catalog store lowercase
    # strings; the enum is for type-safety only.
    tipo = Column(
        Enum(NormType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    # For leyes/decretos: "21.719". For codigos: typically empty.
    numero = Column(String(32), nullable=True, index=True)
    titulo = Column(String(500), nullable=False)
    # Fecha de publicación original en el Diario Oficial.
    fecha_publicacion = Column(Date, nullable=True)
    organismo_emisor = Column(String(255), nullable=True)
    estado = Column(
        String(64),
        default="vigente",
        nullable=False,
    )  # vigente | derogada | parcialmente_derogada
    url_bcn = Column(String(500), nullable=True)
    legal_area = Column(String(50), index=True)  # matches law_chunks.legal_area
    # The currently-active version (one row in law_chunk_versions).
    # FK to LawChunkVersion — set after we ingest at least one version.
    current_version_id = Column(
        Integer,
        ForeignKey("law_chunk_versions.id", use_alter=True, ondelete="SET NULL"),
        nullable=True,
    )
    # Cache of relations (denormalised for fast pre-filtering). The
    # authoritative source is norm_relations; this is refreshed whenever
    # the crawler ingests new relations. We use JSON (not a join) because
    # the typical UI query is "what modifies this norm" — a single row
    # read is enough.
    modifies_norm_ids = Column(JSONType, default=list)
    repealed_by_norm_id = Column(
        Integer,
        ForeignKey("norm_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Live counters for the dashboard.
    chunk_count = Column(Integer, default=0)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    versions = relationship(
        "LawChunkVersion",
        back_populates="norm",
        foreign_keys="LawChunkVersion.norm_id",
    )
    current_version = relationship(
        "LawChunkVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<NormCatalog {self.bcn_id} {self.tipo.value} #{self.numero or '?'} {self.titulo[:40]!r}>"
