from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Datos personales/empresa
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    # TODO S5.5: integrar con SII para auto-rellenar razón social,
    # régimen tributario, inicio de actividades y dirección comercial
    # cuando el RUT corresponde a una persona jurídica. Ver
    # docs/TODO_S5.5_SII_DT_SUSESO.md para el alcance completo
    # (Ettiene SII, DT y SUSESO, multi-sprint). Hoy el dato lo ingresa
    # manualmente el abogado.
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
