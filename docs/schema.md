# Esquema de Base de Datos - Lilian

## Tablas (24)

| Tabla | Descripción |
|-------|-------------|
| `organizations` | Organizaciones/tenants |
| `users` | Usuarios de la plataforma |
| `organization_members` | Relación users ↔ organizations con rol |
| `clients` | Clientes de cada organización |
| `matters` | Casos/legal matters |
| `documents` | Documentos subidos |
| `document_chunks` | Chunks de documentos para RAG |
| `document_analyses` | Análisis estructurados de documentos |
| `templates` | Plantillas de documentos/prompts |
| `matter_notes` | Notas en matters |
| `matter_status_history` | Historial de cambios de estado |
| `analysis_reports` | Reportes de análisis generados |
| `risk_items` | Items de riesgo detectados |
| `precedents` | Precedentes judiciales |
| `legal_sources` | Fuentes legales (leyes) |
| `legal_source_versions` | Versiones de fuentes legales |
| `chat_sessions` | Sesiones de chat |
| `chat_messages` | Mensajes de chat |
| `templates` | Plantillas |
| `audit_logs` | Logs de auditoría |
| `subscriptions` | Suscripciones |
| `usage_events` | Eventos de uso |
| `deadline_alerts` | Alertas de plazos |
| `plans` | Planes disponibles |

## Diagrama de Relaciones

```
organizations
    │
    ├── users (1:N)
    │       │
    │       └── organization_members (N:1 users, N:1 organizations)
    │
    ├── clients (1:N)
    │       │
    │       └── matters (1:N)
    │               │
    │               ├── documents (1:N)
    │               │       │
    │               │       ├── document_chunks (1:N)
    │               │       │
    │               │       └── document_analyses (1:1)
    │               │
    │               ├── matter_notes (1:N)
    │               ├── matter_status_history (1:N)
    │               ├── analysis_reports (1:N)
    │               │       │
    │               │       └── risk_items (N:1 analysis_report)
    │               │
    │               ├── chat_sessions (1:N)
    │               │       │
    │               │       └── chat_messages (N:1 chat_session)
    │               │
    │               └── deadline_alerts (1:N)
    │
    ├── templates (1:N)
    │
    ├── audit_logs (1:N)
    │
    ├── subscriptions (1:N)
    │
    ├── usage_events (1:N)
    │
    ├── precedents (1:N)
    │
    └── legal_sources (1:N)
            │
            └── legal_source_versions (N:1 legal_source)
```

## Foreign Keys

| Tabla | Columna | Referencia |
|-------|---------|------------|
| `organization_members` | `organization_id` | `organizations.id` |
| `organization_members` | `user_id` | `users.id` |
| `clients` | `organization_id` | `organizations.id` |
| `clients` | `created_by_user_id` | `users.id` |
| `matters` | `organization_id` | `organizations.id` |
| `matters` | `created_by_user_id` | `users.id` |
| `matters` | `assigned_lawyer_id` | `users.id` |
| `matters` | `client_id` | `clients.id` |
| `documents` | `organization_id` | `organizations.id` |
| `documents` | `matter_id` | `matters.id` |
| `documents` | `uploaded_by_user_id` | `users.id` |
| `document_chunks` | `document_id` | `documents.id` |
| `document_chunks` | `organization_id` | `organizations.id` |
| `document_chunks` | `matter_id` | `matters.id` |
| `document_analyses` | `document_id` | `documents.id` |
| `document_analyses` | `organization_id` | `organizations.id` |
| `analysis_reports` | `organization_id` | `organizations.id` |
| `analysis_reports` | `matter_id` | `matters.id` |
| `analysis_reports` | `generated_by_user_id` | `users.id` |
| `risk_items` | `analysis_report_id` | `analysis_reports.id` |
| `risk_items` | `matter_id` | `matters.id` |
| `risk_items` | `organization_id` | `organizations.id` |
| `chat_sessions` | `organization_id` | `organizations.id` |
| `chat_sessions` | `matter_id` | `matters.id` |
| `chat_sessions` | `user_id` | `users.id` |
| `chat_messages` | `chat_session_id` | `chat_sessions.id` |
| `templates` | `organization_id` | `organizations.id` |
| `templates` | `created_by_user_id` | `users.id` |
| `matter_notes` | `matter_id` | `matters.id` |
| `matter_notes` | `user_id` | `users.id` |
| `matter_status_history` | `matter_id` | `matters.id` |
| `matter_status_history` | `changed_by_user_id` | `users.id` |
| `subscriptions` | `organization_id` | `organizations.id` |
| `usage_events` | `organization_id` | `organizations.id` |
| `usage_events` | `user_id` | `users.id` |
| `precedents` | `organization_id` | `organizations.id` |
| `legal_source_versions` | `legal_source_id` | `legal_sources.id` |
| `audit_logs` | `organization_id` | `organizations.id` |
| `audit_logs` | `user_id` | `users.id` |
| `deadline_alerts` | `organization_id` | `organizations.id` |
| `deadline_alerts` | `matter_id` | `matters.id` |
| `deadline_alerts` | `document_id` | `documents.id` |
| `deadline_alerts` | `user_id` | `users.id` |

## Constraints

### Primary Keys
Todas las tablas tienen `id` como primary key con auto-incremento.

### Unique Constraints

| Tabla | Columnas |
|-------|----------|
| `organization_members` | `(organization_id, user_id)` |
| `users` | `email` |
| `clients` | `rut` (opcional) |
| `precedents` | `(organization_id, court, year, roll_number)` |
| `templates` | `(organization_id, name)` |
| `plans` | `name` |
| `document_analyses` | `document_id` (1:1) |

### Indexes

| Tabla | Columnas |
|-------|----------|
| `organization_members` | `organization_id`, `user_id` |
| `matters` | `organization_id`, `status`, `client_id` |
| `documents` | `organization_id`, `matter_id`, `status` |
| `document_chunks` | `document_id`, `organization_id`, `matter_id`, `legal_area` |
| `precedents` | `court`, `year`, `legal_area`, `organization_id` |
| `legal_sources` | `code`, `organization_id` |
| `legal_source_versions` | `legal_source_id` |
| `audit_logs` | `organization_id`, `created_at` |

## Notas de Aislamiento Multi-Tenant

- **Todas las tablas** (excepto `users`, `plans`, `legal_sources`, `legal_source_versions`) tienen `organization_id` como FK a `organizations`
- El aislamiento se implementa a nivel de aplicación filtrando por `organization_id`
- `organization_members` es la tabla de unión que define qué usuario pertenece a qué organización y con qué rol
- No hay RLS (Row Level Security) habilitado - el aislamiento es manejado por la aplicación

## Tipos de Datos Frecuentes

| Tipo | Uso |
|------|-----|
| `integer` | IDs, contadores |
| `character varying(n)` | Strings con límite (nombres, emails, etc.) |
| `text` | Contenido largo (texto extraído, markdown) |
| `jsonb` | Datos estructurados (metadata, participantes, etc.) |
| `timestamp without time zone` | Timestamps |
| `date` | Fechas (vencimientos, etc.) |
| `boolean` | Flags (is_active, is_overdue, etc.) |
| `enum` | Estados y tipos predefinidos |
