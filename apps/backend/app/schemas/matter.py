from datetime import datetime

from pydantic import BaseModel


class MatterBase(BaseModel):
    title: str
    matter_type: str = "other"
    description: str | None = None
    urgency: str = "medium"
    counterparty_name: str | None = None
    relevant_date: datetime | None = None
    source_channel: str | None = None


class MatterCreate(MatterBase):
    organization_id: int | None = None
    client_id: int | None = None


class MatterUpdate(BaseModel):
    title: str | None = None
    matter_type: str | None = None
    description: str | None = None
    status: str | None = None
    urgency: str | None = None
    counterparty_name: str | None = None
    relevant_date: datetime | None = None
    assigned_lawyer_id: int | None = None
    client_id: int | None = None


class MatterResponse(MatterBase):
    id: int
    organization_id: int
    created_by_user_id: int
    client_id: int | None = None
    assigned_lawyer_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    class Config:
        from_attributes = True
