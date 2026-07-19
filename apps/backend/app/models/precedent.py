"""
Precedent Model - Sentencias judiciales chilenas
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Precedent(Base):
    __tablename__ = "precedents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)

    # Identificacion unica de la sentencia
    court = Column(String(200), nullable=False, index=True)  # ej: "Corte Suprema"
    tribunal = Column(String(200), nullable=False, index=True)  # ej: "2° Juzgado Civil de Santiago"
    year = Column(Integer, nullable=False, index=True)
    roll_number = Column(String(50), nullable=False)  # ej: "1234-2023"
    full_citation = Column(String(500), nullable=True)  # ej: "CS, 15.01.2020, Rol 1234-2019"

    # Clasificacion
    legal_area = Column(String(50), nullable=False, index=True, default="other")
    matter_type = Column(String(100), nullable=True)  # ej: "Contrato de Arriendo"

    # Contenido
    summary = Column(Text, nullable=False)  # Resumen de la sentencia
    reasoning = Column(Text, nullable=True)  # Considerandos
    decision = Column(Text, nullable=True)  # Fallo
    disposition = Column(Text, nullable=True)  # Parte dispositiva
    voces = Column(String(500), nullable=True)  # Materias juridicas (Separatas/Voces)

    # Metadata adicional
    ponente = Column(String(200), nullable=True)  # Ministro redactor
    type = Column(String(50), nullable=True)  # sentenia, resolucion, Auto, etc.
    precedent_metadata = Column(Text, nullable=True)  # JSON con metadata adicional

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="precedents")

    __table_args__ = (
        Index("idx_precedents_court_year", "court", "year"),
        Index("idx_precedents_legal_area", "legal_area"),
    )

    def __repr__(self):
        return f"<Precedent {self.court} {self.year} Rol {self.roll_number}>"
