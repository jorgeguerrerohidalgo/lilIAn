# API — Search (RAG)

> Router: `apps/backend/app/api/endpoints/search.py` · Prefijo: `/api/v1/search` · Tag OpenAPI: `search`

Búsqueda sobre los fragmentos (*chunks*) de los documentos de un caso. Es la capa de recuperación del pipeline RAG: soporta búsqueda semántica por embeddings con degradación a búsqueda por keyword.

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Modelo de datos](#modelo-de-datos)
- [POST /api/v1/search](#post-apiv1search)
- [Semántica vs keyword](#semántica-vs-keyword)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Éxito | Descripción |
|---|---|---|---|---|
| `POST` | `/api/v1/search` | Bearer + org | `200` | Busca fragmentos relevantes dentro de un caso |

La búsqueda está siempre **acotada a un caso** (`matter_id` obligatorio). No existe búsqueda cross-caso ni cross-organización.

---

## Modelo de datos

### `SearchRequest`

| Campo | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `query` | `str` | Sí | — | Texto de búsqueda |
| `matter_id` | `int` | Sí | — | Caso sobre el que buscar |
| `top_k` | `int` | No | `5` | Número máximo de fragmentos a devolver |
| `use_embeddings` | `bool` | No | `true` | Usar búsqueda semántica. `false` fuerza keyword |

### `SearchResultItem`

| Campo | Tipo | Descripción |
|---|---|---|
| `chunk_id` | `int` | Id del fragmento |
| `document_id` | `int` | Documento del que proviene |
| `content` | `str` | Texto del fragmento |
| `page_number` | `int \| null` | Página de origen |
| `section_title` | `str \| null` | Sección de origen |
| `score` | `float` | Puntuación de relevancia |
| `source` | `str` | Estrategia que produjo el resultado |

### `SearchResponse`

| Campo | Tipo | Descripción |
|---|---|---|
| `results` | `list[SearchResultItem]` | Fragmentos encontrados |
| `query` | `str` | Consulta original |
| `total` | `int` | Número de resultados |

---

## `POST /api/v1/search`

- **Auth**: Bearer + membresía de organización
- **Content-Type**: `application/json`
- **Status éxito**: `200 OK`

### Ejemplos

Búsqueda semántica (comportamiento por defecto):

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "cláusula de confidencialidad",
    "matter_id": 1
  }'
```

```json
{
  "results": [
    {
      "chunk_id": 512,
      "document_id": 42,
      "content": "DÉCIMO: El trabajador se obliga a mantener estricta reserva sobre toda información...",
      "page_number": 4,
      "section_title": "Cláusula Décima",
      "score": 0.91,
      "source": "embedding"
    }
  ],
  "query": "cláusula de confidencialidad",
  "total": 1
}
```

Ampliando el número de resultados:

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "plazo de preaviso",
    "matter_id": 1,
    "top_k": 15
  }'
```

Forzando búsqueda por keyword:

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artículo 162",
    "matter_id": 1,
    "use_embeddings": false
  }'
```

---

## Semántica vs keyword

| Criterio | `use_embeddings: true` | `use_embeddings: false` |
|---|---|---|
| Coincidencia | Similitud de significado | Coincidencia literal de términos |
| Buena para | Preguntas en lenguaje natural, sinónimos, paráfrasis | Referencias exactas: números de artículo, RUT, nombres propios |
| Requisitos | API key de embeddings configurada | Ninguno |
| Latencia | Mayor (hay que vectorizar la consulta) | Menor |

Cadena de resolución de la API key de embeddings (`app/services/embeddings.py`):

```
EMBEDDING_API_KEY → OPENAI_API_KEY → LLM_API_KEY
```

Sin ninguna de las tres, la búsqueda semántica no puede vectorizar la consulta. Comprueba el campo `source` de cada resultado para saber qué estrategia se aplicó realmente.

### Prerrequisito: documentos procesados

Los fragmentos y sus embeddings se generan en el pipeline de procesamiento del documento. Un documento recién subido cuyo `status` aún no indique procesamiento completo **no aparece** en los resultados. Verifícalo con `GET /api/v1/documents/{document_id}` — ver [documents.md](documents.md#ciclo-de-vida-de-un-documento).

---

## Errores comunes

| Código | Causa | `detail` de ejemplo |
|---|---|---|
| `401` | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | Usuario sin membresía de organización | `"Usuario sin organización asignada"` |
| `404` | El caso no existe o pertenece a otra organización | `"Caso no encontrado"` |
| `422` | Falta `query` o `matter_id`, o los tipos no coinciden | Detalle estructurado de pydantic |
| `429` | Límite del plan superado | `"Rate limit exceeded"` |
| `500` | Fallo del proveedor de embeddings | `"Error al ejecutar la búsqueda"` |

Un caso sin documentos procesados no es un error: devuelve `200` con `results: []` y `total: 0`.

---

## Rate limits

Sin decorador `@limiter.limit` específico. Aplica el límite por organización según plan (`free` 100/min, `basic` 500/min, `pro` 2000/min, `enterprise` sin límite).

Cada búsqueda con `use_embeddings: true` consume una llamada al proveedor de embeddings para vectorizar la consulta. En interfaces con búsqueda mientras se escribe, aplica *debounce* en el cliente.

Ver [rate limits globales](../../openapi.md#rate-limits).

---

## Notas de seguridad

- **Aislamiento multi-tenant**: el `matter_id` se valida contra la organización del token antes de buscar. Es el control que impide recuperar fragmentos de documentos de otro tenant.
- **Alcance obligatoriamente acotado**: no hay búsqueda global. Mantén esa restricción: un endpoint de búsqueda sin `matter_id` cruzaría los límites de caso y ampliaría el radio de una eventual fuga.
- **Contenido privilegiado**: `content` devuelve texto literal de documentos que pueden estar amparados por el secreto profesional. No lo registres en logs de acceso ni en herramientas de analítica de frontend.
- **La consulta viaja al proveedor de embeddings**: con `use_embeddings: true`, el texto de `query` se envía al proveedor externo para vectorizarlo. Si la consulta contiene datos sensibles, eso constituye una transferencia a un tercero.
- **`top_k` sin cota superior declarada**: el esquema no fija un máximo. Valores muy altos aumentan el tamaño de la respuesta y el coste de serialización; acótalo en el cliente.
