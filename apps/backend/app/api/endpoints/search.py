from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.models.organization_member import OrganizationMember
from app.models.matter import Matter
from app.models.user import User
from app.api.deps.auth import get_current_user, require_organization
from app.services import rag

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    matter_id: int
    top_k: int = 5
    use_embeddings: bool = True


class SearchResultItem(BaseModel):
    chunk_id: int
    document_id: int
    content: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    score: float
    source: str


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    query: str
    total: int


@router.post("", response_model=SearchResponse)
def search_documents(
    search_data: SearchRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == search_data.matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    if search_data.use_embeddings:
        try:
            from app.services.embeddings import get_embedding_provider
            from app.services.rag import hybrid_search

            provider = get_embedding_provider()
            query_embedding = provider.generate_embedding(search_data.query)

            results = rag.hybrid_search(
                query=search_data.query,
                organization_id=membership.organization_id,
                matter_id=search_data.matter_id,
                top_k=search_data.top_k
            )
        except Exception:
            results = rag.search_chunks_by_keyword(
                query=search_data.query,
                organization_id=membership.organization_id,
                matter_id=search_data.matter_id,
                top_k=search_data.top_k
            )
            for r in results:
                r["source"] = "keyword"
                r["score"] = r.get("keyword_count", 0) / 10.0
    else:
        results = rag.search_chunks_by_keyword(
            query=search_data.query,
            organization_id=membership.organization_id,
            matter_id=search_data.matter_id,
            top_k=search_data.top_k
        )
        for r in results:
            r["source"] = "keyword"
            r["score"] = r.get("keyword_count", 0) / 10.0

    formatted_results = []
    for r in results:
        formatted_results.append(SearchResultItem(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            content=r["content"],
            page_number=r.get("page_number"),
            section_title=r.get("section_title"),
            score=r.get("combined_score", r.get("score", 0)),
            source=r.get("source", "unknown")
        ))

    return SearchResponse(
        results=formatted_results,
        query=search_data.query,
        total=len(formatted_results)
    )
