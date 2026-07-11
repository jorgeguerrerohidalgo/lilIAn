from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
from datetime import datetime
from app.core.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    plan_name = Column(String(100), nullable=False)
    status = Column(String(50), default="active")
    documents_limit = Column(Integer, default=100)
    analyses_limit = Column(Integer, default=50)
    users_limit = Column(Integer, default=5)
    monthly_price = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    renews_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(String(100), nullable=False)
    quantity = Column(Integer, default=1)
    event_metadata = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    description = Column(String)
    documents_limit = Column(Integer, default=100)
    analyses_limit = Column(Integer, default=50)
    users_limit = Column(Integer, default=5)
    monthly_price = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
