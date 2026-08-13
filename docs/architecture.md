# 🏛️ Arquitectura — lilIAn

> Documento vivo de la arquitectura del sistema.
> Última revisión: 2026-08-07

---

## 🎯 Visión General

**lilIAn** es una plataforma SaaS legaltech chilena asistida por IA. Permite a abogados y firmas legales procesar documentos, detectar riesgos legales, analizar precedentes judiciales y gestionar casos (matters) con un enfoque multi-tenant estricto.

---

## 🏗️ Stack

| Capa | Tecnología | Versión |
|------|------------|---------|
| Frontend | Next.js + TypeScript | 14.x |
| Backend | FastAPI + Python | 3.12 |
| Base de datos | Supabase (PostgreSQL + pgvector) | 15.x |
| Cache / Cola | Redis | 7.x |
| Worker | RQ (Redis Queue) | 1.x |
| Storage | Supabase Storage o filesystem local | — |
| IA/LLM | Anthropic / OpenAI / MiniMax | — |
| Deploy backend | Railway | — |
| Deploy frontend | Vercel | — |

---

## 📐 Capas

```
┌─────────────────────────────────────────────────────────────┐
│                  Frontend (Next.js 14)                       │
│  - App Router con React Server Components                     │
│  - Middleware de auth (cookies httpOnly)                     │
│  - lib/api.ts centraliza llamadas al backend                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (JWT en cookie httpOnly)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  api/endpoints/ (16 routers)                            │ │
│  │  - auth, matters, clients, documents, chat, etc.       │ │
│  └────────────┬───────────────────────────────────────────┘ │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  api/deps/auth.py — RBAC dependencies                  │ │
│  │  - get_current_user, require_organization              │ │
│  │  - get_platform_admin_membership                       │ │
│  └────────────┬───────────────────────────────────────────┘ │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  services/ (lógica de negocio)                          │ │
│  │  - analysis, rag, evidence, document_processor, etc.   │ │
│  └────────────┬───────────────────────────────────────────┘ │
│               ▼                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  models/ (SQLAlchemy ORM)                               │ │
│  │  - matter, document, chat, review, organization, etc.   │ │
│  └────────────┬───────────────────────────────────────────┘ │
└───────────────┼──────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL (Supabase)                      │
│  - Multi-tenant via organization_id en cada tabla            │
│  - pgvector para embeddings                                  │
│  - RLS (Row-Level Security) como defensa en profundidad      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Multi-Tenancy & RBAC

### Modelo

- **Organización** = tenant (ej: una firma legal)
- **Usuario** puede pertenecer a múltiples organizaciones vía `OrganizationMember`
- **Roles** (7 totales): `PLATFORM_ADMIN`, `OWNER`, `ADMIN`, `LAWYER`, `COMPANY_USER`, `CLIENT`, `VIEWER`

### Garantías

1. **Cada query filtra por `organization_id`** — los endpoints usan `require_organization` dependency
2. **RLS en PostgreSQL** como segunda capa
3. **Tests de aislamiento** validan que Org A no puede leer/escribir datos de Org B
4. **Audit logging** registra todas las acciones sensibles

Ver [`docs/rbac-matrix.md`](rbac-matrix.md) para el detalle de permisos.

---

## 🔄 Flujo de Procesamiento de un Documento

```
1. Usuario sube PDF/DOCX/TXT
   ↓
2. FastAPI valida:
   - Auth + RBAC (require_organization)
   - Magic bytes del archivo (S0-12)
   - Tamaño máximo (50MB)
   - Filename sanitization
   ↓
3. Storage.save_file() (con _safe_join path validation)
   ↓
4. Background task (RQ o FastAPI BackgroundTasks)
   - process_document(document_id)
   - SELECT FOR UPDATE (lock pesimista)
   ↓
5. Extract text (PDF → fitz, DOCX → python-docx, TXT)
   - Con _safe_open_pdf() (S1-07: max 500 pages, 50MB)
   ↓
6. create_chunks_for_document() (S4-06: 5 helpers)
   - split_text_into_chunks (chunker)
   - generate_embedding por chunk
   - Persistir en DocumentChunk
   ↓
7. _classify_document_async (en background)
   - LLM classification → DocumentAnalysis
   ↓
8. Status: processing → processed (o failed)
```

---

## 🤖 Flujo de Análisis Legal

```
1. POST /api/v1/analysis (matter_id)
   ↓
2. can_use_analysis_for_automated_decisions? (S0-13)
   - Si requires_human_review → requiere review_approved=True
   - Si no requiere → auto-approved pero explícito
   ↓
3. analyze_contract() (services/analysis.py)
   - get_system_prompt_for_matter_type
   - get_laws_context_for_rag (legal context)
   - get_precedents_context_for_rag (judicial precedents)
   - LLM call con schema Pydantic
   ↓
4. _validate_llm_output() (S1-06)
   - Shape check (max 8000 chars, max 200 items, depth 8)
   - Prompt injection detection (6 patterns)
   - Marca requires_human_review si hay sospecha
   ↓
5. detect_normative_conflicts() (S4-03 refactor)
   - Compara contrato con legislación chilena
   - Retorna conflicts + observations
   ↓
6. Persistir AnalysisReport + RiskItem
   ↓
7. Workflow review (si requiere)
   - draft → pending → approved/rejected
   - Lock pesimista en update_analysis_review_status (S3-02)
```

---

## 🛡️ Seguridad

### Capas

1. **CORS restrictivo** (S1-17) — solo orígenes explícitos en producción
2. **JWT en cookies httpOnly** (S0-04) — no localStorage
3. **JWT con iss/aud** (S0-09) — validación fail-fast en arranque
4. **Token blacklist en Redis** (S1-16) — logout invalida inmediatamente
5. **Rate limiting** (S1-05) — 10/minute en `/register` y `/login`
6. **RBAC + multi-tenant** — ver sección anterior
7. **Validación de uploads** (S0-12) — magic bytes + filename safe
8. **Path traversal fix** (S0-11) — `_safe_join()` en storage
9. **Audit logging** — todas las acciones registradas en `audit_logs`

### Procedimiento de Secrets

Ver [`docs/SECRETS_MANAGEMENT.md`](SECRETS_MANAGEMENT.md).

---

## 📊 Observabilidad

- **Logging estructurado** con redacción de secretos
- **Métricas in-process** (`/metrics`) — scoped por organización (S2-01)
- **Audit logs** en PostgreSQL
- **Healthcheck** en `/health`

---

## 🐳 Deployment

- **Backend**: Railway (`railway.json`)
- **Frontend**: Vercel (`vercel.json`)
- **Dockerfile** multi-stage, non-root, healthcheck (S6-01)
- **.dockerignore** raíz (S6-02)

Ver [`DEPLOYMENT.md`](../DEPLOYMENT.md) para detalles completos.

---

## 🔄 CI/CD

- **GitHub Actions** (`.github/workflows/ci.yml`)
- **Multi-stage Dockerfile** verificado
- **Playwright config** (S6-03) para E2E
- **pyproject.toml** con ruff/pytest/coverage (S6-04)

---

## 📚 Referencias

- [`docs/REMEDIATION_PLAN.md`](REMEDIATION_PLAN.md) — Plan de remediación
- [`docs/SECRETS_MANAGEMENT.md`](SECRETS_MANAGEMENT.md) — Procedimiento de secretos
- [`docs/rbac-matrix.md`](rbac-matrix.md) — Matriz RBAC
- [`docs/schema.md`](schema.md) — Schema de DB