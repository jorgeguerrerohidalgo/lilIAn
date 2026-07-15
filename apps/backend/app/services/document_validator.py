"""
Document Validator Service

Performs cross-document validation to detect inconsistencies,
missing documents, and other validation issues.
"""

from typing import Optional
from pydantic import BaseModel
import logging

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.matter import Matter
from app.services.required_documents import (
    get_matter_requirements,
    get_document_type_label,
    get_validation_info
)
from app.services.data_extractor import extract_all_matter_documents_data, ExtractedDocumentData

logger = logging.getLogger(__name__)


class Inconsistency(BaseModel):
    """Represents an inconsistency found between documents."""
    validation_type: str
    field: str
    doc_ids: list[int]
    values: dict[int, str]
    severity: str  # "error", "warning"
    message: str


class ValidationResult(BaseModel):
    """Result of document validation for a matter."""
    is_valid: bool
    inconsistencies: list[Inconsistency]
    missing_required: list[str]
    missing_recommended: list[str]
    warnings: list[str]
    document_types_found: dict[str, int]
    validation_summary: dict


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    if not name:
        return ""
    return name.lower().strip().replace(".", "").replace(",", "")


def _normalize_rut(rut: Optional[str]) -> str:
    """Normalize a RUT for comparison."""
    if not rut:
        return ""
    return rut.lower().strip().replace(".", "").replace("-", "").replace(" ", "")


def _names_consistent(names: dict[int, list[str]]) -> list[Inconsistency]:
    """Check if names are consistent across documents."""
    inconsistencies = []

    all_names: dict[str, list[int]] = {}
    for doc_id, doc_names in names.items():
        for name in doc_names:
            normalized = _normalize_name(name)
            if normalized:
                if normalized not in all_names:
                    all_names[normalized] = []
                all_names[normalized].append(doc_id)

    if len(all_names) > 1:
        doc_id_to_names = {doc_id: names.get(doc_id, []) for doc_id in names.keys()}
        inconsistencies.append(Inconsistency(
            validation_type="name_consistency",
            field="name",
            doc_ids=list(names.keys()),
            values={doc_id: ", ".join(doc_names) for doc_id, doc_names in names.items()},
            severity="error",
            message=f"Se encontraron {len(all_names)} nombres diferentes en los documentos: {', '.join(all_names.keys())}"
        ))

    return inconsistencies


def _rut_consistent(ruts: dict[int, Optional[str]]) -> list[Inconsistency]:
    """Check if RUTs are consistent across documents."""
    inconsistencies = []

    normalized_ruts: dict[str, list[int]] = {}
    for doc_id, rut in ruts.items():
        normalized = _normalize_rut(rut)
        if normalized:
            if normalized not in normalized_ruts:
                normalized_ruts[normalized] = []
            normalized_ruts[normalized].append(doc_id)

    if len(normalized_ruts) > 1:
        inconsistencies.append(Inconsistency(
            validation_type="rut_consistency",
            field="rut",
            doc_ids=list(ruts.keys()),
            values={doc_id: rut or "sin RUT" for doc_id, rut in ruts.items()},
            severity="error",
            message=f"Se encontraron {len(normalized_ruts)} RUTs diferentes: {', '.join(normalized_ruts.keys())}"
        ))

    return inconsistencies


def _company_names_consistent(
    company_names: dict[int, Optional[str]]
) -> list[Inconsistency]:
    """Check if company names are consistent."""
    inconsistencies = []

    normalized_names: dict[str, list[int]] = {}
    for doc_id, name in company_names.items():
        if name:
            normalized = _normalize_name(name)
            if normalized not in normalized_names:
                normalized_names[normalized] = []
            normalized_names[normalized].append(doc_id)

    if len(normalized_names) > 1:
        inconsistencies.append(Inconsistency(
            validation_type="company_name_consistency",
            field="company_name",
            doc_ids=list(company_names.keys()),
            values={doc_id: name or "sin nombre" for doc_id, name in company_names.items()},
            severity="error",
            message=f"Se encontraron nombres de empresa diferentes: {', '.join(normalized_names.keys())}"
        ))

    return inconsistencies


def _roles_consistent(roles: dict[int, list[str]]) -> list[Inconsistency]:
    """Check if roles are consistent (e.g., same employer across labor docs)."""
    inconsistencies = []

    all_roles: dict[str, list[int]] = {}
    for doc_id, doc_roles in roles.items():
        for role in doc_roles:
            normalized = _normalize_name(role)
            if normalized:
                if normalized not in all_roles:
                    all_roles[normalized] = []
                all_roles[normalized].append(doc_id)

    if len(all_roles) > 1:
        inconsistencies.append(Inconsistency(
            validation_type="role_consistency",
            field="roles",
            doc_ids=list(roles.keys()),
            values={doc_id: ", ".join(doc_roles) for doc_id, doc_roles in roles.items()},
            severity="warning",
            message=f"Se encontraron diferentes roles: {', '.join(all_roles.keys())}"
        ))

    return inconsistencies


async def validate_matter_documents(
    matter_id: int,
    organization_id: int
) -> ValidationResult:
    """
    Validates all documents for a matter against the requirements.

    Args:
        matter_id: ID of the matter
        organization_id: ID of the organization

    Returns:
        ValidationResult with all validation issues found
    """
    db = SessionLocal()
    try:
        matter = db.query(Matter).filter(Matter.id == matter_id).first()
        if not matter:
            raise ValueError(f"Matter {matter_id} not found")

        matter_type_value = matter.matter_type.value if hasattr(matter.matter_type, 'value') else str(matter.matter_type)
        requirements = get_matter_requirements(matter_type_value)

        documents = db.query(Document).filter(
            Document.matter_id == matter_id,
            Document.organization_id == organization_id,
            Document.status == "processed"
        ).all()

        document_types_found: dict[str, int] = {}
        for doc in documents:
            doc_type = doc.detected_document_type or "unknown"
            document_types_found[doc_type] = document_types_found.get(doc_type, 0) + 1

        required_types = set(requirements.get("required", []))
        recommended_types = set(requirements.get("recommended", []))
        validation_types = requirements.get("validations", [])

        present_types = set(document_types_found.keys())

        missing_required = list(required_types - present_types)
        missing_recommended = list(recommended_types - present_types)

        all_data = await extract_all_matter_documents_data(matter_id, organization_id)

        inconsistencies: list[Inconsistency] = []
        warnings: list[str] = []

        if "name_consistency" in validation_types:
            names = {doc_id: data.names for doc_id, data in all_data.items() if data.names}
            inconsistencies.extend(_names_consistent(names))

        if "rut_consistency" in validation_types:
            ruts = {doc_id: data.rut for doc_id, data in all_data.items()}
            inconsistencies.extend(_rut_consistent(ruts))

        if "company_name_consistency" in validation_types:
            company_names = {doc_id: data.company_name for doc_id, data in all_data.items()}
            inconsistencies.extend(_company_names_consistent(company_names))

        if "employer_consistency" in validation_types or "role_consistency" in validation_types:
            roles = {doc_id: data.roles for doc_id, data in all_data.items() if data.roles}
            inconsistencies.extend(_roles_consistent(roles))

        error_count = sum(1 for i in inconsistencies if i.severity == "error")
        is_valid = len(missing_required) == 0 and error_count == 0

        validation_summary = {
            "total_documents": len(documents),
            "document_types_found": document_types_found,
            "required_types": list(required_types),
            "required_found": list(required_types & present_types),
            "required_missing": missing_required,
            "recommended_found": list(recommended_types & present_types),
            "recommended_missing": missing_recommended,
            "total_inconsistencies": len(inconsistencies),
            "errors": sum(1 for i in inconsistencies if i.severity == "error"),
            "warnings": sum(1 for i in inconsistencies if i.severity == "warning")
        }

        if missing_required:
            warnings.append(f"Documentos requeridos faltantes: {', '.join([get_document_type_label(t) for t in missing_required])}")

        if missing_recommended:
            warnings.append(f"Documentos recomendados faltantes: {', '.join([get_document_type_label(t) for t in missing_recommended])}")

        return ValidationResult(
            is_valid=is_valid,
            inconsistencies=inconsistencies,
            missing_required=missing_required,
            missing_recommended=missing_recommended,
            warnings=warnings,
            document_types_found=document_types_found,
            validation_summary=validation_summary
        )

    finally:
        db.close()
