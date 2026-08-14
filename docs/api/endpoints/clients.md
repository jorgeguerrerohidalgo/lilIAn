# API — Clients

> Router: `apps/backend/app/api/endpoints/clients.py` · Prefijo: `/api/v1/clients` · Tag OpenAPI: `clients`

CRUD de clientes de la organización. Un cliente puede tener múltiples casos (`matters`) asociados.

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Modelo de datos](#modelo-de-datos)
- [POST /api/v1/clients](#post-apiv1clients)
- [GET /api/v1/clients](#get-apiv1clients)
- [GET /api/v1/clients/{client_id}](#get-apiv1clientsclient_id)
- [PUT /api/v1/clients/{client_id}](#put-apiv1clientsclient_id)
- [DELETE /api/v1/clients/{client_id}](#delete-apiv1clientsclient_id)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Éxito | Descripción |
|---|---|---|---|---|
| `POST` | `/api/v1/clients` | Bearer + org | `201` | Crea un cliente |
| `GET` | `/api/v1/clients` | Bearer + org | `200` | Lista clientes, con búsqueda opcional |
| `GET` | `/api/v1/clients/{client_id}` | Bearer + org | `200` | Detalle de un cliente |
| `PUT` | `/api/v1/clients/{client_id}` | Bearer + org | `200` | Reemplazo completo |
| `DELETE` | `/api/v1/clients/{client_id}` | Bearer + org | `204` | Elimina el cliente |

---

## Modelo de datos

### `ClientBase` / `ClientResponse`

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `name` | `str` | Sí | Nombre de la persona natural o razón social corta |
| `company_name` | `str \| null` | No | Razón social completa |
| `rut` | `str \| null` | No | RUT chileno. Formato sugerido `12.345.678-9` |
| `email` | `str \| null` | No | |
| `phone` | `str \| null` | No | |
| `address` | `str \| null` | No | |
| `notes` | `str \| null` | No | Notas internas |

`ClientResponse` añade los campos de persistencia (`id`, `organization_id`, timestamps).

---

## `POST /api/v1/clients`

- **Auth**: Bearer + membresía de organización
- **Content-Type**: `application/json`
- **Status éxito**: `201 Created`

```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Juan Pérez",
    "company_name": "Comercial Pérez Ltda.",
    "rut": "12.345.678-9",
    "email": "juan.perez@example.cl",
    "phone": "+56912345678",
    "address": "Av. Providencia 1234, Santiago",
    "notes": "Cliente recurrente, materia laboral."
  }'
```

Mínimo viable:

```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "name": "Juan Pérez" }'
```

---

## `GET /api/v1/clients`

### Query params

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `search` | `str \| null` | `None` | Filtro de texto sobre los clientes de la organización |

### Response 200

`list[ClientResponse]`

```bash
# Todos los clientes de la organización
curl http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer $TOKEN"

# Búsqueda por texto
curl "http://localhost:8000/api/v1/clients?search=Pérez" \
  -H "Authorization: Bearer $TOKEN"
```

```json
[
  {
    "id": 7,
    "organization_id": 3,
    "name": "Juan Pérez",
    "company_name": "Comercial Pérez Ltda.",
    "rut": "12.345.678-9",
    "email": "juan.perez@example.cl",
    "phone": "+56912345678",
    "address": "Av. Providencia 1234, Santiago",
    "notes": "Cliente recurrente, materia laboral.",
    "created_at": "2025-01-15T12:34:56Z"
  }
]
```

> Este endpoint no expone `skip`/`limit`. Con un volumen alto de clientes, usa `search` para acotar el resultado.

---

## `GET /api/v1/clients/{client_id}`

```bash
curl http://localhost:8000/api/v1/clients/7 \
  -H "Authorization: Bearer $TOKEN"
```

Un cliente de otra organización devuelve `404`.

---

## `PUT /api/v1/clients/{client_id}`

Actualización con semántica de **reemplazo**: el body es un `ClientCreate` completo. Los campos opcionales que se omitan toman su valor por defecto (`null`), no conservan el valor anterior.

```bash
curl -X PUT http://localhost:8000/api/v1/clients/7 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Juan Pérez González",
    "company_name": "Comercial Pérez Ltda.",
    "rut": "12.345.678-9",
    "email": "jperez@example.cl",
    "phone": "+56987654321",
    "address": "Av. Providencia 1234, Santiago",
    "notes": "Cliente recurrente, materia laboral."
  }'
```

> Envía siempre el objeto completo. Un `PUT` con sólo `{"name": "..."}` borra email, teléfono, dirección y notas.

---

## `DELETE /api/v1/clients/{client_id}`

- **Status éxito**: `204 No Content` (sin body)

```bash
curl -i -X DELETE http://localhost:8000/api/v1/clients/7 \
  -H "Authorization: Bearer $TOKEN"
```

> Los casos (`matters`) referencian al cliente vía `client_id`. Revisa las reglas de integridad referencial en [schema.md](../../schema.md) antes de borrar un cliente con casos abiertos.

---

## Errores comunes

| Código | Causa | `detail` de ejemplo |
|---|---|---|
| `401` | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | Usuario sin membresía de organización | `"Usuario sin organización asignada"` |
| `404` | Cliente inexistente o de otro tenant | `"Cliente no encontrado"` |
| `422` | Body inválido (falta `name`, tipos incorrectos) | Detalle estructurado de pydantic |
| `429` | Límite del plan superado | `"Rate limit exceeded"` |

---

## Rate limits

Sin decorador específico. Aplica el límite por organización según plan (`free` 100/min, `basic` 500/min, `pro` 2000/min, `enterprise` sin límite), impuesto por `OrganizationRateLimitMiddleware`.

Ver [rate limits globales](../../openapi.md#rate-limits).

---

## Notas de seguridad

- **Aislamiento multi-tenant**: todas las queries filtran por `organization_id` del token.
- **Datos personales**: `rut`, `email`, `phone` y `address` son datos personales bajo la Ley 19.628 de protección de la vida privada. Aplican los principios de finalidad y minimización; no los repliques en logs ni en sistemas de terceros sin base legal.
- **`notes` es campo libre**: puede contener información privilegiada abogado-cliente. Trátalo con la misma sensibilidad que el contenido de un caso.
- **`PUT` destructivo**: la semántica de reemplazo puede provocar pérdida silenciosa de datos si el cliente HTTP envía objetos parciales. Considera leer el recurso antes de escribirlo.
- **Sin validación de RUT**: la API acepta cualquier string en `rut`. La validación del dígito verificador debe hacerse en el cliente.
