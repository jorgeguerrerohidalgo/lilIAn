# lilIAn 2.0

Plataforma legaltech chilena asistida por inteligencia artificial para revisión documental, detección de riesgos, análisis de precedentes judiciales y preevaluación de casos legales.

## Características

### Análisis Documental Inteligente
- **Procesamiento de documentos**: PDF, DOCX, TXT con OCR automático
- **Extracción de datos**: Identificación automática de partes, montos, fechas, cláusulas
- **Detección de riesgos**: Cláusulas sospechosas con semáforo de riesgo
- **Validación multi-documento**: Consistencia entre documentos de un caso

### Sistema RAG (Retrieval Augmented Generation)
- **Búsqueda híbrida**: Embeddings + keyword search con Reciprocal Rank Fusion
- **Contexto legal**: Precedentes judiciales y legislación chilena indexada
- **Trazabilidad**: Cada afirmación del análisis linkeada a su fuente original

### Workflow de Revisión
- **Estados**: draft → pending → approved/rejected
- **Gate de revisión**: Análisis con `requires_human_review=True` necesita aprobación
- **Citaciones navegables**: Click para abrir el documento fuente

### Seguridad Multi-Tenant
- **Aislamiento por organización**: Todos los recursos filtrados por `organization_id`
- **RBAC**: 7 roles con permisos diferenciados (PLATFORM_ADMIN, OWNER, ADMIN, LAWYER, COMPANY_USER, CLIENT, VIEWER)
- **Auditoría**: Logs de todas las acciones

## Stack Técnico

| Componente | Tecnología |
|------------|-------------|
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| Backend | FastAPI (Python 3.12) |
| Base de datos | Supabase (PostgreSQL + pgvector) |
| Worker | Redis + RQ |
| Storage | Supabase Storage o filesystem local |
| IA/LLM | Interfaz abstracta (Anthropic, OpenAI, MiniMax) |

## 快速开始

### 1. Clonar y configurar

```bash
git clone https://github.com/Jorge-Guerrero-Hidalgo/lilian.git
cd lilian

# Variables de entorno
cp apps/backend/.env.example apps/backend/.env
# Editar .env con tus credenciales
```

### 2. Docker Compose

```bash
docker-compose up -d
```

### 3. Acceso

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Arquitectura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend  │────▶│   Backend  │────▶│  Supabase   │
│  (Next.js) │     │  (FastAPI) │     │  (PostgreSQL)│
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌─────▼─────┐
                    │   Worker   │
                    │  (Redis)   │
                    └─────────────┘
```

## Estructura del Proyecto

```
lilian/
├── apps/
│   ├── frontend/                    # Next.js 14
│   │   ├── app/                    # App router pages
│   │   ├── components/             # Componentes React
│   │   │   ├── citation-link.tsx   # Citaciones navegables
│   │   │   └── document-analysis-view.tsx
│   │   └── lib/                   # Utilidades
│   └── backend/                    # FastAPI
│       ├── app/
│       │   ├── api/endpoints/      # Routers de API
│       │   │   ├── matters.py       # Casos
│       │   │   ├── documents.py     # Documentos
│       │   │   ├── analysis.py      # Análisis IA
│       │   │   ├── review.py        # Workflow de revisión
│       │   │   ├── precedents.py    # Precedentes
│       │   │   └── admin.py         # Admin
│       │   ├── models/              # Modelos SQLAlchemy
│       │   │   ├── review.py        # Review model
│       │   │   └── ...
│       │   ├── services/            # Lógica de negocio
│       │   │   ├── analysis.py      # Análisis de documentos
│       │   │   ├── evidence.py      # EvidenceBundle
│       │   │   ├── document_processor.py
│       │   │   ├── storage.py       # Storage abstracto
│       │   │   └── precedent_rag.py
│       │   └── deps/               # Dependencies
│       │       └── tenant.py       # TenantContext
│       └── tests/                  # Tests
│           ├── fixtures/legal_cases/ # Dataset golden
│           └── test_isolation.py   # Tests de aislamiento
├── workers/
│   └── document_processor/         # Worker de procesamiento
├── infra/
│   └── supabase/migrations/        # Migraciones SQL
├── docs/
│   ├── schema.md                   # Documentación de BD
│   └── rbac-matrix.md             # Matriz RBAC
└── docker-compose.yml
```

## API Endpoints Principales

### Análisis de Documentos
- `POST /api/v1/analysis/matters/{id}` - Genera análisis
- `GET /api/v1/analysis/matters/{id}/latest` - Último análisis

### Workflow de Revisión
- `POST /api/v1/reviews` - Crear review (draft)
- `POST /api/v1/reviews/{id}/submit` - Enviar para revisión
- `POST /api/v1/reviews/{id}/approve` - Aprobar
- `POST /api/v1/reviews/{id}/reject` - Rechazar

### Precedentes y RAG
- `GET /api/v1/precedents` - Listar precedentes
- `POST /api/v1/precedents/search` - Búsqueda híbrida

## Modelos de Datos

24 tablas incluyendo:
- `organizations`, `users`, `organization_members`
- `clients`, `matters`, `documents`, `document_chunks`
- `analysis_reports`, `risk_items`
- `precedents`, `legal_sources`
- `reviews` (nuevo - workflow)
- `audit_logs`, `chat_sessions`, `templates`

Ver [docs/schema.md](./docs/schema.md) para diagrama completo.

## Seguridad

### Roles y Permisos

| Rol | Descripción |
|-----|-------------|
| PLATFORM_ADMIN | Administrador global (multi-tenant) |
| OWNER | Propietario de organización |
| ADMIN | Administrador de organización |
| LAWYER | Abogado (gestión de casos) |
| COMPANY_USER | Usuario corporativo |
| CLIENT | Cliente (solo ve sus casos) |
| VIEWER | Solo lectura |

Ver [docs/rbac-matrix.md](./docs/rbac-matrix.md) para matriz completa.

### Aislamiento

- Todos los endpoints filtran por `organization_id`
- Validación FK: `client_id` debe pertenecer a la organización
- RLS policies deshabilitadas (incompatibles con auth.uid())

## Testing

```bash
# Tests de aislamiento multi-tenant
cd apps/backend
pytest tests/test_isolation.py -v

# Tests de dataset golden
pytest tests/test_golden_dataset.py -v
```

## Variables de Entorno

```env
# Base de datos
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...

# Seguridad
JWT_SECRET=...
ENCRYPTION_KEY=...

# LLM
LLM_PROVIDER=openai
LLM_API_KEY=sk-...

# Storage (local o supabase)
STORAGE_BACKEND=local
STORAGE_PATH=/app/storage/documents
SUPABASE_STORAGE_BUCKET=documents
```

## Changelog v2.0

### Nuevas Features
- Sistema RAG con búsqueda híbrida (RRF)
- Workflow de revisión de análisis (draft → approved/rejected)
- Gate de revisión para decisiones automatizadas
- Citaciones navegables con EvidenceBundle
- Idempotencia en procesamiento de documentos
- Storage abstracto (Supabase o local)
- Dataset golden para evaluación
- TenantContext como dependencia inyectable

### Seguridad
- RBAC implementado en todos los endpoints
- Aislamiento multi-tenant completo
- Modelo Review para auditoría de decisiones

### Fixes
- Secretos removidos de docker-compose.yml
- RLS policies deshabilitadas (usaban auth.uid() roto)
- Endpoints debug eliminados

## Deployment

Ver [DEPLOYMENT.md](./DEPLOYMENT.md) para instrucciones detalladas.

## Disclaimer Legal

Toda respuesta generada incluye automáticamente:

> Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile.

## Licencia

Privado - Todos los derechos reservados

## Autores

- Jorge Guerrero Hidalgo
