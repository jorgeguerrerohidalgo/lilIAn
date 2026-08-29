from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.core.database import Base


class LawChunk(Base):
    __tablename__ = "law_chunks"

    id = Column(Integer, primary_key=True, index=True)
    law_code = Column(String(100), nullable=False, index=True)
    law_name = Column(String(500), nullable=False)
    article_number = Column(String(50))
    chapter_title = Column(String(500))
    section_title = Column(String(500))
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    # pgvector column — ANN-searchable via the <=> operator with the
    # HNSW index ``ix_law_chunks_embedding_vec_hnsw``. Replaces the
    # earlier JSON-as-text ``embedding`` column (see migration 033).
    embedding_vec = Column(Vector(1536), nullable=True)
    legal_area = Column(String(50), nullable=False, index=True)
    chunk_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    # ---- Fase 1 corpus legal — jerarquía + versionado (idempotent) ----
    # All these columns are nullable=True so the migration doesn't
    # break the 126 chunks that already exist in the DB. The crawler
    # backfills them on first ingest.
    #
    # Human-readable hierarchical breadcrumb, only populated when the
    # parser detected an actual structure. Example:
    # "/Libro_I/Titulo_II/Capitulo_V" for Codigo Penal.
    jerarquia_path = Column(String(255), nullable=True)
    # FK to a parent chunk (eg. the chunk for "Articulo 1" is parent of
    # the chunks for "Articulo 1.1", "Articulo 1.2" etc.). Allows
    # walking up the tree in the UI when a small chunk doesn't give
    # enough context.
    parent_chunk_id = Column(
        Integer,
        ForeignKey("law_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Structured hierarchical fields. Indexed individually so the UI
    # can filter by any level without LIKE matching.
    libro = Column(String(128), nullable=True, index=True)
    titulo = Column(String(128), nullable=True, index=True)
    capitulo = Column(String(128), nullable=True, index=True)
    # ``articulo`` mirrors ``article_number`` but typed differently for
    # consistency with the other hierarchical fields.
    articulo = Column(String(64), nullable=True, index=True)
    inciso = Column(Integer, nullable=True)
    numeral = Column(String(16), nullable=True)
    letra = Column(String(8), nullable=True)
    # FK to the catalog so queries can join the norm metadata in a
    # single index hit.
    norm_id = Column(
        Integer,
        ForeignKey("norm_catalog.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # FK to the historical version of the norm this chunk belongs to.
    # Combined with norm_id lets us answer "¿qué decía este artículo
    # en X fecha?" with a single WHERE clause on the versions table.
    version_id = Column(
        Integer,
        ForeignKey("law_chunk_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
