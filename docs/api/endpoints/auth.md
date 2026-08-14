# API — Auth

> Router: `apps/backend/app/api/endpoints/auth.py` · Prefijo: `/api/v1/auth` · Tag OpenAPI: `auth`

Registro de usuarios, autenticación por OAuth2 Password Flow, emisión de JWT y consulta del perfil autenticado.

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [POST /api/v1/auth/register](#post-apiv1authregister)
- [POST /api/v1/auth/login](#post-apiv1authlogin)
- [POST /api/v1/auth/logout](#post-apiv1authlogout)
- [GET /api/v1/auth/me](#get-apiv1authme)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Rate limit | Descripción |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Pública | 10/min por IP | Crea una cuenta de usuario |
| `POST` | `/api/v1/auth/login` | Pública | 10/min por IP | Emite un access token JWT |
| `POST` | `/api/v1/auth/logout` | Bearer | Plan | Cierra la sesión del cliente |
| `GET` | `/api/v1/auth/me` | Bearer | Plan | Devuelve el usuario autenticado |

---

## `POST /api/v1/auth/register`

Crea una cuenta. El registro **no** crea ni asigna organización: el usuario queda sin membresía hasta que un `OWNER`/`ADMIN` lo invite o hasta que cree su propia organización vía `POST /api/v1/organizations`.

- **Auth**: pública
- **Content-Type**: `application/json`
- **Status éxito**: `201 Created`

### Request body — `UserCreate`

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `email` | `EmailStr` | Sí | Formato de email válido, único en la plataforma |
| `full_name` | `str` | Sí | — |
| `password` | `str` | Sí | Longitud mínima y máxima 128 (`Field(min_length=..., max_length=128)`) |

### Response 201 — `UserResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `int` | |
| `email` | `str` | |
| `full_name` | `str` | |
| `phone` | `str \| null` | |
| `status` | `str` | Estado de la cuenta |
| `created_at` | `datetime` | ISO 8601 |
| `last_login_at` | `datetime \| null` | `null` hasta el primer login |

El hash de la contraseña **nunca** se devuelve.

### Ejemplo

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "abogado@estudio.cl",
    "full_name": "María Fernández",
    "password": "UnaC0ntraseñaSegura!"
  }'
```

```json
{
  "id": 12,
  "email": "abogado@estudio.cl",
  "full_name": "María Fernández",
  "phone": null,
  "status": "active",
  "created_at": "2025-01-15T12:34:56Z",
  "last_login_at": null
}
```

---

## `POST /api/v1/auth/login`

OAuth2 Password Flow. El body va como **formulario**, no como JSON (`OAuth2PasswordRequestForm`).

- **Auth**: pública
- **Content-Type**: `application/x-www-form-urlencoded`
- **Status éxito**: `200 OK`

### Request body — form-encoded

| Campo | Tipo | Requerido | Notas |
|---|---|---|---|
| `username` | `str` | Sí | Es el **email** del usuario |
| `password` | `str` | Sí | |
| `grant_type` | `str` | No | Opcional en el estándar OAuth2 |

### Response 200 — `Token`

| Campo | Tipo | Valor |
|---|---|---|
| `access_token` | `str` | JWT firmado con `JWT_SECRET` |
| `token_type` | `str` | `bearer` |

Claims del token: `sub` (id de usuario como string), `email`, `iss` (`JWT_ISSUER`), `aud` (`JWT_AUDIENCE`), `exp`.

### Ejemplo

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=abogado@estudio.cl&password=UnaC0ntraseñaSegura!"
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Guardar el token para reutilizarlo:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=abogado@estudio.cl&password=UnaC0ntraseñaSegura!" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

## `POST /api/v1/auth/logout`

Cierra la sesión desde el punto de vista del cliente.

- **Auth**: Bearer
- **Status éxito**: `204 No Content` (sin body)

```bash
curl -i -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

> **Importante**: los JWT son stateless. Este endpoint no mantiene una denylist de tokens; un token robado sigue siendo válido hasta su `exp`. El cliente debe descartar el token localmente. Para invalidación inmediata y global hay que rotar `JWT_SECRET`.

---

## `GET /api/v1/auth/me`

Devuelve el usuario correspondiente al token presentado. Útil para rehidratar la sesión al cargar el frontend.

- **Auth**: Bearer
- **Status éxito**: `200 OK`
- **Response**: `UserResponse` (mismo esquema que `register`)

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "id": 12,
  "email": "abogado@estudio.cl",
  "full_name": "María Fernández",
  "phone": "+56912345678",
  "status": "active",
  "created_at": "2025-01-15T12:34:56Z",
  "last_login_at": "2025-01-20T09:12:00Z"
}
```

---

## Errores comunes

| Código | Endpoint | Causa | `detail` de ejemplo |
|---|---|---|---|
| `400` | `register` | Email ya registrado | `"El email ya está registrado"` |
| `401` | `login` | Credenciales inválidas | `"Email o contraseña incorrectos"` |
| `401` | `me`, `logout` | Token ausente, malformado o expirado | `"No se pudo validar las credenciales"` |
| `422` | `register`, `login` | Fallo de validación del esquema (email inválido, password corta) | Detalle estructurado de pydantic |
| `429` | `register`, `login` | Rate limit superado | `"Rate limit exceeded"` |

El `401` incluye la cabecera `WWW-Authenticate: Bearer`.

Formato uniforme:

```json
{ "detail": "Mensaje en español" }
```

Excepto `422`, que devuelve el detalle estructurado de pydantic:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters"
    }
  ]
}
```

---

## Rate limits

| Endpoint | Límite | Clave | Origen |
|---|---|---|---|
| `POST /register` | `10/minute` | IP remota | `@limiter.limit("10/minute")` — S1-05, previene creación masiva de cuentas |
| `POST /login` | `10/minute` | IP remota | `@limiter.limit("10/minute")` — S1-05, previene fuerza bruta |
| `POST /logout`, `GET /me` | Límite del plan | Token o IP | `OrganizationRateLimitMiddleware` |

Al superarse: `429 Too Many Requests` con cabeceras `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` y `Retry-After: 60`.

Ver [rate limits globales](../../openapi.md#rate-limits).

---

## Notas de seguridad

- **Enumeración de usuarios**: `login` responde con el mismo mensaje para email inexistente y contraseña incorrecta. No introducir mensajes diferenciados.
- **Almacenamiento del token en el cliente**: el frontend debe evitar `localStorage` para tokens de larga vida. El default de `ACCESS_TOKEN_EXPIRE_MINUTES` es `86400` minutos (≈60 días); revísalo en producción — ver [env-vars.md](../../env-vars.md#backend--seguridad-y-jwt).
- **Sin refresh token**: la API v1 emite un único access token. No existe `POST /auth/refresh`; para renovar hay que volver a hacer login.
- **`JWT_SECRET`**: mínimo 32 caracteres. En `APP_ENV=production` la app aborta el arranque si detecta un placeholder o un secreto corto.
- **HTTPS obligatorio en producción**: el token viaja en la cabecera `Authorization` en texto plano sobre TLS.
- **CORS**: sólo los orígenes de `ALLOWED_ORIGINS` pueden invocar estos endpoints desde el navegador. El wildcard está bloqueado en producción (S1-17).
