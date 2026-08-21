from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

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
    # S2-01 / S2-04: Stripe linkage. Nullable so existing rows keep working.
    # ``stripe_customer_id`` is the ``cus_…`` of the paying customer;
    # ``stripe_subscription_id`` is the ``sub_…`` for the active recurring
    # subscription. We persist both so the webhook can reconcile even if
    # the metadata on the Stripe side is missing (e.g. older events).
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)
    stripe_status = Column(String(50), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    trial_ends_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
