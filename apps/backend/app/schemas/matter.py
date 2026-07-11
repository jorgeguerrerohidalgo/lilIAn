from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MatterBase(BaseModel):
    title: str
    matter_type: str = "other"
    description: Optional[str] = None
    urgency: str = "medium"
    counterparty_name: Optional[str] = None
    relevant_date: Optional[datetime] = None
    source_channel: Optional[str] = None


class MatterCreate(MatterBase):
    organization_id: int


class MatterUpdate(BaseModel):
    title: Optional[str] = None
    matter_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    urgency: Optional[str] = None
    counterparty_name: Optional[str] = None
    relevant_date: Optional[datetime] = None
    assigned_lawyer_id: Optional[int] = None


class MatterResponse(MatterBase):
    id: int
    organization_id: int
    created_by_user_id: int
    assigned_lawyer_id: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
