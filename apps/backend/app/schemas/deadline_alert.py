from datetime import date, datetime

from pydantic import BaseModel


class DeadlineAlertBase(BaseModel):
    title: str
    description: str | None = None
    event_type: str
    due_date: date
    days_remaining: int | None = None
    is_overdue: bool = False
    urgency: str
    importance_score: int = 50
    status: str = "pending"
    source_event: str | None = None
    legal_reference: str | None = None
    consequence: str | None = None


class DeadlineAlertCreate(DeadlineAlertBase):
    organization_id: int
    matter_id: int
    document_id: int | None = None
    user_id: int | None = None


class DeadlineAlertUpdate(BaseModel):
    status: str | None = None
    acknowledged_by: int | None = None
    resolved_by: int | None = None


class DeadlineAlertResponse(DeadlineAlertBase):
    id: int
    organization_id: int
    matter_id: int
    document_id: int | None = None
    user_id: int | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    acknowledged_by: int | None = None
    resolved_by: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeadlineAlertWithMatter(DeadlineAlertResponse):
    matter_title: str | None = None


class AlertsSummary(BaseModel):
    total: int
    overdue: int
    critical: int
    high: int
    medium: int
    low: int
    by_matter: list[dict]
