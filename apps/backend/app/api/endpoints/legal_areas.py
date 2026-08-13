
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps.auth import require_organization
from app.models.organization_member import OrganizationMember

router = APIRouter(prefix="/legal-areas", tags=["legal-areas"])


class LegalAreaResponse(BaseModel):
    code: str
    name: str
    description: str


LEGAL_AREAS_INFO: dict[str, dict] = {
    "labor": {
        "name": "Derecho Laboral",
        "description": "Contratos, remuneraciones, despidos, negociación colectiva"
    },
    "civil": {
        "name": "Derecho Civil",
        "description": "Contratos, obligaciones, arriendos, responsabilidad civil"
    },
    "consumer": {
        "name": "Derecho del Consumidor",
        "description": "Protección al consumidor, cláusulas abusivas, garantías"
    },
    "family": {
        "name": "Derecho de Familia",
        "description": "Divorcio, custodia, pensiones alimenticias, medidas de protección"
    },
    "commerce": {
        "name": "Derecho Comercial",
        "description": "Sociedades, títulos de crédito, insolvencia, contratos mercantiles"
    },
    "penal": {
        "name": "Derecho Penal",
        "description": "Delitos, medidas cautelares, procedimiento penal"
    },
    "other": {
        "name": "Otras áreas",
        "description": "Consultas generales o áreas no clasificadas"
    },
}


@router.get("", response_model=list[LegalAreaResponse])
def list_legal_areas(
    membership: OrganizationMember = Depends(require_organization),
):
    """
    Lista todas las áreas legales disponibles en el sistema.

    S2-02: use ``require_organization`` so anonymous users can't enumerate
    the catalogue. The membership dependency is unused at runtime but
    enforced for RBAC consistency with every other endpoint.
    """
    return [
        LegalAreaResponse(
            code=code,
            name=info["name"],
            description=info["description"]
        )
        for code, info in LEGAL_AREAS_INFO.items()
    ]
