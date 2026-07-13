from enum import Enum

from app.models.matter import MatterType


class LegalArea(str, Enum):
    """Áreas del derecho soportadas por el sistema."""
    LABOR = "labor"
    CIVIL = "civil"
    CONSUMER = "consumer"
    FAMILY = "family"
    COMMERCE = "commerce"
    PENAL = "penal"
    OTHER = "other"


MATTER_TYPE_TO_LEGAL_AREA: dict[str, LegalArea] = {
    MatterType.LABOR.value: LegalArea.LABOR,
    MatterType.CONTRACT_REVIEW.value: LegalArea.CIVIL,
    MatterType.LEASE.value: LegalArea.CIVIL,
    MatterType.DEBT.value: LegalArea.CIVIL,
    MatterType.DATA_PROTECTION.value: LegalArea.CIVIL,
    MatterType.CONSUMER.value: LegalArea.CONSUMER,
    MatterType.FAMILY.value: LegalArea.FAMILY,
    MatterType.COMPANY.value: LegalArea.COMMERCE,
    MatterType.OTHER.value: LegalArea.OTHER,
}


LAW_CODE_TO_LEGAL_AREA: dict[str, LegalArea] = {
    # Códigos principales
    "codigo_trabajo": LegalArea.LABOR,
    "codigo_civil": LegalArea.CIVIL,
    "codigo_comercio": LegalArea.COMMERCE,
    "codigo_penal": LegalArea.PENAL,
    "codigo_procedimiento_penal": LegalArea.PENAL,
    "codigo_organico_tribunales": LegalArea.OTHER,
    "codigo_aguas": LegalArea.CIVIL,
    # Leyes específicas
    "ley_proteccion_consumidor": LegalArea.CONSUMER,
    "ley_tribunales_familia": LegalArea.FAMILY,
    "ley_bancos": LegalArea.COMMERCE,
    "ley_quiebras": LegalArea.COMMERCE,
    "ley_medicinas": LegalArea.CONSUMER,
    # Estatutos
    "estatuto_administrativo": LegalArea.OTHER,
    "estatuto_seguridad_social": LegalArea.LABOR,
    # Aliases para backwards compatibility
    "ley_19496": LegalArea.CONSUMER,
    "ley_19968": LegalArea.FAMILY,
    "ley_16618": LegalArea.FAMILY,
    "ley_19585": LegalArea.FAMILY,
}


def get_legal_area_from_matter_type(matter_type: str) -> LegalArea:
    """Infiere el área legal desde el matter_type del caso."""
    if not matter_type:
        return LegalArea.OTHER
    return MATTER_TYPE_TO_LEGAL_AREA.get(matter_type.lower(), LegalArea.OTHER)


def get_legal_area_from_law_code(law_code: str) -> LegalArea:
    """Infiere el área legal desde el código de ley."""
    if not law_code:
        return LegalArea.OTHER
    return LAW_CODE_TO_LEGAL_AREA.get(law_code.lower(), LegalArea.OTHER)
