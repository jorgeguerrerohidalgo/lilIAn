from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.models.template import Template
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.api.deps.auth import get_current_user, require_organization

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    template_type: str
    name: str
    description: Optional[str] = None
    content: str
    is_global: bool = False


class TemplateResponse(BaseModel):
    id: int
    template_type: str
    name: str
    description: Optional[str]
    content: str
    is_global: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


DEFAULT_TEMPLATES = [
    {
        "template_type": "prompt",
        "name": "Análisis de contrato de prestación de servicios",
        "description": "Prompt estándar para análisis de contratos de prestación de servicios",
        "content": """Eres un asistente legal chileno especializado en análisis documental y revisión de contratos.

Analiza el siguiente contrato de prestación de servicios bajo enfoque chileno.

OBJETIVO:
1. Identificar tipo de contrato y partes.
2. Resumir el documento.
3. Identificar obligaciones, montos, plazos y cláusulas relevantes.
4. Detectar riesgos.
5. Clasificar riesgos en verde, amarillo, rojo o gris.
6. Indicar información faltante.
7. Sugerir preguntas para revisión humana.
8. Proponer próximos pasos.

REGLAS:
- No inventes normas ni cites fuentes no presentes en el contexto.
- Si el documento es ambiguo, dilo claramente.
- Si falta información, indícalo.
- No entregues asesoría definitiva.
- Usa lenguaje claro para cliente y útil para abogado.

FORMATO DE SALIDA:
- Resumen ejecutivo
- Datos identificados
- Riesgos detectados con nivel
- Información faltante
- Preguntas sugeridas
- Próximos pasos
- Advertencia profesional"""
    },
    {
        "template_type": "prompt",
        "name": "Análisis de contrato de arriendo",
        "description": "Prompt estándar para análisis de contratos de arriendo",
        "content": """Eres un asistente legal chileno especializado en análisis de contratos de arriendo en Chile.

Analiza el siguiente contrato de arriendo considerando la Ley de Arriendos de Predios Urbanos y el Código Civil chileno.

OBJETIVO:
1. Identificar las partes y el inmueble.
2. Resumir condiciones del arriendo.
3. Identificar plazo, renta y garantías.
4. Detectar obligaciones de ambas partes.
5. Identificar cláusulas de término anticipado.
6. Detectar riesgos para el arrendatario/arrendador.
7. Verificar cumplimiento de requisitos legales.

REGLAS:
- Considera normativa chilena vigente.
- No inventes interpretaciones sin base legal.
- Si hay cláusulas abusivas, identifícalas.
- Recomienda revisión profesional para contratos importantes.

SALIDA:
- Resumen del contrato
- Condiciones principales
- Riesgos detectados
- Recomendaciones
- Advertencia legal"""
    },
    {
        "template_type": "email",
        "name": "Respuesta a cliente - Consulta preliminar",
        "description": "Plantilla de email para responder a clientes con análisis preliminar",
        "content": """Estimado/a [NOMBRE_CLIENTE]:

Gracias por confiar en nuestros servicios y proporcionar los antecedentes de su consulta.

Hemos realizado un análisis preliminar de la información y documentos entregados, el cual se adjunta a este correo.

RESUMEN DEL ANÁLISIS:
[RESUMEN_DEL_ANÁLISIS]

CONCLUSIONES PRINCIPALES:
[CONCLUSIONES]

RIESGOS IDENTIFICADOS:
[RIESGOS]

INFORMACIÓN REQUERIDA:
[INFORMACIÓN_FALTANTE]

PRÓXIMOS PASOS:
[PRÓXIMOS_PASOS]

IMPORTANTE: Este análisis es preliminar y tiene carácter informativo. No constituye asesoría legal definitiva. Para tomar decisiones legales importantes, es fundamental la revisión de un abogado habilitado.

Quedamos a su disposición para agendar una reunión y profundizar en su caso.

Saludos cordiales,

[NOMBRE_ABOGADO]
[COLEGIOS/ESPECIALIDADES]"""
    },
    {
        "template_type": "checklist",
        "name": "Checklist de documentos para revisión contractual",
        "description": "Lista de verificación de documentos necesarios para revisión de contratos",
        "content": """CHECKLIST DE DOCUMENTOS PARA REVISIÓN CONTRACTUAL

DOCUMENTOS BÁSICOS:
☐ Contrato original o borrador
☐ Identificación de partes (RUT/DNI)
☐ Antecedentes de la empresa si aplica

PARA CONTRATOS DE SERVICIOS:
☐ Alcance de servicios
☐ Especificaciones técnicas
☐ Cronograma de entregas
☐ Condiciones de pago
☐ Garantías

PARA CONTRATOS DE ARRIENDO:
☐ Título de dominio
☐ Certificado de gravámenes
☐ Planilla de contribuciones
☐ Estado de pago de servicios

PARA CONTRATOS LABORALES:
☐ Contrato de trabajo
☐ Finiquitos anteriores
☐ Certificados de cotizaciones
☐ Liquidaciones de sueldo

PARA EMPRESAS:
☐ Escritura de constitución
☐ Rut de empresa
☐ Estados financieros recientes
☐ Poderes vigentes

NOTAS:
[Espacio para notas adicionales]"""
    }
]


@router.get("", response_model=List[TemplateResponse])
def list_templates(
    template_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    query = db.query(Template).filter(
        (Template.organization_id == membership.organization_id) |
        (Template.is_global == True)
    )

    if template_type:
        query = query.filter(Template.template_type == template_type)

    templates = query.order_by(Template.name).all()

    if not templates:
        default_rows = []
        for tmpl in DEFAULT_TEMPLATES:
            default_rows.append(Template(
                template_type=tmpl["template_type"],
                name=tmpl["name"],
                description=tmpl["description"],
                content=tmpl["content"],
                is_global=True,
                organization_id=membership.organization_id
            ))
            db.add(default_rows[-1])
        db.commit()
        templates = db.query(Template).filter(
            (Template.organization_id == membership.organization_id) |
            (Template.is_global == True)
        ).filter(
            Template.template_type == template_type if template_type else True
        ).order_by(Template.name).all()

    return [
        TemplateResponse(
            id=t.id,
            template_type=t.template_type,
            name=t.name,
            description=t.description,
            content=t.content,
            is_global=t.is_global,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat()
        )
        for t in templates
    ]


@router.post("", response_model=TemplateResponse, status_code=201)
def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    template = Template(
        organization_id=membership.organization_id if not template_data.is_global else None,
        template_type=template_data.template_type,
        name=template_data.name,
        description=template_data.description,
        content=template_data.content,
        is_global=template_data.is_global,
        created_by_user_id=current_user.id
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return TemplateResponse(
        id=template.id,
        template_type=template.template_type,
        name=template.name,
        description=template.description,
        content=template.content,
        is_global=template.is_global,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat()
    )


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    template = db.query(Template).filter(Template.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    if not template.is_global and template.organization_id != membership.organization_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    return TemplateResponse(
        id=template.id,
        template_type=template.template_type,
        name=template.name,
        description=template.description,
        content=template.content,
        is_global=template.is_global,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat()
    )


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    template = db.query(Template).filter(Template.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    if template.is_global:
        raise HTTPException(status_code=403, detail="No se puede eliminar plantilla global")

    if template.organization_id != membership.organization_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    db.delete(template)
    db.commit()
