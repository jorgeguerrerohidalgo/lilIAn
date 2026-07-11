from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class MemberRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    LAWYER = "lawyer"
    COMPANY_USER = "company_user"
    CLIENT = "client"
    VIEWER = "viewer"


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(MemberRole), default=MemberRole.CLIENT)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")
