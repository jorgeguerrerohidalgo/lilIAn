# lilIAn — Documentación de la API REST v1

> Plataforma legaltech chilena asistida por IA.
>
> - **Base URL (desarrollo)**: `http://localhost:8000`
> - **Base URL (producción)**: variable según despliegue
> - **Versión API**: `v1`
> - **Prefijo global**: `/api/v1`
> - **Autenticación**: `Bearer <access_token>` (JWT, encabezado `Authorization`)
> - **OpenAPI interactivo**: `GET /docs` (Swagger UI) y `GET /redoc`
> - **Especificación JSON**: `GET /openapi.json`

---

## Tabla de contenidos

1. [Información general](#información-general)
2. [Autenticación](#autenticación)
3. [Convenciones](#convenciones)
4. [Endpoints raíz](#endpoints-raíz)
5. [Módulos](#módulos)
   - [Auth](#1-auth)
   - [Organizations](#2-organizations)
   - [Matters (Casos)](#3-matters-casos)
   - [Clients](#4-clients)
   - [Documents](#5-documents)
   - [Search](#6-search)
   - [Analysis](#7-analysis)
   - [Chat](#8-chat)
   - [Lawyer](#9-lawyer)
   - [Templates](#10-templates)
   - [Document Generator](#11-document-generator)
   - [Deadline Alerts](#12-deadline-alerts)
   - [Precedents](#13-precedents)
   - [SaaS / Subscription](#14-saas--subscription)
   - [Admin (Plataforma)](#15-admin-plataforma)
   - [Legal Areas](#16-legal-areas)
   - [Observability](#17-observability)
6. [Códigos de error](#códigos-de-error)
7. [Versionado](#versionado)

---

## Información general

| Campo | Valor |
|---|---|
| Título | `lilIAn - API` |
| Descripción | Plataforma legaltech chilena asistida por IA |
| Versión OpenAPI | `0.1.0` |
| Formato de respuesta | `application/json` |
| Timezone | UTC (ISO 8601) |
| Idioma de errores | Español (`detail`) |

### Aislamiento multi-tenant

Todos los endpoints (excepto `/`, `/health`, `/auth/*` y `/saas/plans`) filtran automáticamente los datos por `organization_id` extraído del JWT. Un usuario solo ve recursos de su organización.

### Roles disponibles

| Rol | Descripción |
|---|---|
| `OWNER` | Dueño, acceso total |
| `ADMIN` | Administrador |
| `LAWYER` | Abogado, gestiona casos y notas |
| `COMPANY_USER` | Usuario interno de empresa cliente |
| `CLIENT` | Cliente final (acceso restringido a sus casos) |
| `VIEWER` | Solo lectura |
| `PLATFORM_ADMIN` | Administrador de la plataforma (cross-tenant) |

---

## Autenticación

Todos los endpoints (salvo los marcados como públicos) requieren:

```http
Authorization: Bearer <jwt_token>
```

El token se obtiene con `POST /api/v1/auth/login` (OAuth2 Password Flow) y se envía en cada request. Los claims incluyen `sub` (user id) y `email`.

---

## Convenciones

- **Paginación**: `?skip=0&limit=50`
- **Filtros**: `?status=active&urgency=high`
- **IDs**: enteros autoincrementales
- **Fechas**: ISO 8601 (`2025-01-15T12:34:56Z`)
- **Idioma de campos**: español en respuestas (`detail`, `name`, etc.)

### Estructura de errores

```json
{
  "detail": "Mensaje de error en español"
}
```

---

## Endpoints raíz

### `GET /`

Información básica de la API.

- **Auth**: pública
- **Response 200**:
  ```json
  { "message": "lilIAn API", "version": "0.1.0" }
  ```

### `GET /health`

Health check.

- **Auth**: pública
- **Response 200**:
  ```json
  { "status": "healthy" }
  ```

### `GET /metrics`

Snapshot de observabilidad: contadores de requests, percentiles de latencia y conteos de negocio. Los conteos de negocio se cachean por 60s en el registry.

- **Auth**: pública (uso interno, expón detrás de red privada en producción)
- **Tag OpenAPI**: `observability`
- **Response 200**:
  ```json
  {
    "request_count": { "GET /api/v1/matters": 42, "POST /api/v1/auth/login": 15 },
    "error_count": { "unhandled_exception": 0, "metrics_db_failure": 0 },
    "latency_ms": {
      "GET /api/v1/matters": { "p50": 12.3, "p95": 88.1, "p99": 145.0, "count": 42 }
    },
    "business_counts": {
      "active_matters": 17,
      "active_documents": 3
    },
    "business_counts_loaded_at": 1735689600.0
  }
  ```

---

## Módulos

### 1. Auth

> Prefijo: `/api/v1/auth` · Tag OpenAPI: `auth`

#### `POST /api/v1/auth/register`

Registra un nuevo usuario y crea automáticamente una organización individual.

- **Auth**: pública
- **Status**: `201 Created`
- **Body** (`UserCreate`):
  ```json
  {
    "email": "usuario@ejemplo.cl",
    "password": "Secreta123!",
    "full_name": "Juan Pérez"
  }
  ```
- **Response** (`UserResponse`):
  ```json
  {
    "id": 1,
    "email": "usuario@ejemplo.cl",
    "full_name": "Juan Pérez",
    "status": "active"
  }
  ```
- **Errores**: `400` si el email ya está registrado.

#### `POST /api/v1/auth/login`

Autentica al usuario y devuelve un JWT.

- **Auth**: pública (OAuth2 Password Flow)
- **Content-Type**: `application/x-www-form-urlencoded`
- **Body** (`OAuth2PasswordRequestForm`):
  | Campo | Tipo | Descripción |
  |---|---|---|
  | `username` | string | Email del usuario |
  | `password` | string | Contraseña |
- **Response** (`Token`):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Errores**: `401` credenciales inválidas.
- **Efecto**: actualiza `user.last_login_at`.

#### `GET /api/v1/auth/me`

Devuelve el usuario autenticado.

- **Auth**: requerida
- **Response**: `UserResponse`

---

### 2. Organizations

> Prefijo: `/api/v1/organizations` · Tag OpenAPI: `organizations`

#### `GET /api/v1/organizations`

Lista las organizaciones a las que pertenece el usuario actual.

- **Auth**: requerida
- **Response 200**: `[OrganizationResponse]`
- **Ejemplo**:
  ```json
  [
    {
      "id": 1,
      "name": "Estudio Pérez & Asoc.",
      "type": "firm",
      "rut": "76.123.456-7",
      "billing_email": "facturacion@estudio.cl"
    }
  ]
  ```

#### `POST /api/v1/organizations`

Crea una nueva organización y asigna al usuario como `OWNER`.

- **Auth**: requerida
- **Status**: `201 Created`
- **Body** (`OrganizationCreate`):
  ```json
  {
    "name": "Mi Estudio",
    "type": "firm",
    "rut": "76.123.456-7",
    "billing_email": "billing@estudio.cl"
  }
  ```

#### `GET /api/v1/organizations/me`

Devuelve la organización activa del usuario.

- **Auth**: requerida
- **Errores**: `404` si no se encuentra.

#### `GET /api/v1/organizations/me/members`

Lista los miembros de la organización activa con sus datos básicos.

- **Auth**: requerida
- **Response 200**:
  ```json
  [
    {
      "id": 1,
      "user_id": 5,
      "role": "owner",
      "user": {
        "id": 5,
        "email": "user@ejemplo.cl",
        "full_name": "Juan Pérez",
        "status": "active"
      }
    }
  ]
  ```

---

### 3. Matters (Casos)

> Prefijo: `/api/v1/matters` · Tag OpenAPI: `matters`
>
> Permisos:
> - **READ**: `OWNER, ADMIN, LAWYER, COMPANY_USER, CLIENT, VIEWER`
> - **WRITE**: `OWNER, ADMIN, LAWYER`
> - **DELETE**: `OWNER, ADMIN`
>
> Los usuarios con rol `CLIENT` solo ven casos cuyos clientes les pertenecen.

#### `GET /api/v1/matters`

Lista casos con paginación y filtros.

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Default | Descripción |
  |---|---|---|---|
  | `skip` | int | `0` | Offset |
  | `limit` | int | `50` | Límite de resultados |
  | `status_filter` | string | — | Filtrar por estado |
  | `client_id` | int | — | Filtrar por cliente |
- **Response**: `[MatterResponse]`

#### `POST /api/v1/matters`

Crea un nuevo caso.

- **Auth**: requerida (rol WRITE)
- **Status**: `201 Created`
- **Body** (`MatterCreate`):
  ```json
  {
    "client_id": 1,
    "title": "Despido injustificado Juan Soto",
    "matter_type": "labor",
    "description": "Cliente fue despedido sin causal",
    "urgency": "high",
    "counterparty_name": "Empresa XYZ S.A.",
    "relevant_date": "2025-01-10",
    "source_channel": "email"
  }
  ```
- **Errores**: `404` cliente no pertenece a la organización.

#### `GET /api/v1/matters/{matter_id}`

Obtiene un caso por ID.

- **Auth**: requerida
- **Errores**: `404` no existe, `403` no pertenece a la organización.

#### `PATCH /api/v1/matters/{matter_id}`

Actualiza parcialmente un caso.

- **Auth**: requerida (rol WRITE)
- **Body** (`MatterUpdate`): cualquier subconjunto de campos de `MatterCreate`.

#### `DELETE /api/v1/matters/{matter_id}`

Elimina un caso (hard delete).

- **Auth**: requerida (rol ADMIN)
- **Status**: `204 No Content`

#### `GET /api/v1/matters/{matter_id}/participants`

Devuelve los participantes extraídos de los análisis del caso, con su nivel de completitud documental.

- **Auth**: requerida
- **Response**:
  ```json
  {
    "matter_id": 1,
    "participants": [
      {
        "name": "Juan Soto",
        "rut": "12.345.678-9",
        "role": "demandante",
        "documents": [1, 2, 3],
        "documents_types": ["contrato_trabajo", "finiquito"],
        "documents_count": 2,
        "required_documents": ["contrato_trabajo", "finiquito", "liquidaciones"],
        "missing_documents": ["liquidaciones"],
        "completeness_score": 0.67
      }
    ],
    "requirements": {
      "required": ["contrato_trabajo", "finiquito"],
      "recommended": ["cartola_afp"]
    }
  }
  ```

---

### 4. Clients

> Prefijo: `/api/v1/clients` · Tag OpenAPI: `clients`

#### `POST /api/v1/clients`

Crea un cliente en la organización del usuario.

- **Auth**: requerida
- **Status**: `201 Created`
- **Body** (`ClientCreate`):
  ```json
  {
    "name": "Juan Soto",
    "company_name": "Empresa S.A.",
    "rut": "12.345.678-9",
    "email": "juan@cliente.cl",
    "phone": "+56912345678",
    "address": "Av. Principal 123, Santiago",
    "notes": "Cliente referido por María"
  }
  ```
- **Response** (`ClientResponse`).

#### `GET /api/v1/clients`

Lista clientes activos con búsqueda opcional.

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Descripción |
  |---|---|---|
  | `search` | string | Búsqueda parcial en `name`, `company_name`, `rut`, `email` |
- **Response**: `[ClientResponse]`

#### `GET /api/v1/clients/{client_id}`

Obtiene un cliente por ID.

- **Auth**: requerida
- **Errores**: `404` no existe.

#### `PUT /api/v1/clients/{client_id}`

Reemplaza los datos de un cliente.

- **Auth**: requerida
- **Body**: `ClientCreate` completo.

#### `DELETE /api/v1/clients/{client_id}`

Soft delete: marca `is_active = false`.

- **Auth**: requerida
- **Status**: `204 No Content`

---

### 5. Documents

> Prefijo: `/api/v1/documents` · Tag OpenAPI: `documents`
>
> Tipos MIME permitidos: `application/pdf`, DOCX, DOC, TXT.
> Tamaño máximo: **50 MB**.

#### `POST /api/v1/documents/matters/{matter_id}/documents`

Sube un documento y lo encola para procesamiento asíncrono.

- **Auth**: requerida
- **Content-Type**: `multipart/form-data`
- **Form**:
  | Campo | Tipo | Descripción |
  |---|---|---|
  | `file` | UploadFile | Archivo a subir |
- **Status**: `201 Created`
- **Response** (`DocumentResponse`):
  ```json
  {
    "id": 42,
    "matter_id": 1,
    "original_filename": "contrato.pdf",
    "mime_type": "application/pdf",
    "file_size": 245678,
    "status": "uploaded",
    "created_at": "2025-01-15T12:00:00Z"
  }
  ```
- **Errores**:
  - `400` tipo MIME no permitido
  - `400` tamaño excedido
  - `404` caso no existe
- **Comportamiento asíncrono**: encola job RQ `document_processing`.

#### `GET /api/v1/documents/matters/{matter_id}/documents`

Lista los documentos de un caso.

- **Auth**: requerida
- **Response**: `[DocumentResponse]`

#### `GET /api/v1/documents/{document_id}`

Obtiene un documento por ID.

- **Auth**: requerida

#### `DELETE /api/v1/documents/{document_id}`

Elimina un documento, sus chunks asociados y el archivo físico.

- **Auth**: requerida
- **Status**: `204 No Content`

#### `POST /api/v1/documents/{document_id}/process`

Re-encola el documento para procesamiento (reset a estado `uploaded`).

- **Auth**: requerida
- **Response**:
  ```json
  {
    "message": "Documento encolado para procesamiento",
    "document_id": 42
  }
  ```
- **Errores**: `500` si no se puede encolar (Redis no disponible).

#### `POST /api/v1/documents/{document_id}/analyze`

Analiza el documento extrayendo datos estructurados (estilo Harvey.ai).

- **Auth**: requerida
- **Requisito**: el documento debe tener `extracted_text` (procesado previamente).
- **Response**:
  ```json
  {
    "message": "Documento analizado exitosamente",
    "document_id": 42,
    "has_analysis": true
  }
  ```
- **Errores**:
  - `400` sin texto extraído
  - `500` error de análisis

#### `GET /api/v1/documents/{document_id}/analysis`

Recupera el análisis estructurado.

- **Auth**: requerida
- **Response**:
  ```json
  {
    "has_analysis": true,
    "document_id": 42,
    "document_type": "contrato_prestacion_servicios",
    "participants": [
      { "name": "Empresa X", "rut": "76.123.456-7", "role": "prestador" }
    ],
    "financial_terms": { "monto_total": 5000000, "moneda": "CLP" },
    "obligations": ["Entregar informe mensual", "Pagar dentro de 30 días"],
    "clauses_by_type": { "terminacion": [], "confidencialidad": [] },
    "unusual_clauses": [],
    "risk_assessment": [
      { "type": "terminacion", "level": "high", "description": "..." }
    ],
    "contract_timeline": [],
    "legal_references": [],
    "indexed_content": true,
    "created_at": "2025-01-15T12:30:00Z"
  }
  ```
- Si no hay análisis: `{ "has_analysis": false, "document_id": 42 }`.

#### `GET /api/v1/documents/matters/{matter_id}/risk-dashboard`

Dashboard agregado de riesgos de todos los documentos analizados de un caso.

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Default | Descripción |
  |---|---|---|---|
  | `level` | string | — | `high`, `medium`, `low` |
  | `risk_type` | string | — | `terminacion`, `penalidades`, etc. |
  | `sort_by` | string | `score` | `score`, `level`, `type` |
  | `sort_order` | string | `desc` | `asc`, `desc` |
- **Response**:
  ```json
  {
    "matter_id": 1,
    "documents_analyzed": 5,
    "total_risks": 12,
    "risk_summary": { "high": 3, "medium": 6, "low": 3 },
    "risk_types": ["terminacion", "penalidades", "confidencialidad"],
    "risks": [
      {
        "document_id": 42,
        "document_name": "contrato.pdf",
        "clause_type": "terminacion",
        "risk_level": "high",
        "risk_score": 0.85,
        "description": "..."
      }
    ]
  }
  ```

---

### 6. Search

> Prefijo: `/api/v1/search` · Tag OpenAPI: `search`

#### `POST /api/v1/search`

Búsqueda híbrida (semántica + keyword) sobre los chunks de un caso.

- **Auth**: requerida
- **Body** (`SearchRequest`):
  ```json
  {
    "query": "cláusula de término anticipado",
    "matter_id": 1,
    "top_k": 5,
    "use_embeddings": true
  }
  ```
- **Response** (`SearchResponse`):
  ```json
  {
    "results": [
      {
        "chunk_id": 102,
        "document_id": 42,
        "content": "El prestador podrá dar término anticipado...",
        "page_number": 3,
        "section_title": "Cláusula 9",
        "score": 0.87,
        "source": "hybrid"
      }
    ],
    "query": "cláusula de término anticipado",
    "total": 1
  }
  ```
- **Comportamiento**:
  - Si `use_embeddings=true` y falla el provider, hace fallback automático a keyword.
  - `source` puede ser: `hybrid`, `semantic`, `keyword`.

---

### 7. Analysis

> Prefijo: `/api/v1/analysis` · Tag OpenAPI: `analysis`

#### `POST /api/v1/analysis`

Genera un análisis en segundo plano para un caso.

- **Auth**: requerida
- **Status**: `202 Accepted`
- **Body** (`GenerateAnalysisRequest`):
  ```json
  { "matter_id": 1 }
  ```
- **Response**:
  ```json
  {
    "message": "Análisis iniciado en segundo plano",
    "matter_id": 1,
    "status": "processing"
  }
  ```

#### `GET /api/v1/analysis/matters/{matter_id}`

Lista todos los análisis de un caso (ordenados por fecha desc).

- **Auth**: requerida
- **Response**: `[AnalysisReportResponse]`

#### `GET /api/v1/analysis/reports/{report_id}`

Obtiene un informe con sus riesgos.

- **Auth**: requerida
- **Response** (`AnalysisReportDetailResponse`):
  ```json
  {
    "id": 1,
    "matter_id": 1,
    "summary": "Contrato de prestación de servicios con cláusulas estándar...",
    "confidence": 0.85,
    "validation_summary": { "status": "complete", "missing": [] },
    "risks": [
      { "id": 1, "level": "red", "title": "Término unilateral", "description": "..." }
    ],
    "created_at": "2025-01-15T13:00:00Z"
  }
  ```

#### `GET /api/v1/analysis/matters/{matter_id}/latest`

Obtiene el último análisis generado para un caso.

- **Auth**: requerida
- **Errores**: `404` si no hay análisis.

#### `GET /api/v1/analysis/matters/{matter_id}/risks`

Lista riesgos de un caso (ordenados por nivel y fecha desc).

- **Auth**: requerida
- **Response**: `[RiskItemResponse]`

#### `PATCH /api/v1/analysis/risks/{risk_id}/review`

Actualiza el estado de revisión de un riesgo.

- **Auth**: requerida
- **Query param**: `review_status` (string) — valores: `pending`, `reviewed`, `accepted`, `dismissed`
- **Response**:
  ```json
  {
    "message": "Estado actualizado",
    "risk_id": 1,
    "review_status": "accepted"
  }
  ```

---

### 8. Chat

> Prefijo: `/api/v1/chat` · Tag OpenAPI: `chat`

#### `POST /api/v1/chat/sessions`

Crea una nueva sesión de chat ligada a un caso.

- **Auth**: requerida
- **Status**: `201 Created`
- **Body** (`CreateSessionRequest`):
  ```json
  { "matter_id": 1, "title": "Consulta sobre despido" }
  ```
- **Response** (`ChatSessionResponse`).

#### `GET /api/v1/chat/sessions`

Lista sesiones de chat.

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Descripción |
  |---|---|---|
  | `matter_id` | int (opcional) | Filtrar por caso |
- **Response**: `[ChatSessionResponse]`

#### `GET /api/v1/chat/sessions/{session_id}/messages`

Obtiene el historial de mensajes de una sesión.

- **Auth**: requerida
- **Response**: `[ChatMessageResponse]`

#### `POST /api/v1/chat/message`

Envía un mensaje en una sesión. Persiste el mensaje del usuario, genera respuesta del asistente, y la persiste.

- **Auth**: requerida
- **Body** (`SendMessageRequest`):
  ```json
  {
    "session_id": 1,
    "message": "¿Cuáles son los riesgos del contrato?",
    "legal_area_override": "labor"
  }
  ```
- **Response** (`MessageResponse`):
  ```json
  {
    "content": "Basándome en el documento, identifico tres riesgos principales...",
    "session_id": 1,
    "message_id": 42
  }
  ```
- **Nota**: `legal_area_override` acepta: `labor`, `civil`, `consumer`, `family`, `commerce`, `penal`, `other`.

#### `DELETE /api/v1/chat/sessions/{session_id}`

Elimina una sesión (y sus mensajes en cascada).

- **Auth**: requerida
- **Status**: `204 No Content`

---

### 9. Lawyer

> Prefijo: `/api/v1/lawyer` · Tag OpenAPI: `lawyer`
>
> Acceso: roles `LAWYER`, `ADMIN`, `OWNER`.

#### `GET /api/v1/lawyer/cases`

Lista casos del "pipeline" del abogado: estados `new`, `analysis_ready`, `pending_human_review`, `missing_information`, `contact_client`.

- **Auth**: requerida (rol LAWYER+)
- **Query params**:
  | Nombre | Tipo | Descripción |
  |---|---|---|
  | `status_filter` | string | Filtrar por estado |
  | `urgency_filter` | string | Filtrar por urgencia |
- **Response** (`[LawyerMatterResponse]`):
  ```json
  [
    {
      "id": 1,
      "title": "Despido injustificado",
      "matter_type": "labor",
      "status": "pending_human_review",
      "urgency": "high",
      "description": "...",
      "counterparty_name": "Empresa XYZ",
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T11:30:00Z",
      "risk_count": 3,
      "has_analysis": true,
      "created_by_name": "Juan Pérez"
    }
  ]
  ```

#### `POST /api/v1/lawyer/matters/{matter_id}/notes`

Agrega una nota al caso.

- **Auth**: requerida
- **Status**: `201 Created`
- **Body** (`MatterNoteCreate`):
  ```json
  { "matter_id": 1, "content": "Cliente confirmó que recibió carta de despido." }
  ```

#### `GET /api/v1/lawyer/matters/{matter_id}/notes`

Lista las notas de un caso (ordenadas por fecha desc).

- **Auth**: requerida
- **Response**: `[MatterNoteResponse]`

#### `PATCH /api/v1/lawyer/matters/{matter_id}/status`

Cambia el estado de un caso y registra el histórico.

- **Auth**: requerida
- **Body** (`MatterStatusUpdate`):
  ```json
  { "matter_id": 1, "new_status": "in_progress", "notes": "Iniciando revisión" }
  ```
- **Errores**: `400` si `new_status` no es válido.
- **Valores `new_status`**: `new`, `analysis_ready`, `pending_human_review`, `missing_information`, `contact_client`, `in_progress`, `closed`, `archived`.

#### `POST /api/v1/lawyer/matters/{matter_id}/assign`

Asigna un caso a un abogado.

- **Auth**: requerida (rol LAWYER+)
- **Query param**: `lawyer_user_id` (int)
- **Errores**: `400` si el usuario no es abogado válido.
- **Response**:
  ```json
  {
    "message": "Abogado asignado",
    "matter_id": 1,
    "lawyer_id": 5
  }
  ```

#### `GET /api/v1/lawyer/matters/{matter_id}/summary`

Resumen ejecutivo del caso: datos básicos, último análisis, conteo de riesgos, notas recientes.

- **Auth**: requerida
- **Response**:
  ```json
  {
    "matter": {
      "id": 1,
      "title": "Despido injustificado",
      "status": "pending_human_review",
      "urgency": "high",
      "created_at": "2025-01-15T10:00:00Z"
    },
    "analysis": {
      "exists": true,
      "summary": "...",
      "confidence": 0.85,
      "created_at": "2025-01-15T11:00:00Z"
    },
    "risks": { "total": 5, "red": 2, "yellow": 2, "green": 1, "gray": 0 },
    "recent_notes": []
  }
  ```

---

### 10. Templates

> Prefijo: `/api/v1/templates` · Tag OpenAPI: `templates`

#### `GET /api/v1/templates`

Lista plantillas disponibles (globales + de la organización).

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Descripción |
  |---|---|---|
  | `template_type` | string | `prompt`, `email`, `checklist` |
- **Response**: `[TemplateResponse]`
- **Nota**: si la organización no tiene plantillas, se siembran las plantillas por defecto (4 incluidas).

#### `POST /api/v1/templates`

Crea una nueva plantilla.

- **Auth**: requerida
- **Status**: `201 Created`
- **Body** (`TemplateCreate`):
  ```json
  {
    "template_type": "prompt",
    "name": "Análisis de finiquito",
    "description": "Prompt para análisis de finiquitos",
    "content": "...",
    "is_global": false
  }
  ```

#### `GET /api/v1/templates/{template_id}`

Obtiene una plantilla por ID.

- **Auth**: requerida
- **Errores**: `404` no existe, `403` no pertenece a la organización.

#### `DELETE /api/v1/templates/{template_id}`

Elimina una plantilla.

- **Auth**: requerida
- **Errores**: `403` si es global.
- **Status**: `204 No Content`

---

### 11. Document Generator

> Prefijo: `/api/v1/doc-templates` · Tag OpenAPI: `document-generator`

#### `GET /api/v1/doc-templates/templates`

Lista templates de generación de documentos (diferente a `/templates`).

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Descripción |
  |---|---|---|
  | `category` | string | Filtrar por categoría |
- **Response** (`[TemplateResponse]`):
  ```json
  [
    {
      "id": "finiquito_001",
      "name": "Finiquito estándar",
      "category": "laboral",
      "description": "Carta de finiquito conforme a la ley",
      "variables": [
        { "name": "empleador", "type": "string", "required": true },
        { "name": "trabajador", "type": "string", "required": true }
      ]
    }
  ]
  ```

#### `GET /api/v1/doc-templates/templates/categories`

Lista todas las categorías disponibles.

- **Auth**: requerida
- **Response**:
  ```json
  { "categories": ["laboral", "civil", "comercial"] }
  ```

#### `GET /api/v1/doc-templates/templates/{template_id}`

Detalle de un template con sus variables.

- **Auth**: requerida
- **Errores**: `404` no existe.

#### `POST /api/v1/doc-templates/suggest-variables`

Usa LLM para sugerir valores de variables a partir de los documentos de un caso.

- **Auth**: requerida
- **Query params**: `template_id` (string, requerido)
- **Body** (`SuggestVariablesRequest`):
  ```json
  { "matter_id": 1, "matter_type": "labor" }
  ```
- **Response**: objeto con variables sugeridas extraídas del contexto.

#### `POST /api/v1/doc-templates/generate`

Genera un documento a partir de un template y variables.

- **Auth**: requerida
- **Body** (`GenerateDocumentRequest`):
  ```json
  {
    "template_id": "finiquito_001",
    "variables": {
      "empleador": "Empresa XYZ S.A.",
      "trabajador": "Juan Soto"
    },
    "matter_id": 1
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "errors": [],
    "content": "En Santiago, a 15 de enero de 2025...",
    "document_name": "Finiquito - Juan Soto",
    "template_name": "Finiquito estándar"
  }
  ```

#### `POST /api/v1/doc-templates/templates/{template_id}/validate`

Valida las variables antes de generar.

- **Auth**: requerida
- **Body**: `dict` con las variables a validar.
- **Response**:
  ```json
  { "valid": true, "errors": [] }
  ```

---

### 12. Deadline Alerts

> Prefijo: `/api/v1/alerts` · Tag OpenAPI: `deadline-alerts`

#### `GET /api/v1/alerts/`

Lista alertas de plazos de la organización.

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Default | Descripción |
  |---|---|---|---|
  | `status` | string | — | `pending`, `acknowledged`, `resolved`, `dismissed` |
  | `urgency` | string | — | `critical`, `high`, `medium`, `low` |
  | `overdue` | bool | — | Filtrar solo vencidas |
  | `matter_id` | int | — | Filtrar por caso |
  | `limit` | int | `50` | (max 200) |
  | `offset` | int | `0` | |
- **Response**: `[AlertDict]`:
  ```json
  [
    {
      "id": 1,
      "matter_id": 1,
      "title": "Vencimiento plazo demanda",
      "due_date": "2025-02-01",
      "days_remaining": 17,
      "is_overdue": false,
      "urgency": "high",
      "importance_score": 0.9,
      "status": "pending",
      "matter_title": "Despido injustificado"
    }
  ]
  ```

#### `GET /api/v1/alerts/summary`

Resumen de alertas para dashboard.

- **Auth**: requerida
- **Response** (`AlertsSummary`):
  ```json
  {
    "total": 25,
    "overdue": 3,
    "critical": 2,
    "high": 5,
    "medium": 10,
    "low": 8,
    "by_matter": [
      { "matter_id": 1, "matter_title": "Despido", "count": 4 }
    ]
  }
  ```

#### `GET /api/v1/alerts/matters/{matter_id}`

Alertas de un caso específico.

- **Auth**: requerida
- **Query params**: `status`, `urgency`.

#### `GET /api/v1/alerts/{alert_id}`

Detalle de una alerta.

- **Auth**: requerida

#### `PATCH /api/v1/alerts/{alert_id}`

Actualiza el estado de una alerta (acknowledge, resolve, dismiss).

- **Auth**: requerida
- **Body** (`DeadlineAlertUpdate`):
  ```json
  { "status": "acknowledged" }
  ```
- **Efecto**: setea `acknowledged_at`/`resolved_at` y `acknowledged_by`/`resolved_by` automáticamente.

#### `POST /api/v1/alerts/matter/{matter_id}/refresh`

Recalcula el estado de vencidas para todas las alertas de un caso.

- **Auth**: requerida
- **Response**:
  ```json
  { "updated": 5 }
  ```

---

### 13. Precedents

> Prefijo: `/api/v1/precedents` · Tag OpenAPI: `precedents`

#### `GET /api/v1/precedents/search`

Búsqueda de precedentes judiciales (semántica + keyword).

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Default | Descripción |
  |---|---|---|---|
  | `q` | string | requerido (min 3) | Texto de búsqueda |
  | `court` | string | — | Filtrar por tribunal |
  | `year` | int | — | Filtrar por año |
  | `legal_area` | string | — | Filtrar por área legal |
  | `matter_type` | string | — | Filtrar por tipo |
  | `search_type` | string | `hybrid` | `semantic`, `keyword`, `hybrid` |
  | `top_k` | int | `5` | (max 20) |
- **Response** (`PrecedentSearchResponse`):
  ```json
  {
    "results": [
      {
        "id": 1,
        "court": "Corte Suprema",
        "tribunal": "Tercera Sala",
        "year": 2023,
        "roll_number": "1234-2023",
        "full_citation": "CS, 12 mayo 2023, Rol 1234-2023",
        "legal_area": "labor",
        "summary": "...",
        "score": 0.92
      }
    ],
    "query": "despido sin causal",
    "total": 1,
    "search_type": "semantic"
  }
  ```

#### `GET /api/v1/precedents/context`

Obtiene contexto de precedentes formateado para integración con RAG.

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Default | Descripción |
  |---|---|---|---|
  | `q` | string | requerido (min 3) | Texto |
  | `court`, `year`, `legal_area` | — | — | Filtros |
  | `top_k` | int | `3` | (max 10) |
- **Response**:
  ```json
  { "context": "Precedente 1: ...\n\nPrecedente 2: ...", "count": 3 }
  ```

#### `GET /api/v1/precedents/courts`

Lista los tribunales disponibles en la base de precedentes.

- **Auth**: requerida
- **Response**:
  ```json
  { "courts": ["Corte Suprema", "Corte de Apelaciones de Santiago"] }
  ```

#### `GET /api/v1/precedents/legal-areas`

Lista las áreas legales disponibles en precedentes.

- **Auth**: requerida
- **Response**:
  ```json
  { "legal_areas": ["labor", "civil", "comercial"] }
  ```

#### `GET /api/v1/precedents/analytics`

Analítica agregada de precedentes (tendencias por año, área, tribunal).

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Descripción |
  |---|---|---|
  | `legal_area` | string | Filtro |
  | `court` | string | Filtro |
  | `year_from`, `year_to` | int | Rango de años |
  | `matter_type` | string | Filtro |
  | `include_text_analysis` | bool | (más lento) análisis textual |
- **Response**: estructura de analítica con counts y series temporales.

#### `GET /api/v1/precedents/analytics/filters`

Opciones de filtros disponibles según los datos existentes.

- **Auth**: requerida
- **Response**:
  ```json
  {
    "legal_areas": [...],
    "courts": [...],
    "years": { "min": 2010, "max": 2024 }
  }
  ```

#### `POST /api/v1/precedents/`

Crea un nuevo precedente y lo indexa para RAG.

- **Auth**: requerida
- **Status**: `201 Created`
- **Body** (`PrecedentCreateRequest`):
  ```json
  {
    "court": "Corte Suprema",
    "tribunal": "Tercera Sala",
    "year": 2024,
    "roll_number": "5678-2024",
    "full_citation": "CS, 10 marzo 2024, Rol 5678-2024",
    "legal_area": "labor",
    "matter_type": "despido",
    "summary": "La Corte resolvió que...",
    "decision": "acogido",
    "ponente": "Ministro Juan Pérez"
  }
  ```
- **Errores**: `400` precedente duplicado (mismo court/year/roll).

#### `GET /api/v1/precedents/{precedent_id}`

Obtiene un precedente por ID.

- **Auth**: requerida

---

### 14. SaaS / Subscription

> Prefijo: `/api/v1/saas` · Tag OpenAPI: `saas`

#### `GET /api/v1/saas/plans`

Lista los planes comerciales disponibles.

- **Auth**: pública
- **Response** (`[PlanResponse]`):
  ```json
  [
    {
      "id": 1,
      "name": "starter",
      "display_name": "Starter",
      "description": "Plan inicial",
      "documents_limit": 50,
      "analyses_limit": 25,
      "users_limit": 3,
      "monthly_price": 29990
    }
  ]
  ```

#### `GET /api/v1/saas/subscription`

Obtiene la suscripción activa de la organización.

- **Auth**: requerida
- **Response** (`SubscriptionResponse`):
  ```json
  {
    "id": 1,
    "plan_name": "starter",
    "status": "active",
    "documents_limit": 50,
    "analyses_limit": 25,
    "users_limit": 3,
    "monthly_price": 29990,
    "started_at": "2025-01-01T00:00:00Z",
    "renews_at": "2025-02-01T00:00:00Z",
    "documents_used": 12,
    "analyses_used": 5,
    "users_used": 2
  }
  ```

#### `POST /api/v1/saas/subscription`

Crea o renueva la suscripción (cancela la activa antes).

- **Auth**: requerida (rol OWNER/ADMIN)
- **Query param**: `plan_name` (string) — `starter`, `pro`, `enterprise`, etc.
- **Errores**: `404` plan no existe.
- **Response**:
  ```json
  { "message": "Suscripción creada", "plan": "starter" }
  ```

#### `GET /api/v1/saas/metrics`

Métricas agregadas de la organización.

- **Auth**: requerida
- **Response** (`OrganizationMetrics`):
  ```json
  {
    "total_matters": 12,
    "total_documents": 45,
    "total_analyses": 30,
    "total_users": 3,
    "matters_by_status": { "new": 2, "in_progress": 5, "closed": 5 },
    "matters_by_type": { "labor": 4, "civil": 5, "commerce": 3 },
    "documents_this_month": 8,
    "analyses_this_month": 6
  }
  ```

#### `GET /api/v1/saas/usage/events`

Eventos de uso de la organización (últimos N días).

- **Auth**: requerida
- **Query params**:
  | Nombre | Tipo | Default | Descripción |
  |---|---|---|---|
  | `days` | int | `30` | Ventana de tiempo |
- **Response**:
  ```json
  [
    {
      "id": 1,
      "event_type": "document_uploaded",
      "quantity": 1,
      "user_id": 5,
      "metadata": { "matter_id": 1 },
      "created_at": "2025-01-15T10:00:00Z"
    }
  ]
  ```

---

### 15. Admin (Plataforma)

> Prefijo: `/api/v1/admin` · Tag OpenAPI: `admin`
>
> **Requiere rol `PLATFORM_ADMIN`** (cross-tenant).

#### `GET /api/v1/admin/audit-logs`

Lista los logs de auditoría de la plataforma.

- **Auth**: requerida (PLATFORM_ADMIN)
- **Query params**:
  | Nombre | Tipo | Default | Descripción |
  |---|---|---|---|
  | `action_filter` | string | — | Filtrar por acción (`login`, etc.) |
  | `entity_type` | string | — | Tipo de entidad |
  | `days` | int | `7` | Ventana de tiempo |
  | `limit` | int | `100` | Límite |
- **Response**: `[AuditLogResponse]`.

#### `GET /api/v1/admin/organizations`

Lista todas las organizaciones (cross-tenant).

- **Auth**: requerida (PLATFORM_ADMIN)
- **Response**: `[OrganizationAdminResponse]`.

#### `GET /api/v1/admin/stats`

Estadísticas globales de plataforma.

- **Auth**: requerida (PLATFORM_ADMIN)
- **Response** (`DashboardStats`):
  ```json
  {
    "total_organizations": 50,
    "total_users": 200,
    "total_matters": 1500,
    "total_documents": 8000,
    "active_subscriptions": 45,
    "recent_logins": 120
  }
  ```

#### `POST /api/v1/admin/organizations/{org_id}/suspend`

Suspende una organización.

- **Auth**: requerida (PLATFORM_ADMIN)
- **Response**:
  ```json
  { "message": "Organización suspendida", "org_id": 5 }
  ```

#### `POST /api/v1/admin/organizations/{org_id}/activate`

Activa una organización previamente suspendida.

- **Auth**: requerida (PLATFORM_ADMIN)
- **Response**:
  ```json
  { "message": "Organización activada", "org_id": 5 }
  ```

---

### 16. Legal Areas

> Prefijo: `/api/v1/legal-areas` · Tag OpenAPI: `legal-areas`

#### `GET /api/v1/legal-areas`

Lista las áreas legales soportadas por el sistema (estáticas).

- **Auth**: requerida
- **Response** (`[LegalAreaResponse]`):
  ```json
  [
    { "code": "labor",    "name": "Derecho Laboral",         "description": "Contratos, remuneraciones, despidos, negociación colectiva" },
    { "code": "civil",    "name": "Derecho Civil",           "description": "Contratos, obligaciones, arriendos, responsabilidad civil" },
    { "code": "consumer", "name": "Derecho del Consumidor",  "description": "Protección al consumidor, cláusulas abusivas, garantías" },
    { "code": "family",   "name": "Derecho de Familia",      "description": "Divorcio, custodia, pensiones alimenticias" },
    { "code": "commerce", "name": "Derecho Comercial",       "description": "Sociedades, títulos de crédito, insolvencia" },
    { "code": "penal",    "name": "Derecho Penal",           "description": "Delitos, medidas cautelares, procedimiento penal" },
    { "code": "other",    "name": "Otras áreas",             "description": "Consultas generales o áreas no clasificadas" }
  ]
  ```

---

### 17. Observability

> Ruta: `/metrics` · Tag OpenAPI: `observability`

El endpoint `/metrics` (registrado en la raíz, sin prefijo `/api/v1`) está documentado en [Endpoints raíz](#endpoints-raíz).

---

## Códigos de error

| Código | Significado | Cuándo ocurre |
|---|---|---|
| `400` | Bad Request | Datos inválidos, validación fallida, recurso duplicado |
| `401` | Unauthorized | Token JWT ausente, inválido o expirado |
| `403` | Forbidden | Permisos insuficientes para el rol del usuario |
| `404` | Not Found | Recurso no existe o no pertenece a la organización del usuario |
| `500` | Internal Server Error | Error inesperado (BD, provider LLM, Redis, etc.) |

### Estructura uniforme

```json
{ "detail": "Mensaje en español" }
```

---

## Versionado

- **Versión actual**: `v1` (prefijo `/api/v1`)
- **Estrategia**: versionado por prefijo en URL (sin header `Accept-Version`)
- **Compatibilidad**: mientras no se publique `v2`, los endpoints `v1` se mantienen estables
- **Próxima versión**: cuando se introduzcan cambios incompatibles, se expondrá `/api/v2/...` y `/api/v1` seguirá funcionando por un periodo de deprecación documentado

### Mapeo router → archivo fuente

| Prefijo | Archivo |
|---|---|
| `/auth` | `app/api/endpoints/auth.py` |
| `/organizations` | `app/api/endpoints/organizations.py` |
| `/matters` | `app/api/endpoints/matters.py` |
| `/documents` | `app/api/endpoints/documents.py` |
| `/search` | `app/api/endpoints/search.py` |
| `/analysis` | `app/api/endpoints/analysis.py` |
| `/chat` | `app/api/endpoints/chat.py` |
| `/lawyer` | `app/api/endpoints/lawyer.py` |
| `/templates` | `app/api/endpoints/templates.py` |
| `/saas` | `app/api/endpoints/saas.py` |
| `/admin` | `app/api/endpoints/admin.py` |
| `/clients` | `app/api/endpoints/clients.py` |
| `/legal-areas` | `app/api/endpoints/legal_areas.py` |
| `/alerts` | `app/api/endpoints/deadline_alerts.py` |
| `/doc-templates` | `app/api/endpoints/document_generator.py` |
| `/precedents` | `app/api/endpoints/precedents.py` |
| `/metrics` | `app/api/endpoints/metrics.py` (prefijo raíz, sin `/api/v1`) |

> Nota: `app/api/endpoints/review.py` define endpoints de workflow de revisión (`/reviews`) pero actualmente **no está registrado** en `app/main.py`. Se incluye aquí solo a modo de referencia.
