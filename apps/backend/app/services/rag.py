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


def search_chunks_by_embedding(
    query_embedding: list[float],
    organization_id: int,
    matter_id: int,
    top_k: int = 5,
    similarity_threshold: float = 0.3,  # DEBUG: lowering from 0.5 to 0.3
    legal_area: LegalArea | None = None
) -> list[dict]:
    db = SessionLocal()
    try:
        # Usar SQL directo para evitar problemas con ORM
        from sqlalchemy import text
        sql = text("""
            SELECT id, document_id, organization_id, matter_id, chunk_index,
                   content, page_number, section_title, embedding, legal_area,
                   chunk_metadata, created_at
            FROM document_chunks
            WHERE organization_id = :org_id AND matter_id = :matter_id
        """)
        result = db.execute(sql, {"org_id": organization_id, "matter_id": matter_id})
        rows = result.fetchall()

        logger.debug(f"[DEBUG RAG] SQL direct result: {len(rows)} rows")  # S4-05
        # Convertir a objetos similar a chunk
        chunks = []
        for row in rows:
            chunk_dict = {
                "id": row[0],
                "document_id": row[1],
                "organization_id": row[2],
                "matter_id": row[3],
                "chunk_index": row[4],
                "content": row[5],
                "page_number": row[6],
                "section_title": row[7],
                "embedding": row[8],
                "legal_area": row[9],
                "chunk_metadata": row[10],
                "created_at": row[11]
            }
            chunks.append(chunk_dict)

        logger.debug(f"[DEBUG RAG] Found {len(chunks)} chunks in DB for org={organization_id}, matter={matter_id}")  # S4-05
        results = []
        skipped_no_embedding = 0
        skipped_threshold = 0
        errors = 0

        for chunk in chunks:
            if not chunk["embedding"]:
                skipped_no_embedding += 1
                continue

            try:
                stored_embedding = json.loads(chunk["embedding"])
                similarity = cosine_similarity(query_embedding, stored_embedding)

                if similarity >= similarity_threshold:
                    results.append({
                        "chunk_id": chunk["id"],
                        "document_id": chunk["document_id"],
                        "content": chunk["content"],
                        "page_number": chunk["page_number"],
                        "section_title": chunk["section_title"],
                        "similarity": similarity,
                        "chunk_index": chunk["chunk_index"]
                    })
                else:
                    skipped_threshold += 1
            except (json.JSONDecodeError, TypeError):
                errors += 1
                continue

        logger.debug(f"[DEBUG RAG] Chunks processed: {len(results)} passed, {skipped_no_embedding} no embedding, {skipped_threshold} below threshold, {errors} errors")  # S4-05
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    finally:
        db.close()


def search_chunks_by_keyword(
    query: str,
    organization_id: int,
    matter_id: int,
    top_k: int = 10,
    legal_area: LegalArea | None = None
) -> list[dict]:
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
    legal_area: LegalArea | None = None
) -> list[dict]:
    """Busca en chunks de leyes chilenas por embedding."""
    if not LAW_CHUNKS_AVAILABLE:
        return []

    db = SessionLocal()
    try:
        query = db.query(LawChunk)
        if law_code:
            query = query.filter(LawChunk.law_code == law_code)
        if legal_area is not None:
            query = query.filter(LawChunk.legal_area == legal_area)

        chunks = query.all()

        results = []
        for chunk in chunks:
            if not chunk.embedding:
                continue

            try:
                stored_embedding = json.loads(chunk.embedding)
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
            except (json.JSONDecodeError, TypeError):
                continue

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


