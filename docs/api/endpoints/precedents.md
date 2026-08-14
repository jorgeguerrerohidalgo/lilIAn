# API — Precedents

> Router: `apps/backend/app/api/endpoints/precedents.py` · Prefijo: `/api/v1/precedents` · Tag OpenAPI: `precedents`

Búsqueda, consulta y analítica de precedentes judiciales chilenos. Sirve tanto para búsqueda directa por parte del usuario como para inyectar contexto jurisprudencial en el pipeline RAG.

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Modelo de datos](#modelo-de-datos)
- [GET /api/v1/precedents/search](#get-apiv1precedentssearch)
- [GET /api/v1/precedents/context](#get-apiv1precedentscontext)
- [GET /api/v1/precedents/courts](#get-apiv1precedentscourts)
- [GET /api/v1/precedents/legal-areas](#get-apiv1precedentslegal-areas)
- [GET /api/v1/precedents/analytics](#get-apiv1precedentsanalytics)
- [GET /api/v1/precedents/analytics/filters](#get-apiv1precedentsanalyticsfilters)
- [POST /api/v1/precedents/](#post-apiv1precedents)
- [GET /api/v1/precedents/{precedent_id}](#get-apiv1precedentsprecedent_id)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Rate limit | Descripción |
|---|---|---|---|---|
| `GET` | `/api/v1/precedents/search` | Bearer + org | Plan | Búsqueda de precedentes con filtros |
| `GET` | `/api/v1/precedents/context` | Bearer + org | Plan | Top-K precedentes como contexto RAG |
| `GET` | `/api/v1/precedents/courts` | Bearer + org | Plan | Tribunales disponibles |
| `GET` | `/api/v1/precedents/legal-areas` | Bearer + org | Plan | Áreas legales presentes |
| `GET` | `/api/v1/precedents/analytics` | Bearer + org | **10/min por IP** | Analítica agregada |
| `GET` | `/api/v1/precedents/analytics/filters` | Bearer + org | Plan | Opciones válidas de filtro |
| `POST` | `/api/v1/precedents/` | Bearer + org | Plan | Crea un precedente (`201`) |
| `GET` | `/api/v1/precedents/{precedent_id}` | Bearer + org | Plan | Detalle de un precedente |

---

## Modelo de datos

### `PrecedentResponse`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | |
| `court` | `str` | Corte (por ejemplo, Corte Suprema) |
| `tribunal` | `str` | Tribunal concreto |
| `year` | `int` | Año de la sentencia |
| `roll_number` | `str` | Número de rol |
| `full_citation` | `str \| null` | Cita completa |
| `legal_area` | `str` | Área legal |
| `matter_type` | `str \| null` | Tipo de materia |
| `summary` | `str` | Resumen del fallo |
| `reasoning` | `str \| null` | Considerandos |
| `decision` | `str \| null` | Decisión |
| `disposition` | `str \| null` | Parte resolutiva |
| `voces` | `str \| null` | Voces / descriptores |

### `PrecedentSearchResponse`

| Campo | Tipo | Descripción |
|---|---|---|
| `results` | `list[dict]` | Precedentes encontrados |
| `query` | `str` | Consulta original |
| `total` | `int` | Número de resultados |
| `search_type` | `str` | Estrategia usada (semántica o por keyword) |

---

## `GET /api/v1/precedents/search`

Búsqueda de precedentes con filtros combinables.

### Query params

| Param | Tipo | Requerido | Restricciones | Descripción |
|---|---|---|---|---|
| `q` | `str` | **Sí** | `min_length=3` | Texto de búsqueda |
| `court` | `str \| null` | No | — | Filtrar por tribunal |
| `year` | `int \| null` | No | — | Filtrar por año |
| `legal_area` | `str \| null` | No | — | Filtrar por área legal |
| `matter_type` | `str \| null` | No | — | Filtrar por tipo de materia |

```bash
# Búsqueda simple
curl "http://localhost:8000/api/v1/precedents/search?q=despido%20injustificado" \
  -H "Authorization: Bearer $TOKEN"

# Con filtros
curl "http://localhost:8000/api/v1/precedents/search?q=despido%20injustificado&court=Corte%20Suprema&year=2023&legal_area=laboral" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "results": [
    {
      "id": 88,
      "court": "Corte Suprema",
      "tribunal": "Cuarta Sala",
      "year": 2023,
      "roll_number": "12345-2023",
      "full_citation": "CS, Rol 12345-2023, 14 de marzo de 2023",
      "legal_area": "laboral",
      "summary": "Se acoge recurso de unificación de jurisprudencia sobre despido injustificado...",
      "score": 0.87
    }
  ],
  "query": "despido injustificado",
  "total": 1,
  "search_type": "semantic"
}
```

> `q` con menos de 3 caracteres devuelve `422`.

---

## `GET /api/v1/precedents/context`

Devuelve los `top_k` precedentes más relevantes en un formato pensado para inyectarse como contexto en un prompt.

### Query params

| Param | Tipo | Requerido | Restricciones | Default |
|---|---|---|---|---|
| `q` | `str` | **Sí** | `min_length=3` | — |
| `court` | `str \| null` | No | — | `None` |
| `year` | `int \| null` | No | — | `None` |
| `legal_area` | `str \| null` | No | — | `None` |
| `top_k` | `int` | No | `ge=1`, `le=10` | `3` |

```bash
curl "http://localhost:8000/api/v1/precedents/context?q=indemnizacion%20por%20años%20de%20servicio&top_k=5&legal_area=laboral" \
  -H "Authorization: Bearer $TOKEN"
```

---

## `GET /api/v1/precedents/courts`

Lista los tribunales disponibles en el corpus. Útil para poblar un selector en la UI.

```bash
curl http://localhost:8000/api/v1/precedents/courts \
  -H "Authorization: Bearer $TOKEN"
```

---

## `GET /api/v1/precedents/legal-areas`

Lista las áreas legales presentes en el corpus de precedentes.

```bash
curl http://localhost:8000/api/v1/precedents/legal-areas \
  -H "Authorization: Bearer $TOKEN"
```

> No confundir con `GET /api/v1/legal-areas`, que devuelve el catálogo general de áreas legales de la plataforma.

---

## `GET /api/v1/precedents/analytics`

Analítica agregada del corpus: distribución por tribunal, año, área y tipo de materia.

**Este endpoint está limitado a 10 peticiones por minuto** (`@limiter.limit("10/minute")`), porque las agregaciones son costosas.

### Query params

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `legal_area` | `str \| null` | `None` | Filtrar por área legal |
| `court` | `str \| null` | `None` | Filtrar por tribunal |
| `year_from` | `int \| null` | `None` | Año inicial del rango |
| `year_to` | `int \| null` | `None` | Año final del rango |
| `matter_type` | `str \| null` | `None` | Filtrar por tipo de materia |
| `include_text_analysis` | `bool` | `false` | Incluir análisis de texto. **Notablemente más lento** |

```bash
# Analítica básica
curl "http://localhost:8000/api/v1/precedents/analytics?legal_area=laboral&year_from=2020&year_to=2024" \
  -H "Authorization: Bearer $TOKEN"

# Con análisis de texto (lento)
curl "http://localhost:8000/api/v1/precedents/analytics?legal_area=laboral&include_text_analysis=true" \
  -H "Authorization: Bearer $TOKEN"
```

> Deja `include_text_analysis` en `false` salvo que realmente necesites el desglose textual: combinado con el límite de 10/min, unas pocas llamadas pesadas agotan la cuota.

---

## `GET /api/v1/precedents/analytics/filters`

Devuelve los valores válidos para los filtros de `/analytics` (tribunales, años, áreas, tipos de materia disponibles).

```bash
curl http://localhost:8000/api/v1/precedents/analytics/filters \
  -H "Authorization: Bearer $TOKEN"
```

---

## `POST /api/v1/precedents/`

Crea un precedente en el corpus.

- **Content-Type**: `application/json`
- **Status éxito**: `201 Created`
- **Nota**: el path lleva **barra final**.

### Request body — `PrecedentCreateRequest`

| Campo | Tipo | Requerido |
|---|---|---|
| `court` | `str` | Sí |
| `tribunal` | `str` | Sí |
| `year` | `int` | Sí |
| `roll_number` | `str` | Sí |
| `legal_area` | `str` | Sí |
| `summary` | `str` | Sí |
| `full_citation` | `str \| null` | No |
| `matter_type` | `str \| null` | No |
| `reasoning` | `str \| null` | No |
| `decision` | `str \| null` | No |
| `disposition` | `str \| null` | No |
| `voces` | `str \| null` | No |
| `ponente` | `str \| null` | No |
| `type` | `str \| null` | No |

```bash
curl -X POST http://localhost:8000/api/v1/precedents/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "court": "Corte Suprema",
    "tribunal": "Cuarta Sala",
    "year": 2023,
    "roll_number": "12345-2023",
    "full_citation": "CS, Rol 12345-2023, 14 de marzo de 2023",
    "legal_area": "laboral",
    "matter_type": "despido",
    "summary": "Se acoge recurso de unificación de jurisprudencia sobre despido injustificado.",
    "reasoning": "Que conforme al artículo 162 del Código del Trabajo...",
    "decision": "Se acoge el recurso.",
    "voces": "despido injustificado; carta de aviso; art. 162"
  }'
```

---

## `GET /api/v1/precedents/{precedent_id}`

Detalle completo de un precedente.

- **Response 200**: `PrecedentResponse`

```bash
curl http://localhost:8000/api/v1/precedents/88 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Errores comunes

| Código | Endpoint | Causa | `detail` de ejemplo |
|---|---|---|---|
| `401` | todos | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | todos | Usuario sin membresía de organización | `"Usuario sin organización asignada"` |
| `404` | `{precedent_id}` | Precedente inexistente | `"Precedente no encontrado"` |
| `422` | `search`, `context` | `q` con menos de 3 caracteres, o `top_k` fuera de `[1, 10]` | Detalle estructurado de pydantic |
| `422` | `POST /` | Falta un campo obligatorio | Detalle estructurado de pydantic |
| `429` | `analytics` | Más de 10 peticiones por minuto desde la misma IP | `"Rate limit exceeded"` |
| `429` | resto | Límite del plan superado | `"Rate limit exceeded"` |

---

## Rate limits

| Endpoint | Límite | Clave |
|---|---|---|
| `GET /analytics` | `10/minute` | IP remota (`@limiter.limit("10/minute")`) |
| Resto | Límite del plan (`free` 100, `basic` 500, `pro` 2000, `enterprise` sin límite) | Token o IP |

Respuesta `429` con cabeceras `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` y `Retry-After: 60`.

Ver [rate limits globales](../../openapi.md#rate-limits).

---

## Notas de seguridad

- **Corpus compartido, autenticación obligatoria**: los precedentes son jurisprudencia pública, pero todos los endpoints exigen token y membresía de organización. No expongas este router sin autenticación.
- **Escritura sin restricción de rol explícita**: `POST /precedents/` sólo requiere `require_organization`. Si el corpus debe ser curado, añade una comprobación de rol (`ADMIN`/`PLATFORM_ADMIN`) — ver [rbac-matrix.md](../../rbac-matrix.md).
- **Coste de `analytics`**: el límite de 10/min es la protección principal contra un DoS por agregación. `include_text_analysis=true` multiplica el coste; no lo actives desde una UI que refresque automáticamente.
- **Entrada de búsqueda**: `q` es texto libre del usuario. El `min_length=3` evita barridos triviales del corpus, pero no sustituye a la parametrización de las consultas a la base de datos.
- **Uso como contexto de IA**: `/context` alimenta prompts del LLM. Los precedentes devueltos deben citarse con su `roll_number` y `full_citation` para que el usuario pueda verificarlos; nunca los presentes como conclusión sin traza a la fuente.
