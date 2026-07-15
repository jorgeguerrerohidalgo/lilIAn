"""
Document Classification Service
Uses LLM to automatically detect the type of document uploaded.
"""

from typing import Optional
import logging

from app.core.database import SessionLocal
from app.models.document import Document
from app.core.config import settings

logger = logging.getLogger(__name__)


DOCUMENT_TYPES = {
    "identity_card": "Cédula de identidad chilena (RUT/Run) o documento de identificación",
    "contract": "Contrato de cualquier tipo (arriendo, trabajo, compraventa, mutuo, etc.)",
    "company_certificate": "Certificado de existencia de empresa, certificado de vigencia, extracto de escritura social",
    "pay_slip": "Liquidación de sueldo, nómina de pago, boleta de remuneraciones",
    "birth_certificate": "Certificado de nacimiento, partida de nacimiento",
    "family_registry": "Registro civil de familia, certificado de estado familiar",
    "receipt": "Comprobante de pago, factura, boleta, recibo",
    "legal_proceeding": "Demanda, querella, resolución judicial, notificación judicial",
    "property_registry": "Certificado de dominio, certificado de hipotecas, registro de propiedad",
    "consent_form": "Formulario de consentimiento informado, autorización",
    "correspondence": "Carta, email impreso, notificación, comunicación oficial",
    "bylaws": "Estatutos de empresa, reglamento interno, pacto social",
    "power_of_attorney": "Poder notarial, representación legal",
    "debt_instrument": "Pagaré, letra de cambio, cheque, documento de deuda",
    "unknown": "No pudo determinarse el tipo de documento"
}


DOCUMENT_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "description": "Tipo de documento identificado",
            "enum": list(DOCUMENT_TYPES.keys())
        },
        "confidence": {
            "type": "string",
            "description": "Nivel de confianza en la clasificación",
            "enum": ["high", "medium", "low"]
        },
        "extracted_data": {
            "type": "object",
            "description": "Datos extraídos del documento",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nombres de personas mencionados"
                },
                "rut": {
                    "type": "string",
                    "description": "RUT o RUN de persona (formato XX.XXX.XXX-X)"
                },
                "company_name": {
                    "type": "string",
                    "description": "Nombre de empresa mencionado"
                },
                "company_rut": {
                    "type": "string",
                    "description": "RUT de empresa (formato XX.XXX.XXX-X)"
                },
                "addresses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Direcciones mencionadas"
                },
                "dates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fechas relevantes encontradas"
                },
                "amounts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Montos de dinero mencionados"
                }
            }
        },
        "reasoning": {
            "type": "string",
            "description": "Razonamiento breve de por qué se clasificó así"
        }
    },
    "required": ["document_type", "confidence"]
}


async def classify_document(document_id: int) -> dict:
    """
    Uses LLM to classify a document and extract basic structured data.

    Args:
        document_id: ID of the document to classify

    Returns:
        dict with document_type, confidence, extracted_data, and reasoning
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        if not document.extracted_text or len(document.extracted_text.strip()) < 50:
            return {
                "document_type": "unknown",
                "confidence": "low",
                "extracted_data": {},
                "reasoning": "Document has insufficient text for classification"
            }

        from app.services.llm import get_llm_provider
        provider = get_llm_provider()

        document_type_list = "\n".join([f"- {k}: {v}" for k, v in DOCUMENT_TYPES.items()])

        prompt = f"""Analiza el siguiente documento y clasifícalo según su tipo.

DOCUMENTO:
{document.extracted_text[:15000]}

TIPOS DE DOCUMENTOS POSIBLES:
{document_type_list}

Proporciona la clasificación en formato JSON siguiendo el esquema especificado."""

        system_prompt = """Eres un clasificador de documentos legales chileno. Analiza el documento y clasifícalo en una de las categorías proporcionadas. Sé preciso y usa el sentido común."""

        try:
            result = provider.generate_structured(prompt, system_prompt, DOCUMENT_CLASSIFICATION_SCHEMA)

            detected_type = result.get("document_type", "unknown")
            confidence = result.get("confidence", "low")
            extracted_data = result.get("extracted_data", {})
            reasoning = result.get("reasoning", "")

            document.detected_document_type = detected_type
            db.commit()

            logger.info(f"Document {document_id} classified as {detected_type} (confidence: {confidence})")

            return {
                "document_type": detected_type,
                "confidence": confidence,
                "extracted_data": extracted_data,
                "reasoning": reasoning
            }

        except Exception as e:
            logger.error(f"LLM classification failed for document {document_id}: {e}")
            return {
                "document_type": "unknown",
                "confidence": "low",
                "extracted_data": {},
                "reasoning": f"Classification failed: {str(e)}"
            }

    finally:
        db.close()


async def classify_all_matter_documents(matter_id: int, organization_id: int) -> list[dict]:
    """
    Classifies all unclassified documents for a matter.

    Args:
        matter_id: ID of the matter
        organization_id: ID of the organization

    Returns:
        List of classification results
    """
    db = SessionLocal()
    try:
        documents = db.query(Document).filter(
            Document.matter_id == matter_id,
            Document.organization_id == organization_id,
            Document.status == "processed",
            Document.detected_document_type.is_(None)
        ).all()

        results = []
        for doc in documents:
            result = await classify_document(doc.id)
            results.append({
                "document_id": doc.id,
                "filename": doc.original_filename,
                **result
            })

        return results

    finally:
        db.close()
