from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from datetime import datetime
from app.core.database import Base


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    generated_by_user_id = Column(Integer, ForeignKey("users.id"))
    model_provider = Column(String(100))
    model_name = Column(String(100))
    report_type = Column(String(100), default="preliminary_case_analysis")
    summary = Column(Text)
    facts = Column(Text)
    missing_information = Column(Text)
    next_steps = Column(Text)
    disclaimer = Column(Text)
    confidence = Column(String(50), default="medium")
    status = Column(String(50), default="generated")
    validation_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
