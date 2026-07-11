from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrganizationBase(BaseModel):
    name: str
    type: str = "individual"
    rut: Optional[str] = None
    billing_email: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: int
    plan_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
