"""
Data Extraction Service

Extracts structured data from documents using LLM.
"""

from typing import Optional
from pydantic import BaseModel
import logging

from app.core.database import SessionLocal
from app.models.document import Document

logger = logging.getLogger(__name__)


class ExtractedDocumentData(BaseModel):
    """Structured data extracted from a document."""
    names: list[str] = []
    rut: Optional[str] = None
    company_name: Optional[str] = None
    company_rut: Optional[str] = None
    addresses: list[str] = []
    dates: list[str] = []
    amounts: list[str] = []
    roles: list[str] = []  # deudor, acreedor, representante, etc.
    email: Optional[str] = None
    phone: Optional[str] = None


DATA_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "names": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Nombres completos de personas mencionadas en el documento"
        },
        "rut": {
            "type": "string",
            "description": "RUT o RUN de persona (formato XX.XXX.XXX-X)"
        },
        "company_name": {
            "type": "string",
            "description": "Nombre de empresa o sociedad mencionada"
        },
        "company_rut": {
            "type": "string",
            "description": "RUT de empresa (formato XX.XXX.XXX-X)"
        },
        "addresses": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Direcciones mencionadas en el documento"
        },
        "dates": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Fechas relevantes mencionadas (formato legible)"
        },
        "amounts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Montos de dinero mencionados con su descripción"
        },
        "roles": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Roles mencionados (arrendador, arrendatario, empleador, trabajador, etc.)"
        },
        "email": {
            "type": "string",
            "description": "Correo electrónico de contacto"
        },
        "phone": {
            "type": "string",
            "description": "Teléfono de contacto"
        }
    }
}


async def extract_document_data(document_id: int) -> ExtractedDocumentData:
    """
    Uses LLM to extract structured data from a document.

    Args:
        document_id: ID of the document to extract from

    Returns:
        ExtractedDocumentData with all extracted fields
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        if not document.extracted_text or len(document.extracted_text.strip()) < 50:
            return ExtractedDocumentData()

        from app.services.llm import get_llm_provider
        provider = get_llm_provider()

        prompt = f"""Extrae datos estructurados del siguiente documento legal chileno.

DOCUMENTO:
{document.extracted_text[:20000]}

Extrae toda la información estructurada que puedas. Si un campo no está presente, omítelo o deja el array vacío.
Presta especial atención a:
- RUT de personas (formato XX.XXX.XXX-X)
- RUT de empresas (mismo formato)
- Nombres completos de personas
- Nombre de empresas
- Direcciones completas
- Montos de dinero con su moneda (CLP, UF, etc.)
- Fechas importantes
- Roles de las partes (arrendador/arrendatario, empleador/trabajador, etc.)
- Emails y teléfonos de contacto

Proporciona la información en formato JSON siguiendo el esquema especificado."""

        system_prompt = """Eres un extractor de datos de documentos legales chilenos. Extrae información estructurada con alta precisión. Para RUTs usa el formato XX.XXX.XXX-X."""

        try:
            result = provider.generate_structured(prompt, system_prompt, DATA_EXTRACTION_SCHEMA)

            return ExtractedDocumentData(
                names=result.get("names", []),
                rut=result.get("rut"),
                company_name=result.get("company_name"),
                company_rut=result.get("company_rut"),
                addresses=result.get("addresses", []),
                dates=result.get("dates", []),
                amounts=result.get("amounts", []),
                roles=result.get("roles", []),
                email=result.get("email"),
                phone=result.get("phone")
            )

        except Exception as e:
            logger.error(f"LLM data extraction failed for document {document_id}: {e}")
            return ExtractedDocumentData()

    finally:
        db.close()


async def extract_all_matter_documents_data(matter_id: int, organization_id: int) -> dict[int, ExtractedDocumentData]:
    """
    Extract data from all processed documents for a matter.

    Args:
        matter_id: ID of the matter
        organization_id: ID of the organization

    Returns:
        Dict mapping document_id to ExtractedDocumentData
    """
    db = SessionLocal()
    try:
        documents = db.query(Document).filter(
            Document.matter_id == matter_id,
            Document.organization_id == organization_id,
            Document.status == "processed"
        ).all()

        results = {}
        for doc in documents:
            try:
                extracted = await extract_document_data(doc.id)
                results[doc.id] = extracted
            except Exception as e:
                logger.error(f"Failed to extract data from document {doc.id}: {e}")
                results[doc.id] = ExtractedDocumentData()

        return results

    finally:
        db.close()
