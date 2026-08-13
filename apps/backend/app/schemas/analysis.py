import json
from datetime import datetime

from pydantic import BaseModel, field_validator


class RiskItemResponse(BaseModel):
    id: int
    level: str
    title: str
    description: str | None = None
    source_fragment: str | None = None
    impact: str | None = None
    recommendation: str | None = None
    confidence: str
    review_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisReportResponse(BaseModel):
    id: int
    matter_id: int
    model_provider: str | None = None
    model_name: str | None = None
    report_type: str
    summary: str | None = None
    facts: str | None = None
    missing_information: str | None = None
    next_steps: str | None = None
    disclaimer: str | None = None
    confidence: str
    status: str
    validation_summary: dict | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator('validation_summary', mode='before')
    @classmethod
    def parse_validation_summary(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return None

    class Config:
        from_attributes = True


class AnalysisReportDetailResponse(AnalysisReportResponse):
    risks: list[RiskItemResponse] = []

    class Config:
        from_attributes = True


class GenerateAnalysisRequest(BaseModel):
    matter_id: int
