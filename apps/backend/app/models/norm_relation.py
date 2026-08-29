"""Relaciones entre normas chilenas (grafo jurídico mínimo viable).

Each row is a directed edge between two ``norm_catalog`` rows with a
relation type from ``NormRelationType``. This is the smallest possible
representation of the BCN knowledge graph that still delivers the
promised UX (e.g. "esta ley modifica el Código Civil art. X").

The authoritative source for these triples is the BCN Open Data
SPARQL endpoint (``bcnnorms:modifica``, ``bcnnorms:deroga``, etc.).
The crawler hydrates this table on Tier 1 (top 30 normas), Tier 2
(full 100 leyes), and Tier 3 (the full ~6.000 normas).

Why we keep a local copy of the graph (instead of querying SPARQL on
every request):

- SPARQL endpoint has 1 req/sec rate limits.
- The relations are stable over months — we only refresh on new versions.
- Local graph gives us millisecond reads vs 100ms+ network calls.
- We can denormalise into the ``norm_catalog`` row for the most-used
  relations, so the /dashboard detail page renders without joins.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class NormRelationType(str, enum.Enum):
    """Tipos de relación normativa según la ontología ``bcnnorms``.

    Mantener estable: cambiar valores rompe el grafo existente. Agregar
    nuevos tipos si BCN introduce nuevas relaciones.
    """

    MODIFICA = "modifica"
    DEROGA = "deroga"
    RECTIFICA = "rectifica"
    REFUNDE = "refunde"
    PRORROGA = "prorroga"
    REGLAMENTA = "reglamenta"
    INTERPRETA = "interpreta"


class NormRelation(Base):
    __tablename__ = "norm_relations"

    id = Column(Integer, primary_key=True, index=True)
    from_norm_id = Column(
        Integer,
        ForeignKey("norm_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_norm_id = Column(
        Integer,
        ForeignKey("norm_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type = Column(Enum(NormRelationType), nullable=False)
    # Optional reference to a specific article (ej. "art. 1545") when
    # the relation is scoped to a single article. Null = applies to the
    # whole norm.
    article_ref = Column(String(64), nullable=True)
    # Where did we learn about this relation?
    # - "bcn"     → SPARQL endpoint
    # - "manual"  → manually entered by ops
    # - "heuristic" → inferred by the crawler from version deltas
    source = Column(String(64), default="bcn", nullable=False)
    # 0..1, used when source="heuristic" to flag low-confidence edges
    # so the UI can render them with a different colour.
    confidence = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    from_norm = relationship("NormCatalog", foreign_keys=[from_norm_id])
    to_norm = relationship("NormCatalog", foreign_keys=[to_norm_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<NormRelation {self.from_norm_id} -{self.relation_type.value}-> {self.to_norm_id}>"
