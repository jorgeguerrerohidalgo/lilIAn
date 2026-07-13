from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Datos personales/empresa
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    rut = Column(String(20), nullable=True)  # RUT chileno o CI/Pasaporte
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    # Datos adicionales
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Estado
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    organization = relationship("Organization", back_populates="clients")
    created_by = relationship("User", back_populates="clients")
    matters = relationship("Matter", back_populates="client")
