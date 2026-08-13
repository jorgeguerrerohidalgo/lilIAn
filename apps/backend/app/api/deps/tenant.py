from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.organization_member import OrganizationMember
from app.models.user import User


class TenantContext:
    """Contexto del tenant (organización) actual para una petición."""

    def __init__(self, organization_id: int, membership: OrganizationMember):
        self.organization_id = organization_id
        self.membership = membership

    @property
    def role(self):
        return self.membership.role


def _resolve_organization_id(request: Request) -> int:
    """Lee el organization_id de la URL path o del header X-Organization-Id."""
    org_id = request.path_params.get("organization_id")
    if org_id is not None:
        try:
            return int(org_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="organization_id inválido",
            )

    header_value = request.headers.get("X-Organization-Id")
    if header_value:
        try:
            return int(header_value)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Organization-Id inválido",
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Falta organization_id en la ruta o en el header X-Organization-Id",
    )


async def get_tenant_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """Resuelve el tenant actual validando que el usuario pertenece a la organización."""
    organization_id = _resolve_organization_id(request)

    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id == organization_id,
        )
        .first()
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta organización",
        )

    return TenantContext(
        organization_id=organization_id,
        membership=membership,
    )
