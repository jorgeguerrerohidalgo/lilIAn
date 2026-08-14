"""
Data Extraction Service

Extracts structured data from documents using LLM.
"""

import logging

from pydantic import BaseModel

from app.core.database import SessionLocal
from app.models.document import Document

logger = logging.getLogger(__name__)


class ExtractedDocumentData(BaseModel):
    """Structured data extracted from a document."""
    names: list[str] = []
    rut: str | None = None
    company_name: str | None = None
    company_rut: str | None = None
    addresses: list[str] = []
    dates: list[str] = []
    amounts: list[str] = []
    roles: list[str] = []  # deudor, acreedor, representante, etc.
    email: str | None = None
    phone: str | None = None


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


_EXTRACTION_MIN_TEXT = 50
_EXTRACTION_TEXT_SAMPLE = 20_000


async def extract_document_data(document_id: int) -> ExtractedDocumentData:
    """Uses LLM to extract structured data from a document.

    S4-24: extracted the LLM call + result-shaping into helpers so the
    top-level reads as: load → text-validate → run extraction → map
    fields → return.
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        if not _has_sufficient_text(document):
            return ExtractedDocumentData()

        try:
            result = await _run_extraction(document)
        except Exception as exc:
            logger.error(f"LLM data extraction failed for document {document_id}: {exc}")
            return ExtractedDocumentData()
        return _map_extraction_result(result)
    finally:
        db.close()


def _has_sufficient_text(document) -> bool:
    return bool(
        document.extracted_text
        and len(document.extracted_text.strip()) >= _EXTRACTION_MIN_TEXT
    )


async def _run_extraction(document) -> dict:
    """Single LLM call. Returns the raw structured dict from the provider."""
    from app.services.llm import get_llm_provider

    provider = get_llm_provider()
    prompt = _build_extraction_prompt(document)
    system_prompt = (
        "Eres un extractor de datos de documentos legales chilenos. "
        "Extrae información estructurada con alta precisión. Para RUTs "
        "usa el formato XX.XXX.XXX-X."
    )
    return provider.generate_structured(prompt, system_prompt, DATA_EXTRACTION_SCHEMA)


def _build_extraction_prompt(document) -> str:
    sample = (document.extracted_text or "")[:_EXTRACTION_TEXT_SAMPLE]
    return (
        "Extrae datos estructurados del siguiente documento legal chileno.\n\n"
        f"DOCUMENTO:\n{sample}\n\n"
        "Extrae toda la información estructurada que puedas. Si un campo "
        "no está presente, omítelo o deja el array vacío.\n"
        "Presta especial atención a:\n"
        "- RUT de personas (formato XX.XXX.XXX-X)\n"
        "- RUT de empresas (mismo formato)\n"
        "- Nombres completos de personas\n"
        "- Nombre de empresas\n"
        "- Direcciones completas\n"
        "- Montos de dinero con su moneda (CLP, UF, etc.)\n"
        "- Fechas importantes\n"
        "- Roles de las partes (arrendador/arrendatario, empleador/trabajador, etc.)\n"
        "- Emails y teléfonos de contacto\n\n"
        "Proporciona la información en formato JSON siguiendo el esquema "
        "especificado."
    )


def _map_extraction_result(result: dict) -> ExtractedDocumentData:
    """Map the LLM provider's structured dict to the typed result model."""
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
        phone=result.get("phone"),
    )

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
