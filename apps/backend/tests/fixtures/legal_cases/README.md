# Dataset Golden - Casos Curados para Evaluación

Este directorio contiene casos de prueba curados para evaluar el sistema de análisis legal.

## Casos Disponibles

| ID | Tipo | Dificultad | Descripción |
|----|------|------------|-------------|
| `contrato_servicios_001` | contract_review | Media | Contrato de servicios con cláusula de exclusividad excesiva |
| `contrato_arriendo_001` | lease | Baja | Contrato de arrendamiento con garantía de 3 meses |
| `demanda_laboral_001` | labor | Alta | Demanda por despido injustificado con cláusula de confidencialidad |
| `reclamo_consumo_001` | consumer | Baja | Reclamo por producto defectuoso |

## Estructura de un Caso

```json
{
  "id": "caso_001",
  "tipo_caso": "contract_review|labor|lease|consumer|...",
  "dificultad": "alta|media|baja",
  "descripcion": "Descripción breve del caso",
  "texto_fuente": "Texto legal a analizar",
  "metadata": {
    // Datos estructurados del caso
  },
  "expected_analysis": {
    // Análisis que el sistema DEBE generar
  },
  "test_expectations": {
    // Qué debe detectar/identificar el sistema
  }
}
```

## Uso en Tests

```python
from tests.fixtures.legal_cases import load_all_cases, load_case_by_id

# Cargar todos los casos
cases = load_all_cases()

# Cargar caso específico
case = load_case_by_id("contrato_servicios_001")

# Cargar por tipo
from tests.fixtures.legal_cases import load_cases_by_type
labor_cases = load_cases_by_type("labor")

# Cargar por dificultad
from tests.fixtures.legal_cases import load_cases_by_difficulty
hard_cases = load_cases_by_difficulty("alta")
```

## Cómo Agregar Nuevos Casos

1. Crear archivo JSON en este directorio
2. Incluir todos los campos requeridos
3. El `expected_analysis` debe estar curado por un experto
4. Actualizar este README

## Métricas de Evaluación

El sistema debe pasar los tests de:
- Identificación correcta de partes
- Detección de cláusulas peligrosas
- Cálculo correcto de montos/indemnizaciones
- Citación de artículos relevantes
- Niveles de confidence apropiados
