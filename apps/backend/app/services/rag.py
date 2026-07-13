from typing import List, Optional, Tuple
import json
import numpy as np

from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.legal_area import LegalArea

try:
    from app.models.law_chunk import LawChunk
    LAW_CHUNKS_AVAILABLE = True
except ImportError:
    LAW_CHUNKS_AVAILABLE = False


def cosine_similarity(a: List[float], b: List[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def search_chunks_by_embedding(
    query_embedding: List[float],
    organization_id: int,
    matter_id: int,
    top_k: int = 5,
    similarity_threshold: float = 0.5,
    legal_area: Optional[LegalArea] = None
) -> List[dict]:
    db = SessionLocal()
    try:
        query = db.query(DocumentChunk).filter(
            DocumentChunk.organization_id == organization_id,
            DocumentChunk.matter_id == matter_id
        )
        if legal_area is not None:
            query = query.filter(DocumentChunk.legal_area == legal_area)

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
                        "document_id": chunk.document_id,
                        "content": chunk.content,
                        "page_number": chunk.page_number,
                        "section_title": chunk.section_title,
                        "similarity": similarity,
                        "chunk_index": chunk.chunk_index
                    })
            except (json.JSONDecodeError, TypeError):
                continue

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    finally:
        db.close()


def search_chunks_by_keyword(
    query: str,
    organization_id: int,
    matter_id: int,
    top_k: int = 10,
    legal_area: Optional[LegalArea] = None
) -> List[dict]:
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
    query_embedding: List[float],
    law_code: str = None,
    top_k: int = 5,
    similarity_threshold: float = 0.5,
    legal_area: Optional[LegalArea] = None
) -> List[dict]:
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


def hybrid_search(
    query: str,
    organization_id: int,
    matter_id: int,
    top_k: int = 5,
    embedding_weight: float = 0.7,
    include_laws: bool = True,
    legal_area: Optional[LegalArea] = None
) -> List[dict]:
    embedding_provider = None
    try:
        from app.services.embeddings import get_embedding_provider
        embedding_provider = get_embedding_provider()
        query_embedding = embedding_provider.generate_embedding(query)
        embedding_results = search_chunks_by_embedding(
            query_embedding, organization_id, matter_id, top_k * 2,
            legal_area=legal_area
        )
    except Exception:
        embedding_results = []

    keyword_results = search_chunks_by_keyword(
        query, organization_id, matter_id, top_k * 2,
        legal_area=legal_area
    )

    seen_ids = set()
    final_results = []

    for result in embedding_results:
        chunk_id = result["chunk_id"]
        if chunk_id not in seen_ids:
            result["source"] = "embedding"
            result["combined_score"] = result["similarity"] * embedding_weight
            final_results.append(result)
            seen_ids.add(chunk_id)

    max_keyword_count = max((r["keyword_count"] for r in keyword_results), default=1)

    for result in keyword_results:
        chunk_id = result["chunk_id"]
        if chunk_id not in seen_ids:
            keyword_score = result["keyword_count"] / max_keyword_count
            result["source"] = "keyword"
            result["combined_score"] = keyword_score * (1 - embedding_weight)
            final_results.append(result)
            seen_ids.add(chunk_id)

    # Buscar en leyes si está habilitado
    if include_laws and embedding_provider:
        try:
            law_results = search_laws_by_embedding(
                query_embedding, top_k=top_k, legal_area=legal_area
            )
            for result in law_results:
                result["source"] = "law"
                result["document_id"] = None
                result["page_number"] = None
                result["section_title"] = f"{result['law_name']} - Art. {result['article_number']}" if result['article_number'] else result['law_name']
                result["combined_score"] = result["similarity"] * 0.8  # Prioridad alta para leyes
                final_results.append(result)
        except Exception:
            pass

    final_results.sort(key=lambda x: x["combined_score"], reverse=True)
    return final_results[:top_k]
