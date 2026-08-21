import json
import logging

import numpy as np

from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.legal_area import LegalArea

logger = logging.getLogger(__name__)

try:
    from app.models.law_chunk import LawChunk
    LAW_CHUNKS_AVAILABLE = True
except ImportError:
    LAW_CHUNKS_AVAILABLE = False


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


_EMBEDDING_SIMILARITY_DEFAULT = 0.3  # DEBUG: lowered from 0.5


def search_chunks_by_embedding(
    query_embedding: list[float],
    organization_id: int,
    matter_id: int,
    top_k: int = 5,
    similarity_threshold: float = _EMBEDDING_SIMILARITY_DEFAULT,
    legal_area: LegalArea | None = None,
) -> list[dict]:
    """Search the document chunks for the closest embeddings.

    S4-21: previously this 79-line function did 4 things inline (raw
    SQL fetch, row->dict conversion, per-chunk similarity scoring,
    sort+trim). Refactored into focused helpers so the top-level is
    a linear fetch → score → sort → trim pipeline.
    """
    db = SessionLocal()
    try:
        chunks = _fetch_chunks_for_matter(db, organization_id, matter_id)
        scored, stats = _score_chunks(chunks, query_embedding, similarity_threshold)
        _log_scoring_stats(stats, organization_id, matter_id, len(scored))
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# S4-21: search_chunks_by_embedding helpers
# ---------------------------------------------------------------------------
_CHUNK_FIELDS = (
    "id", "document_id", "organization_id", "matter_id", "chunk_index",
    "content", "page_number", "section_title", "embedding", "legal_area",
    "chunk_metadata", "created_at",
)


def _fetch_chunks_for_matter(db, organization_id: int, matter_id: int) -> list[dict]:
    """Pull raw chunk rows via direct SQL and shape them as dicts."""
    from sqlalchemy import text

    sql = text(
        "SELECT id, document_id, organization_id, matter_id, chunk_index, "
        "content, page_number, section_title, embedding, legal_area, "
        "chunk_metadata, created_at "
        "FROM document_chunks "
        "WHERE organization_id = :org_id AND matter_id = :matter_id"
    )
    rows = db.execute(
        sql, {"org_id": organization_id, "matter_id": matter_id}
    ).fetchall()
    return [dict(zip(_CHUNK_FIELDS, row, strict=False)) for row in rows]


def _score_chunks(
    chunks: list[dict], query_embedding: list[float], threshold: float
) -> tuple[list[dict], dict]:
    """Compute similarity and return (scored_chunks, counters).

    The counters dict tracks why chunks were excluded so the caller's
    debug log can surface the breakdown.
    """
    scored: list[dict] = []
    stats = {
        "skipped_no_embedding": 0,
        "skipped_threshold": 0,
        "errors": 0,
    }
    for chunk in chunks:
        result, status = _score_one_chunk(chunk, query_embedding, threshold)
        if result is None:
            stats[status] += 1
            continue
        scored.append(result)
    return scored, stats


def _score_one_chunk(
    chunk: dict, query_embedding: list[float], threshold: float
) -> tuple[dict | None, str | None]:
    """Score a single chunk; return (result_dict, skip_reason) where
    ``skip_reason`` is one of ``skipped_no_embedding``, ``skipped_threshold``,
    ``errors`` when the chunk was excluded.
    """
    if not chunk["embedding"]:
        return None, "skipped_no_embedding"
    try:
        stored_embedding = json.loads(chunk["embedding"])
    except (json.JSONDecodeError, TypeError):
        return None, "errors"

    similarity = cosine_similarity(query_embedding, stored_embedding)
    if similarity < threshold:
        return None, "skipped_threshold"

    return {
        "chunk_id": chunk["id"],
        "document_id": chunk["document_id"],
        "content": chunk["content"],
        "page_number": chunk["page_number"],
        "section_title": chunk["section_title"],
        "similarity": similarity,
        "chunk_index": chunk["chunk_index"],
    }, None


def _log_scoring_stats(stats: dict, organization_id: int, matter_id: int, passed: int) -> None:
    logger.debug(
        f"[DEBUG RAG] Chunks processed: {passed} passed, "
        f"{stats['skipped_no_embedding']} no embedding, "
        f"{stats['skipped_threshold']} below threshold, "
        f"{stats['errors']} errors"
    )
    logger.debug(
        f"[DEBUG RAG] Found {passed} chunks in DB for org={organization_id}, matter={matter_id}"
    )

def search_chunks_by_keyword(
    query: str,
    organization_id: int,
    matter_id: int,
    top_k: int = 10,
    legal_area: LegalArea | None = None
) -> list[dict]:
    """Busca chunks por coincidencia literal de la consulta.

    Filtra los chunks del caso y área legal indicada, cuenta las
    ocurrencias de ``query`` (case-insensitive) en ``content`` y
    devuelve los ``top_k`` con más matches, ordenados de mayor a menor
    recuento.

    Args:
        query: Texto a buscar (case-insensitive).
        organization_id: ID de la organización (multi-tenant).
        matter_id: ID del caso donde buscar.
        top_k: Número máximo de resultados.
        legal_area: Filtro opcional por área legal.

    Returns:
        Lista de dicts con ``chunk_id``, ``document_id``, ``content``,
        ``page_number``, ``section_title``, ``keyword_count`` y
        ``chunk_index``. Lista vacía si no hay coincidencias.
    """
    db = SessionLocal()
    try:
        db_query = db.query(DocumentChunk).filter(
            DocumentChunk.organization_id == organization_id,
            DocumentChunk.matter_id == matter_id
        )
        if legal_area is not None:
            db_query = db_query.filter(DocumentChunk.legal_area == legal_area)

        chunks = db_query.all()

        results = []
        query_lower = query.lower()
        for chunk in chunks:
            content_lower = chunk.content.lower()
            if query_lower in content_lower:
                count = content_lower.count(query_lower)
                results.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title,
                    "keyword_count": count,
                    "chunk_index": chunk.chunk_index
                })

        results.sort(key=lambda x: x["keyword_count"], reverse=True)
        return results[:top_k]

    finally:
        db.close()


def search_laws_by_embedding(
    query_embedding: list[float],
    law_code: str = None,
    top_k: int = 5,
    similarity_threshold: float = 0.5,
    legal_area: LegalArea | None = None,
    candidate_limit: int = 4000,
) -> list[dict]:
    """Busca en chunks de leyes chilenas por embedding.

    S5.1 — pragmatic implementation: load at most ``candidate_limit``
    chunks and score them in Python. The proper long-term fix is to
    migrate ``law_chunks.embedding`` to a real pgvector column and use
    the ``<=>`` operator with an IVFFlat / HNSW index. See
    ROADMAP_HARVEY_FEATURES.md → "Real embeddings" follow-ups.

    The ``candidate_limit`` cap protects against Supabase statement
    timeouts when the corpus grows past a few thousand chunks: the
    query below loads every embedding column into Python memory, which
    is ``O(N * 1536 * 8 bytes)`` — ~110 MB for 17K chunks — and is the
    bottleneck, not the cosine math.
    """
    if not LAW_CHUNKS_AVAILABLE:
        return []

    db = SessionLocal()
    try:
        query = db.query(LawChunk)
        if law_code:
            query = query.filter(LawChunk.law_code == law_code)
        if legal_area is not None:
            query = query.filter(LawChunk.legal_area == legal_area)

        # Order by id so the candidate window is stable across calls;
        # the random sample alternative would skew results.
        chunks = query.order_by(LawChunk.id).limit(candidate_limit).all()

        results = []
        skipped_dim_mismatch = 0
        query_dim = len(query_embedding)
        for chunk in chunks:
            if not chunk.embedding:
                continue

            try:
                stored_embedding = json.loads(chunk.embedding)
            except (json.JSONDecodeError, TypeError):
                continue

            # S5.1 — law_indexer used EMBEDDING_DIM_SHORT (512) for chunks
            # shorter than SHORT_DOC_CHAR_THRESHOLD and 1536 otherwise, so
            # the corpus has mixed dimensions. Cosine requires matching
            # dims; skip (don't error) and count. TODO: reindex all
            # law_chunks at 1536 dims to drop the 512-dim branch entirely.
            if len(stored_embedding) != query_dim:
                skipped_dim_mismatch += 1
                continue

            similarity = cosine_similarity(query_embedding, stored_embedding)

            if similarity >= similarity_threshold:
                results.append({
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "law_code": chunk.law_code,
                    "law_name": chunk.law_name,
                    "article_number": chunk.article_number,
                    "similarity": similarity
                })

        if skipped_dim_mismatch:
            logger.debug(
                "search_laws_by_embedding skipped %d chunks (dim %d != query dim %d)",
                skipped_dim_mismatch, len(stored_embedding) if chunks else -1, query_dim,
            )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    finally:
        db.close()


_RRF_K_DEFAULT = 60  # Constante típica para Reciprocal Rank Fusion


def hybrid_search(
    query: str,
    organization_id: int,
    matter_id: int,
    top_k: int = 5,
    include_laws: bool = True,
    legal_area: LegalArea | None = None
) -> list[dict]:
    """Búsqueda híbrida con Reciprocal Rank Fusion (RRF).

    Combina resultados de embedding y keyword search usando RRF para
    mejor ranking.

    S4-16: previously a 118-line function with three embedded concerns
    (embedding fetch, keyword fetch, RRF fusion). Split into three
    helpers so the top-level is the strategy + the merge.

    Args:
        query: Texto de la consulta del usuario.
        organization_id: ID de la organización (multi-tenant).
        matter_id: ID del caso sobre el que se busca.
        top_k: Número máximo de resultados a devolver.
        include_laws: Reservado para futuro filtrado por leyes; hoy se
            ignora (mantenido por compatibilidad).
        legal_area: Filtro opcional por área legal.

    Returns:
        Lista de chunks rankeados, cada uno con ``chunk_id``,
        ``content``, ``page_number``, ``section_title``,
        ``rrf_score``, ``source`` (``embedding``/``keyword``/``both``),
        ``embedding_rank``, ``keyword_rank``, ``embedding_score`` y
        ``keyword_score``.
    """
    embedding_results = _run_embedding_search(
        query, organization_id, matter_id, top_k, legal_area
    )
    keyword_results = search_chunks_by_keyword(
        query, organization_id, matter_id, top_k * 3, legal_area=legal_area
    )
    logger.debug(f"[DEBUG RAG] Keyword results: {len(keyword_results)}")  # S4-05

    merged = _merge_with_rrf(embedding_results, keyword_results)
    ranked = _sort_by_rrf_score(merged)
    return ranked[:top_k]


def _run_embedding_search(
    query: str, organization_id: int, matter_id: int,
    top_k: int, legal_area: LegalArea | None,
) -> list[dict]:
    """Run the embedding-based search; degrade gracefully on provider errors."""
    try:
        from app.services.embeddings import get_embedding_provider

        provider = get_embedding_provider()
        query_embedding = provider.generate_embedding(query)
        logger.debug(
            f"[DEBUG RAG] Query embedding generated, length: {len(query_embedding)}"
        )  # S4-05
        results = search_chunks_by_embedding(
            query_embedding, organization_id, matter_id, top_k * 3,
            legal_area=legal_area,
        )
        logger.debug(f"[DEBUG RAG] Document embedding results: {len(results)}")
        return results
    except Exception as exc:
        logger.debug(f"[DEBUG RAG] Embedding search failed: {exc}")  # S4-05
        import traceback
        traceback.print_exc()
        return []


def _merge_with_rrf(
    embedding_results: list[dict], keyword_results: list[dict]
) -> dict[int, dict]:
    """Combine two ranked result lists using Reciprocal Rank Fusion.

    Each result dict is augmented with ``source``, ``embedding_rank``,
    ``keyword_rank``, ``embedding_score`` and ``keyword_score`` fields so
    downstream scoring can weight by rank origin.
    """
    merged: dict[int, dict] = {}

    for rank, result in enumerate(embedding_results, 1):
        chunk_id = result["chunk_id"]
        merged[chunk_id] = {
            **result,
            "source": "embedding",
            "embedding_rank": rank,
            "keyword_rank": None,
            "embedding_score": result["similarity"],
            "keyword_score": 0,
        }

    for rank, result in enumerate(keyword_results, 1):
        chunk_id = result["chunk_id"]
        if chunk_id in merged:
            merged[chunk_id]["keyword_rank"] = rank
            merged[chunk_id]["keyword_score"] = result.get("score", 1.0)
            merged[chunk_id]["source"] = "both"
        else:
            merged[chunk_id] = {
                **result,
                "source": "keyword",
                "embedding_rank": None,
                "keyword_rank": rank,
                "embedding_score": 0,
                "keyword_score": result.get("score", 1.0),
            }

    return merged


def _sort_by_rrf_score(merged: dict[int, dict]) -> list[dict]:
    """Sort by RRF score (descending) and attach the computed field."""
    for _chunk_id, result in merged.items():
        result["rrf_score"] = _rrf_score(result)
    return sorted(
        merged.values(),
        key=lambda r: r["rrf_score"],
        reverse=True,
    )


def _rrf_score(result: dict) -> float:
    """Reciprocal Rank Fusion score: sum of 1/(k+rank) across present ranks."""
    score = 0.0
    if result.get("embedding_rank") is not None:
        score += 1 / (_RRF_K_DEFAULT + result["embedding_rank"])
    if result.get("keyword_rank") is not None:
        score += 1 / (_RRF_K_DEFAULT + result["keyword_rank"])
    return score


