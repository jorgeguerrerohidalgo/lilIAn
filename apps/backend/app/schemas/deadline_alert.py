from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class DeadlineAlertBase(BaseModel):
    title: str
    description: Optional[str] = None
    event_type: str
    due_date: date
    days_remaining: Optional[int] = None
    is_overdue: bool = False
    urgency: str
    importance_score: int = 50
    status: str = "pending"
    source_event: Optional[str] = None
    legal_reference: Optional[str] = None
    consequence: Optional[str] = None


class DeadlineAlertCreate(DeadlineAlertBase):
    organization_id: int
    matter_id: int
    document_id: Optional[int] = None
    user_id: Optional[int] = None


class DeadlineAlertUpdate(BaseModel):
    status: Optional[str] = None
    acknowledged_by: Optional[int] = None
    resolved_by: Optional[int] = None


class DeadlineAlertResponse(DeadlineAlertBase):
    id: int
    organization_id: int
    matter_id: int
    document_id: Optional[int] = None
    user_id: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    resolved_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeadlineAlertWithMatter(DeadlineAlertResponse):
    matter_title: Optional[str] = None


class AlertsSummary(BaseModel):
    total: int
    overdue: int
    critical: int
    high: int
    medium: int
    low: int
    by_matter: List[dict]
