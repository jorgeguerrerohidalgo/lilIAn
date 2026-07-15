"""
Required Documents Catalog by Matter Type

Defines which documents are required, recommended, and what validations
should be performed for each type of legal matter.
"""

from app.models.matter import MatterType


class DocumentRequirement:
    """Represents requirements for a specific document type in a matter."""

    def __init__(
        self,
        required: bool = False,
        recommended: bool = False,
        description: str = ""
    ):
        self.required = required
        self.recommended = recommended
        self.description = description


REQUIRED_DOCUMENTS: dict[str, dict] = {
    str(MatterType.CONTRACT_REVIEW): {
        "required": ["identity_card", "contract"],
        "recommended": ["receipt", "correspondence"],
        "validations": ["name_consistency", "rut_consistency", "date_consistency"],
        "description": "Revisión de contratos generales"
    },
    str(MatterType.LEASE): {
        "required": ["identity_card", "contract"],
        "recommended": ["property_registry", "receipt"],
        "validations": ["name_consistency", "rut_consistency", "property_address_consistency"],
        "description": "Casos de arriendo de bienes raíces"
    },
    str(MatterType.LABOR): {
        "required": ["identity_card", "contract", "pay_slip"],
        "recommended": ["company_certificate", "correspondence"],
        "validations": ["name_consistency", "rut_consistency", "employer_consistency", "date_consistency"],
        "description": "Casos laborales y de empleo"
    },
    str(MatterType.COMPANY): {
        "required": ["identity_card", "company_certificate"],
        "recommended": ["contract", "bylaws", "power_of_attorney"],
        "validations": ["representative_consistency", "company_name_consistency", "rut_consistency"],
        "description": "Casos de empresas y sociedades"
    },
    str(MatterType.DATA_PROTECTION): {
        "required": ["identity_card", "consent_form"],
        "recommended": ["contract", "correspondence"],
        "validations": ["name_consistency", "rut_consistency"],
        "description": "Casos de protección de datos personales"
    },
    str(MatterType.CONSUMER): {
        "required": ["identity_card", "contract", "receipt"],
        "recommended": ["correspondence"],
        "validations": ["name_consistency", "rut_consistency", "date_consistency", "amount_consistency"],
        "description": "Casos de derecho del consumidor"
    },
    str(MatterType.FAMILY): {
        "required": ["identity_card", "birth_certificate", "family_registry"],
        "recommended": ["correspondence", "legal_proceeding"],
        "validations": ["name_consistency", "rut_consistency", "family_relationship", "date_consistency"],
        "description": "Casos de derecho de familia"
    },
    str(MatterType.DEBT): {
        "required": ["identity_card", "contract", "debt_instrument"],
        "recommended": ["receipt", "correspondence"],
        "validations": ["name_consistency", "rut_consistency", "amount_consistency", "debtor_creditor_consistency"],
        "description": "Casos de deudas y cobranza"
    },
    str(MatterType.OTHER): {
        "required": ["identity_card"],
        "recommended": ["contract", "correspondence"],
        "validations": ["name_consistency", "rut_consistency"],
        "description": "Otros casos legales"
    }
}


DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "identity_card": "Cédula de Identidad (RUT)",
    "contract": "Contrato",
    "company_certificate": "Certificado de Empresa",
    "pay_slip": "Liquidación de Sueldo",
    "birth_certificate": "Certificado de Nacimiento",
    "family_registry": "Registro de Familia",
    "receipt": "Comprobante de Pago",
    "legal_proceeding": "Procedimiento Legal",
    "property_registry": "Registro de Propiedad",
    "consent_form": "Formulario de Consentimiento",
    "correspondence": "Correspondencia",
    "bylaws": "Estatutos",
    "power_of_attorney": "Poder Notarial",
    "debt_instrument": "Instrumento de Deuda",
    "unknown": "Tipo Desconocido"
}


VALIDATION_TYPES: dict[str, dict] = {
    "name_consistency": {
        "name": "Consistencia de Nombres",
        "description": "Verifica que los nombres sean idénticos en todos los documentos",
        "severity": "error"
    },
    "rut_consistency": {
        "name": "Consistencia de RUT",
        "description": "Verifica que el RUT sea el mismo en todos los documentos",
        "severity": "error"
    },
    "date_consistency": {
        "name": "Consistencia de Fechas",
        "description": "Verifica que las fechas sean coherentes entre documentos",
        "severity": "warning"
    },
    "company_name_consistency": {
        "name": "Consistencia de Nombre de Empresa",
        "description": "Verifica coherencia del nombre de empresa en certificados",
        "severity": "error"
    },
    "representative_consistency": {
        "name": "Consistencia de Representantes",
        "description": "Verifica que los representantes legales sean los mismos",
        "severity": "error"
    },
    "amount_consistency": {
        "name": "Consistencia de Montos",
        "description": "Verifica coherencia de montos mencionados",
        "severity": "warning"
    },
    "debtor_creditor_consistency": {
        "name": "Consistencia Deudor-Acreedor",
        "description": "Verifica que deudor y acreedor sean consistentes",
        "severity": "error"
    },
    "property_address_consistency": {
        "name": "Consistencia de Dirección de Propiedad",
        "description": "Verifica que la dirección de la propiedad sea consistente",
        "severity": "warning"
    },
    "family_relationship": {
        "name": "Consistencia de Relaciones Familiares",
        "description": "Verifica coherencia en relaciones familiares",
        "severity": "error"
    },
    "employer_consistency": {
        "name": "Consistencia de Empleador",
        "description": "Verifica que el empleador sea consistente en documentos laborales",
        "severity": "error"
    }
}


def get_matter_requirements(matter_type: str) -> dict:
    """
    Get document requirements for a specific matter type.

    Args:
        matter_type: The matter type string

    Returns:
        dict with required, recommended, validations, and description
    """
    normalized = matter_type.lower() if matter_type else ""

    for key in REQUIRED_DOCUMENTS:
        if key.lower() == normalized:
            return REQUIRED_DOCUMENTS[key]

    return REQUIRED_DOCUMENTS.get(str(MatterType.OTHER), REQUIRED_DOCUMENTS[str(MatterType.OTHER)])


def get_document_type_label(doc_type: str) -> str:
    """Get human-readable label for a document type."""
    return DOCUMENT_TYPE_LABELS.get(doc_type, doc_type)


def get_validation_info(validation_type: str) -> dict:
    """Get information about a validation type."""
    return VALIDATION_TYPES.get(validation_type, {
        "name": validation_type,
        "description": "Validación desconocida",
        "severity": "warning"
    })
