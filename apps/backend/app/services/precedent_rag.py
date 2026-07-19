"""
Precedent RAG Service - Busqueda de precedentes judiciales chilenas
"""
import json
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.precedent import Precedent
from app.services.embeddings import get_embedding_provider


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import numpy as np
    a = np.array(a)
    b = np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def search_precedents_by_embedding(
    query_embedding: List[float],
    court: Optional[str] = None,
    year: Optional[int] = None,
    legal_area: Optional[str] = None,
    matter_type: Optional[str] = None,
    top_k: int = 5,
    similarity_threshold: float = 0.7
) -> List[dict]:
    """Search precedents by semantic similarity."""
    db = SessionLocal()
    try:
        query = db.query(Precedent)

        if court:
            query = query.filter(Precedent.court.ilike(f"%{court}%"))
        if year:
            query = query.filter(Precedent.year == year)
        if legal_area:
            query = query.filter(Precedent.legal_area == legal_area)
        if matter_type:
            query = query.filter(Precedent.matter_type.ilike(f"%{matter_type}%"))

        precedents = query.all()
        results = []

        for p in precedents:
            if not p.precedent_metadata:
                continue
            try:
                stored_embedding = json.loads(p.precedent_metadata)
                if not stored_embedding or "embedding" not in stored_embedding:
                    continue
                similarity = cosine_similarity(query_embedding, stored_embedding["embedding"])
                if similarity >= similarity_threshold:
                    results.append({
                        "id": p.id,
                        "court": p.court,
                        "tribunal": p.tribunal,
                        "year": p.year,
                        "roll_number": p.roll_number,
                        "full_citation": p.full_citation,
                        "legal_area": p.legal_area,
                        "matter_type": p.matter_type,
                        "summary": p.summary,
                        "reasoning": p.reasoning[:500] if p.reasoning else None,
                        "decision": p.decision[:500] if p.decision else None,
                        "disposition": p.disposition,
                        "voces": p.voces,
                        "similarity": round(similarity, 4)
                    })
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    finally:
        db.close()


def search_precedents_by_keyword(
    query: str,
    court: Optional[str] = None,
    year: Optional[int] = None,
    legal_area: Optional[str] = None,
    matter_type: Optional[str] = None,
    top_k: int = 10
) -> List[dict]:
    """Search precedents by keyword in summary/decision."""
    db = SessionLocal()
    try:
        search_pattern = f"%{query}%"

        q = db.query(Precedent).filter(
            (Precedent.summary.ilike(search_pattern)) |
            (Precedent.decision.ilike(search_pattern)) |
            (Precedent.reasoning.ilike(search_pattern)) |
            (Precedent.voces.ilike(search_pattern))
        )

        if court:
            q = q.filter(Precedent.court.ilike(f"%{court}%"))
        if year:
            q = q.filter(Precedent.year == year)
        if legal_area:
            q = q.filter(Precedent.legal_area == legal_area)
        if matter_type:
            q = q.filter(Precedent.matter_type.ilike(f"%{matter_type}%"))

        precedents = q.limit(top_k).all()

        return [{
            "id": p.id,
            "court": p.court,
            "tribunal": p.tribunal,
            "year": p.year,
            "roll_number": p.roll_number,
            "full_citation": p.full_citation,
            "legal_area": p.legal_area,
            "matter_type": p.matter_type,
            "summary": p.summary,
            "decision": p.decision[:500] if p.decision else None,
            "voces": p.voces,
            "match_type": "keyword"
        } for p in precedents]
    finally:
        db.close()


def get_precedent_context(
    query: str,
    court: Optional[str] = None,
    year: Optional[int] = None,
    legal_area: Optional[str] = None,
    top_k: int = 3
) -> str:
    """Returns formatted precedent context for RAG integration."""
    try:
        provider = get_embedding_provider()
        query_embedding = provider.generate_embedding(query)
    except Exception:
        # Fallback to keyword search if embedding fails
        results = search_precedents_by_keyword(
            query, court=court, year=year, legal_area=legal_area, top_k=top_k
        )
        if not results:
            return ""
        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(
                f"[Precedente {i}] {r['court']}, {r['year']}, Rol {r['roll_number']}\n"
                f"Materia: {r.get('legal_area', 'N/A')} | Tipo: {r.get('matter_type', 'N/A')}\n"
                f"Resumen: {r['summary'][:800]}..."
            )
        return "\n\n---\n\n".join(context_parts)

    results = search_precedents_by_embedding(
        query_embedding,
        court=court,
        year=year,
        legal_area=legal_area,
        top_k=top_k
    )

    if not results:
        # Try keyword search as fallback
        results = search_precedents_by_keyword(
            query, court=court, year=year, legal_area=legal_area, top_k=top_k
        )
        if not results:
            return ""

    context_parts = []
    for i, r in enumerate(results, 1):
        context_parts.append(
            f"[Precedente {i}] {r['court']}, {r['year']}, Rol {r['roll_number']}\n"
            f"Materia: {r.get('legal_area', 'N/A')} | Tipo: {r.get('matter_type', 'N/A')}\n"
            f"Resumen: {r['summary'][:800]}...\n"
            f"Fallo: {r.get('decision', 'N/A')[:400]}..."
        )

    return "\n\n---\n\n".join(context_parts)


def index_precedent(precedent_id: int, db: Session) -> bool:
    """Generate and store embedding for a precedent."""
    from app.services.embeddings import get_embedding_provider

    precedent = db.query(Precedent).filter(Precedent.id == precedent_id).first()
    if not precedent:
        return False

    # Combine text for embedding
    text_to_embed = f"{precedent.summary} {precedent.decision or ''} {precedent.voces or ''}"

    try:
        provider = get_embedding_provider()
        embedding = provider.generate_embedding(text_to_embed)

        metadata = {
            "embedding": embedding,
            "indexed_at": "2026-07-17",
            "text_length": len(text_to_embed)
        }

        precedent.precedent_metadata = json.dumps(metadata)
        db.commit()
        return True
    except Exception as e:
        print(f"Error indexing precedent {precedent_id}: {e}")
        return False
