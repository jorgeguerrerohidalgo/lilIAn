# lilIAn

Plataforma legaltech chilena asistida por inteligencia artificial para revisión documental, detección de riesgos y preevaluación de casos legales.

## Características principales

- **Análisis documental**: Sube contratos y documentos (PDF, DOCX, TXT) para recibir un análisis preliminar estructurado.
- **Detección de riesgos**: Identifica cláusulas riesgosas con semáforo de riesgo (verde/amarillo/rojo/gris).
- **Chat contextual**: Pregunta sobre tus documentos y recibe respuestas basadas en su contenido mediante RAG.
- **Multi-tenancy**: Soporte para múltiples organizaciones (estudios jurídicos, empresas, usuarios individuales).
- **Panel de abogado**: Gestiona casos entrantes, prioriza y genera respuestas para captación de clientes.
- **Plantillas y playbooks**: Plantillas de prompts, emails y checklists para flujo de trabajo legal.
- **SaaS completo**: Planes, métricas de uso, límites por organización.

## Stack técnico

| Componente | Tecnología |
|------------|-------------|
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| Backend | FastAPI (Python) |
| Base de datos | Supabase Online (PostgreSQL + pgvector) |
| Worker | Redis + RQ |
| IA/LLM | Interfaz abstracta (Anthropic, OpenAI, MiniMax, Dummy) |
| Containerización | Docker + Docker Compose |

## Requisitos previos

- Docker y Docker Compose instalados
- Cuenta de Supabase con proyecto creado
- API keys de proveedores de IA (opcional para desarrollo)

## Configuración

### 1. Variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales de Supabase:

```env
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
SUPABASE_URL=https://[PROJECT_REF].supabase.co
SUPABASE_ANON_KEY=tu_anon_key
SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key
JWT_SECRET=tu_jwt_secret_seguro
```

### 2. Ejecutar migraciones en Supabase

```bash
psql $DATABASE_URL -f infra/supabase/migrations/001_enable_extensions.sql
psql $DATABASE_URL -f infra/supabase/migrations/002_create_organizations.sql
psql $DATABASE_URL -f infra/supabase/migrations/003_create_users.sql
psql $DATABASE_URL -f infra/supabase/migrations/004_create_organization_members.sql
psql $DATABASE_URL -f infra/supabase/migrations/005_create_matters.sql
psql $DATABASE_URL -f infra/supabase/migrations/006_create_documents.sql
psql $DATABASE_URL -f infra/supabase/migrations/007_create_audit_logs.sql
psql $DATABASE_URL -f infra/supabase/migrations/008_create_pgvector.sql
psql $DATABASE_URL -f infra/supabase/migrations/009_create_document_chunks.sql
psql $DATABASE_URL -f infra/supabase/migrations/010_create_legal_sources.sql
psql $DATABASE_URL -f infra/supabase/migrations/011_create_analysis_reports.sql
psql $DATABASE_URL -f infra/supabase/migrations/012_create_risk_items.sql
psql $DATABASE_URL -f infra/supabase/migrations/013_create_chat_sessions.sql
psql $DATABASE_URL -f infra/supabase/migrations/014_create_templates.sql
psql $DATABASE_URL -f infra/supabase/migrations/015_create_subscriptions_and_usage.sql
```

### 3. Levantar servicios

```bash
docker compose up -d
```

Servicios:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs
- **Redis**: puerto 6379

## Desarrollo local sin Docker

```bash
# Backend
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000

# Frontend
cd apps/frontend && npm install && npm run dev

# Worker
cd workers/document_processor && pip install -r requirements.txt && python -m worker
```

## Estructura del proyecto

```
lilian/
├── apps/
│   ├── frontend/          # Next.js 14
│   │   ├── app/          # App router pages
│   │   ├── public/images/ # Logo e imágenes
│   │   └── components/   # Componentes React
│   └── backend/          # FastAPI
│       ├── app/
│       │   ├── api/endpoints/  # Routers de API
│       │   ├── core/           # Config, security, database
│       │   ├── models/        # Modelos SQLAlchemy
│       │   ├── schemas/       # Schemas Pydantic
│       │   └── services/      # Lógica de negocio (LLM, RAG, etc.)
│       └── requirements.txt
├── workers/
│   └── document_processor/  # Worker de procesamiento
├── infra/
│   └── supabase/migrations/  # Migraciones SQL
├── scripts/
│   └── migrate_supabase.sh   # Script de migración
├── images/                    # Logo original
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints

### Autenticación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Registro de usuario |
| POST | `/api/v1/auth/login` | Inicio de sesión |
| GET | `/api/v1/auth/me` | Usuario actual |

### Organizaciones
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/organizations` | Listar organizaciones |
| POST | `/api/v1/organizations` | Crear organización |
| GET | `/api/v1/organizations/me` | Mi organización |
| GET | `/api/v1/organizations/me/members` | Miembros de organización |

### Casos (Matters)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/matters` | Listar casos |
| POST | `/api/v1/matters` | Crear caso |
| GET | `/api/v1/matters/{id}` | Ver caso |
| PATCH | `/api/v1/matters/{id}` | Actualizar caso |
| DELETE | `/api/v1/matters/{id}` | Eliminar caso |

### Documentos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/documents/matters/{matter_id}/documents` | Subir documento |
| GET | `/api/v1/documents/matters/{matter_id}/documents` | Listar documentos del caso |
| GET | `/api/v1/documents/{id}` | Ver documento |
| DELETE | `/api/v1/documents/{id}` | Eliminar documento |
| POST | `/api/v1/documents/{id}/process` | Reprocesar documento |

### Análisis IA
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/analysis` | Generar análisis (background) |
| GET | `/api/v1/analysis/matters/{matter_id}` | Lista de análisis del caso |
| GET | `/api/v1/analysis/matters/{matter_id}/latest` | Último análisis |
| GET | `/api/v1/analysis/matters/{matter_id}/risks` | Riesgos del caso |
| GET | `/api/v1/analysis/reports/{report_id}` | Ver informe completo |
| PATCH | `/api/v1/analysis/risks/{risk_id}/review` | Actualizar estado de revisión |

### Búsqueda RAG
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/search` | Búsqueda híbrida en documentos |

### Chat
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/chat/sessions` | Crear sesión de chat |
| GET | `/api/v1/chat/sessions` | Listar sesiones |
| GET | `/api/v1/chat/sessions/{id}/messages` | Mensajes de sesión |
| POST | `/api/v1/chat/message` | Enviar mensaje |
| DELETE | `/api/v1/chat/sessions/{id}` | Eliminar sesión |

### Panel de Abogado
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/lawyer/cases` | Casos entrantes |
| POST | `/api/v1/lawyer/matters/{id}/notes` | Agregar nota |
| GET | `/api/v1/lawyer/matters/{id}/notes` | Ver notas |
| PATCH | `/api/v1/lawyer/matters/{id}/status` | Cambiar estado |
| POST | `/api/v1/lawyer/matters/{id}/assign` | Asignar abogado |
| GET | `/api/v1/lawyer/matters/{id}/summary` | Resumen para abogado |

### Plantillas
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/templates` | Listar plantillas |
| POST | `/api/v1/templates` | Crear plantilla |
| GET | `/api/v1/templates/{id}` | Ver plantilla |
| DELETE | `/api/v1/templates/{id}` | Eliminar plantilla |

### SaaS
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/saas/plans` | Listar planes disponibles |
| GET | `/api/v1/saas/subscription` | Mi suscripción |
| POST | `/api/v1/saas/subscription` | Crear/actualizar suscripción |
| GET | `/api/v1/saas/metrics` | Métricas de organización |
| GET | `/api/v1/saas/usage/events` | Eventos de uso |

### Admin
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/admin/audit-logs` | Logs de auditoría |
| GET | `/api/v1/admin/organizations` | Todas las organizaciones |
| GET | `/api/v1/admin/stats` | Estadísticas de plataforma |
| POST | `/api/v1/admin/organizations/{id}/suspend` | Suspender org |
| POST | `/api/v1/admin/organizations/{id}/activate` | Activar org |

## Modelo de datos

### Tablas principales
- `organizations` - Organizaciones/Empresas
- `users` - Usuarios
- `organization_members` - Relación usuario-organización con roles
- `matters` - Casos legales
- `documents` - Documentos cargados
- `document_chunks` - Fragmentos para búsqueda RAG
- `analysis_reports` - Informes de análisis IA
- `risk_items` - Riesgos detectados
- `chat_sessions` / `chat_messages` - Conversaciones
- `templates` - Plantillas
- `matter_notes` - Notas de abogado
- `subscriptions` - Suscripciones SaaS
- `usage_events` - Eventos de uso
- `audit_logs` - Logs de auditoría

### Roles de usuario
- `owner` - Dueño de organización
- `admin` - Administrador
- `lawyer` - Abogado
- `company_user` - Usuario de empresa
- `client` - Cliente
- `viewer` - Solo lectura

## Seguridad

- Contraseñas hasheadas con bcrypt
- JWT para autenticación con expiración
- Separación multi-tenant por `organization_id`
- Logs de auditoría para acciones sensibles
- Rate limiting configurable
- Variables de entorno para secrets
- `SUPABASE_SERVICE_ROLE_KEY` solo en backend/worker

## Disclaimer legal

Toda respuesta generada incluye automáticamente:

> Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile.

## Configuración de IA

El sistema soporta múltiples proveedores de LLM mediante interfaz abstracta:

```env
# Proveedores soportados: anthropic, openai, minimax
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
# Para MiniMax: LLM_MODEL=MiniMax-Text-01
LLM_API_KEY=tu_api_key

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=tu_api_key
```

## Licencia

Privado - Todos los derechos reservados
