"""
Clause Comparator Service

Compara las cláusulas extraídas del contrato contra templates estándar
para detectar desviaciones y generar alertas.
"""
import re


def extract_clause_value(clause_text: str, clause_type: str) -> dict | None:
    """Extrae valores específicos de una cláusula para comparar.

    Returns dict con valores relevantes para comparar contra el template.
    """
    values = {"raw_text": clause_text}

    if clause_type == "terminacion":
        # Extraer días de aviso previo
        match = re.search(r'(\d+)\s*(?:d[ií]as?|días?)\s*(?:de\s*anticipaci[ió]n|previo)', clause_text.lower())
        if match:
            values["notice_days"] = int(match.group(1))
        else:
            # Buscar cualquier número seguido de días
            match = re.search(r'(\d+)\s*(?:d[ií]as?|días?)', clause_text.lower())
            if match:
                values["notice_days"] = int(match.group(1))

        # Detectar si permite terminación sin causa
        values["allows_termination_without_cause"] = any(word in clause_text.lower() for word in [
            "sin causa", "sin necesidad", "sin expresión", "libremente",
            "a su total criterio", "sin expresión de causa"
        ])

        # Detectar si requiere causa justificada
        values["requires_justified_cause"] = any(word in clause_text.lower() for word in [
            "causa justificada", "incumplimiento", "justificado", "grave"
        ])

    elif clause_type == "penalidades":
        # Extraer porcentaje de multa/penalidad
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', clause_text)
        if match:
            values["penalty_percentage"] = float(match.group(1))

        # Detectar topes (máximo/mínimo)
        match_max = re.search(r'(?:máximo|max|máx)[:\s]+(\d+(?:\.\d+)?)\s*%', clause_text.lower())
        match_min = re.search(r'(?:mínimo|min|mín)[:\s]+(\d+(?:\.\d+)?)\s*%', clause_text.lower())
        if match_max:
            values["penalty_max"] = float(match_max.group(1))
        if match_min:
            values["penalty_min"] = float(match_min.group(1))

    elif clause_type == "garantia":
        # Extraer porcentaje de garantía
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', clause_text)
        if match:
            values["guarantee_percentage"] = float(match.group(1))

        # Detectar tipo de garantía
        values["has_bank_guarantee"] = "boleta bancaria" in clause_text.lower()
        values["has_insurance"] = "seguro" in clause_text.lower()

    elif clause_type == "confidencialidad":
        # Extraer años de confidencialidad
        match = re.search(r'(\d+)\s*(?:años?|anos?)', clause_text.lower())
        if match:
            values["confidentiality_years"] = int(match.group(1))

    elif clause_type == "renovacion":
        # Extraer meses de renovación automática
        match = re.search(r'(\d+)\s*(?:meses?|meses)', clause_text.lower())
        if match:
            values["renewal_months"] = int(match.group(1))

        # Detectar si es automática
        values["is_automatic"] = "automátic" in clause_text.lower()

        # Extraer días de aviso para no renovar
        match = re.search(r'(\d+)\s*(?:días?|dias?)\s*(?:de\s*anticipación|previo)', clause_text.lower())
        if match:
            values["cancellation_notice_days"] = int(match.group(1))

    elif clause_type == "incremento":
        # Extraer porcentaje máximo de incremento
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', clause_text)
        if match:
            values["max_increase_percentage"] = float(match.group(1))

    return values if values != {"raw_text": clause_text} else None


def compare_clause_to_template(
    clause_type: str,
    contract_type: str,
    clause_text: str,
    clause_template: dict
) -> dict | None:
    """Compara una cláusula extraída contra el template estándar.

    Returns dict con:
    - has_deviation: bool
    - deviation_level: "none" | "minor" | "moderate" | "major" | "critical"
    - deviation_description: str
    - risk_score_adjustment: int (-50 to +50)

    S4-12: previously this 127-line function embedded a per-clause
    switch-statement. Refactor into a registry of per-type handlers so
    new clause types register with `_register_clause_handler` without
    touching the dispatcher.
    """
    from app.services.clause_templates import get_template_for_clause

    template = clause_template or get_template_for_clause(contract_type, clause_type)

    if not template:
        return None

    result = _build_baseline_result(template)

    actual_values = extract_clause_value(clause_text, clause_type)
    if not actual_values:
        return result

    handler = _CLAUSE_HANDLERS.get(clause_type)
    if handler is None:
        return result
    return handler(result, actual_values, template)


def _build_baseline_result(template: dict) -> dict:
    """Return the no-deviation baseline result populated with template context."""
    return {
        "has_deviation": False,
        "deviation_level": "none",
        "deviation_description": "",
        "risk_score_adjustment": 0,
        "standard_clause": template.get("standard", ""),
        "industry_default": template.get("industry_default", ""),
    }


# ---------------------------------------------------------------------------
# Per-clause-type handlers
# ---------------------------------------------------------------------------
def _check_terminacion(result, actual_values, template):
    template_vars = template.get("variables", {})

    if actual_values.get("allows_termination_without_cause"):
        result["has_deviation"] = True
        result["deviation_level"] = "major"
        result["deviation_description"] = (
            "La cláusula permite terminación SIN causa justificada, "
            "lo cual es desfavorable"
        )
        result["risk_score_adjustment"] = 25
    elif actual_values.get("requires_justified_cause"):
        result["deviation_description"] = (
            "La cláusula requiere causa justificada - OK"
        )

    actual_days = actual_values.get("notice_days")
    template_days = template_vars.get("dias")
    if actual_days is not None and template_days is not None and actual_days < template_days:
        result["has_deviation"] = True
        result["deviation_level"] = (
            "major" if actual_days < template_days * 0.5 else "moderate"
        )
        result["risk_score_adjustment"] = (
            20 if actual_days < template_days * 0.5 else 10
        )
        result["deviation_description"] = (
            f"Días de aviso previo insuficientes: {actual_days} días "
            f"vs estándar de {template_days} días"
        )
    return result


def _check_penalidades(result, actual_values, template):
    template_vars = template.get("variables", {})
    template_pct = template_vars.get("porcentaje", 5)
    actual_pct = actual_values.get("penalty_percentage")
    if actual_pct is None:
        return result
    if actual_pct > template_pct * 2:
        result.update({
            "has_deviation": True,
            "deviation_level": "major",
            "risk_score_adjustment": 20,
            "deviation_description": (
                f"Penalidad excesiva: {actual_pct}% vs estándar de {template_pct}%"
            ),
        })
    elif actual_pct > template_pct:
        result.update({
            "has_deviation": True,
            "deviation_level": "moderate",
            "risk_score_adjustment": 10,
            "deviation_description": (
                f"Penalidad高于标准: {actual_pct}% vs estándar de {template_pct}%"
            ),
        })
    return result


def _check_garantia(result, actual_values, template):
    template_vars = template.get("variables", {})
    template_pct = template_vars.get("porcentaje", 10)
    actual_pct = actual_values.get("guarantee_percentage")
    if actual_pct is None:
        return result
    if actual_pct > template_pct * 2:
        result.update({
            "has_deviation": True,
            "deviation_level": "major",
            "risk_score_adjustment": 20,
            "deviation_description": (
                f"Garantía excesiva: {actual_pct}% vs estándar de {template_pct}%"
            ),
        })
    elif actual_pct > template_pct:
        result.update({
            "has_deviation": True,
            "deviation_level": "minor",
            "risk_score_adjustment": 5,
            "deviation_description": (
                f"Garantía por encima del estándar: {actual_pct}% vs {template_pct}%"
            ),
        })
    return result


def _check_renovacion(result, actual_values, template):
    if actual_values.get("is_automatic") and not actual_values.get("cancellation_notice_days"):
        result.update({
            "has_deviation": True,
            "deviation_level": "moderate",
            "risk_score_adjustment": 10,
            "deviation_description": (
                "Renovación automática sin plazo de aviso para cancelar"
            ),
        })
    return result


def _check_incremento(result, actual_values, template):
    template_vars = template.get("variables", {})
    template_pct = template_vars.get("porcentaje", 10)
    actual_pct = actual_values.get("max_increase_percentage")
    if actual_pct is not None and actual_pct > template_pct:
        result.update({
            "has_deviation": True,
            "deviation_level": "moderate",
            "risk_score_adjustment": 10,
            "deviation_description": (
                f"Incremento máximo elevado: {actual_pct}% vs estándar de {template_pct}%"
            ),
        })
    return result


_CLAUSE_HANDLERS = {
    "terminacion": _check_terminacion,
    "penalidades": _check_penalidades,
    "garantia": _check_garantia,
    "renovacion": _check_renovacion,
    "incremento": _check_incremento,
}

def compare_contract_clauses_to_templates(
    clauses_by_type: dict[str, list[str]],
    contract_type: str = "contract_review"
) -> list[dict]:
    """Compara todas las cláusulas de un contrato contra los templates.

    Returns lista de desviaciones encontradas.
    """
    deviations = []

    for clause_type, clauses in clauses_by_type.items():
        if not clauses:
            continue

        for clause_text in clauses:
            comparison = compare_clause_to_template(
                clause_type=clause_type,
                contract_type=contract_type,
                clause_text=clause_text,
                clause_template=None
            )

            if comparison and comparison.get("has_deviation"):
                deviation = {
                    "clause_type": clause_type,
                    "clause_text": clause_text[:200] + "..." if len(clause_text) > 200 else clause_text,
                    "deviation_level": comparison["deviation_level"],
                    "description": comparison["deviation_description"],
                    "standard_clause": comparison.get("standard_clause", ""),
                    "industry_default": comparison.get("industry_default", ""),
                    "risk_score_adjustment": comparison.get("risk_score_adjustment", 0)
                }
                deviations.append(deviation)

    # Ordenar por nivel de desviación (major primero)
    level_order = {"critical": 0, "major": 1, "moderate": 2, "minor": 3, "none": 4}
    deviations.sort(key=lambda x: level_order.get(x["deviation_level"], 5))

    return deviations
