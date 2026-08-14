# lilIAn Backend

> FastAPI + SQLAlchemy + Pydantic v2 sobre Python 3.12.

Backend multi-tenant de lilIAn. Expone la API REST, ejecuta el pipeline de analisis documental (extraccion, chunking, embedding, RAG) y aplica el modelo RBAC en cada endpoint.

---

## Tabla de Contenidos

- [Overview](#overview)
- [Stack](#stack)
- [Setup Local](#setup-local)
- [Variables de Entorno](#variables-de-entorno)
- [Comandos](#comandos)
- [Estructura de Directorios](#estructura-de-directorios)
- [Modelo Multi-Tenant](#modelo-multi-tenant)
- [Migraciones (Alembic)](#migraciones-alembic)
- [Testing](#testing)
- [Lint y Formato](#lint-y-formato)
- [Documentacion Tecnica](#documentacion-tecnica)

---

## Overview

El backend esta organizado en capas claras:

- **API** (`app/api/endpoints/`): routers FastAPI, uno por dominio (matters, documents, analysis, review, precedents, admin)
- **Dependencies** (`app/api/deps/`): dependencias inyectables, incluyendo el `TenantContext` que aisla cada request por organizacion
- **Services** (`app/services/`): logica de negocio (procesamiento de documentos, RAG, generacion de analisis, almacenamiento)
- **Models** (`app/models/`): modelos SQLAlchemy 2.x (ORM)
- **Schemas** (`app/schemas/`): Pydantic v2 para request/response
- **Core** (`app/core/`): configuracion, seguridad, logging

Todo endpoint requiere JWT valido, extrae `TenantContext` y aplica filtros RBAC antes de cualquier operacion.

---

## Stack

| Componente        | Tecnologia           | Notas                                |
|-------------------|----------------------|--------------------------------------|
| Runtime           | Python               | 3.12                                 |
| Framework web     | FastAPI              | async, OpenAPI auto-generado         |
| Validacion        | Pydantic             | v2                                   |
| ORM               | SQLAlchemy           | 2.x, async session                   |
| Migraciones       | Alembic              | integrado con SQLAlchemy             |
| Auth              | python-jose (JWT)    | HS256, claims `org_id` y `role`      |
| HTTP client       | httpx                | para integraciones con LLM providers |
| Testing           | pytest               | con markers unit / integration / slow |
| Lint / formato    | Ruff                 | line-length 100, target py312        |
| Coverage          | coverage.py          | baseline 60%, objetivo 80%           |

---

## Setup Local

### Pre-requisitos

- Python 3.12
- pip o uv
- PostgreSQL 15 (Supabase en produccion, local via Docker Compose)
- Redis 7 (Upstash en produccion, local via Docker Compose)

### Con Docker Compose (recomendado desde raiz)

```bash
cd ../..
docker compose up -d
```

Esto levanta Postgres, Redis, backend y worker.

### Sin Docker

```bash
# Crear y activar virtualenv
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# Aplicar migraciones
alembic upgrade head

# Levantar servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Variables de Entorno

Catalogadas en `.env.example`. Resumen:

| Variable                  | Descripcion                                                  |
|---------------------------|--------------------------------------------------------------|
| `DATABASE_URL`            | URL de conexion PostgreSQL (async driver preferido)          |
| `SUPABASE_URL`            | URL del proyecto Supabase                                    |
| `SUPABASE_SERVICE_KEY`    | Service role key (solo backend, NUNCA en frontend)           |
| `REDIS_URL`               | URL de Redis para RQ worker                                  |
| `JWT_SECRET`              | secreto para firmar tokens (>= 32 chars)                     |
| `ENCRYPTION_KEY`          | clave Fernet para cifrado en reposo (32 bytes base64)        |
| `LLM_PROVIDER`            | `openai` \| `anthropic` \| `minimax`                         |
| `LLM_API_KEY`             | API key del provider seleccionado                            |
| `LLM_MODEL`               | modelo especifico (ej. `gpt-4o-mini`, `claude-3-5-sonnet`)   |
| `STORAGE_BACKEND`         | `local` \| `supabase`                                        |
| `STORAGE_PATH`            | path local (cuando `STORAGE_BACKEND=local`)                  |
| `SUPABASE_STORAGE_BUCKET`| nombre del bucket (cuando `STORAGE_BACKEND=supabase`)        |
| `CORS_ORIGINS`            | lista separada por comas (NO usar `*` con cookies/credenciales) |
| `ENV`                     | `development` \| `staging` \| `production`                   |
| `LOG_LEVEL`               | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`                    |

Detalles sensibles y manejo de rotacion en [../../docs/SECRETS_MANAGEMENT.md](../../docs/SECRETS_MANAGEMENT.md).

---

## Comandos

### Servidor

```bash
uvicorn app.main:app --reload --port 8000      # dev
uvicorn app.main:app --host 0.0.0.0 --port 8000 # prod (gunicorn + workers recomendado)
```

OpenAPI docs:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- JSON: http://localhost:8000/openapi.json

### Worker (RQ)

```bash
# Worker de procesamiento de documentos
cd ../../workers/document_processor
rq worker --url $REDIS_URL default
```

### Migraciones

```bash
alembic upgrade head              # aplicar
alembic downgrade -1              # revertir una
alembic revision --autogenerate -m "mensaje"  # generar
```

### Tests

```bash
pytest                                          # toda la suite
pytest -m unit                                   # solo unit
pytest -m integration                            # solo integration
pytest tests/test_isolation.py -v                # aislamiento multi-tenant
pytest tests/test_golden_dataset.py -v           # evaluacion RAG
pytest --cov=app --cov-report=term-missing       # con coverage
```

### Lint y formato

```bash
ruff check .          # lint
ruff check . --fix    # auto-fix seguro
ruff format .         # formato
```

---

## Estructura de Directorios

```
apps/backend/
├── app/
│   ├── main.py                   # entrypoint FastAPI
│   ├── api/
│   │   ├── deps/
│   │   │   └── tenant.py         # TenantContext dependency
│   │   └── endpoints/
│   │       ├── matters.py        # /api/v1/matters
│   │       ├── documents.py      # /api/v1/documents
│   │       ├── analysis.py       # /api/v1/analysis
│   │       ├── review.py         # /api/v1/reviews
│   │       ├── precedents.py     # /api/v1/precedents
│   │       └── admin.py          # /api/v1/admin
│   ├── core/
│   │   ├── config.py             # settings (Pydantic Settings)
│   │   ├── security.py           # JWT, password hashing, encryption
│   │   └── logging.py            # structured logging
│   ├── models/                   # SQLAlchemy ORM
│   │   ├── organization.py
│   │   ├── user.py
│   │   ├── matter.py
│   │   ├── document.py
│   │   ├── analysis.py
│   │   ├── review.py
│   │   └── ...
│   ├── schemas/                  # Pydantic v2
│   │   ├── matter.py
│   │   ├── document.py
│   │   └── ...
│   └── services/                 # logica de negocio
│       ├── document_processor.py # extraccion + chunking + idempotencia
│       ├── analysis.py           # orquestacion de analisis
│       ├── evidence.py           # EvidenceBundle + citaciones
│       ├── storage.py            # storage abstracto (local/supabase)
│       ├── precedent_rag.py      # busqueda hibrida con RRF
│       └── llm/                  # clientes LLM (openai, anthropic, minimax)
├── migrations/                   # Alembic
├── tests/
│   ├── conftest.py               # fixtures (db, client, tenant, golden dataset)
│   ├── test_isolation.py         # aislamiento multi-tenant (S2)
│   ├── test_golden_dataset.py    # evaluacion RAG
│   ├── test_rbac.py              # permisos por rol
│   ├── test_review_workflow.py   # gate de revision humana
│   ├── fixtures/
│   │   └── legal_cases/          # dataset golden (json + pdf)
│   └── ...
├── pyproject.toml                # ruff + pytest + coverage
├── requirements.txt              # runtime deps
├── Dockerfile
├── Dockerfile.worker
└── .env.example
```

---

## Modelo Multi-Tenant

Todas las tablas de negocio incluyen `organization_id`. El flujo de cada request:

1. Middleware extrae JWT del header `Authorization: Bearer <token>`
2. Valida firma, expiracion y claims (`org_id`, `role`, `user_id`)
3. Construye `TenantContext` y lo inyecta via `Depends(get_tenant_context)`
4. Cada query y operacion pasa por helpers de repositorio que aplican `WHERE organization_id = :tenant_id` automaticamente
5. Las FK entre entidades validan pertenencia a la misma organizacion antes de aceptar la relacion

Consecuencias:

- Imposible por construccion leer o escribir datos de otra organizacion
- Tests de aislamiento (`tests/test_isolation.py`) verifican esta propiedad para todos los endpoints
- Los `PLATFORM_ADMIN` son la unica excepcion: pueden cruzar tenants con un parametro explicito y trazado en `audit_logs`

---

## Migraciones (Alembic)

```bash
# Estado actual
alembic current

# Crear nueva migracion despues de cambiar modelos
alembic revision --autogenerate -m "add foo table"

# Aplicar
alembic upgrade head

# Revertir
alembic downgrade -1

# Historial
alembic history --verbose
```

Convenciones:

- Una migracion por cambio logico (no agrupar features distintos)
- Mensaje descriptivo y corto
- Verificar con `alembic upgrade head` y `alembic downgrade -1` antes de commitear
- Para cambios destructivos incluir data migration

---

## Testing

### Estrategia

- **Unit tests**: funciones puras, logica de negocio sin DB
- **Integration tests**: API + DB SQLite en memoria; cubren todos los routers
- **Golden dataset** (`tests/test_golden_dataset.py`): casos legales reales con respuestas esperadas, mide recall del RAG
- **Isolation tests** (`tests/test_isolation.py`): S2 audit, garantiza que cross-tenant no es posible

### Coverage

```bash
pytest --cov=app --cov-report=term-missing
```

Baseline Sprint 6: 60%. Sprint 8/9 apunta a 80%.

### Markers

Definidos en `pyproject.toml`:

- `unit` — sin DB ni red
- `integration` — usa DB SQLite test
- `slow` — > 5s, excluido por defecto en CI

```bash
pytest -m "not slow"        # CI tipico
pytest -m unit              # solo unit
pytest -m integration       # solo integration
```

---

## Lint y Formato

Configurado en `pyproject.toml`. Ignores documentados:

- `B008` — false positives en defaults async (ej. `Field(default=datetime.utcnow)`)
- `UP045` — mantener `Optional[X]` por compat de schema export
- `E402` — docstrings de modulo van despues de imports (PEP 257)
- `BLE001` — boundary logging defensivo

```bash
ruff check . && ruff format --check .
```

CI corre ambos en cada PR.

---

## Documentacion Tecnica

- Arquitectura general: [../../docs/architecture.md](../../docs/architecture.md)
- Esquema de DB: [../../docs/schema.md](../../docs/schema.md)
- OpenAPI: [../../docs/openapi.md](../../docs/openapi.md)
- Manejo de secretos: [../../docs/SECRETS_MANAGEMENT.md](../../docs/SECRETS_MANAGEMENT.md)
- Deploy: [../../DEPLOYMENT.md](../../DEPLOYMENT.md)

---

## Volver

[README raiz](../../README.md)