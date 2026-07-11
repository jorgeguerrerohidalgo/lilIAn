from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from datetime import datetime
from app.core.database import Base


class RiskItem(Base):
    __tablename__ = "risk_items"

    id = Column(Integer, primary_key=True, index=True)
    analysis_report_id = Column(Integer, ForeignKey("analysis_reports.id"), nullable=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    level = Column(String(20), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    source_fragment = Column(Text)
    impact = Column(Text)
    recommendation = Column(Text)
    confidence = Column(String(50), default="medium")
    review_status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
