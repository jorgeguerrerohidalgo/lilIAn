from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
import json


class RiskItemResponse(BaseModel):
    id: int
    level: str
    title: str
    description: Optional[str] = None
    source_fragment: Optional[str] = None
    impact: Optional[str] = None
    recommendation: Optional[str] = None
    confidence: str
    review_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisReportResponse(BaseModel):
    id: int
    matter_id: int
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    report_type: str
    summary: Optional[str] = None
    facts: Optional[str] = None
    missing_information: Optional[str] = None
    next_steps: Optional[str] = None
    disclaimer: Optional[str] = None
    confidence: str
    status: str
    validation_summary: Optional[dict] = None
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
    risks: List[RiskItemResponse] = []

    class Config:
        from_attributes = True


class GenerateAnalysisRequest(BaseModel):
    matter_id: int
