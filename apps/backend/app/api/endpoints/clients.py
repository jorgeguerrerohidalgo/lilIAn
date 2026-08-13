from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import get_db
from app.models.client import Client
from app.models.organization_member import OrganizationMember
from app.models.user import User

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientBase(BaseModel):
    name: str
    company_name: str | None = None
    rut: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientResponse(ClientBase):
    id: int
    organization_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    client_data: ClientCreate,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    client = Client(
        organization_id=membership.organization_id,
        created_by_user_id=current_user.id,
        name=client_data.name,
        company_name=client_data.company_name,
        rut=client_data.rut,
        email=client_data.email,
        phone=client_data.phone,
        address=client_data.address,
        notes=client_data.notes,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    return client


@router.get("", response_model=list[ClientResponse])
def list_clients(
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    query = db.query(Client).filter(
        Client.organization_id == membership.organization_id,
        Client.is_active
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Client.name.ilike(search_term)) |
            (Client.company_name.ilike(search_term)) |
            (Client.rut.ilike(search_term)) |
            (Client.email.ilike(search_term))
        )

    clients = query.order_by(Client.name).all()
    return clients


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db),
):
    # S1-10: hide soft-deleted clients by default. Callers that need to
    # audit deleted records can opt in via ``include_inactive=True``.
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == membership.organization_id,
        Client.is_active,
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    client_data: ClientCreate,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == membership.organization_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    for field, value in client_data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)

    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.organization_id == membership.organization_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Soft delete
    client.is_active = False
    db.commit()
