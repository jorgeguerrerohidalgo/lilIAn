# API — Matters (Casos)

> Router: `apps/backend/app/api/endpoints/matters.py` · Prefijo: `/api/v1/matters` · Tag OpenAPI: `matters`

CRUD de casos legales. El caso (*matter*) es la entidad central: agrupa documentos, análisis, sesiones de chat y alertas de plazo.

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Modelo de datos](#modelo-de-datos)
- [GET /api/v1/matters](#get-apiv1matters)
- [POST /api/v1/matters](#post-apiv1matters)
- [GET /api/v1/matters/{matter_id}](#get-apiv1mattersmatter_id)
- [PATCH /api/v1/matters/{matter_id}](#patch-apiv1mattersmatter_id)
- [DELETE /api/v1/matters/{matter_id}](#delete-apiv1mattersmatter_id)
- [GET /api/v1/matters/{matter_id}/participants](#get-apiv1mattersmatter_idparticipants)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Éxito | Descripción |
|---|---|---|---|---|
| `GET` | `/api/v1/matters` | Bearer + org | `200` | Lista paginada de casos |
| `POST` | `/api/v1/matters` | Bearer + org | `201` | Crea un caso |
| `GET` | `/api/v1/matters/{matter_id}` | Bearer + org | `200` | Detalle de un caso |
| `PATCH` | `/api/v1/matters/{matter_id}` | Bearer + org | `200` | Actualización parcial |
| `DELETE` | `/api/v1/matters/{matter_id}` | Bearer + org | `204` | Elimina el caso |
| `GET` | `/api/v1/matters/{matter_id}/participants` | Bearer + org | `200` | Participantes del caso |

Todos exigen `Depends(get_current_user)` y `Depends(require_organization)`: el usuario debe estar autenticado **y** tener membresía en una organización.

---

## Modelo de datos

### `MatterResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `int` | |
| `organization_id` | `int` | Tenant propietario |
| `created_by_user_id` | `int` | |
| `client_id` | `int \| null` | Cliente asociado |
| `assigned_lawyer_id` | `int \| null` | Abogado asignado |
| `title` | `str` | |
| `matter_type` | `str` | Default `other` |
| `description` | `str \| null` | |
| `urgency` | `str` | Default `medium` |
| `status` | `str` | Estado del caso |
| `counterparty_name` | `str \| null` | Contraparte |
| `relevant_date` | `datetime \| null` | Fecha relevante del caso |
| `source_channel` | `str \| null` | Canal de origen |
| `created_at` | `datetime` | |
| `updated_at` | `datetime` | |
| `closed_at` | `datetime \| null` | |

---

## `GET /api/v1/matters`

Lista los casos de la organización del usuario.

### Query params

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `skip` | `int` | `0` | Offset de paginación |
| `limit` | `int` | `50` | Máximo de resultados |
| `status_filter` | `str` | `None` | Filtra por estado |
| `client_id` | `int` | `None` | Filtra por cliente |

### Response 200

`list[MatterResponse]`

```bash
curl "http://localhost:8000/api/v1/matters?skip=0&limit=20&status_filter=active" \
  -H "Authorization: Bearer $TOKEN"
```

```json
[
  {
    "id": 1,
    "organization_id": 3,
    "created_by_user_id": 12,
    "client_id": 7,
    "assigned_lawyer_id": 12,
    "title": "Despido injustificado - Pérez vs. Constructora XYZ",
    "matter_type": "laboral",
    "description": "Trabajador despedido sin carta de aviso.",
    "urgency": "high",
    "status": "active",
    "counterparty_name": "Constructora XYZ SpA",
    "relevant_date": "2025-01-10T00:00:00Z",
    "source_channel": "web",
    "created_at": "2025-01-15T12:34:56Z",
    "updated_at": "2025-01-16T08:00:00Z",
    "closed_at": null
  }
]
```

Filtrar por cliente:

```bash
curl "http://localhost:8000/api/v1/matters?client_id=7" \
  -H "Authorization: Bearer $TOKEN"
```

---

## `POST /api/v1/matters`

Crea un caso dentro de la organización del usuario autenticado.

### Request body — `MatterCreate`

| Campo | Tipo | Requerido | Default | Notas |
|---|---|---|---|---|
| `title` | `str` | Sí | — | |
| `matter_type` | `str` | No | `other` | Tipo de materia legal |
| `description` | `str \| null` | No | `null` | |
| `urgency` | `str` | No | `medium` | |
| `counterparty_name` | `str \| null` | No | `null` | |
| `relevant_date` | `datetime \| null` | No | `null` | ISO 8601 |
| `source_channel` | `str \| null` | No | `null` | |
| `organization_id` | `int \| null` | No | `null` | Se ignora en favor de la organización del token |
| `client_id` | `int \| null` | No | `null` | Debe pertenecer a la misma organización |

### Response 201 — `MatterResponse`

```bash
curl -X POST http://localhost:8000/api/v1/matters \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Despido injustificado - Pérez vs. Constructora XYZ",
    "matter_type": "laboral",
    "description": "Trabajador despedido sin carta de aviso.",
    "urgency": "high",
    "counterparty_name": "Constructora XYZ SpA",
    "client_id": 7
  }'
```

---

## `GET /api/v1/matters/{matter_id}`

### Path params

| Param | Tipo | Descripción |
|---|---|---|
| `matter_id` | `int` | Id del caso |

### Response 200 — `MatterResponse`

```bash
curl http://localhost:8000/api/v1/matters/1 \
  -H "Authorization: Bearer $TOKEN"
```

Si el caso pertenece a otra organización la respuesta es `404`, no `403`: la API no revela la existencia de recursos de otros tenants.

---

## `PATCH /api/v1/matters/{matter_id}`

Actualización parcial. Sólo se modifican los campos presentes en el body.

### Request body — `MatterUpdate`

Todos los campos son opcionales:

| Campo | Tipo |
|---|---|
| `title` | `str \| null` |
| `matter_type` | `str \| null` |
| `description` | `str \| null` |
| `status` | `str \| null` |
| `urgency` | `str \| null` |
| `counterparty_name` | `str \| null` |
| `relevant_date` | `datetime \| null` |
| `assigned_lawyer_id` | `int \| null` |
| `client_id` | `int \| null` |

### Response 200 — `MatterResponse`

```bash
curl -X PATCH http://localhost:8000/api/v1/matters/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "status": "closed", "urgency": "low" }'
```

Reasignar abogado:

```bash
curl -X PATCH http://localhost:8000/api/v1/matters/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "assigned_lawyer_id": 22 }'
```

---

## `DELETE /api/v1/matters/{matter_id}`

- **Status éxito**: `204 No Content` (sin body)

```bash
curl -i -X DELETE http://localhost:8000/api/v1/matters/1 \
  -H "Authorization: Bearer $TOKEN"
```

> Elimina el caso. Los recursos dependientes (documentos, análisis, sesiones de chat, alertas) quedan afectados por las reglas de cascada del esquema — ver [schema.md](../../schema.md).

---

## `GET /api/v1/matters/{matter_id}/participants`

Devuelve los participantes del caso (cliente, abogado asignado, creador y demás actores vinculados).

```bash
curl http://localhost:8000/api/v1/matters/1/participants \
  -H "Authorization: Bearer $TOKEN"
```

---

## Errores comunes

| Código | Causa | `detail` de ejemplo |
|---|---|---|
| `401` | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | Usuario autenticado sin membresía de organización | `"Usuario sin organización asignada"` |
| `404` | El caso no existe **o** pertenece a otra organización | `"Caso no encontrado"` |
| `422` | Body o query params inválidos | Detalle estructurado de pydantic |
| `429` | Límite del plan superado | `"Rate limit exceeded"` |

---

## Rate limits

Sin decorador `@limiter.limit` específico. Aplica el límite por organización según el plan de suscripción, impuesto por `OrganizationRateLimitMiddleware`:

| Plan | Requests/minuto |
|---|---|
| `free` | 100 |
| `basic` | 500 |
| `pro` | 2000 |
| `enterprise` | Sin límite |

Ver [rate limits globales](../../openapi.md#rate-limits).

---

## Notas de seguridad

- **Aislamiento multi-tenant**: todas las queries filtran por el `organization_id` derivado del token. `organization_id` enviado en el body de `POST` **no** se usa para elegir tenant.
- **Fuga por código de estado**: el acceso a un caso de otro tenant devuelve `404`, evitando confirmar su existencia.
- **RBAC**: `require_organization` sólo garantiza pertenencia a una organización. Las restricciones por rol (`LAWYER`, `CLIENT`, `VIEWER`, …) se detallan en [rbac-matrix.md](../../rbac-matrix.md).
- **Borrado**: `DELETE` es irreversible desde la API. No hay endpoint de restauración.
- **Datos personales**: `counterparty_name`, `description` y campos libres pueden contener datos sensibles bajo la Ley 19.628. No los registres en logs de aplicación.
