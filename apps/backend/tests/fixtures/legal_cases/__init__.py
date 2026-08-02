"""
Dataset Golden - Casos curados para evaluación de análisis legal.

Este módulo proporciona acceso a los casos de prueba curados.
Cada caso incluye el texto fuente y el análisis esperado.

Uso:
    from tests.fixtures.legal_cases import load_all_cases, load_case_by_id

    cases = load_all_cases()
    case = load_case_by_id("contrato_servicios_001")
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional

FIXTURES_DIR = Path(__file__).parent


def load_case_by_id(case_id: str) -> Optional[Dict]:
    """
    Carga un caso por su ID.

    Args:
        case_id: ID del caso (ej: "contrato_servicios_001")

    Returns:
        Dict con el caso o None si no existe
    """
    for json_file in FIXTURES_DIR.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            case = json.load(f)
            if case.get("id") == case_id:
                return case
    return None


def load_all_cases() -> List[Dict]:
    """
    Carga todos los casos del dataset.

    Returns:
        Lista de casos (dicts)
    """
    cases = []
    for json_file in FIXTURES_DIR.glob("*.json"):
        if json_file.name == "__init__.py":
            continue
        with open(json_file, "r", encoding="utf-8") as f:
            cases.append(json.load(f))
    return cases


def load_cases_by_type(tipo_caso: str) -> List[Dict]:
    """
    Carga casos filtrados por tipo.

    Args:
        tipo_caso: Tipo de caso (contract_review, labor, lease, consumer, etc.)

    Returns:
        Lista de casos del tipo especificado
    """
    all_cases = load_all_cases()
    return [c for c in all_cases if c.get("tipo_caso") == tipo_caso]


def load_cases_by_difficulty(dificultad: str) -> List[Dict]:
    """
    Carga casos filtrados por dificultad.

    Args:
        dificultad: "alta", "media" o "baja"

    Returns:
        Lista de casos de la dificultad especificada
    """
    all_cases = load_all_cases()
    return [c for c in all_cases if c.get("dificultad") == dificultad]


def get_test_cases_for_evaluation() -> List[Dict]:
    """
    Retorna casos formateados para evaluación de LLM.

    Returns:
        Lista de casos con solo texto_fuente y metadata (sin expected_analysis)
    """
    cases = load_all_cases()
    return [
        {
            "id": c["id"],
            "tipo_caso": c["tipo_caso"],
            "dificultad": c["dificultad"],
            "descripcion": c["descripcion"],
            "texto_fuente": c["texto_fuente"],
            "metadata": c["metadata"]
        }
        for c in cases
    ]


# Exports
__all__ = [
    "load_case_by_id",
    "load_all_cases",
    "load_cases_by_type",
    "load_cases_by_difficulty",
    "get_test_cases_for_evaluation",
]
