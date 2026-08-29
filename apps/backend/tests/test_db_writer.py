"""Tests for the corpus DBWriter.

We use SQLite-in-memory via the same harness as test_auth so the
DB layer exercises the same ON CONFLICT semantics the prod Postgres
uses. ``versioning`` is exercised separately.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Force-load the corpus models so they register against Base.metadata
# before ``create_all`` runs. Without this import the test DB sees
# zero tables and the inserts blow up with "no such table: norm_catalog".
from app.models import (  # noqa: F401  - import side-effect
    LawChunk,
    LawChunkVersion,
    NormCatalog,
    NormRelation,
)

# Use SQLite in-memory. The pg_insert ON CONFLICT clause is
# Postgres-specific, but we test with plain ORM operations against the
# real PKs; idempotency is exercised via re-calling upsert_*.
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture
def db() -> Session:
    """Fresh in-memory DB with only the corpus tables (skipping
    ``law_chunks`` whose pgvector ``embedding_vec`` column trips
    SQLite on CREATE TABLE). We mirror the schema with plain SQL so
    the tests run on both engines."""
    session = TestSession()
    try:
        # Corpus tables — mirror the migration with SQLite-compatible
        # types. JSON columns (not JSONB) so SQLite compiles them.
        for ddl in [
            """CREATE TABLE IF NOT EXISTS norm_catalog (
                id INTEGER PRIMARY KEY,
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
                modifies_norm_ids JSON DEFAULT '[]',
                repealed_by_norm_id INTEGER,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                last_synced_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS law_chunk_versions (
                id INTEGER PRIMARY KEY,
                norm_id INTEGER NOT NULL REFERENCES norm_catalog(id) ON DELETE CASCADE,
                version_label VARCHAR(128) NOT NULL,
                valid_from DATE NOT NULL,
                valid_until DATE,
                is_current BOOLEAN NOT NULL DEFAULT 1,
                source_url VARCHAR(500),
                raw_source_hash VARCHAR(64),
                chunk_count INTEGER NOT NULL DEFAULT 0,
                extra JSON DEFAULT '{}',
                imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(norm_id, version_label)
            )""",
            """CREATE TABLE IF NOT EXISTS norm_relations (
                id INTEGER PRIMARY KEY,
                from_norm_id INTEGER NOT NULL REFERENCES norm_catalog(id) ON DELETE CASCADE,
                to_norm_id INTEGER NOT NULL REFERENCES norm_catalog(id) ON DELETE CASCADE,
                relation_type VARCHAR(32) NOT NULL,
                article_ref VARCHAR(64),
                source VARCHAR(64) NOT NULL DEFAULT 'bcn',
                confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS law_chunks (
                id INTEGER PRIMARY KEY,
                law_code VARCHAR(100) NOT NULL,
                law_name VARCHAR(500) NOT NULL,
                article_number VARCHAR(50),
                chapter_title VARCHAR(500),
                section_title VARCHAR(500),
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding_vec BLOB,
                legal_area VARCHAR(50) NOT NULL,
                chunk_metadata JSON DEFAULT '{}',
                created_at TIMESTAMP,
                jerarquia_path VARCHAR(255),
                parent_chunk_id INTEGER,
                libro VARCHAR(128),
                titulo VARCHAR(128),
                capitulo VARCHAR(128),
                articulo VARCHAR(64),
                inciso INTEGER,
                numeral VARCHAR(16),
                letra VARCHAR(8),
                norm_id INTEGER REFERENCES norm_catalog(id) ON DELETE SET NULL,
                version_id INTEGER REFERENCES law_chunk_versions(id) ON DELETE SET NULL
            )""",
        ]:
            session.execute(text(ddl))
        session.commit()
        yield session
    finally:
        session.execute(text("DROP TABLE IF EXISTS law_chunks"))
        session.execute(text("DROP TABLE IF EXISTS norm_relations"))
        session.execute(text("DROP TABLE IF EXISTS law_chunk_versions"))
        session.execute(text("DROP TABLE IF EXISTS norm_catalog"))
        session.commit()
        session.close()


def _writer(db: Session):
    """Wrap the DB session in a DBWriter. We bypass the session_factory
    indirection here — the writer only needs a way to get a Session,
    and we already have one."""
    from scripts.db_writer import DBWriter

    class _Factory:
        def __call__(self) -> Session:
            return db

    return DBWriter(_Factory())


def test_upsert_norm_inserts_then_returns_id(db):
    w = _writer(db)
    norm_id = w.upsert_norm({
        "bcn_id": "1984",
        "titulo": "Codigo Penal",
        "tipo": "codigo",
        "numero": "2561",
        "fecha_publicacion": "1874-11-12",
        "url_bcn": "https://www.bcn.cl/leychile/navegar?idNorma=1984",
    })
    assert isinstance(norm_id, int) and norm_id > 0

    row = db.execute(text("SELECT bcn_id, titulo, tipo, numero, estado FROM norm_catalog WHERE id = :id"),
                      {"id": norm_id}).one()
    assert row.bcn_id == "1984"
    assert row.titulo == "Codigo Penal"
    assert row.tipo == "codigo"
    assert row.numero == "2561"
    assert row.estado == "vigente"


def test_upsert_norm_is_idempotent(db):
    w = _writer(db)
    first = w.upsert_norm({"bcn_id": "1984", "titulo": "Codigo Penal"})
    second = w.upsert_norm({"bcn_id": "1984", "titulo": "Codigo Penal"})
    assert first == second  # no duplicate row created


def test_upsert_norm_refreshes_metadata(db):
    """Re-running the crawler with a corrected titulo should overwrite
    the cached one without creating a new row."""
    w = _writer(db)
    w.upsert_norm({"bcn_id": "1984", "titulo": "Old title"})
    w.upsert_norm({"bcn_id": "1984", "titulo": "New title", "fecha_publicacion": "1874-11-12"})
    row = db.execute(text("SELECT titulo FROM norm_catalog WHERE bcn_id = '1984'")).one()
    assert row.titulo == "New title"


def test_upsert_version_and_mark_superseded(db):
    w = _writer(db)
    norm_id = w.upsert_norm({"bcn_id": "1984", "titulo": "Codigo Penal"})

    v1 = w.upsert_version(norm_id, "vigente hasta 2024", date(1874, 11, 12))
    v2 = w.upsert_version(norm_id, "vigente 2024 en adelante", date(2024, 1, 1))

    rows = db.execute(text(
        "SELECT version_label, is_current, valid_from, valid_until "
        "FROM law_chunk_versions WHERE norm_id = :n ORDER BY valid_from"
    ), {"n": norm_id}).all()
    assert len(rows) == 2
    assert rows[0].is_current in (True, 1)
    assert rows[1].is_current in (True, 1)

    # Simulate publishing a new version: v1 should be flipped to
    # is_current=false with valid_until = the new version's start date.
    flipped = w.mark_previous_versions_superseded(
        norm_id, superseded_from=date(2024, 1, 1), exclude_version_id=v2,
    )
    assert flipped == 1
    rows = db.execute(text(
        "SELECT version_label, is_current, valid_until "
        "FROM law_chunk_versions WHERE norm_id = :n ORDER BY valid_from"
    ), {"n": norm_id}).all()
    assert rows[0].is_current in (False, 0)
    # SQLite returns DATE columns as ISO strings ("2024-01-01") while
    # Postgres returns datetime.date instances. Compare the canonical
    # string form so the test is portable across engines.
    assert str(rows[0].valid_until) == "2024-01-01"
    assert rows[1].is_current in (True, 1)


def test_upsert_chunks_writes_rows_with_hierarchy(db):
    """Chunks get their hierarchical fields populated so /precedents
    can filter by libro / titulo / capitulo without LIKE."""
    from scripts.html_parser import ParsedChunk
    w = _writer(db)
    norm_id = w.upsert_norm({"bcn_id": "test-1984", "titulo": "Codigo de Prueba"})
    version_id = w.upsert_version(norm_id, "v1", date(2024, 1, 1))

    chunks = [
        ParsedChunk(
            article_number="1",
            libro="PRIMERO",
            titulo="Disposiciones generales",
            capitulo="Normas preliminares",
            content="El presente codigo establece...",
            parent_hint="LIBRO PRIMERO / TITULO I",
        ),
        ParsedChunk(
            article_number="2",
            libro="PRIMERO",
            titulo="Disposiciones generales",
            capitulo="Normas preliminares",
            content="Las disposiciones de este codigo se aplican...",
            parent_hint="LIBRO PRIMERO / TITULO I",
        ),
    ]
    written = w.upsert_chunks(
        version_id,
        chunks,
        law_code="test-1984",
        law_name="Codigo de Prueba",
        legal_area="civil",
        source_url="https://example.invalid/test",
        generate_embeddings=False,  # skip — no OpenAI key in the test env
    )
    assert written == 2
    rows = db.execute(text(
        "SELECT article_number, libro, titulo, capitulo, jerarquia_path "
        "FROM law_chunks WHERE version_id = :v ORDER BY chunk_index"
    ), {"v": version_id}).all()
    assert rows[0].article_number == "1"
    assert rows[0].libro == "PRIMERO"
    assert "PRIMERO" in rows[0].jerarquia_path
    assert "Disposiciones" in rows[0].jerarquia_path


def test_upsert_chunks_skips_empty_content(db):
    from scripts.html_parser import ParsedChunk
    w = _writer(db)
    norm_id = w.upsert_norm({"bcn_id": "test-empty", "titulo": "Test"})
    version_id = w.upsert_version(norm_id, "v1", date(2024, 1, 1))
    chunks = [
        ParsedChunk(article_number="1", content="Real content."),
        ParsedChunk(article_number="2", content=""),       # empty → skip
        ParsedChunk(article_number="3", content="   "),    # whitespace only → skip
    ]
    written = w.upsert_chunks(
        version_id, chunks,
        law_code="test-empty", law_name="Test", legal_area="other",
        generate_embeddings=False,
    )
    assert written == 1
