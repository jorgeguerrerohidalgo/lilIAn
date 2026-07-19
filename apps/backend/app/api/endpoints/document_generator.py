"""
Document Generator API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps.auth import get_current_user, require_organization
from app.models.user import User
from app.models.organization_member import OrganizationMember
from app.models.matter import Matter
from app.services.document_generator import (
    get_all_templates,
    get_template_by_id,
    get_templates_by_category,
    get_categories,
    generate_document,
    validate_variables,
    extract_variables_from_matter
)

router = APIRouter(prefix="/doc-templates", tags=["document-generator"])


class GenerateDocumentRequest(BaseModel):
    template_id: str
    variables: dict
    matter_id: Optional[int] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    variables: List[Any]


@router.get("/templates", response_model=List[TemplateResponse])
def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Lista todos los templates disponibles."""
    if category:
        templates = get_templates_by_category(category)
    else:
        templates = get_all_templates()

    return [
        TemplateResponse(
            id=t["id"],
            name=t["name"],
            category=t["category"],
            description=t.get("description", ""),
            variables=t.get("variables", [])
        )
        for t in templates
    ]


@router.get("/templates/categories")
def list_categories(
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Lista todas las categorías de templates."""
    return {"categories": get_categories()}


@router.get("/templates/{template_id}")
def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Obtiene un template específico con sus variables."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template no encontrado")

    return TemplateResponse(
        id=template["id"],
        name=template["name"],
        category=template["category"],
        description=template.get("description", ""),
        variables=template.get("variables", [])
    )


class SuggestVariablesRequest(BaseModel):
    matter_id: int
    matter_type: Optional[str] = None


@router.post("/suggest-variables")
def suggest_variables(
    template_id: str,
    request: SuggestVariablesRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Extrae variables sugeridas desde los documentos de un matter.

    Usa LLM para analizar los documentos y sugerir valores para
    completar el template seleccionado.
    """
    # Validar que el matter existe y pertenece a la organización
    matter = db.query(Matter).filter(
        Matter.id == request.matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    # Extraer variables usando LLM
    result = extract_variables_from_matter(
        template_id=template_id,
        matter_id=request.matter_id,
        organization_id=membership.organization_id,
        matter_type=request.matter_type or (matter.matter_type.value if hasattr(matter.matter_type, 'value') else str(matter.matter_type))
    )

    return result


@router.post("/generate")
def create_document(
    request: GenerateDocumentRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    """Genera un documento desde un template."""
    # Validar template existe
    template = get_template_by_id(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template no encontrado")

    # Si hay matter_id, obtener contexto
    context = {}
    if request.matter_id:
        matter = db.query(Matter).filter(
            Matter.id == request.matter_id,
            Matter.organization_id == membership.organization_id
        ).first()

        if matter:
            context = {
                "ciudad": "Santiago",  # Podría tomarse del matter si tuviera ese campo
                "materia": matter.matter_type.value if hasattr(matter.matter_type, 'value') else str(matter.matter_type),
                "descripcion_caso": matter.description,
            }

    # Generar documento
    result = generate_document(
        template_id=request.template_id,
        variables=request.variables,
        context=context
    )

    if not result["success"]:
        return {
            "success": False,
            "errors": result["errors"],
            "content": None,
            "document_name": None
        }

    return {
        "success": True,
        "errors": [],
        "content": result["content"],
        "document_name": result["document_name"],
        "template_name": template["name"]
    }


@router.post("/templates/{template_id}/validate")
def validate_doc_variables(
    template_id: str,
    variables: dict,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """Valida las variables antes de generar."""
    validation = validate_variables(template_id, variables)
    return validation
