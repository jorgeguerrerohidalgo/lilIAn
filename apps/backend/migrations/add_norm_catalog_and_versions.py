"""Migration: norm_catalog + law_chunk_versions + norm_relations + extend law_chunks.

Fase 1 corpus legal — see docs/lilian-3.0.md §4.2 and
.cosmic-tickling-unicorn.md (plan). Creates:

- norm_catalog          — single source of truth for which Chilean norms
                            exist + their lifecycle status.
- law_chunk_versions    — versionado temporal: each row is one historical
                            snapshot of a norm's text.
- norm_relations        — grafo jurídico: directed edges between norms
                            (modifica / deroga / rectifica / etc.).
- New columns on law_chunks: jerarquia_path, parent_chunk_id, libro,
  titulo, capitulo, articulo, inciso, numeral, letra, norm_id,
  version_id.

All new columns are nullable=True so the migration doesn't break the
126 chunks already in the DB. The crawler backfills them on first
ingest.

Idempotent — uses CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT
EXISTS. Safe to re-run.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import SessionLocal, engine

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

NORM_CATALOG_SQL = """
CREATE TABLE IF NOT EXISTS norm_catalog (
    id SERIAL PRIMARY KEY,
    bcn_id VARCHAR(64) UNIQUE NOT NULL,
    tipo VARCHAR(32) NOT NULL,
    numero VARCHAR(32),
    titulo VARCHAR(500) NOT NULL,
    fecha_publicacion DATE,
    organismo_emisor VARCHAR(255),
    estado VARCHAR(64) NOT NULL DEFAULT 'vigente',
    url_bcn VARCHAR(500),
    legal_area VARCHAR(50),
    current_version_id INTEGER,
    modifies_norm_ids JSONB DEFAULT '[]'::jsonb,
    repealed_by_norm_id INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
"""

NORM_CATALOG_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_norm_catalog_bcn_id ON norm_catalog(bcn_id);",
    "CREATE INDEX IF NOT EXISTS ix_norm_catalog_tipo ON norm_catalog(tipo);",
    "CREATE INDEX IF NOT EXISTS ix_norm_catalog_numero ON norm_catalog(numero);",
    "CREATE INDEX IF NOT EXISTS ix_norm_catalog_legal_area ON norm_catalog(legal_area);",
]

LAW_CHUNK_VERSIONS_SQL = """
CREATE TABLE IF NOT EXISTS law_chunk_versions (
    id SERIAL PRIMARY KEY,
    norm_id INTEGER NOT NULL REFERENCES norm_catalog(id) ON DELETE CASCADE,
    version_label VARCHAR(128) NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    source_url VARCHAR(500),
    raw_source_hash VARCHAR(64),
    chunk_count INTEGER NOT NULL DEFAULT 0,
    extra JSONB DEFAULT '{}'::jsonb,
    imported_at TIMESTAMP NOT NULL DEFAULT now()
);
"""

LAW_CHUNK_VERSIONS_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_law_chunk_versions_norm_id ON law_chunk_versions(norm_id);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunk_versions_valid_from ON law_chunk_versions(valid_from);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunk_versions_valid_until ON law_chunk_versions(valid_until);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunk_versions_is_current ON law_chunk_versions(is_current);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunk_versions_raw_source_hash ON law_chunk_versions(raw_source_hash);",
]

NORM_RELATIONS_SQL = """
CREATE TABLE IF NOT EXISTS norm_relations (
    id SERIAL PRIMARY KEY,
    from_norm_id INTEGER NOT NULL REFERENCES norm_catalog(id) ON DELETE CASCADE,
    to_norm_id INTEGER NOT NULL REFERENCES norm_catalog(id) ON DELETE CASCADE,
    relation_type VARCHAR(32) NOT NULL,
    article_ref VARCHAR(64),
    source VARCHAR(64) NOT NULL DEFAULT 'bcn',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
"""

NORM_RELATIONS_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_norm_relations_from_norm_id ON norm_relations(from_norm_id);",
    "CREATE INDEX IF NOT EXISTS ix_norm_relations_to_norm_id ON norm_relations(to_norm_id);",
]

# ---------------------------------------------------------------------------
# law_chunks extensions (hierarchical + versioned)
# ---------------------------------------------------------------------------

LAW_CHUNKS_EXTEND_SQL = [
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS jerarquia_path VARCHAR(255);",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS parent_chunk_id INTEGER REFERENCES law_chunks(id) ON DELETE SET NULL;",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS libro VARCHAR(128);",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS titulo VARCHAR(128);",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS capitulo VARCHAR(128);",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS articulo VARCHAR(64);",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS inciso INTEGER;",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS numeral VARCHAR(16);",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS letra VARCHAR(8);",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS norm_id INTEGER REFERENCES norm_catalog(id) ON DELETE SET NULL;",
    "ALTER TABLE law_chunks ADD COLUMN IF NOT EXISTS version_id INTEGER REFERENCES law_chunk_versions(id) ON DELETE SET NULL;",
]

LAW_CHUNKS_EXTEND_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_law_chunks_libro ON law_chunks(libro);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunks_titulo ON law_chunks(titulo);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunks_capitulo ON law_chunks(capitulo);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunks_articulo ON law_chunks(articulo);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunks_norm_id ON law_chunks(norm_id);",
    "CREATE INDEX IF NOT EXISTS ix_law_chunks_version_id ON law_chunks(version_id);",
]

# ---------------------------------------------------------------------------
# Deferred FK: norm_catalog.current_version_id → law_chunk_versions.id
# We can't declare this in the CREATE TABLE because law_chunk_versions
# doesn't exist yet when norm_catalog is created. PostgreSQL is fine
# because of the IF NOT EXISTS guard, but we add the FK constraint
# separately after both tables exist.
# ---------------------------------------------------------------------------

NORM_CATALOG_FK_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'norm_catalog'
          AND constraint_name = 'norm_catalog_current_version_id_fkey'
    ) THEN
        ALTER TABLE norm_catalog
            ADD CONSTRAINT norm_catalog_current_version_id_fkey
            FOREIGN KEY (current_version_id)
            REFERENCES law_chunk_versions(id)
            ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END
$$;
"""

NORM_CATALOG_REPEALED_FK_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'norm_catalog'
          AND constraint_name = 'norm_catalog_repealed_by_norm_id_fkey'
    ) THEN
        ALTER TABLE norm_catalog
            ADD CONSTRAINT norm_catalog_repealed_by_norm_id_fkey
            FOREIGN KEY (repealed_by_norm_id)
            REFERENCES norm_catalog(id)
            ON DELETE SET NULL;
    END IF;
END
$$;
"""


def main() -> None:
    log.info("Fase 1 corpus legal migration: norm_catalog + versions + relations")
    with engine.begin() as conn:
        # 1. Tables in FK-safe order.
        for ddl in (NORM_CATALOG_SQL, LAW_CHUNK_VERSIONS_SQL, NORM_RELATIONS_SQL):
            conn.execute(text(ddl))

        # 2. Indexes.
        for ddl in (
            *NORM_CATALOG_INDEXES_SQL,
            *LAW_CHUNK_VERSIONS_INDEXES_SQL,
            *NORM_RELATIONS_INDEXES_SQL,
        ):
            conn.execute(text(ddl))

        # 3. Deferred FKs (current_version_id + repealed_by_norm_id on
        #    norm_catalog) — only meaningful on Postgres, guarded by
        #    DO $$ blocks so SQLite tests don't choke.
        for ddl in (NORM_CATALOG_FK_SQL, NORM_CATALOG_REPEALED_FK_SQL):
            conn.execute(text(ddl))

        # 4. Extend law_chunks with hierarchical + versioned columns.
        for ddl in LAW_CHUNKS_EXTEND_SQL:
            conn.execute(text(ddl))
        for ddl in LAW_CHUNKS_EXTEND_INDEXES_SQL:
            conn.execute(text(ddl))

    # Smoke check — open a session and assert tables / columns exist.
    session = SessionLocal()
    try:
        from sqlalchemy import inspect
        from app.models.norm_catalog import NormCatalog
        from app.models.law_chunk_version import LawChunkVersion
        from app.models.norm_relation import NormRelation, NormRelationType

        inspector = inspect(engine)
        for table in ("norm_catalog", "law_chunk_versions", "norm_relations"):
            assert inspector.has_table(table), f"missing table: {table}"
        # Verify the new columns landed on law_chunks.
        chunk_cols = {c["name"] for c in inspector.get_columns("law_chunks")}
        for col in (
            "jerarquia_path",
            "parent_chunk_id",
            "libro",
            "titulo",
            "capitulo",
            "articulo",
            "inciso",
            "numeral",
            "letra",
            "norm_id",
            "version_id",
        ):
            assert col in chunk_cols, f"missing law_chunks.{col}"

        log.info(
            "Fase 1 corpus legal migration: tables ready "
            "(norm_catalog=%d, law_chunk_versions=%d, norm_relations=%d)",
            session.query(NormCatalog).count(),
            session.query(LawChunkVersion).count(),
            session.query(NormRelation).count(),
        )
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
