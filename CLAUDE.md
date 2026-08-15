# lilIAn

SaaS legal multi-tenant. Monorepo con frontend Next.js, backend FastAPI y un worker de procesamiento de documentos.

## Estructura

| Ruta | Qué es | Stack |
|------|--------|-------|
| `apps/frontend` | UI + BFF | Next.js 14 App Router, React 18, TypeScript, Tailwind, react-hook-form + zod |
| `apps/backend` | API | FastAPI 0.111, SQLAlchemy 2.0 async, Alembic, Redis, slowapi |
| `workers/document_processor` | Procesado asíncrono | RQ + Redis, PyMuPDF, python-docx |
| `infra/supabase` | Esquema y migraciones de datos | |
| `tests/e2e` | E2E de todo el sistema | Playwright |

Backend por capas: `app/api/endpoints` (rutas) → `app/services` (lógica) → `app/models` (SQLAlchemy) · `app/schemas` (Pydantic) · `app/core` (config, seguridad) · `app/api/deps` (dependencias de auth y tenant).

Despliegue: frontend en **Vercel**, backend en **Railway**.

## Contrato de autenticación (leer antes de tocar auth)

Frontend y backend viven en **dominios distintos** (`*.vercel.app` y `*.railway.app`). El cookie jar del navegador es por host, así que una cookie emitida por Railway nunca viaja a Vercel. De ahí el patrón BFF:

1. El navegador hace `POST /api/auth/login` — **same-origin**, nunca al backend directamente.
2. `app/api/auth/login/route.ts` llama al backend y **reescribe el `Set-Cookie`** para emitir `lilian_auth_token` en el dominio del frontend (`HttpOnly`, `SameSite=Lax`, `Max-Age=86400`, `Secure` en HTTPS).
3. `middleware.ts` lee esa cookie para proteger `/dashboard`, `/matters`, `/documents` y `/precedents`. Es solo un gate informativo — el backend sigue siendo la fuente de verdad.
4. Toda llamada al API pasa por el catch-all `app/api/v1/[...path]/route.ts`.

**El backend usa `OAuth2PasswordBearer`: solo lee el header `Authorization: Bearer <jwt>`, nunca cookies.** El catch-all extrae el JWT de la cookie y lo reemite como Bearer. Si alguna petición autenticada devuelve 401, este es el primer sitio donde mirar.

Reglas que se rompen con facilidad:

- El frontend llama a **rutas relativas** `/api/v1/*`. Nunca construyas URLs contra el host del backend desde el cliente: la cookie no viajaría.
- No reenvíes los `Set-Cookie` del backend al navegador — pertenecen a otro origen y se ignoran.
- `getApiUrl()` (`lib/api.ts`) devuelve cadena vacía en el navegador (mismo origen) y solo usa `NEXT_PUBLIC_API_URL` en servidor.

### `NEXT_PUBLIC_API_URL` solo existe en Production (intencional)

`getApiUrl()` cae a `http://localhost:8000` cuando la variable falta, y está definida **únicamente en el entorno Production de Vercel**. Como consecuencia, la auth no funciona en deploys de Preview.

Esto es deliberado: el proyecto está en fase piloto y despliega directo a producción, sin usar Preview. **No lo "arregles" añadiendo la variable a otros entornos** salvo que el flujo de despliegue cambie.

## Comandos

```bash
# Frontend (desde apps/frontend)
npm run dev · npm run build · npm run lint

# Backend (desde apps/backend)
pytest                                    # cobertura mínima 70%
ruff check apps/backend workers/document_processor   # desde la raíz

# E2E
npx playwright test                       # desde tests/e2e
```

CI (`.github/workflows/ci.yml`) corre Python 3.11 y Node 20: ruff, ESLint, pytest, `compileall` y build del frontend. `e2e.yml` corre Playwright.

## Convenciones

- **Ruff** es el linter y formateador del Python (comillas dobles, línea 100). Los `ignore` en `apps/backend/pyproject.toml` están justificados con comentario cada uno — no los quites sin leer el porqué.
- Los tests de backend usan marcadores `unit`, `integration`, `e2e`, `slow`. Declara el marcador; `--strict-markers` está activo.
- Migraciones de esquema vía **Alembic**, nunca a mano.
- Sin Prettier en el proyecto: el formato de TS/TSX lo gobierna ESLint (`eslint-config-next`).

## Seguridad

- `.env`, `.env.local` y `.env.production.example` viven en la raíz y contienen secretos reales. No los edites ni los vuelques en logs.
- El JWT usa `python-jose`; los hashes de contraseña llaman a `bcrypt` directamente (`app/core/security.py`). `passlib` se eliminó a propósito por incompatibilidad con bcrypt ≥ 4.2.
- `slowapi` limita el rate de `/register` y `/login`. Redis mantiene la blacklist de tokens.
