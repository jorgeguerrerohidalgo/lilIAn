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
    similarity_threshold: float = 0.3,  # DEBUG: lowering from 0.5 to 0.3
    legal_area: Optional[LegalArea] = None
) -> List[dict]:
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

        print(f"[DEBUG RAG] SQL direct result: {len(rows)} rows")

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

        print(f"[DEBUG RAG] Found {len(chunks)} chunks in DB for org={organization_id}, matter={matter_id}")

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
            except (json.JSONDecodeError, TypeError) as e:
                errors += 1
                continue

        print(f"[DEBUG RAG] Chunks processed: {len(results)} passed, {skipped_no_embedding} no embedding, {skipped_threshold} below threshold, {errors} errors")

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
    include_laws: bool = True,
    legal_area: Optional[LegalArea] = None
) -> List[dict]:
    """
    Búsqueda híbrida con Reciprocal Rank Fusion (RRF).
    Combina resultados de embedding y keyword search usando RRF para mejor ranking.
    """
    embedding_provider = None
    try:
        from app.services.embeddings import get_embedding_provider
        embedding_provider = get_embedding_provider()
        query_embedding = embedding_provider.generate_embedding(query)
        print(f"[DEBUG RAG] Query embedding generated, length: {len(query_embedding)}")
        embedding_results = search_chunks_by_embedding(
            query_embedding, organization_id, matter_id, top_k * 3,
            legal_area=legal_area
        )
        print(f"[DEBUG RAG] Document embedding results: {len(embedding_results)}")
    except Exception as e:
        print(f"[DEBUG RAG] Embedding search failed: {e}")
        import traceback
        traceback.print_exc()
        embedding_results = []

    keyword_results = search_chunks_by_keyword(
        query, organization_id, matter_id, top_k * 3,
        legal_area=legal_area
    )
    print(f"[DEBUG RAG] Keyword results: {len(keyword_results)}")

    # RRF: Reciprocal Rank Fusion para combinar rankings
    RRF_K = 60  # Constante típica para RRF

    # Crear diccionario de resultados por chunk_id
    all_results = {}

    # Agregar resultados de embedding search con su ranking
    for rank, result in enumerate(embedding_results, 1):
        chunk_id = result["chunk_id"]
        result["source"] = "embedding"
        result["embedding_rank"] = rank
        result["keyword_rank"] = None
        result["embedding_score"] = result["similarity"]
        result["keyword_score"] = 0
        all_results[chunk_id] = result

    # Agregar/actualizar resultados de keyword search
    for rank, result in enumerate(keyword_results, 1):
        chunk_id = result["chunk_id"]
        if chunk_id in all_results:
            # Ya existe, actualizar ranks y scores
            all_results[chunk_id]["keyword_rank"] = rank
            all_results[chunk_id]["keyword_score"] = result["keyword_count"]
            all_results[chunk_id]["source"] = "both"  # Aparece en ambos
        else:
            # Nuevo resultado solo de keyword
            result["source"] = "keyword"
            result["embedding_rank"] = None
            result["keyword_rank"] = rank
            result["embedding_score"] = 0
            result["keyword_score"] = result["keyword_count"]
            all_results[chunk_id] = result

    # Calcular RRF score para cada resultado
    final_results = []
    for chunk_id, result in all_results.items():
        rrf_score = 0

        # RRF de embedding (si tiene ranking)
        if result["embedding_rank"]:
            rrf_score += 1 / (RRF_K + result["embedding_rank"])

        # RRF de keyword (si tiene ranking)
        if result["keyword_rank"]:
            rrf_score += 1 / (RRF_K + result["keyword_rank"])

        # Normalizar: documentos que aparecen en ambos rankings得到 bonus
        if result["source"] == "both":
            rrf_score *= 1.5  # 50% bonus por estar en ambos

        result["rrf_score"] = rrf_score
        result["combined_score"] = rrf_score
        final_results.append(result)

    # Agregar leyes como fallback si hay pocos resultados
    doc_count = len(final_results)
    if include_laws and embedding_provider and doc_count < 3:
        try:
            law_results = search_laws_by_embedding(
                query_embedding, top_k=top_k, legal_area=legal_area
            )
            print(f"[DEBUG RAG] Law results (fallback): {len(law_results)}")
            for rank, result in enumerate(law_results, 1):
                result["source"] = "law"
                result["document_id"] = None
                result["page_number"] = None
                result["section_title"] = f"{result['law_name']} - Art. {result['article_number']}" if result['article_number'] else result['law_name']
                result["rrf_score"] = 1 / (RRF_K + rank) * 0.3  # Peso bajo para leyes
                result["combined_score"] = result["rrf_score"]
                final_results.append(result)
        except Exception:
            pass

    # Ordenar por RRF score
    final_results.sort(key=lambda x: x["rrf_score"], reverse=True)

    # Debug: print top 5 results
    print(f"[DEBUG RAG] Final {len(final_results)} results, top 5:")
    for i, r in enumerate(final_results[:5]):
        src = r.get('source', 'unknown')
        score = r.get('rrf_score', 0)
        title = r.get('section_title', r.get('content', '')[:50])
        print(f"  {i+1}. source={src}, rrf={score:.4f}, title={title}")

    return final_results[:top_k]
