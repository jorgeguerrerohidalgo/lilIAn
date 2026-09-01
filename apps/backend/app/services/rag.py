import json
import logging

import numpy as np
from sqlalchemy import text

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


_EMBEDDING_SIMILARITY_DEFAULT = -0.4


def search_chunks_by_embedding(
    query_embedding: list[float],
    organization_id: int,
    matter_id: int,
    top_k: int = 5,
    similarity_threshold: float = _EMBEDDING_SIMILARITY_DEFAULT,
    legal_area: LegalArea | None = None,
) -> list[dict]:
    """ANN-search the document chunks for the closest embeddings.

    S5.1: uses pgvector's ``<=>`` operator against the HNSW index
    ``ix_document_chunks_embedding_vec_hnsw`` so search is O(log N)
    in SQL instead of pulling every chunk into Python. The previous
    numpy.cosine path was O(N) per matter and silently failed on the
    dim mismatch between 512-dim and 1536-dim chunks (now resolved by
    migration 034).

    Returns up to ``top_k`` chunks with similarity >= threshold.
    """
    if similarity_threshold < -1 or similarity_threshold > 1:
        raise ValueError("similarity_threshold must be in [-1, 1]")
    max_distance = 2.0 * (1.0 - similarity_threshold)

    db = SessionLocal()
    try:
        sql = """
            SELECT id, document_id, organization_id, matter_id, chunk_index,
                   content, page_number, section_title, legal_area,
                   chunk_metadata, created_at,
                   (embedding_vec <=> CAST(:q AS vector)) AS distance
              FROM document_chunks
             WHERE organization_id = :org_id
               AND matter_id = :matter_id
               AND embedding_vec IS NOT NULL
               {legal_area_clause}
             ORDER BY embedding_vec <=> CAST(:q AS vector)
             LIMIT :k
        """

        legal_area_clause = (
            "AND legal_area = :legal_area" if legal_area is not None else ""
        )
        sql = sql.format(legal_area_clause=legal_area_clause)

        params: dict = {
            "q": query_embedding,
            "org_id": organization_id,
            "matter_id": matter_id,
            "k": top_k,
        }
        if legal_area is not None:
            params["legal_area"] = (
                legal_area.value if hasattr(legal_area, "value") else legal_area
            )

        rows = db.execute(text(sql), params).fetchall()
        # SQL returns rows in distance-ascending order; we filter the
        # ``distance <= max_distance`` (== similarity >= threshold) cut
        # in Python so the threshold semantics match the previous impl.
        out: list[dict] = []
        for r in rows:
            distance = r[-1]
            if distance > max_distance:
                break
            out.append({
                "chunk_id": r[0],
                "document_id": r[1],
                "organization_id": r[2],
                "matter_id": r[3],
                "chunk_index": r[4],
                "content": r[5],
                "page_number": r[6],
                "section_title": r[7],
                "legal_area": r[8],
                "chunk_metadata": r[9],
                "created_at": r[10],
                "similarity": 1.0 - distance / 2.0,
            })
        return out
    finally:
        db.close()


def search_chunks_by_keyword(
    query: str,
    organization_id: int,
    matter_id: int,
    top_k: int = 10,
    legal_area: LegalArea | None = None,
    as_of = None,
    libro: str | None = None,
    capitulo: str | None = None,
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
    similarity_threshold: float = -0.4,
    legal_area: LegalArea | None = None,
    query_text: str | None = None,
    as_of = None,
    libro: str | None = None,
    capitulo: str | None = None,
) -> list[dict]:
    """Busca en chunks de leyes chilenas por embedding con pgvector.

    S5.1 — uses the pgvector ``<=>`` operator against the HNSW index
    on ``law_chunks.embedding_vec`` for ANN search in SQL. Returns
    top-k most similar chunks in O(log N) instead of the O(N) Python
    loop we used before.

    A keyword pre-filter (``ILIKE`` on ``content``) narrows the
    candidate set when ``query_text`` is supplied. This is what stops
    "causales de despido" from returning unrelated general-intro
    articles — those don't contain any of the substantive tokens.

    The ``<=>`` operator returns *distance* (0 = identical, 2 =
    opposite). We convert to cosine *similarity* as ``1 - distance/2``
    so callers can keep using a 0..1 scale they understand.
    """
    if not LAW_CHUNKS_AVAILABLE:
        return []

    # pgvector cosine distance is 0 (identical) → 2 (opposite). Convert
    # to a 0..1 similarity scale that matches the threshold semantics.
    if similarity_threshold < -1 or similarity_threshold > 1:
        raise ValueError("similarity_threshold must be in [-1, 1]")
    max_distance = 2.0 * (1.0 - similarity_threshold)

    from sqlalchemy import bindparam, or_

    db = SessionLocal()
    try:
        # Optional keyword pre-filter: cheap ILIKE clauses against the
        # same column. If the query has no substantive tokens we skip
        # this and let pgvector rank over the whole corpus.
        tokens: list[str] = []
        if query_text:
            tokens = [t for t in query_text.lower().split() if len(t) >= 4 and t.isalpha()]

        # SQL: ORDER BY embedding_vec <=> :q LIMIT :k. pgvector's
        # ``<=>`` operator uses the HNSW index.
        sql = """
            SELECT id, content, law_code, law_name, article_number,
                   (embedding_vec <=> CAST(:q AS vector)) AS distance
              FROM law_chunks
             WHERE embedding_vec IS NOT NULL
               {law_code_clause}
               {legal_area_clause}
               {keyword_clause}
               {temporal_clause}
               {libro_clause}
               {capitulo_clause}
             ORDER BY embedding_vec <=> CAST(:q AS vector)
             LIMIT :k
        """

        law_code_clause = "AND law_code = :law_code" if law_code else ""
        legal_area_clause = (
            "AND legal_area = :legal_area" if legal_area is not None else ""
        )
        keyword_clause = ""
        temporal_clause = ""
        libro_clause = ""
        capitulo_clause = ""
        params: dict = {"q": query_embedding, "k": top_k}
        if tokens:
            keyword_clause = "AND (" + " OR ".join(
                f"content ILIKE :kw{i}" for i in range(len(tokens))
            ) + ")"
            for i, tok in enumerate(tokens):
                params[f"kw{i}"] = f"%{tok}%"

        # Temporal versionado (Fase 1 corpus legal): when ``as_of`` is
        # set, restrict to chunks whose version was in force on that
        # date. The NULL-handling lets a version with ``valid_until IS
        # NULL`` (i.e. currently in force) pass through any as_of >= its
        # valid_from.
        if as_of is not None:
            temporal_clause = (
                "AND version_id IN ("
                "  SELECT id FROM law_chunk_versions v"
                "  WHERE v.valid_from <= :as_of"
                "    AND (v.valid_until IS NULL OR v.valid_until > :as_of)"
                ")"
            )
            params["as_of"] = as_of

        if libro:
            libro_clause = "AND libro = :libro"
            params["libro"] = libro

        if capitulo:
            capitulo_clause = "AND capitulo = :capitulo"
            params["capitulo"] = capitulo

        if law_code:
            params["law_code"] = law_code
        if legal_area is not None:
            params["legal_area"] = (
                legal_area.value if hasattr(legal_area, "value") else legal_area
            )

        sql = sql.format(
            law_code_clause=law_code_clause,
            legal_area_clause=legal_area_clause,
            keyword_clause=keyword_clause,
            temporal_clause=temporal_clause,
            libro_clause=libro_clause,
            capitulo_clause=capitulo_clause,
        )

        sql = sql.format(
            law_code_clause=law_code_clause,
            legal_area_clause=legal_area_clause,
            keyword_clause=keyword_clause,
        )

        rows = db.execute(text(sql), params).fetchall()
        return [
            {
                "chunk_id": row[0],
                "content": row[1],
                "law_code": row[2],
                "law_name": row[3],
                "article_number": row[4],
                "similarity": 1.0 - row[5] / 2.0,  # distance → similarity
            }
            for row in rows
            if (1.0 - row[5] / 2.0) >= similarity_threshold
        ]
    finally:
        db.close()


def search_laws_by_keyword(
    query: str,
    top_k: int = 10,
    legal_area=None,
    as_of=None,
    libro: str | None = None,
    capitulo: str | None = None,
) -> list[dict]:
    """Full-text search on ``law_chunks`` for the corpus legal.

    Uses Postgres ``to_tsvector`` / ``to_tsquery`` (Spanish config) on
    ``content`` so articles with exact keyword matches rank above
    vector-only neighbors. Returns chunks ordered by ``ts_rank_cd``.

    Complements :func:`search_laws_by_embedding` in the hybrid-search
    flow: the endpoint calls both and merges with RRF.

    The query is sanitized so a single bad token (e.g. ``&``) doesn't
    raise — we strip non-alnum and rebuild with ``&`` between tokens.
    Empty after sanitization returns ``[]`` so callers can short-circuit
    the keyword half of the RRF.
    """
    if not LAW_CHUNKS_AVAILABLE:
        return []

    import re as _re
    tokens = [
        t for t in _re.findall(r"[a-záéíóúñü0-9]+", query.lower())
        if len(t) >= 3
    ]
    if not tokens:
        return []

    tsquery = " & ".join(tokens)

    db = SessionLocal()
    try:
        sql = """
            SELECT id, content, law_code, law_name, article_number,
                   ts_rank_cd(
                       to_tsvector('spanish', content),
                       to_tsquery('spanish', :q)
                   ) AS rank
              FROM law_chunks
             WHERE to_tsvector('spanish', content) @@ to_tsquery('spanish', :q)
               {legal_area_clause}
               {temporal_clause}
               {libro_clause}
               {capitulo_clause}
             ORDER BY rank DESC
             LIMIT :k
        """

        legal_area_clause = (
            "AND legal_area = :legal_area" if legal_area is not None else ""
        )
        temporal_clause = ""
        libro_clause = ""
        capitulo_clause = ""
        params: dict = {"q": tsquery, "k": top_k}
        if legal_area is not None:
            params["legal_area"] = (
                legal_area.value if hasattr(legal_area, "value") else legal_area
            )
        if as_of is not None:
            temporal_clause = (
                "AND version_id IN ("
                "  SELECT id FROM law_chunk_versions v"
                "  WHERE v.valid_from <= :as_of"
                "    AND (v.valid_until IS NULL OR v.valid_until > :as_of)"
                ")"
            )
            params["as_of"] = as_of
        if libro:
            libro_clause = "AND libro = :libro"
            params["libro"] = libro
        if capitulo:
            capitulo_clause = "AND capitulo = :capitulo"
            params["capitulo"] = capitulo

        sql = sql.format(
            legal_area_clause=legal_area_clause,
            temporal_clause=temporal_clause,
            libro_clause=libro_clause,
            capitulo_clause=capitulo_clause,
        )

        rows = db.execute(text(sql), params).fetchall()
        return [
            {
                "chunk_id": row[0],
                "content": row[1],
                "law_code": row[2],
                "law_name": row[3],
                "article_number": row[4],
                "keyword_rank": float(row[5]),
            }
            for row in rows
        ]
    finally:
        db.close()


_RRF_K_DEFAULT = 60  # Constante típica para Reciprocal Rank Fusion


def hybrid_search(
    query: str,
    organization_id: int,
    matter_id: int,
    top_k: int = 5,
    include_laws: bool = True,
    legal_area: LegalArea | None = None,
    as_of = None,
    libro: str | None = None,
    capitulo: str | None = None,
) -> list[dict]:
    """Búsqueda híbrida con Reciprocal Rank Fusion (RRF).

    Combina resultados de embedding y keyword search usando RRF para
    mejor ranking.

    S4-16: previously a 118-line function with three embedded concerns
    (embedding fetch, keyword fetch, RRF fusion). Split into three
    helpers so the top-level is the strategy + the merge.

    Fase 1 corpus legal — extras:

    - ``as_of``     : datetime.date | None — temporal filter. When set,
                       only chunks whose associated law_chunk_versions
                       row has ``valid_from <= as_of < valid_until``
                       (or ``valid_until IS NULL``) are returned. Lets
                       us answer "¿qué establecía esta ley en X fecha?"
    - ``libro``     : book filter (only Códigos typically have LIBRO).
    - ``capitulo``  : chapter filter.

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
        query, organization_id, matter_id, top_k,
        legal_area=legal_area, as_of=as_of, libro=libro, capitulo=capitulo,
    )
    keyword_results = search_chunks_by_keyword(
        query, organization_id, matter_id, top_k * 3,
        legal_area=legal_area, as_of=as_of, libro=libro, capitulo=capitulo,
    )
    logger.debug(f"[DEBUG RAG] Keyword results: {len(keyword_results)}")

    merged = _merge_with_rrf(embedding_results, keyword_results)
    ranked = _sort_by_rrf_score(merged)
    return ranked[:top_k]


def _run_embedding_search(
    query: str, organization_id: int, matter_id: int,
    top_k: int, legal_area: LegalArea | None,
    *,
    as_of = None,
    libro: str | None = None,
    capitulo: str | None = None,
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


