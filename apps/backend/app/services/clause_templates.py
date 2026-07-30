"""
Clause Templates Catalog - Estándares del sector legal chileno

Catálogo de cláusulas modelo para diferentes tipos de contratos.
Estas son las cláusulas estándar consideradas razonables en el mercado chileno.
"""

# Templates por tipo de contrato y tipo de cláusula
CLAUSE_TEMPLATES = {
    "contract_review": {
        "terminacion": {
            "template": "El presente contrato podrá ser terminado por cualquiera de las partes mediante aviso previo escrito con a lo menos {dias} días de anticipación, fundado en incumplimiento grave de la otra parte o por mutuo acuerdo.",
            "variables": {"dias": 30},
            "standard": "La terminación unilateral requiere aviso previo mínimo de 30 días y causa justificada.",
            "industry_default": "30-60 días de aviso previo",
            "risk_indicator": "allowed_termination_notice_days"
        },
        "penalidades": {
            "template": "En caso de incumplimiento, la parte infractora deberá pagar una multa equivalente al {porcentaje}% del valor del contrato, sin perjuicio de la indemnización de perjuicios.",
            "variables": {"porcentaje": 5},
            "standard": "Las penalidades en contratos comerciales en Chile suelen ser entre 0.5% y 10% del valor del contrato.",
            "industry_default": "1-5% del valor del contrato",
            "risk_indicator": "penalty_percentage"
        },
        "garantia": {
            "template": "El contratista deberá constituir una garantía de fiel cumplimiento equivalente al {porcentaje}% del valor total del contrato, mediante boleta bancaria o seguro de garantía.",
            "variables": {"porcentaje": 10},
            "standard": "Las garantías de fiel cumplimiento suelen ser entre 5% y 30% del valor del contrato.",
            "industry_default": "10% del valor del contrato",
            "risk_indicator": "guarantee_percentage"
        },
        "confidencialidad": {
            "template": "Las partes se obligan a mantener estricta confidencialidad sobre toda información sensible intercambiada durante la vigencia del contrato y hasta {anos} años después de su término.",
            "variables": {"anos": 3},
            "standard": "La confidencialidad suele ser de 2-5 años post-término del contrato.",
            "industry_default": "3 años post-término",
            "risk_indicator": "confidentiality_years"
        },
        "renovacion": {
            "template": "El presente contrato se entenderá renovado automáticamente por períodos iguales de {meses} meses, salvo que alguna de las partes manifieste su intención de no renovar con al menos {dias} días de anticipación.",
            "variables": {"meses": 12, "dias": 60},
            "standard": "La renovación automática es común en contratos de prestación de servicios.",
            "industry_default": "Renovación automática por 12 meses con aviso de 60 días",
            "risk_indicator": "auto_renewal_terms"
        }
    },
    "lease": {
        "terminacion": {
            "template": "El arrendador podrá poner término al arriendo en caso de incumplimiento grave del arrendatario, debiendo hacerlo saber con a lo menos {dias} días de anticipación.",
            "variables": {"dias": 30},
            "standard": "Según Ley 18.101, el arrendador puede terminar por incumplimiento o conveniencia",
            "industry_default": "30-60 días de aviso",
            "risk_indicator": "lease_termination_notice_days"
        },
        "incremento": {
            "template": "ElCanon de arrendamiento podrá ser incrementado anualmente hasta un máximo del {porcentaje}% del canon anterior.",
            "variables": {"porcentaje": 10},
            "standard": "Según Ley 18.101, el incremento no puede ser abusivo ni superar la variación del IPC",
            "industry_default": "Máximo 10% anual o variación IPC",
            "risk_indicator": "annual_increase_cap"
        },
        "garantia": {
            "template": "El arrendatario deberá garantizar el cumplimiento del contrato con un depósito de {meses} meses de canon, el que será devuelto al término del contrato.",
            "variables": {"meses": 2},
            "standard": "La garantía de arriendo suele ser 1-3 meses de canon",
            "industry_default": "2-3 meses de canon",
            "risk_indicator": "lease_deposit_months"
        }
    },
    "labor": {
        "terminacion": {
            "template": "El contrato podrá terminar por mutuo acuerdo, renuncia del trabajador,_TIMEOUT_, o por necesidades de la empresa según el Código del Trabajo.",
            "variables": {},
            "standard": "Según el Código del Trabajo, el despido debe ser con aviso previo o indemnización sustitutiva",
            "industry_default": "Aviso con 30 días de anticipación o pago de indemnización",
            "risk_indicator": "labor_termination_justified"
        },
        "remuneracion": {
            "template": "El trabajador tendrá derecho a una remuneración bruta mensual de $ {monto}, más beneficios de ley.",
            "variables": {"monto": "mínimo RMV"},
            "standard": "Remuneración debe ser igual o superior al ingreso mínimo mensual",
            "industry_default": ">= Sueldo mínimo legal",
            "risk_indicator": "minimum_wage_compliance"
        }
    },
    "consumer": {
        "clausulas_abusivas": {
            "template": "No se consideran abusivas las cláusulas que limiten derechos del consumidor cuando exista causa justificada y se informen claramente.",
            "variables": {},
            "standard": "Según Ley 19.496, son abusivas las cláusulas que impongan responsabilidades excesivas o irrazonables",
            "industry_default": "Prohibidas cláusulas que afecten derechos del consumidor",
            "risk_indicator": "abusive_clause_detection"
        },
        "derecho_retracto": {
            "template": "El consumidor tendrá un plazo de {dias} días para retractarse de la compra.",
            "variables": {"dias": 10},
            "standard": "Según Ley 19.496, el derecho a retracto es de 10 días en ventas a distancia",
            "industry_default": "10 días para retracto",
            "risk_indicator": "retracto_days"
        }
    }
}


# Templates por defecto para cualquier tipo de contrato
DEFAULT_TEMPLATES = {
    "terminacion": {
        "template": "El contrato puede ser terminado por cualquiera de las partes con aviso previo de 30 días.",
        "variables": {},
        "standard": "Aviso previo mínimo de 30 días se considera razonable",
        "industry_default": "30 días de aviso previo",
        "risk_indicator": "general_termination_notice"
    },
    "penalidades": {
        "template": "Las penalidades por incumplimiento no excederán el 5% del valor del contrato.",
        "variables": {},
        "standard": "Penalidades comerciales razonables son 1-10%",
        "industry_default": "5% máximo",
        "risk_indicator": "general_penalty_cap"
    },
    "garantia": {
        "template": "El contratista garantizará el cumplimiento con una garantía del 10% del valor del contrato.",
        "variables": {},
        "standard": "Garantías de 5-20% son estándar en contratos comerciales",
        "industry_default": "10% del valor",
        "risk_indicator": "general_guarantee_percentage"
    }
}


def get_templates_for_contract_type(contract_type: str) -> dict:
    """Obtiene los templates para un tipo de contrato específico."""
    return CLAUSE_TEMPLATES.get(contract_type, DEFAULT_TEMPLATES)


def get_all_clause_types() -> list:
    """Obtiene todos los tipos de cláusulas disponibles."""
    types = set()
    for contract_templates in CLAUSE_TEMPLATES.values():
        types.update(contract_templates.keys())
    types.update(DEFAULT_TEMPLATES.keys())
    return sorted(list(types))


def get_template_for_clause(contract_type: str, clause_type: str) -> dict:
    """Obtiene el template para un tipo de contrato y tipo de cláusula específico."""
    templates = get_templates_for_contract_type(contract_type)
    if clause_type in templates:
        return templates[clause_type]

    # Fallback a templates por defecto
    if clause_type in DEFAULT_TEMPLATES:
        return DEFAULT_TEMPLATES[clause_type]

    return None


def get_clause_variance_description(clause_type: str, contract_type: str, actual_value: dict = None) -> str:
    """Genera una descripción de la variación detectada vs el estándar."""
    template = get_template_for_clause(contract_type, clause_type)

    if not template:
        return "Template no disponible para comparación"

    standard = template.get("industry_default", "Estándar no definido")
    indicator = template.get("risk_indicator", "")

    description = f"Estándar del sector: {standard}"

    if actual_value:
        description += f"\nCláusula actual: {actual_value}"

    return description
