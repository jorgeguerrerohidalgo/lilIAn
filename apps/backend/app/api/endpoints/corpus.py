"""Corpus legal endpoints — Fase 1.

Surface for the BCN-derived law corpus:
- search the corpus with optional hierarchical + temporal filters
- fetch related norms (BCN relations graph)
- expose the catalog of norms already ingested
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.norm_catalog import NormCatalog, NormType
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.rag import hybrid_search

router = APIRouter(prefix="/corpus", tags=["corpus"])


class CorpusChunkResult(BaseModel):
    chunk_id: int
    law_code: str
    law_name: str
    article_number: Optional[str] = None
    jerarquia_path: Optional[str] = None
    libro: Optional[str] = None
    titulo: Optional[str] = None
    capitulo: Optional[str] = None
    content: str
    rrf_score: float
    source: str


class CorpusSearchResponse(BaseModel):
    query: str
    total: int
    chunks: list[CorpusChunkResult]


class RelatedNorm(BaseModel):
    bcn_id: str
    titulo: str
    relation_type: str
    article_ref: Optional[str] = None
    direction: str  # "from" (this norm modifies the other) | "to"


class NormSummary(BaseModel):
    id: int
    bcn_id: str
    tipo: str
    numero: Optional[str] = None
    titulo: str
    estado: str
    legal_area: Optional[str] = None
    chunk_count: int


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@router.get("/search", response_model=CorpusSearchResponse)
def search_corpus(
    q: str = Query(..., min_length=3, description="Texto de búsqueda"),
    legal_area: Optional[str] = Query(None, description="Filtrar por área legal"),
    law_code: Optional[str] = Query(None, description="Filtrar por código de ley"),
    libro: Optional[str] = Query(None, description="Filtrar por libro (ej. 'PRIMERO')"),
    capitulo: Optional[str] = Query(None, description="Filtrar por capítulo"),
    as_of: Optional[date] = Query(None, description="Fecha para filtrar por versionado temporal"),
    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Búsqueda RAG en el corpus legal chileno.

    Combina embedding + keyword search con Reciprocal Rank Fusion.
    Filtros disponibles:
      - legal_area: laboral | civil | penal | comercial | tributario | ...
      - law_code   : bcn_id específico
      - libro      : nombre del libro (solo aplica a Códigos)
      - capitulo   : nombre del capítulo
      - as_of      : fecha — solo versiones vigentes en esa fecha

    Devuelve los top_k chunks rankeados, cada uno con su jerarquía
    para que la UI pueda citarlos con precisión.
    """
    # ``hybrid_search`` is the wrong entry point here — it filters on
    # ``document_chunks.organization_id / matter_id``, but the corpus
    # legal lives in ``law_chunks`` (no org/matter scoping). The
    # matching function is ``search_laws_by_embedding`` which already
    # supports ``law_code``, ``legal_area``, ``libro``, ``capitulo``,
    # and ``as_of`` filters. Hybrid keyword + vector is layered in
    # below.
    from app.services.embeddings import get_embedding_provider
    from app.services.rag import (
        search_laws_by_embedding,
        search_laws_by_keyword,
        _RRF_K_DEFAULT,
    )

    provider = get_embedding_provider()
    if provider.provider_name == "dummy":
        # No real embeddings available — fall back to keyword-only.
        embedding_results: list[dict] = []
    else:
        try:
            query_embedding = provider.generate_embedding(q)
            # Use a low threshold because text-embedding-3-small returns
            # similarities in the 0.4-0.8 range for clear matches and the
            # previous default of 0.3 was clipping almost everything.
            # -0.4 lets through anything that's even remotely related and
            # lets the RRF ranker sort. See services/rag.py:_RRF_K_DEFAULT.
            embedding_results = search_laws_by_embedding(
                query_embedding,
                law_code=law_code,
                top_k=top_k * 3,
                legal_area=legal_area,
                query_text=q,
                as_of=as_of,
                libro=libro,
                capitulo=capitulo,
                similarity_threshold=-0.4,
            )
        except Exception:
            embedding_results = []

    keyword_results = search_laws_by_keyword(
        q, top_k=top_k * 3,
        legal_area=legal_area, as_of=as_of, libro=libro, capitulo=capitulo,
    )

    # Re-route keyword_results to the corpus space (the underlying
    # ``search_chunks_by_keyword`` still hits ``document_chunks`` which
    # the corpus doesn't use; in practice the vector search above
    # covers it). If the user really wants keyword-only corpus search
    # we add a dedicated ``search_laws_by_keyword`` later.
    merged: dict[int, dict] = {}
    for rank, r in enumerate(embedding_results, 1):
        cid = r["chunk_id"]
        merged[cid] = {
            **r,
            "source": "embedding",
            "embedding_rank": rank,
            "rrf_score": 1.0 / (_RRF_K_DEFAULT + rank),
        }
    for rank, r in enumerate(keyword_results, 1):
        cid = r["chunk_id"]
        if cid in merged:
            merged[cid]["source"] = "both"
            merged[cid]["keyword_rank"] = rank
            merged[cid]["rrf_score"] += 1.0 / (_RRF_K_DEFAULT + rank)
        else:
            merged[cid] = {
                **r,
                "source": "keyword",
                "keyword_rank": rank,
                "rrf_score": 1.0 / (_RRF_K_DEFAULT + rank),
            }
    results = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)[:top_k]

    # Re-query with law_code if provided (the helper signature doesn't
    # accept law_code directly so we filter in Python).
    if law_code:
        results = [r for r in results if r.get("law_code") == law_code]

    # Decorate each row with the hierarchical fields. We do a single
    # batched query to avoid N+1.
    chunk_ids = [r["chunk_id"] for r in results if r.get("chunk_id")]
    hierarchy = _fetch_hierarchy(db, chunk_ids)

    chunks = [
        CorpusChunkResult(
            chunk_id=r["chunk_id"],
            law_code=r.get("law_code", ""),
            law_name=r.get("law_name", ""),
            article_number=r.get("article_number"),
            jerarquia_path=hierarchy.get(r["chunk_id"], {}).get("jerarquia_path"),
            libro=hierarchy.get(r["chunk_id"], {}).get("libro"),
            titulo=hierarchy.get(r["chunk_id"], {}).get("titulo"),
            capitulo=hierarchy.get(r["chunk_id"], {}).get("capitulo"),
            content=r.get("content", ""),
            rrf_score=r.get("rrf_score", 0.0),
            source=r.get("source", ""),
        )
        for r in results
    ]
    return CorpusSearchResponse(query=q, total=len(chunks), chunks=chunks)


def _fetch_hierarchy(db: Session, chunk_ids: list[int]) -> dict[int, dict]:
    if not chunk_ids:
        return {}
    rows = db.execute(
        text(
            "SELECT id, jerarquia_path, libro, titulo, capitulo "
            "FROM law_chunks WHERE id = ANY(:ids)"
        ),
        {"ids": chunk_ids},
    ).fetchall()
    return {
        row[0]: {
            "jerarquia_path": row[1],
            "libro": row[2],
            "titulo": row[3],
            "capitulo": row[4],
        }
        for row in rows
    }


# ---------------------------------------------------------------------------
# Related norms (BCN relations graph)
# ---------------------------------------------------------------------------

@router.get("/norms/{bcn_id}/related", response_model=list[RelatedNorm])
def get_related_norms(
    bcn_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return edges in the BCN relations graph for a given norm.

    Each edge carries ``direction`` ("from" if the norm is the source,
    "to" if the norm is the target) and ``relation_type``
    (modifica | deroga | rectifica | refunde | prorroga | reglamenta).
    """
    norm = db.query(NormCatalog).filter(NormCatalog.bcn_id == bcn_id).first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found in catalog")

    rows = db.execute(
        text("""
            SELECT r.relation_type, r.article_ref,
                   from_n.bcn_id AS from_bcn_id, from_n.titulo AS from_titulo,
                   to_n.bcn_id   AS to_bcn_id,   to_n.titulo   AS to_titulo
              FROM norm_relations r
              JOIN norm_catalog from_n ON from_n.id = r.from_norm_id
              JOIN norm_catalog to_n   ON to_n.id   = r.to_norm_id
             WHERE r.from_norm_id = :nid OR r.to_norm_id = :nid
        """),
        {"nid": norm.id},
    ).fetchall()

    out = []
    for row in rows:
        relation_type, article_ref, from_bcn, from_titulo, to_bcn, to_titulo = row
        if from_bcn == bcn_id:
            out.append(RelatedNorm(
                bcn_id=to_bcn,
                titulo=to_titulo or "",
                relation_type=str(relation_type),
                article_ref=article_ref,
                direction="to",
            ))
        else:
            out.append(RelatedNorm(
                bcn_id=from_bcn,
                titulo=from_titulo or "",
                relation_type=str(relation_type),
                article_ref=article_ref,
                direction="from",
            ))
    return out


# ---------------------------------------------------------------------------
# Catalog list (for the /precedents filter dropdown)
# ---------------------------------------------------------------------------

@router.get("/norms", response_model=list[NormSummary])
def list_norms(
    legal_area: Optional[str] = Query(None, description="Filtrar por área legal"),
    tipo: Optional[NormType] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the norms in our local catalog.

    Used by the /precedents filter UI to populate the law_code dropdown
    without having to call the BCN SPARQL endpoint on every page load.
    """
    q = db.query(NormCatalog)
    if legal_area is not None:
        q = q.filter(NormCatalog.legal_area == legal_area)
    if tipo is not None:
        q = q.filter(NormCatalog.tipo == tipo)
    rows = q.order_by(NormCatalog.titulo).limit(200).all()
    return [
        NormSummary(
            id=n.id,
            bcn_id=n.bcn_id,
            tipo=n.tipo.value if hasattr(n.tipo, "value") else str(n.tipo),
            numero=n.numero,
            titulo=n.titulo,
            estado=n.estado,
            legal_area=n.legal_area,
            chunk_count=n.chunk_count or 0,
        )
        for n in rows
    ]
