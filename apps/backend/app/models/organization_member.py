import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.core.database import Base


class MemberRole(enum.StrEnum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    LAWYER = "LAWYER"
    COMPANY_USER = "COMPANY_USER"
    CLIENT = "CLIENT"
    VIEWER = "VIEWER"


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(MemberRole), default=MemberRole.CLIENT)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")
