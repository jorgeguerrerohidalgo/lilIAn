# lilIAn — Variables de entorno

> Referencia completa de las variables de entorno del backend y del frontend.
>
> - **Fuente de verdad backend**: `apps/backend/app/core/config.py` (clase `Settings`, pydantic-settings)
> - **Fuente adicional backend**: `apps/backend/app/services/storage.py` (leídas con `os.environ`)
> - **Fuente de verdad frontend**: `apps/frontend/next.config.js`
> - **Plantilla raíz**: [`.env.example`](../.env.example)
> - **Plantilla producción**: [`.env.production.example`](../.env.production.example)

---

## Tabla de contenidos

1. [Cómo se cargan las variables](#cómo-se-cargan-las-variables)
2. [Backend — Aplicación](#backend--aplicación)
3. [Backend — Base de datos y Supabase](#backend--base-de-datos-y-supabase)
4. [Backend — Redis](#backend--redis)
5. [Backend — Seguridad y JWT](#backend--seguridad-y-jwt)
6. [Backend — CORS](#backend--cors)
7. [Backend — LLM](#backend--llm)
8. [Backend — Embeddings](#backend--embeddings)
9. [Backend — Almacenamiento](#backend--almacenamiento)
10. [Backend — Rate limiting y uploads](#backend--rate-limiting-y-uploads)
11. [Frontend](#frontend)
12. [Infraestructura (docker-compose / render)](#infraestructura-docker-compose--render)
13. [Variables declaradas pero no consumidas](#variables-declaradas-pero-no-consumidas)
14. [Seguridad](#seguridad)
15. [Checklist de despliegue](#checklist-de-despliegue)

---

## Cómo se cargan las variables

El backend usa `pydantic-settings`. La configuración vive en `apps/backend/app/core/config.py`:

```python
class Config:
    env_file = ".env"
    case_sensitive = True
    extra = "ignore"
```

Implicaciones prácticas:

| Comportamiento | Detalle |
|---|---|
| Archivo por defecto | `.env` en el working directory del proceso backend |
| Sensible a mayúsculas | Sí. `database_url` **no** se resuelve como `DATABASE_URL` |
| Variables extra | Se **ignoran** (`extra = "ignore"`), no rompen el arranque |
| Precedencia | Variables de entorno del proceso > `.env` > default del modelo |

> **Advertencia**: como `extra = "ignore"`, un typo en el nombre de una variable (`JWT_SECRETT`) **no** genera error; la app arranca con el default y el valor real se pierde silenciosamente. Verifica siempre los nombres contra esta tabla.

El frontend (Next.js) sólo expone al navegador variables con prefijo `NEXT_PUBLIC_`. Cualquier otra variable queda restringida al proceso de build/servidor.

---

## Backend — Aplicación

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `APP_ENV` | No | `development` | `str` | Entorno de ejecución. El valor `production` activa validaciones estrictas de `ALLOWED_ORIGINS` y `JWT_SECRET` (fail-fast en el arranque). |
| `DEBUG` | No | `true` | `bool` | Modo debug. Debe ser `false` en producción. |
| `LOG_LEVEL` | No | `INFO` | `str` | Nivel de logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |

Ejemplo:

```dotenv
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
```

---

## Backend — Base de datos y Supabase

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `DATABASE_URL` | **Sí** | — | `str` | Cadena de conexión PostgreSQL. Sin default: si falta, el arranque falla con `ValidationError`. |
| `SUPABASE_URL` | No | `None` | `str \| None` | URL del proyecto Supabase. Necesaria si `STORAGE_BACKEND=supabase`. |
| `SUPABASE_ANON_KEY` | No | `None` | `str \| None` | Clave pública (anon) de Supabase. Segura para exponer al cliente. |
| `SUPABASE_SERVICE_ROLE_KEY` | No | `None` | `str \| None` | Clave de service role. **Solo backend**: salta RLS y tiene acceso total. Nunca la expongas al navegador. |

Ejemplo:

```dotenv
DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...
```

---

## Backend — Redis

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `REDIS_URL` | No | `redis://redis:6379/0` | `str` | Conexión Redis. El default apunta al servicio `redis` de `docker-compose.yml`. Fuera de Docker usa `redis://localhost:6379/0`. |

```dotenv
REDIS_URL=redis://localhost:6379/0
```

---

## Backend — Seguridad y JWT

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `JWT_SECRET` | **Sí** | — | `str` | Clave HMAC para firmar los access tokens. Mínimo 32 caracteres. |
| `JWT_ALGORITHM` | No | `HS256` | `str` | Algoritmo de firma JWT. |
| `JWT_ISSUER` | No | `lilian` | `str` | Claim `iss` emitido y validado. |
| `JWT_AUDIENCE` | No | `lilian-api` | `str` | Claim `aud` emitido y validado. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `86400` | `int` | Vigencia del access token **en minutos**. El default del código es `60 * 60 * 24 = 86400` minutos (≈ 60 días). Para una expiración de 24 horas usa `1440`. |

### Validación fail-fast de `JWT_SECRET`

`config.py` ejecuta `_validate_jwt_secret()` al importar el módulo. El secreto se considera inválido si:

- tiene menos de 32 caracteres, o
- está en la lista de placeholders conocidos (`changeme`, `secret`, `your-secret-key`, …), o
- contiene la subcadena `change` o `placeholder` (case-insensitive).

Comportamiento según entorno:

| `APP_ENV` | Secreto inválido |
|---|---|
| `production` | `RuntimeError` — la aplicación **no arranca** |
| cualquier otro | `RuntimeWarning` — arranca, pero avisa |

Generar un secreto válido:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```dotenv
JWT_SECRET=Xk3f9pQr7sT2vW5yA8bC1dE4gH6jK0mN9oP2qR5sT8u
JWT_ALGORITHM=HS256
JWT_ISSUER=lilian
JWT_AUDIENCE=lilian-api
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

---

## Backend — CORS

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `ALLOWED_ORIGINS` | No (**sí en producción**) | `http://localhost:3000` | `str` | Lista de orígenes permitidos separada por comas. Se parsea con `get_allowed_origins()`. |

Reglas aplicadas por `Settings.get_allowed_origins()`:

| `APP_ENV` | `*` o `null` presentes | Lista vacía |
|---|---|---|
| `production` | `RuntimeError` (arranque abortado) | `RuntimeError` |
| desarrollo | `RuntimeWarning` + fallback a `http://localhost:3000` | lista vacía |

El wildcard con credenciales está prohibido por la especificación CORS; este bloqueo es defensa en profundidad (S1-17).

```dotenv
# Desarrollo
ALLOWED_ORIGINS=http://localhost:3000

# Producción — dominios explícitos, sin wildcard
ALLOWED_ORIGINS=https://app.lilian.cl,https://www.lilian.cl
```

---

## Backend — LLM

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `LLM_PROVIDER` | No | `openai` | `str` | Proveedor del modelo de lenguaje: `openai`, `anthropic` o `minimax`. |
| `LLM_MODEL` | No | `gpt-4o-mini` | `str` | Identificador del modelo. Debe corresponder al proveedor seleccionado. |
| `LLM_API_KEY` | No* | `None` | `str \| None` | API key del proveedor LLM. |
| `OPENAI_API_KEY` | No* | `None` | `str \| None` | Fallback de API key. |

\* Al menos una de las dos es necesaria para que funcionen análisis, chat y generación de documentos. La resolución es:

```python
@property
def resolved_llm_api_key(self) -> str | None:
    return self.LLM_API_KEY or self.OPENAI_API_KEY
```

Modelos por proveedor:

| `LLM_PROVIDER` | `LLM_MODEL` de ejemplo |
|---|---|
| `openai` | `gpt-4o-mini` |
| `anthropic` | `claude-sonnet-4-20250514` |
| `minimax` | `MiniMax-Text-01` |

```dotenv
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
LLM_API_KEY=sk-ant-...
```

---

## Backend — Embeddings

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `EMBEDDING_PROVIDER` | No | `openai` | `str` | Proveedor de embeddings para búsqueda semántica y RAG. |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | `str` | Modelo de embeddings. |
| `EMBEDDING_API_KEY` | No* | `None` | `str \| None` | API key específica de embeddings. |

\* Cadena de fallback en `app/services/embeddings.py`:

```
EMBEDDING_API_KEY → OPENAI_API_KEY → LLM_API_KEY
```

Sin ninguna de las tres, `POST /api/v1/search` con `use_embeddings=true` degrada a búsqueda por keyword.

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=sk-...
```

---

## Backend — Almacenamiento

Estas variables **no** están en la clase `Settings`; se leen directamente con `os.environ` en `app/services/storage.py`.

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `STORAGE_BACKEND` | No | `local` | `str` | Backend de almacenamiento de documentos: `local` o `supabase`. |
| `STORAGE_PATH` | No | `/app/storage/documents` | `str` | Raíz del almacenamiento local. Se normaliza con `os.path.realpath` y se usa como jaula anti path-traversal. |
| `SUPABASE_STORAGE_BUCKET` | No | `documents` | `str` | Nombre del bucket cuando `STORAGE_BACKEND=supabase`. |

> **Nota**: el `.env.example` histórico usaba `STORAGE_PROVIDER`. El código lee `STORAGE_BACKEND`. Usa `STORAGE_BACKEND`.

```dotenv
STORAGE_BACKEND=local
STORAGE_PATH=/app/storage/documents

# o bien
STORAGE_BACKEND=supabase
SUPABASE_STORAGE_BUCKET=legal-documents
```

---

## Backend — Rate limiting y uploads

| Variable | Requerida | Default | Tipo | Descripción |
|---|---|---|---|---|
| `RATE_LIMIT_PER_MINUTE` | No | `60` | `int` | Límite global por minuto configurado en `Settings`. |
| `RATE_LIMIT_AUTH_PER_MINUTE` | No | `10` | `int` | Límite por minuto para endpoints de autenticación. |
| `MAX_FILE_SIZE` | No | `52428800` | `int` | Tamaño máximo de archivo en bytes (`50 * 1024 * 1024` = 50 MB). |

> **Nota de implementación**: los decoradores `@limiter.limit("10/minute")` en `auth.py` y `precedents.py` usan valores literales, no estas variables. El límite efectivo por organización lo aplica `OrganizationRateLimitMiddleware` según el plan de suscripción. Ver [Rate limits en openapi.md](openapi.md#rate-limits).

> **Nota**: `documents.py` define su propia constante `MAX_FILE_SIZE = 50 * 1024 * 1024` a nivel de módulo. Cambiar la variable de entorno no altera el límite de upload sin un cambio de código.

---

## Frontend

Archivo: `apps/frontend/.env.local` (gitignored).

| Variable | Requerida | Default | Expuesta al navegador | Descripción |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | **Sí** | URL base del backend. Inyectada en `next.config.js`. |
| `PORT` | No | `3000` | No | Puerto del servidor Next.js. Usado también por `playwright.config.ts`. |
| `PLAYWRIGHT_BASE_URL` | No | `http://localhost:${PORT}` | No | URL base para los tests E2E de Playwright. |
| `CI` | No | — | No | Cuando está definida, Playwright activa `forbidOnly`, 2 reintentos, 1 worker y reporter `github`. |

```dotenv
# apps/frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> **Crítico**: cualquier variable con prefijo `NEXT_PUBLIC_` se compila dentro del bundle JavaScript y es **legible por cualquier visitante**. No pongas nunca secretos ahí (`SUPABASE_SERVICE_ROLE_KEY`, `LLM_API_KEY`, `JWT_SECRET`).

---

## Infraestructura (docker-compose / render)

### `docker-compose.yml`

| Variable | Default en compose | Servicio |
|---|---|---|
| `DATABASE_URL` | — (obligatoria) | backend |
| `REDIS_URL` | `redis://redis:6379/0` | backend |
| `JWT_SECRET` | — (obligatoria) | backend |
| `ENCRYPTION_KEY` | — | backend (ver nota abajo) |
| `LLM_PROVIDER` | `openai` | backend |
| `LLM_API_KEY` | — | backend |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8000` | backend |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | frontend |
| `POSTGRES_USER` | `postgres` | db |
| `POSTGRES_PASSWORD` | `postgres` | db |
| `POSTGRES_DB` | `lilian` | db |

### `render.yaml`

Declara `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS`, `LLM_PROVIDER` y `NEXT_PUBLIC_API_URL`.

---

## Variables declaradas pero no consumidas

Estas aparecen en plantillas o manifiestos de infraestructura pero **ningún módulo del backend las lee**. Se documentan para evitar la falsa sensación de que están configurando algo:

| Variable | Aparece en | Estado |
|---|---|---|
| `ENCRYPTION_KEY` | `.env.example`, `docker-compose.yml` | No leída por el código. Reservada para cifrado en reposo, aún no implementado. |
| `SECRET_KEY` | `render.yaml` | No leída. El backend usa `JWT_SECRET`. Renombrar en el manifiesto de Render. |
| `STORAGE_PROVIDER` | `.env.example` histórico | No leída. El nombre correcto es `STORAGE_BACKEND`. |

Como `extra = "ignore"`, su presencia no rompe el arranque.

---

## Seguridad

### Reglas obligatorias

1. **Nunca commitear secretos.** `.gitignore` ya excluye `.env`, `.env.local`, `.env.production`, `.env.*.local`, `.env.backup` y `.env*`. Sólo los `*.example` deben versionarse.
2. **Sólo placeholders en los `*.example`.** Nunca un valor real, ni siquiera de desarrollo.
3. **`SUPABASE_SERVICE_ROLE_KEY` es backend-only.** Salta RLS. Su filtración equivale a acceso total a la base de datos.
4. **Nada sensible bajo `NEXT_PUBLIC_`.** Ese prefijo publica el valor en el bundle del navegador.
5. **Sin wildcard en `ALLOWED_ORIGINS`.** En producción el arranque falla; no lo esquives.
6. **`JWT_SECRET` de mínimo 32 caracteres aleatorios**, distinto por entorno.

### Rotación tras una exposición

```bash
# 1. Generar nuevo secreto
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Actualizar el gestor de secretos del entorno afectado
# 3. Redesplegar (rotar JWT_SECRET invalida todos los tokens emitidos)
# 4. Rotar también las API keys de proveedores desde su consola
```

Rotar `JWT_SECRET` cierra la sesión de todos los usuarios: los tokens firmados con el secreto anterior dejan de validar.

### Comprobaciones antes de commitear

```bash
# ¿Hay algún .env rastreado por git?
git ls-files | grep -E '^\.env' | grep -v example

# ¿El diff en staging contiene algo que parezca una clave?
git diff --cached | grep -iE '(api[_-]?key|secret|password|token)\s*=\s*\S{16,}'
```

Ver también [`SECRETS_MANAGEMENT.md`](SECRETS_MANAGEMENT.md).

---

## Checklist de despliegue

Antes de desplegar a producción:

- [ ] `APP_ENV=production`
- [ ] `DEBUG=false`
- [ ] `DATABASE_URL` apunta a la base de producción
- [ ] `JWT_SECRET` con 32+ caracteres aleatorios, distinto del de desarrollo
- [ ] `ALLOWED_ORIGINS` con dominios explícitos, sin `*` ni `null`
- [ ] `LLM_API_KEY` (o `OPENAI_API_KEY`) presente
- [ ] `EMBEDDING_API_KEY` presente si se usa búsqueda semántica
- [ ] `STORAGE_BACKEND` configurado y el bucket/directorio accesible
- [ ] `REDIS_URL` apunta a la instancia de producción
- [ ] `ACCESS_TOKEN_EXPIRE_MINUTES` revisado (el default son ≈60 días)
- [ ] `NEXT_PUBLIC_API_URL` apunta a la URL pública del backend
- [ ] Ningún `.env` real en el repositorio
