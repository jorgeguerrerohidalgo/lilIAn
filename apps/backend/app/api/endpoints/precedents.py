"""
Precedents API Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps.auth import get_current_user, require_organization
from app.models.user import User
from app.models.organization_member import OrganizationMember
from app.services.precedent_rag import (
    search_precedents_by_embedding,
    search_precedents_by_keyword,
    get_precedent_context
)

router = APIRouter(prefix="/precedents", tags=["precedents"])


class PrecedentSearchResponse(BaseModel):
    results: List[dict]
    query: str
    total: int
    search_type: str


class PrecedentCreateRequest(BaseModel):
    court: str
    tribunal: str
    year: int
    roll_number: str
    full_citation: Optional[str] = None
    legal_area: str
    matter_type: Optional[str] = None
    summary: str
    reasoning: Optional[str] = None
    decision: Optional[str] = None
    disposition: Optional[str] = None
    voces: Optional[str] = None
    ponente: Optional[str] = None
    type: Optional[str] = None


class PrecedentResponse(BaseModel):
    id: int
    court: str
    tribunal: str
    year: int
    roll_number: str
    full_citation: Optional[str]
    legal_area: str
    matter_type: Optional[str]
    summary: str
    reasoning: Optional[str]
    decision: Optional[str]
    disposition: Optional[str]
    voces: Optional[str]


@router.get("/search", response_model=PrecedentSearchResponse)
def search_precedents(
    q: str = Query(..., min_length=3, description="Texto de busqueda"),
    court: Optional[str] = Query(None, description="Filtrar por tribunal"),
    year: Optional[int] = Query(None, description="Filtrar por año"),
    legal_area: Optional[str] = Query(None, description="Filtrar por área legal"),
    matter_type: Optional[str] = Query(None, description="Filtrar por tipo de materia"),
    search_type: str = Query("hybrid", description="Tipo de busqueda: semantic, keyword, o hybrid"),
    top_k: int = Query(5, ge=1, le=20, description="Numero de resultados"),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Busca precedentes judiciales usando busqueda semantica o por palabras clave."""
    results = []
    used_search_type = search_type

    if search_type == "semantic" or search_type == "hybrid":
        try:
            from app.services.embeddings import get_embedding_provider
            provider = get_embedding_provider()
            query_embedding = provider.generate_embedding(q)

            results = search_precedents_by_embedding(
                query_embedding,
                court=court,
                year=year,
                legal_area=legal_area,
                matter_type=matter_type,
                top_k=top_k
            )
            used_search_type = "semantic"
        except Exception as e:
            if search_type == "semantic":
                raise HTTPException(status_code=500, detail=f"Error en busqueda semantica: {str(e)}")

    if not results and (search_type == "keyword" or search_type == "hybrid"):
        results = search_precedents_by_keyword(
            q,
            court=court,
            year=year,
            legal_area=legal_area,
            matter_type=matter_type,
            top_k=top_k
        )
        used_search_type = "keyword"

    return PrecedentSearchResponse(
        results=results,
        query=q,
        total=len(results),
        search_type=used_search_type
    )


@router.get("/context")
def get_precedents_context(
    q: str = Query(..., min_length=3, description="Texto para buscar precedentes"),
    court: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    legal_area: Optional[str] = Query(None),
    top_k: int = Query(3, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Obtiene contexto de precedentes para integracion con RAG."""
    context = get_precedent_context(
        query=q,
        court=court,
        year=year,
        legal_area=legal_area,
        top_k=top_k
    )

    if not context:
        return {"context": "No se encontraron precedentes relevantes para esta consulta.", "count": 0}

    return {"context": context, "count": top_k}


@router.get("/courts")
def list_courts(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Lista tribunales disponibles."""
    from app.models.precedent import Precedent

    courts = db.query(Precedent.court).distinct().all()
    return {"courts": [c[0] for c in courts if c[0]]}


@router.get("/legal-areas")
def list_legal_areas_in_precedents(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Lista areas legales disponibles en precedentes."""
    from app.models.precedent import Precedent

    areas = db.query(Precedent.legal_area).distinct().all()
    return {"legal_areas": [a[0] for a in areas if a[0]]}


@router.post("/", response_model=PrecedentResponse, status_code=201)
def create_precedent(
    precedent_data: PrecedentCreateRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Crea un nuevo precedente."""
    from app.models.precedent import Precedent
    from app.services.precedent_rag import index_precedent

    # Check if already exists
    existing = db.query(Precedent).filter(
        Precedent.court == precedent_data.court,
        Precedent.year == precedent_data.year,
        Precedent.roll_number == precedent_data.roll_number,
        Precedent.organization_id == membership.organization_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Este precedente ya existe")

    precedent = Precedent(
        organization_id=membership.organization_id,
        court=precedent_data.court,
        tribunal=precedent_data.tribunal,
        year=precedent_data.year,
        roll_number=precedent_data.roll_number,
        full_citation=precedent_data.full_citation,
        legal_area=precedent_data.legal_area,
        matter_type=precedent_data.matter_type,
        summary=precedent_data.summary,
        reasoning=precedent_data.reasoning,
        decision=precedent_data.decision,
        disposition=precedent_data.disposition,
        voces=precedent_data.voces,
        ponente=precedent_data.ponente,
        type=precedent_data.type
    )

    db.add(precedent)
    db.commit()
    db.refresh(precedent)

    # Index the precedent for RAG
    index_precedent(precedent.id, db)

    return precedent


@router.get("/{precedent_id}", response_model=PrecedentResponse)
def get_precedent(
    precedent_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Obtiene un precedente por ID."""
    from app.models.precedent import Precedent

    precedent = db.query(Precedent).filter(
        Precedent.id == precedent_id,
        Precedent.organization_id == membership.organization_id
    ).first()

    if not precedent:
        raise HTTPException(status_code=404, detail="Precedente no encontrado")

    return precedent
