# lilIAn

> Plataforma legaltech chilena asistida por IA para revision documental, deteccion de riesgos, analisis de precedentes judiciales y preevaluacion de casos legales.

[![CI](https://img.shields.io/badge/CI-passing-2ea44f?logo=githubactions&logoColor=white)](https://github.com/Jorge-Guerrero-Hidalgo/lilian/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3120/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Multi-tenant](https://img.shields.io/badge/architecture-multi--tenant-7c3aed)](#arquitectura)
[![WCAG 2.1 AA](https://img.shields.io/badge/WCAG-2.1%20AA-0a7c2f)](./apps/frontend/README.md)

---

## Tabla de Contenidos

- [Vision](#vision)
- [Features](#features)
- [Stack](#stack)
- [Quickstart](#quickstart)
- [Arquitectura](#arquitectura)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [API Endpoints](#api-endpoints)
- [Modelo Multi-Tenant y RBAC](#modelo-multi-tenant-y-rbac)
- [Testing](#testing)
- [Deployment](#deployment)
- [Variables de Entorno](#variables-de-entorno)
- [Documentacion](#documentacion)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [Disclaimer Legal](#disclaimer-legal)
- [Licencia](#licencia)

---

## Vision

lilIAn es una plataforma SaaS B2B para firmas legales y abogados en Chile. Procesa documentos contractuales y judiciales, identifica riesgos automaticamente con un sistema de semaforo, busca precedentes judiciales relevantes y permite revisar cada decision automatica con trazabilidad completa a la fuente original.

El producto esta construido sobre una arquitectura multi-tenant estricta: cada organizacion trabaja en un aislamiento total de datos, con un modelo RBAC de 7 roles y un workflow de revision humana para cualquier decision automatizada que pueda afectar el resultado de un caso.

---

## Features

### Analisis Documental Inteligente

- Procesamiento de PDF, DOCX y TXT con extraccion automatica de texto
- Identificacion de partes, montos, fechas y clausulas relevantes
- Deteccion de riesgos con semaforo (verde / amarillo / rojo) y explicacion
- Validacion de consistencia entre multiples documentos del mismo caso

### Sistema RAG (Retrieval Augmented Generation)

- Busqueda hibrida: embeddings + keyword search fusionadas con Reciprocal Rank Fusion (RRF)
- Indice de precedentes judiciales y legislacion chilena con pgvector
- Citaciones navegables: cada afirmacion del analisis apunta a su fuente original via `EvidenceBundle`

### Workflow de Revision Humana

- Estados del analisis: `draft` -> `pending` -> `approved` | `rejected`
- Review gate: cualquier decision automatizada marcada `requires_human_review=True` no se ejecuta hasta ser aprobada
- Auditoria: modelo `reviews` registra quien aprobo/rechazo, cuando y por que

### Seguridad Multi-Tenant

- Aislamiento estricto por `organization_id` en cada query y FK
- RBAC con 7 roles diferenciados (PLATFORM_ADMIN, OWNER, ADMIN, LAWYER, COMPANY_USER, CLIENT, VIEWER)
- Tokens JWT firmados, claves de encriptacion rotadas, secretos fuera del repositorio
- Logs de auditoria para acciones sensibles

### Accesibilidad

- WCAG 2.1 AA: navegacion por teclado, regiones ARIA, roles semanticos, contraste validado
- Skip-to-content, fieldset/legend, htmlFor explicito, `aria-current` y `aria-label` en navegacion
- Estados de carga y mensajes de error con `aria-live` y `role=alert`

---

## Stack

| Capa            | Tecnologia                                  | Version |
|-----------------|---------------------------------------------|---------|
| Frontend        | Next.js (App Router) + TypeScript + Tailwind | 14.2.x  |
| UI              | React, lucide-react, clsx, tailwind-merge    | 18.3.x  |
| Forms / schemas | react-hook-form + zod                       | 7.52 / 3.23 |
| Backend         | FastAPI + Pydantic                          | Python 3.12 |
| ORM             | SQLAlchemy 2.x + Alembic                    | 2.x     |
| Base de datos   | Supabase (PostgreSQL 15 + pgvector)         | 15.x    |
| Cache / Cola    | Redis + RQ                                  | 7.x     |
| Storage         | Supabase Storage o filesystem local         | -       |
| LLM             | Interfaz abstracta (OpenAI / Anthropic / MiniMax) | - |
| Deploy          | Railway (backend) + Vercel (frontend)       | -       |

---

## Quickstart

### Pre-requisitos

- Python 3.12+
- Node.js 20+
- Docker + Docker Compose (recomendado para Postgres + Redis locales)
- Credenciales: cuenta de Supabase, Redis (Upstash o local), y al menos una API key LLM

### 1. Clonar

```bash
git clone https://github.com/Jorge-Guerrero-Hidalgo/lilian.git
cd lilian
```

### 2. Configurar variables de entorno

```bash
cp apps/backend/.env.example apps/backend/.env
cp apps/frontend/.env.example apps/frontend/.env.local
```

Editar `apps/backend/.env` con tus credenciales (Supabase, Redis, API key de LLM, JWT secret).

### 3. Levantar con Docker Compose (recomendado)

```bash
docker compose up -d
```

Esto inicia backend, worker de Redis y dependencias. Las migraciones de base de datos se aplican automaticamente en el primer arranque.

### 4. Sin Docker (modo desarrollo)

```bash
# Backend
cd apps/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Worker (otra terminal)
cd workers/document_processor
rq worker --url $REDIS_URL

# Frontend (otra terminal)
cd apps/frontend
npm install
npm run dev
```

### 5. Acceso local

| Servicio        | URL                                    |
|-----------------|----------------------------------------|
| Frontend        | http://localhost:3000                  |
| Backend API     | http://localhost:8000                  |
| OpenAPI / Swagger | http://localhost:8000/docs            |
| ReDoc           | http://localhost:8000/redoc            |

---

## Arquitectura

```
┌────────────────┐     HTTPS     ┌────────────────┐     SQL      ┌────────────────┐
│   Frontend     │──────────────▶│    Backend     │─────────────▶│   Supabase     │
│   (Next.js)    │    JWT/CORS   │   (FastAPI)    │              │  (PostgreSQL   │
│   Vercel       │◀──────────────│   Railway      │◀─────────────│   + pgvector)  │
└────────────────┘               └───────┬────────┘              └────────────────┘
                                         │ Redis RQ
                                         ▼
                                 ┌────────────────┐
                                 │    Worker      │
                                 │ (document_proc)│
                                 └────────────────┘
```

Componentes principales:

- **Frontend**: Next.js 14 con App Router, server components para datos sensibles y cliente para interactividad
- **Backend**: FastAPI expone routers REST bajo `/api/v1/*`. Cada request valida token JWT, extrae `TenantContext` y aplica filtros RBAC
- **Worker**: proceso Python separado que consume la cola Redis (RQ) para procesamiento pesado de documentos (extraccion, embedding, chunking)
- **Supabase**: PostgreSQL para datos transaccionales + pgvector para busqueda semantica. Storage opcional para documentos
- **LLM**: interfaz abstracta que permite swap entre OpenAI, Anthropic y MiniMax sin cambiar la logica de negocio

Para el detalle de modulos, modelos y patrones internos ver [docs/architecture.md](./docs/architecture.md).

---

## Estructura del Proyecto

```
lilian/
├── apps/
│   ├── frontend/                    # Next.js 14 (App Router)
│   │   ├── app/                     # Pages y layouts
│   │   │   ├── auth/                # login, register
│   │   │   ├── dashboard/           # panel principal
│   │   │   ├── matters/             # CRUD de casos
│   │   │   ├── documents/           # gestion documental
│   │   │   └── precedents/          # busqueda de precedentes
│   │   ├── components/              # React components
│   │   │   ├── chat/  layout/  matters/  ui/
│   │   └── lib/                     # clientes API, hooks, utils
│   └── backend/                     # FastAPI
│       ├── app/
│       │   ├── api/                 # routers REST
│       │   │   ├── endpoints/       # matters, documents, analysis,
│       │   │   │                    # review, precedents, admin
│       │   │   └── deps/            # tenant, auth, deps inyectables
│       │   ├── core/                # config, security, logging
│       │   ├── models/              # SQLAlchemy ORM
│       │   ├── schemas/             # Pydantic v2
│       │   └── services/            # logica de negocio
│       ├── migrations/              # Alembic
│       └── tests/                   # pytest
├── workers/
│   └── document_processor/          # RQ worker
├── infra/
│   └── supabase/migrations/         # SQL adicional
├── docs/                            # documentacion tecnica
├── scripts/                         # utilidades operativas
├── docker-compose.yml
├── DEPLOYMENT.md                    # guia de deploy
└── README.md
```

Detalles por subproyecto:

- [apps/backend/README.md](./apps/backend/README.md) — backend FastAPI, setup, comandos, estructura, modelos, testing
- [apps/frontend/README.md](./apps/frontend/README.md) — frontend Next.js, setup, build, accesibilidad, testing

---

## API Endpoints

### Analisis

- `POST   /api/v1/analysis/matters/{id}` — genera analisis de un caso
- `GET    /api/v1/analysis/matters/{id}/latest` — ultimo analisis
- `GET    /api/v1/analysis/{id}/evidence` — evidencia del analisis

### Workflow de revision

- `POST   /api/v1/reviews` — crea review en estado `draft`
- `POST   /api/v1/reviews/{id}/submit` — envia a revision
- `POST   /api/v1/reviews/{id}/approve` — aprueba (gate)
- `POST   /api/v1/reviews/{id}/reject` — rechaza con motivo

### Precedentes / RAG

- `GET    /api/v1/precedents` — lista precedentes
- `POST   /api/v1/precedents/search` — busqueda hibrida (embeddings + keyword, RRF)

### Documentacion OpenAPI

- `GET    /docs` — Swagger UI
- `GET    /redoc` — ReDoc
- `GET    /openapi.json` — esquema JSON

Catalogo completo y ejemplos en [docs/openapi.md](./docs/openapi.md).

---

## Modelo Multi-Tenant y RBAC

Todas las tablas de negocio llevan `organization_id`. Los endpoints validan que el recurso pertenece a la organizacion del usuario antes de cualquier lectura o escritura. La inyeccion de `TenantContext` se hace via dependencia FastAPI (`Depends(get_tenant_context)`).

### Roles

| Rol             | Alcance                                                    |
|-----------------|------------------------------------------------------------|
| PLATFORM_ADMIN  | Administrador global (multi-tenant, soporte interno)       |
| OWNER           | Propietario de la organizacion (facturacion, config critica) |
| ADMIN           | Administrador de la organizacion (usuarios, recursos)      |
| LAWYER          | Abogado (gestion de casos, documentos, plantillas)         |
| COMPANY_USER    | Usuario corporativo (casos asignados)                      |
| CLIENT          | Cliente final (solo sus casos)                             |
| VIEWER          | Solo lectura (visibilidad explicita)                       |

Matriz completa rol x recurso x accion en [docs/rbac-matrix.md](./docs/rbac-matrix.md).

---

## Testing

```bash
# Backend: tests unit, integration y golden dataset
cd apps/backend
pytest                                  # toda la suite
pytest tests/test_isolation.py -v       # aislamiento multi-tenant (S2)
pytest tests/test_golden_dataset.py -v  # evaluacion RAG con dataset golden
pytest -m unit                          # solo unit tests
pytest --cov=app --cov-report=term-missing

# Lint y formato
ruff check .
ruff format .
```

```bash
# Frontend
cd apps/frontend
npm run lint
npm run build   # valida TypeScript y build de produccion
```

Cobertura objetivo backend: 80% (baseline 60% en Sprint 6, sprint 8/9 lo elevan).

---

## Deployment

Despliegue estandar: **Railway** para backend + worker, **Vercel** para frontend, **Supabase** como managed Postgres + Storage.

Guia paso a paso, variables de entorno requeridas, configuracion de Redis (Upstash) y checklists de pre-deploy en [DEPLOYMENT.md](./DEPLOYMENT.md).

---

## Variables de Entorno

Catalogo completo y descripcion de cada variable en [docs/architecture.md#environment-variables](./docs/architecture.md).

Backend (resumen):

```env
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
REDIS_URL=redis://...
JWT_SECRET=...
ENCRYPTION_KEY=...
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
STORAGE_BACKEND=local|supabase
```

Frontend:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Nunca commitear `.env` ni archivos con credenciales. Ver [docs/SECRETS_MANAGEMENT.md](./docs/SECRETS_MANAGEMENT.md).

---

## Documentacion

- [docs/architecture.md](./docs/architecture.md) — arquitectura detallada, modulos, flujos
- [docs/schema.md](./docs/schema.md) — esquema completo de base de datos
- [docs/rbac-matrix.md](./docs/rbac-matrix.md) — matriz de permisos
- [docs/openapi.md](./docs/openapi.md) — documentacion interactiva de la API
- [docs/SECRETS_MANAGEMENT.md](./docs/SECRETS_MANAGEMENT.md) — manejo de secretos
- [docs/REMEDIATION_PLAN.md](./docs/REMEDIATION_PLAN.md) — historial de remediaciones
- [DEPLOYMENT.md](./DEPLOYMENT.md) — guia de despliegue
- [STATUS_v2.1.md](./STATUS_v2.1.md) — estado actual del proyecto
- [ROADMAP_HARVEY_FEATURES.md](./ROADMAP_HARVEY_FEATURES.md) — funcionalidades estilo Harvey.ai
- [HANDOFF.md](./HANDOFF.md) — estado post-deploy

---

## Contributing

Las contribuciones se gestionan por Pull Request. Antes de abrir un PR:

1. Crea una rama desde `main` con prefijo descriptivo (`feat/...`, `fix/...`, `refactor/...`, `docs/...`)
2. Sigue las convenciones del proyecto (commits conventional, ruff + prettier, type hints en Python, tipado estricto en TS)
3. Incluye tests para cualquier cambio funcional
4. Verifica que `pytest`, `ruff check`, `npm run lint` y `npm run build` pasan localmente
5. Enlaza el issue o ticket correspondiente

Plantillas y guia detallada: ver [CONTRIBUTING.md](./CONTRIBUTING.md) (en construccion).

---

## Changelog

Historial completo en [CHANGELOG.md](./CHANGELOG.md).

---

## Disclaimer Legal

Toda respuesta generada por el sistema incluye automaticamente:

> Este analisis es preliminar y no reemplaza la revision profesional de un abogado habilitado en Chile.

lilIAn es una herramienta de asistencia. Las decisiones legales finales deben ser tomadas por un profesional habilitado.

---

## Licencia

MIT — ver [LICENSE](./LICENSE) para el texto completo.