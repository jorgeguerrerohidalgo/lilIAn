# API — SaaS (Suscripción, uso y facturación)

> Router: `apps/backend/app/api/endpoints/saas.py` · Prefijo: `/api/v1/saas` · Tag OpenAPI: `saas`

Planes disponibles, suscripción activa de la organización, métricas de negocio y eventos de uso. Los límites de plan aquí expuestos son los que aplica `OrganizationRateLimitMiddleware` a toda la API.

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Planes y límites](#planes-y-límites)
- [Modelo de datos](#modelo-de-datos)
- [GET /api/v1/saas/plans](#get-apiv1saasplans)
- [GET /api/v1/saas/subscription](#get-apiv1saassubscription)
- [POST /api/v1/saas/subscription](#post-apiv1saassubscription)
- [GET /api/v1/saas/metrics](#get-apiv1saasmetrics)
- [GET /api/v1/saas/usage/events](#get-apiv1saasusageevents)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Éxito | Descripción |
|---|---|---|---|---|
| `GET` | `/api/v1/saas/plans` | Bearer | `200` | Catálogo de planes |
| `GET` | `/api/v1/saas/subscription` | Bearer + org | `200` | Suscripción activa (o `null`) |
| `POST` | `/api/v1/saas/subscription` | Bearer + org | `200` | Crea o cambia la suscripción |
| `GET` | `/api/v1/saas/metrics` | Bearer + org | `200` | Métricas agregadas de la organización |
| `GET` | `/api/v1/saas/usage/events` | Bearer + org | `200` | Eventos de uso recientes |

> `GET /plans` sólo exige `get_current_user`: es el único endpoint del router que **no** requiere membresía de organización, para que un usuario recién registrado pueda ver el catálogo antes de tener organización.

---

## Planes y límites

Los límites de rate limiting por plan están definidos en `app/core/rate_limit.py`:

| Plan | Requests/minuto | Constante |
|---|---|---|
| `free` | 100 | `FREE_LIMIT` |
| `basic` | 500 | `BASIC_LIMIT` |
| `pro` | 2000 | `PRO_LIMIT` |
| `enterprise` | Sin límite | `ENTERPRISE_LIMIT = None` |

Resolución del plan (`get_subscription_plan`): se toma la suscripción con `status = "active"` más reciente de la organización. Sin suscripción activa, el plan efectivo es `free`.

Además del rate limit HTTP, cada plan lleva cuotas de negocio: `documents_limit`, `analyses_limit` y `users_limit`.

---

## Modelo de datos

### `PlanResponse`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | |
| `name` | `str` | Identificador del plan (`free`, `basic`, `pro`, `enterprise`) |
| `display_name` | `str` | Nombre para mostrar |
| `description` | `str \| null` | |
| `documents_limit` | `int` | Máximo de documentos |
| `analyses_limit` | `int` | Máximo de análisis |
| `users_limit` | `int` | Máximo de usuarios |
| `monthly_price` | `int` | Precio mensual |

### `SubscriptionResponse`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | |
| `plan_name` | `str` | Plan contratado |
| `status` | `str` | Estado (`active`, …) |
| `documents_limit` | `int` | Cuota de documentos |
| `analyses_limit` | `int` | Cuota de análisis |
| `users_limit` | `int` | Cuota de usuarios |
| `monthly_price` | `int` | Precio mensual |
| `started_at` | `str` | ISO 8601 |
| `renews_at` | `str \| null` | ISO 8601, `null` si no renueva |
| `documents_used` | `int` | Consumo actual |
| `analyses_used` | `int` | Consumo actual |
| `users_used` | `int` | Consumo actual |

### `OrganizationMetrics`

| Campo | Tipo | Descripción |
|---|---|---|
| `total_matters` | `int` | Casos totales |
| `total_documents` | `int` | Documentos totales |
| `total_analyses` | `int` | Análisis totales |
| `total_users` | `int` | Usuarios de la organización |
| `matters_by_status` | `dict` | Conteo de casos por estado |
| `matters_by_type` | `dict` | Conteo de casos por tipo |
| `documents_this_month` | `int` | Documentos del mes en curso |
| `analyses_this_month` | `int` | Análisis del mes en curso |

---

## `GET /api/v1/saas/plans`

Catálogo de planes disponibles.

- **Auth**: Bearer (sin requerir organización)
- **Response 200**: `list[PlanResponse]`

```bash
curl http://localhost:8000/api/v1/saas/plans \
  -H "Authorization: Bearer $TOKEN"
```

```json
[
  {
    "id": 1,
    "name": "free",
    "display_name": "Gratis",
    "description": "Para probar la plataforma",
    "documents_limit": 10,
    "analyses_limit": 5,
    "users_limit": 1,
    "monthly_price": 0
  },
  {
    "id": 3,
    "name": "pro",
    "display_name": "Profesional",
    "description": "Para estudios jurídicos",
    "documents_limit": 1000,
    "analyses_limit": 500,
    "users_limit": 20,
    "monthly_price": 99000
  }
]
```

---

## `GET /api/v1/saas/subscription`

Suscripción activa de la organización del usuario.

- **Response 200**: `SubscriptionResponse` o `null` si la organización no tiene suscripción (plan efectivo `free`).

```bash
curl http://localhost:8000/api/v1/saas/subscription \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "id": 15,
  "plan_name": "pro",
  "status": "active",
  "documents_limit": 1000,
  "analyses_limit": 500,
  "users_limit": 20,
  "monthly_price": 99000,
  "started_at": "2025-01-01T00:00:00Z",
  "renews_at": "2025-02-01T00:00:00Z",
  "documents_used": 143,
  "analyses_used": 62,
  "users_used": 7
}
```

Comprobar el consumo antes de una operación cara:

```bash
curl -s http://localhost:8000/api/v1/saas/subscription \
  -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['analyses_used']}/{d['analyses_limit']} análisis\")"
```

> El `200` con body `null` es una respuesta válida. Trátalo en el cliente antes de acceder a campos.

---

## `POST /api/v1/saas/subscription`

Crea o cambia la suscripción de la organización.

- **Parámetro**: `plan_name` (`str`). Se declara como parámetro de la función sin `Body(...)`, por lo que FastAPI lo interpreta como **query param**.
- **Status éxito**: `200 OK`

```bash
curl -X POST "http://localhost:8000/api/v1/saas/subscription?plan_name=pro" \
  -H "Authorization: Bearer $TOKEN"
```

El nuevo plan se aplica en la siguiente petición, ya que `OrganizationRateLimitMiddleware` resuelve el plan en cada request.

---

## `GET /api/v1/saas/metrics`

Métricas agregadas de la organización, pensadas para el dashboard.

- **Response 200**: `OrganizationMetrics`

```bash
curl http://localhost:8000/api/v1/saas/metrics \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "total_matters": 48,
  "total_documents": 143,
  "total_analyses": 62,
  "total_users": 7,
  "matters_by_status": { "active": 31, "closed": 17 },
  "matters_by_type": { "laboral": 22, "civil": 15, "other": 11 },
  "documents_this_month": 19,
  "analyses_this_month": 8
}
```

> No confundir con `GET /metrics` (raíz, sin prefijo `/api/v1`), que expone observabilidad técnica: contadores de requests y percentiles de latencia.

---

## `GET /api/v1/saas/usage/events`

Eventos de uso registrados para la organización.

### Query params

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `days` | `int` | `30` | Ventana temporal en días hacia atrás |

```bash
# Últimos 30 días (default)
curl http://localhost:8000/api/v1/saas/usage/events \
  -H "Authorization: Bearer $TOKEN"

# Últimos 7 días
curl "http://localhost:8000/api/v1/saas/usage/events?days=7" \
  -H "Authorization: Bearer $TOKEN"
```

Estos eventos son la base de la facturación por consumo y del cálculo de `documents_used` / `analyses_used`.

---

## Errores comunes

| Código | Endpoint | Causa | `detail` de ejemplo |
|---|---|---|---|
| `400` | `POST /subscription` | `plan_name` no corresponde a un plan existente | `"Plan no válido"` |
| `401` | todos | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | todos salvo `/plans` | Usuario sin membresía de organización | `"Usuario sin organización asignada"` |
| `422` | `POST /subscription` | Falta el query param `plan_name` | Detalle estructurado de pydantic |
| `422` | `usage/events` | `days` no es un entero | Detalle estructurado de pydantic |
| `429` | todos | Límite del plan superado | `"Rate limit exceeded"` |

---

## Rate limits

Sin decorador `@limiter.limit` específico. Aplica el límite por organización según plan.

### Cabeceras de la respuesta

`OrganizationRateLimitMiddleware` añade a cada respuesta:

| Cabecera | Significado |
|---|---|
| `X-RateLimit-Limit` | Límite del plan, en requests por minuto |
| `X-RateLimit-Remaining` | Peticiones restantes en la ventana actual |
| `X-RateLimit-Reset` | Timestamp Unix del reinicio de la ventana |

Al agotar la cuota se devuelve `429` con `Retry-After: 60` y body `{"detail":"Rate limit exceeded"}`.

Las organizaciones con plan `enterprise` no pasan por el contador y **no** reciben estas cabeceras.

Inspeccionar la cuota restante:

```bash
curl -sD - -o /dev/null http://localhost:8000/api/v1/saas/metrics \
  -H "Authorization: Bearer $TOKEN" | grep -i x-ratelimit
```

Ver [rate limits globales](../../openapi.md#rate-limits).

---

## Notas de seguridad

- **`POST /subscription` sin restricción de rol explícita**: sólo requiere `require_organization`. Cualquier miembro de la organización, incluido un `VIEWER`, puede cambiar el plan. Si el cambio de plan tiene efecto económico, restringe el endpoint a `OWNER`/`ADMIN` — ver [rbac-matrix.md](../../rbac-matrix.md).
- **Sin integración de pagos**: el endpoint registra la suscripción en la base de datos; no hay cobro, ni webhook de pasarela, ni verificación de pago. No trates un `200` como confirmación de cobro.
- **Sin webhooks entrantes**: la API v1 no expone endpoints de webhook. Cuando se integre una pasarela habrá que añadir verificación de firma y protección contra replay.
- **`GET /plans` con menor exigencia**: no requiere organización. No añadas ahí información específica de tenant.
- **Escalada de cuota**: el rate limit se deriva de la suscripción almacenada. Cualquier ruta que permita escribir `plan_name` o `status` de una suscripción es, en la práctica, una vía para elevar el límite de peticiones. Audítalas junto con los cambios de rol.
- **Ventana de rate limit en memoria**: el contador vive en el proceso (`defaultdict` protegido por `Lock`). Con varias réplicas, cada una lleva su propio contador y el límite efectivo se multiplica por el número de instancias.
