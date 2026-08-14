# API — Analysis

> Router: `apps/backend/app/api/endpoints/analysis.py` · Prefijo: `/api/v1/analysis` · Tag OpenAPI: `analysis`

Generación e inspección de informes de análisis legal a nivel de **caso**. Cada informe agrega hechos, información faltante, próximos pasos y una lista de riesgos revisables.

> Para el análisis de un **documento individual** ver [documents.md](documents.md#post-apiv1documentsdocument_idanalyze).

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Modelo de datos](#modelo-de-datos)
- [POST /api/v1/analysis](#post-apiv1analysis)
- [GET /api/v1/analysis/matters/{matter_id}](#get-apiv1analysismattersmatter_id)
- [GET /api/v1/analysis/reports/{report_id}](#get-apiv1analysisreportsreport_id)
- [GET /api/v1/analysis/matters/{matter_id}/latest](#get-apiv1analysismattersmatter_idlatest)
- [GET /api/v1/analysis/matters/{matter_id}/risks](#get-apiv1analysismattersmatter_idrisks)
- [PATCH /api/v1/analysis/risks/{risk_id}/review](#patch-apiv1analysisrisksrisk_idreview)
- [Flujo completo](#flujo-completo)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Éxito | Descripción |
|---|---|---|---|---|
| `POST` | `/api/v1/analysis` | Bearer + org | `202` | Encola la generación de un informe |
| `GET` | `/api/v1/analysis/matters/{matter_id}` | Bearer + org | `200` | Lista informes del caso |
| `GET` | `/api/v1/analysis/reports/{report_id}` | Bearer + org | `200` | Informe completo con riesgos |
| `GET` | `/api/v1/analysis/matters/{matter_id}/latest` | Bearer + org | `200` | Último informe del caso |
| `GET` | `/api/v1/analysis/matters/{matter_id}/risks` | Bearer + org | `200` | Riesgos del caso |
| `PATCH` | `/api/v1/analysis/risks/{risk_id}/review` | Bearer + org | `200` | Marca el estado de revisión de un riesgo |

---

## Modelo de datos

### `AnalysisReportResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `int` | |
| `matter_id` | `int` | |
| `model_provider` | `str \| null` | Proveedor LLM que generó el informe |
| `model_name` | `str \| null` | Modelo concreto |
| `report_type` | `str` | Tipo de informe |
| `summary` | `str \| null` | Resumen ejecutivo |
| `facts` | `str \| null` | Hechos extraídos |
| `missing_information` | `str \| null` | Información que falta para concluir |
| `next_steps` | `str \| null` | Próximos pasos sugeridos |
| `disclaimer` | `str \| null` | Aviso legal del informe |
| `confidence` | `str` | Nivel de confianza declarado |
| `status` | `str` | Estado de generación |
| `validation_summary` | `dict \| null` | Resultado de las validaciones automáticas |
| `created_at` | `datetime` | |
| `updated_at` | `datetime` | |

### `AnalysisReportDetailResponse`

Extiende `AnalysisReportResponse` añadiendo:

| Campo | Tipo | Notas |
|---|---|---|
| `risks` | `list[RiskItemResponse]` | Riesgos detectados. Default `[]` |

### `RiskItemResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `int` | |
| `level` | `str` | Nivel del riesgo (`high`, `medium`, `low`) |
| `title` | `str` | |
| `description` | `str \| null` | |
| `source_fragment` | `str \| null` | Fragmento del documento que lo sustenta |
| `impact` | `str \| null` | Impacto estimado |
| `recommendation` | `str \| null` | Recomendación de mitigación |
| `confidence` | `str` | Confianza del modelo |
| `review_status` | `str` | Estado de revisión humana |
| `created_at` | `datetime` | |

---

## `POST /api/v1/analysis`

Encola la generación de un informe para un caso. Se ejecuta en `BackgroundTasks`, por eso responde `202 Accepted` y **no** incluye el informe terminado.

- **Content-Type**: `application/json`
- **Status éxito**: `202 Accepted`

### Request body — `GenerateAnalysisRequest`

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `matter_id` | `int` | Sí | Caso a analizar. Debe pertenecer a la organización del usuario |

```bash
curl -i -X POST http://localhost:8000/api/v1/analysis \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "matter_id": 1 }'
```

Tras el `202`, consulta `GET /api/v1/analysis/matters/1/latest` hasta que `status` indique que la generación terminó.

---

## `GET /api/v1/analysis/matters/{matter_id}`

Lista los informes generados para el caso, sin los riesgos anidados.

- **Response 200**: `list[AnalysisReportResponse]`

```bash
curl http://localhost:8000/api/v1/analysis/matters/1 \
  -H "Authorization: Bearer $TOKEN"
```

---

## `GET /api/v1/analysis/reports/{report_id}`

Informe completo, con la lista de riesgos.

- **Response 200**: `AnalysisReportDetailResponse`

```bash
curl http://localhost:8000/api/v1/analysis/reports/9 \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "id": 9,
  "matter_id": 1,
  "model_provider": "anthropic",
  "model_name": "claude-sonnet-4-20250514",
  "report_type": "matter_analysis",
  "summary": "El despido carece de carta de aviso conforme al art. 162 del Código del Trabajo.",
  "facts": "El trabajador prestó servicios desde 2019-03-01...",
  "missing_information": "Falta el finiquito y las liquidaciones de los últimos 3 meses.",
  "next_steps": "Solicitar copia del finiquito; evaluar demanda por despido injustificado.",
  "disclaimer": "Este informe es una orientación generada por IA y no sustituye asesoría legal.",
  "confidence": "medium",
  "status": "completed",
  "validation_summary": { "citations_checked": 4, "citations_valid": 4 },
  "created_at": "2025-01-15T13:00:00Z",
  "updated_at": "2025-01-15T13:02:11Z",
  "risks": [
    {
      "id": 31,
      "level": "high",
      "title": "Ausencia de carta de aviso de despido",
      "description": "No consta comunicación escrita al trabajador.",
      "source_fragment": "...se le comunicó verbalmente el término de la relación laboral...",
      "impact": "Posible declaración de despido injustificado con recargo de indemnización.",
      "recommendation": "Reunir prueba de la comunicación o preparar defensa alternativa.",
      "confidence": "high",
      "review_status": "pending",
      "created_at": "2025-01-15T13:02:11Z"
    }
  ]
}
```

---

## `GET /api/v1/analysis/matters/{matter_id}/latest`

Devuelve el informe más reciente del caso, con riesgos. Es el endpoint recomendado para hacer *polling* tras un `POST /analysis`.

- **Response 200**: `AnalysisReportDetailResponse`

```bash
curl http://localhost:8000/api/v1/analysis/matters/1/latest \
  -H "Authorization: Bearer $TOKEN"
```

Polling del estado:

```bash
curl -s http://localhost:8000/api/v1/analysis/matters/1/latest \
  -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json; print(json.load(sys.stdin)['status'])"
```

---

## `GET /api/v1/analysis/matters/{matter_id}/risks`

Lista plana de todos los riesgos del caso, independientemente del informe que los originó.

- **Response 200**: `list[RiskItemResponse]`

```bash
curl http://localhost:8000/api/v1/analysis/matters/1/risks \
  -H "Authorization: Bearer $TOKEN"
```

---

## `PATCH /api/v1/analysis/risks/{risk_id}/review`

Registra la revisión humana de un riesgo generado por IA (aceptado, descartado, pendiente…). Es el mecanismo de *human-in-the-loop* del sistema.

- **Response 200**: riesgo actualizado

```bash
curl -X PATCH http://localhost:8000/api/v1/analysis/risks/31/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "review_status": "accepted" }'
```

---

## Flujo completo

```bash
# 1. Encolar el análisis del caso 1
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"matter_id": 1}'

# 2. Esperar y consultar el último informe
sleep 10
curl http://localhost:8000/api/v1/analysis/matters/1/latest \
  -H "Authorization: Bearer $TOKEN"

# 3. Revisar los riesgos detectados
curl http://localhost:8000/api/v1/analysis/matters/1/risks \
  -H "Authorization: Bearer $TOKEN"

# 4. Marcar un riesgo como revisado
curl -X PATCH http://localhost:8000/api/v1/analysis/risks/31/review \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"review_status": "accepted"}'
```

---

## Errores comunes

| Código | Endpoint | Causa | `detail` de ejemplo |
|---|---|---|---|
| `400` | `POST /analysis` | El caso no tiene documentos procesados | `"El caso no tiene documentos procesados"` |
| `401` | todos | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | todos | Usuario sin membresía de organización | `"Usuario sin organización asignada"` |
| `404` | todos | Caso, informe o riesgo inexistente / de otro tenant | `"Informe no encontrado"` |
| `404` | `latest` | El caso aún no tiene ningún informe | `"No hay análisis para este caso"` |
| `422` | `POST /analysis` | Falta `matter_id` o tipo incorrecto | Detalle estructurado de pydantic |
| `429` | todos | Límite del plan superado | `"Rate limit exceeded"` |
| `500` | generación | Fallo del proveedor LLM o API key ausente | `"Error al generar el análisis"` |

---

## Rate limits

Sin decorador `@limiter.limit` específico. Aplica el límite por organización según plan (`free` 100/min, `basic` 500/min, `pro` 2000/min, `enterprise` sin límite).

Además, la suscripción impone una cuota de análisis independiente del rate limit HTTP:

| Cuota | Campo en `SubscriptionResponse` |
|---|---|
| Análisis | `analyses_limit` / `analyses_used` |

Consulta el consumo con `GET /api/v1/saas/subscription` — ver [saas.md](saas.md).

---

## Notas de seguridad

- **La salida de IA no es asesoría legal**: el campo `disclaimer` debe mostrarse siempre en la UI junto al informe. `confidence` y `review_status` existen para que un profesional valide antes de actuar.
- **`validation_summary`**: recoge las verificaciones automáticas (por ejemplo, comprobación de citas). Un informe con validaciones fallidas no debe presentarse como concluyente.
- **Alucinación de citas**: los `source_fragment` provienen del documento, pero las referencias normativas del `summary` pueden ser inventadas por el modelo. Verifícalas contra [precedents](precedents.md) o fuentes oficiales.
- **Transferencia a terceros**: la generación envía el texto de los documentos del caso al proveedor LLM configurado. Aplica lo indicado en [documents.md](documents.md#notas-de-seguridad).
- **Aislamiento multi-tenant**: informes y riesgos filtran por `organization_id`; el acceso cross-tenant devuelve `404`.
- **Trazabilidad**: `model_provider` y `model_name` quedan registrados en cada informe. No los elimines: son necesarios para auditar decisiones tomadas con apoyo de IA.
