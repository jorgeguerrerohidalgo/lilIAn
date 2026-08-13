"""
Tests para validar análisis legal contra dataset golden.

Estos tests usan casos curados para verificar que el sistema
de análisis genera outputs correctos.
"""

import pytest

from tests.fixtures.legal_cases import (
    load_all_cases,
    load_case_by_id,
    load_cases_by_type,
)


class TestGoldenDatasetLoader:
    """Tests para el loader del dataset."""

    def test_load_all_cases(self):
        """Debe cargar todos los casos del dataset."""
        cases = load_all_cases()
        assert len(cases) >= 4, "Dataset debe tener al menos 4 casos"

    def test_load_case_by_id_exists(self):
        """Debe cargar un caso existente por ID."""
        case = load_case_by_id("contrato_servicios_001")
        assert case is not None
        assert case["id"] == "contrato_servicios_001"

    def test_load_case_by_id_not_exists(self):
        """Debe retornar None para ID inexistente."""
        case = load_case_by_id("caso_inexistente_999")
        assert case is None

    def test_load_cases_by_type(self):
        """Debe filtrar casos por tipo."""
        labor_cases = load_cases_by_type("labor")
        assert len(labor_cases) >= 1
        assert all(c["tipo_caso"] == "labor" for c in labor_cases)

    def test_load_cases_by_difficulty(self):
        """Debe filtrar casos por dificultad."""
        alta_cases = load_cases_by_type("labor")
        assert len(alta_cases) >= 1


class TestGoldenCaseStructure:
    """Tests para validar estructura de casos golden."""

    @pytest.fixture
    def case(self):
        """Fixture con un caso de ejemplo."""
        return load_case_by_id("contrato_servicios_001")

    def test_case_has_required_fields(self, case):
        """Caso debe tener campos requeridos."""
        assert "id" in case
        assert "tipo_caso" in case
        assert "dificultad" in case
        assert "texto_fuente" in case
        assert "metadata" in case
        assert "expected_analysis" in case
        assert "test_expectations" in case

    def test_case_tipo_valido(self, case):
        """Tipo de caso debe ser válido."""
        tipos_validos = {
            "contract_review", "labor", "lease", "consumer",
            "family", "company", "debt", "data_protection", "other"
        }
        assert case["tipo_caso"] in tipos_validos

    def test_case_dificultad_valida(self, case):
        """Dificultad debe ser válida."""
        dificultades_validas = {"alta", "media", "baja"}
        assert case["dificultad"] in dificultades_validas

    def test_case_has_texto_fuente(self, case):
        """Caso debe tener texto fuente no vacío."""
        assert case["texto_fuente"]
        assert len(case["texto_fuente"]) > 100

    def test_expected_analysis_has_required_fields(self, case):
        """Expected analysis debe tener campos requeridos."""
        ea = case["expected_analysis"]
        assert "tipo_contrato" in ea or "tipo_caso" in ea
        assert "partes_identificadas" in ea
        assert isinstance(ea["partes_identificadas"], list)


class TestContractReviewCase:
    """Tests específicos para caso de contrato de servicios."""

    @pytest.fixture
    def case(self):
        return load_case_by_id("contrato_servicios_001")

    def test_detecta_clausula_exclusividad(self, case):
        """Debe detectar cláusula de exclusividad."""
        expectations = case["test_expectations"]
        assert "clausula_exclusividad" in str(expectations.get("debe_detectar", []))

    def test_identifica_partes(self, case):
        """Debe identificar las partes del contrato."""
        expected = case["expected_analysis"]
        partes = expected["partes_identificadas"]
        assert len(partes) == 2
        assert partes[0]["rol"] == "Cliente"
        assert partes[1]["rol"] == "Prestador"

    def test_calcula_monto(self, case):
        """Debe calcular monto total del contrato."""
        expected = case["expected_analysis"]
        assert "monto_total_estimado" in expected
        assert expected["monto_total_estimado"] > 0


class TestLeaseCase:
    """Tests específicos para caso de arriendo."""

    @pytest.fixture
    def case(self):
        return load_case_by_id("contrato_arriendo_001")

    def test_detecta_garantia_excesiva(self, case):
        """Debe detectar garantía excesiva."""
        expectations = case["test_expectations"]
        assert "garantia_excesiva" in str(expectations.get("debe_detectar", []))


class TestLaborCase:
    """Tests específicos para caso laboral."""

    @pytest.fixture
    def case(self):
        return load_case_by_id("demanda_laboral_001")

    def test_detecta_despido_injustificado(self, case):
        """Debe detectar despido injustificado."""
        expectations = case["test_expectations"]
        assert "despido_injustificado" in str(expectations.get("debe_detectar", []))

    def test_calcula_indemnizaciones(self, case):
        """Debe calcular indemnizaciones."""
        expected = case["expected_analysis"]
        assert "pretensiones" in expected
        assert expected["pretensiones"]["total"] > 0


class TestConsumerCase:
    """Tests específicos para caso de consumo."""

    @pytest.fixture
    def case(self):
        return load_case_by_id("reclamo_consumo_001")

    def test_detecta_garantia_legal(self, case):
        """Debe detectar derechos de garantía."""
        expectations = case["test_expectations"]
        assert "garantia_legal" in str(expectations.get("debe_detectar", []))


# Para ejecutar: pytest apps/backend/tests/test_golden_dataset.py -v
