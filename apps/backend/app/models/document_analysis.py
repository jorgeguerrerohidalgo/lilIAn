from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class DocumentAnalysis(Base):
    """Análisis estructurado de documento individual - estilo Harvey.ai

    No resume el documento sino que extrae y estructura datos.
    """
    __tablename__ = "document_analyses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, unique=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # Tipo de documento detectado
    document_type = Column(String(100))

    # Participantes identificados [{rut, name, role, verified}]
    participants = Column(JSON, default=list)

    # Términos financieros {dates: [], amounts: [], terms: []}
    financial_terms = Column(JSON, default=dict)

    # Obligaciones [{party, type, description}]
    obligations = Column(JSON, default=list)

    # Cláusulas por tipo {penalidades: [], terminacion: [], etc}
    clauses_by_type = Column(JSON, default=dict)

    # Cláusulas inusuales/atípicas detectadas
    unusual_clauses = Column(JSON, default=list)

    # Evaluación de riesgo por cláusula
    risk_assessment = Column(JSON, default=list)

    # Línea de tiempo del contrato
    contract_timeline = Column(JSON, default=list)

    # Referencias legales citadas en el documento
    legal_references = Column(JSON, default=list)

    # Contenido indexado para búsqueda semántica
    indexed_content = Column(Text)

    # Metadatos adicionales
    analysis_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    document = relationship("Document", back_populates="analysis")
