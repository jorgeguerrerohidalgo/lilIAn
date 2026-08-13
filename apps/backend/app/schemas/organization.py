from datetime import datetime

from pydantic import BaseModel


class OrganizationBase(BaseModel):
    name: str
    type: str = "individual"
    rut: str | None = None
    billing_email: str | None = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: int
    plan_id: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
