# API — Documents

> Routers: `apps/backend/app/api/endpoints/documents.py` y `apps/backend/app/api/endpoints/document_analysis.py`
> Prefijo: `/api/v1/documents` · Tag OpenAPI: `documents`

Carga, procesamiento (extracción de texto y chunking) y análisis de riesgos de documentos legales asociados a un caso.

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Ciclo de vida de un documento](#ciclo-de-vida-de-un-documento)
- [Modelo de datos](#modelo-de-datos)
- [POST .../matters/{matter_id}/documents](#post-apiv1documentsmattersmatter_iddocuments)
- [GET .../matters/{matter_id}/documents](#get-apiv1documentsmattersmatter_iddocuments)
- [GET /api/v1/documents/{document_id}](#get-apiv1documentsdocument_id)
- [DELETE /api/v1/documents/{document_id}](#delete-apiv1documentsdocument_id)
- [POST /api/v1/documents/{document_id}/process](#post-apiv1documentsdocument_idprocess)
- [POST /api/v1/documents/{document_id}/analyze](#post-apiv1documentsdocument_idanalyze)
- [GET /api/v1/documents/{document_id}/analysis](#get-apiv1documentsdocument_idanalysis)
- [GET /api/v1/documents/{document_id}/analysis/markdown](#get-apiv1documentsdocument_idanalysismarkdown)
- [GET .../matters/{matter_id}/risk-dashboard](#get-apiv1documentsmattersmatter_idrisk-dashboard)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Éxito | Descripción |
|---|---|---|---|---|
| `POST` | `/api/v1/documents/matters/{matter_id}/documents` | Bearer + org | `201` | Sube un documento al caso |
| `GET` | `/api/v1/documents/matters/{matter_id}/documents` | Bearer + org | `200` | Lista los documentos del caso |
| `GET` | `/api/v1/documents/{document_id}` | Bearer + org | `200` | Detalle del documento |
| `DELETE` | `/api/v1/documents/{document_id}` | Bearer + org | `204` | Elimina el documento |
| `POST` | `/api/v1/documents/{document_id}/process` | Bearer + org | `200` | Reprocesa (extracción + chunking) |
| `POST` | `/api/v1/documents/{document_id}/analyze` | Bearer + org | `200` | Lanza análisis de riesgos con LLM |
| `GET` | `/api/v1/documents/{document_id}/analysis` | Bearer + org | `200` | Resultado del análisis (JSON) |
| `GET` | `/api/v1/documents/{document_id}/analysis/markdown` | Bearer + org | `200` | Resultado del análisis en Markdown |
| `GET` | `/api/v1/documents/matters/{matter_id}/risk-dashboard` | Bearer + org | `200` | Agregación de riesgos del caso |

---

## Ciclo de vida de un documento

```
upload  ──▶  storage (local | supabase)
   │
   └──▶ BackgroundTasks: extracción de texto ──▶ chunking ──▶ embeddings
                                                       │
                                                       └──▶ status pasa a procesado
   │
   └──▶ POST /analyze ──▶ LLM ──▶ riesgos detectados
                                    │
                                    └──▶ GET /analysis, /analysis/markdown, /risk-dashboard
```

El upload responde `201` de inmediato; el procesamiento ocurre en `BackgroundTasks`. Consulta `status` en `GET /documents/{id}` hasta que el documento esté procesado antes de lanzar `analyze` o `search`.

---

## Modelo de datos

### `DocumentResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `int` | |
| `organization_id` | `int` | |
| `matter_id` | `int` | Caso al que pertenece |
| `uploaded_by_user_id` | `int` | |
| `original_filename` | `str` | Nombre original del archivo |
| `mime_type` | `str \| null` | MIME detectado |
| `file_size` | `int \| null` | Bytes |
| `storage_path` | `str \| null` | Ruta interna. No es una URL pública |
| `file_hash` | `str \| null` | Hash del contenido, usado para deduplicación |
| `status` | `str` | Estado del pipeline de procesamiento |
| `extracted_text` | `str \| null` | Texto extraído. Puede ser muy largo |
| `page_count` | `int \| null` | Páginas detectadas |
| `detected_document_type` | `str \| null` | Tipo inferido (contrato, demanda, …) |
| `created_at` | `datetime` | |
| `processed_at` | `datetime \| null` | `null` mientras no termine el procesamiento |

---

## `POST /api/v1/documents/matters/{matter_id}/documents`

Sube un archivo al caso indicado.

- **Auth**: Bearer + membresía de organización
- **Content-Type**: `multipart/form-data`
- **Status éxito**: `201 Created`

### Form fields

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `file` | `UploadFile` | Sí | Archivo a subir |

### Restricciones de validación

| Restricción | Valor | Constante |
|---|---|---|
| Tamaño máximo | 50 MB | `MAX_FILE_SIZE = 50 * 1024 * 1024` en `documents.py` |
| MIME permitidos | `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (.docx), `application/msword` (.doc), `text/plain` | `ALLOWED_MIME_TYPES` |
| Verificación de contenido | Magic bytes (`MAGIC_SIGNATURES`) | El `Content-Type` declarado se contrasta con la firma real del archivo |

Un `Content-Type` fuera del conjunto permitido se rechaza y se registra en el log (`"Rejected upload with disallowed declared mime type"`).

### Ejemplo

```bash
curl -X POST http://localhost:8000/api/v1/documents/matters/1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@contrato-trabajo.pdf;type=application/pdf"
```

```json
{
  "id": 42,
  "organization_id": 3,
  "matter_id": 1,
  "uploaded_by_user_id": 12,
  "original_filename": "contrato-trabajo.pdf",
  "mime_type": "application/pdf",
  "file_size": 284512,
  "storage_path": "3/1/42-contrato-trabajo.pdf",
  "file_hash": "9f2c...",
  "status": "processing",
  "extracted_text": null,
  "page_count": null,
  "detected_document_type": null,
  "created_at": "2025-01-15T12:34:56Z",
  "processed_at": null
}
```

Subir un `.docx`:

```bash
curl -X POST http://localhost:8000/api/v1/documents/matters/1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@demanda.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document"
```

---

## `GET /api/v1/documents/matters/{matter_id}/documents`

Lista los documentos del caso.

```bash
curl http://localhost:8000/api/v1/documents/matters/1/documents \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta: `list[DocumentResponse]`.

---

## `GET /api/v1/documents/{document_id}`

Detalle de un documento, incluido `extracted_text` cuando el procesamiento ha terminado.

```bash
curl http://localhost:8000/api/v1/documents/42 \
  -H "Authorization: Bearer $TOKEN"
```

Comprobar sólo el estado sin arrastrar el texto completo:

```bash
curl -s http://localhost:8000/api/v1/documents/42 \
  -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d['processed_at'])"
```

---

## `DELETE /api/v1/documents/{document_id}`

- **Status éxito**: `204 No Content` (sin body)

```bash
curl -i -X DELETE http://localhost:8000/api/v1/documents/42 \
  -H "Authorization: Bearer $TOKEN"
```

Elimina el registro y su contenido asociado (chunks, embeddings).

---

## `POST /api/v1/documents/{document_id}/process`

Reprocesa el documento: vuelve a extraer texto, rehace el chunking y regenera embeddings. Útil tras un fallo de procesamiento o un cambio de modelo de embeddings.

Se ejecuta en `BackgroundTasks`; la respuesta es inmediata y no contiene el resultado.

```bash
curl -X POST http://localhost:8000/api/v1/documents/42/process \
  -H "Authorization: Bearer $TOKEN"
```

---

## `POST /api/v1/documents/{document_id}/analyze`

Lanza el análisis de riesgos del documento con el proveedor LLM configurado (`LLM_PROVIDER` / `LLM_MODEL`).

```bash
curl -X POST http://localhost:8000/api/v1/documents/42/analyze \
  -H "Authorization: Bearer $TOKEN"
```

Requiere que el documento tenga texto extraído. Si `LLM_API_KEY` / `OPENAI_API_KEY` no están configuradas, el análisis falla — ver [env-vars.md](../../env-vars.md#backend--llm).

---

## `GET /api/v1/documents/{document_id}/analysis`

Devuelve el resultado del análisis en JSON: riesgos detectados con nivel, descripción, fragmento fuente y recomendación.

```bash
curl http://localhost:8000/api/v1/documents/42/analysis \
  -H "Authorization: Bearer $TOKEN"
```

---

## `GET /api/v1/documents/{document_id}/analysis/markdown`

Mismo análisis renderizado en Markdown, listo para exportar o mostrar en la UI.

```bash
curl http://localhost:8000/api/v1/documents/42/analysis/markdown \
  -H "Authorization: Bearer $TOKEN"
```

---

## `GET /api/v1/documents/matters/{matter_id}/risk-dashboard`

Agrega los riesgos de todos los documentos del caso.

### Query params

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `level` | `str \| null` | `None` | Filtra por nivel de riesgo: `high`, `medium`, `low` |
| `risk_type` | `str \| null` | `None` | Filtra por tipo de riesgo |

```bash
# Dashboard completo
curl http://localhost:8000/api/v1/documents/matters/1/risk-dashboard \
  -H "Authorization: Bearer $TOKEN"

# Sólo riesgos altos
curl "http://localhost:8000/api/v1/documents/matters/1/risk-dashboard?level=high" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Errores comunes

| Código | Endpoint | Causa | `detail` de ejemplo |
|---|---|---|---|
| `400` | `upload` | Archivo mayor que el máximo | `"El archivo excede el tamaño máximo de 50MB"` |
| `400` | `upload` | MIME declarado no permitido o incoherente con los magic bytes | `"Tipo de archivo no permitido"` |
| `400` | `analyze` | Documento sin texto extraído todavía | `"El documento aún no ha sido procesado"` |
| `401` | todos | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | todos | Usuario sin membresía de organización | `"Usuario sin organización asignada"` |
| `404` | todos | Documento o caso inexistente / de otro tenant | `"Documento no encontrado"` |
| `422` | `upload` | Falta el campo `file` en el multipart | Detalle estructurado de pydantic |
| `429` | todos | Límite del plan superado | `"Rate limit exceeded"` |
| `500` | `analyze` | Fallo del proveedor LLM o API key ausente | `"Error al generar el análisis"` |

---

## Rate limits

Sin decorador `@limiter.limit` específico. Aplica el límite por organización según plan (`free` 100/min, `basic` 500/min, `pro` 2000/min, `enterprise` sin límite).

Adicionalmente, la suscripción impone cuotas de negocio independientes del rate limit HTTP:

| Cuota | Campo en `SubscriptionResponse` |
|---|---|
| Documentos | `documents_limit` / `documents_used` |
| Análisis | `analyses_limit` / `analyses_used` |

Consulta el consumo con `GET /api/v1/saas/subscription` — ver [saas.md](saas.md).

---

## Notas de seguridad

- **Path traversal**: el almacenamiento local resuelve `STORAGE_PATH` con `os.path.realpath` y lo usa como jaula. `storage_path` es una ruta interna, nunca una URL servida directamente.
- **Validación en dos capas**: además del `Content-Type` declarado, se verifica la firma real del archivo (`MAGIC_SIGNATURES`). Renombrar un `.exe` a `.pdf` no basta para pasar la validación.
- **Límite de tamaño**: 50 MB por archivo. El cuerpo se lee en memoria antes de comprobar el tamaño; ten en cuenta el consumo de RAM al dimensionar el proceso.
- **Contenido privilegiado**: `extracted_text` puede contener comunicaciones amparadas por el secreto profesional. No lo envíes a logs, sistemas de trazas ni servicios de terceros no contratados.
- **Envío al proveedor LLM**: `analyze` transmite el texto del documento al proveedor configurado (`LLM_PROVIDER`). Esto implica una transferencia de datos a un tercero; verifica que exista base contractual (DPA) antes de habilitarlo en producción.
- **Aislamiento multi-tenant**: los documentos filtran por `organization_id`; el acceso cross-tenant devuelve `404`.
- **Deduplicación por hash**: `file_hash` permite detectar cargas duplicadas, pero no debe usarse como control de acceso.
