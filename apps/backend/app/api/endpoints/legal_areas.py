from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List

from app.models.legal_area import LegalArea
from app.models.user import User
from app.api.deps.auth import get_current_user

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


@router.get("", response_model=List[LegalAreaResponse])
def list_legal_areas(
    current_user: User = Depends(get_current_user),
):
    """
    Lista todas las áreas legales disponibles en el sistema.
    """
    return [
        LegalAreaResponse(
            code=code,
            name=info["name"],
            description=info["description"]
        )
        for code, info in LEGAL_AREAS_INFO.items()
    ]
