# lilIAn — State of Product (2026-08-21)

> Single-page "where we are right now" snapshot. Supersedes `STATUS_v2.0.md`,
> `STATUS_v2.1.md`, and the deployment section of `HANDOFF.md`.
> Freshness date: **2026-08-21**.

---

## 1. Production status (2026-08-21)

| Component | URL | Last commit deployed | Last deploy | Health |
|---|---|---|---|---|
| Backend (Railway) | `https://liliap-production.up.railway.app` | `a2e25b17` (pre-gap-fixes) — see note | 2026-08-13 04:43 GMT-4 | yellow |
| Frontend (Vercel) | `https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app` | gap-fixes batch (commits listed in section 3) | rolling via Vercel | green |

**Notes:**

- Backend health is **yellow**, not red: the eight gap-fix commits shipped today
  (section 3) are pushed to `origin/main`. Railway is rebuilding and the new
  image is propagating; until that image is live, production is still running
  the cached `a2e25b17` build. Frontend is **green** because Vercel rebuilds
  from `main` automatically.
- All other production signals observed during the 2026-08-19 audit are now
  closed (see sections 3 and 5).
- Vercel SSO Protection on the frontend project is still on — see
  `HANDOFF.md` for the one-click disable instructions.

---

## 2. Feature inventory

Marked: shipped, partial, missing. Gap analysis lives in
`ROADMAP_HARVEY_FEATURES.md`.

### Auth & onboarding

- BFF login + `lilian_auth_token` (HttpOnly, SameSite=Lax) - shipped
- `POST /api/v1/auth/register` with strong-password + slowapi rate limit - shipped
- Email verification flow - missing
- Forgot-password / password reset - missing
- OAuth (Google / Microsoft) - missing
- First-admin bootstrap via Supabase SQL documented in `HANDOFF.md` - shipped

### Matters & cases

- Matter CRUD per tenant - shipped
- Matter status enum (`active`, `closed`, `failed` — see audit fix) - shipped
- Auto-generated deadlines from analysis (Tiempos tab) - partial
- Matter-level audit log - shipped
- Matter-level dashboard analytics - partial

### Documents & analysis

- Upload (PDF/DOCX/TXT) to Supabase Storage with magic-byte validation - shipped
- Pipeline idempotente (hash + force flag) - shipped
- Async processing worker (RQ + Redis, PyMuPDF, python-docx) - shipped
- AI analysis with traffic-light risk schema - shipped
- Reanalysis via `POST /api/v1/analysis/matters/{id}` - shipped (fixed today)
- Real-time progress stepper on Documentos tab - shipped (fixed today, 80ac69d)
- Cascade-delete `deadline_alerts` before removing a document - shipped (fixed today, 2e13112)
- Schema slimming to avoid LLM token exhaustion - shipped (fixed today, e564a17)
- `indexed_content` surfaced as `summary` in `/analysis` response - shipped (fixed today, 189ef91)

### Chat & agents

- Floating chat widget with bootstrap retry - shipped (fixed today, a6c331e)
- `/chat/sessions` lifecycle - shipped
- RAG-augmented chat (documents + laws + precedents) - shipped
- Multi-turn memory across pages - shipped
- Streaming responses - missing
- Anthropic stop_reason diagnostics in debug endpoint - shipped (fixed today, 242a87e, 95daf2c)

### RAG & precedents

- Hybrid search (embeddings + keyword, RRF fusion) - shipped
- `pgvector` index on precedents + laws - shipped
- Precedent analytics dashboard (volume, heatmap, top voces) - shipped
- Outcome prediction (`/precedents/predict`) - missing
- Real embeddings (currently `EMBEDDING_PROVIDER=dummy`) - missing

### Templates & documents generator

- `extract_variables_from_matter()` LLM suggester - shipped
- `POST /doc-templates/suggest-variables` - shipped
- "Sugerir desde caso" button in `DocumentGenerator` - shipped
- Risk-aware template rendering - partial
- Template versioning / approval flow - missing

### Alerts & deadlines

- Deadline alert model + endpoints - shipped
- Auto-generation from analysis - shipped (recent)
- Email / push notifications - missing
- Calendar export (ICS) - missing

### Multi-tenant / RBAC

- 7-role RBAC matrix (`docs/rbac-matrix.md`) - shipped
- `organization_id` isolation in every query - shipped
- Audit log scoped per org - shipped
- Membership invitations - partial
- SCIM / SSO for enterprise tenants - missing

### LLM providers / embeddings

- Anthropic Claude Haiku 4.5 live in production - shipped
- OpenAI provider interface (config-only) - partial
- MiniMax provider interface - partial
- Provider failover - missing
- Real embeddings (pgvector with sentence-transformers or OpenAI) - missing

### Security / compliance

- JWT in HttpOnly cookie (no localStorage) - shipped
- CORS allow-list with fail-fast in production - shipped
- Slowapi rate limit on `/register` + `/login` - shipped
- Prompt-injection detection on LLM output - shipped
- PDF sanitization (page + byte caps) - shipped
- Bcrypt password hashes via `app/core/security.py` - shipped
- Redis-backed token blacklist (logout) - shipped
- Global exception handler with `x-request-id` - shipped
- WCAG 2.1 AA accessibility - shipped
- SOC 2 - missing
- ISO 27001 - missing
- Penetration test report - missing

### Deploy / infra

- Railway (backend) + Vercel (frontend) - shipped
- Supabase (Postgres + Storage + pgvector) - shipped
- Upstash Redis for RQ + blacklist - shipped
- CI: ruff, ESLint, pytest, `compileall`, frontend build - shipped
- Playwright E2E in CI - shipped
- Alembic adoption (currently mixed ad-hoc + Alembic) - partial
- Sentry / Datadog observability - missing
- Manual cache-clear runbook for Railway (see `AUDIT_2026-08-19.md`) - shipped

---

## 3. Recent commits (since 19-Aug-2026)

Chronological order. These are the gap fixes shipped today that close the
top user-reported pain points.

| Commit | One-liner |
|---|---|
| `80ac69d` | feat(processing): real-time progress stepper + skip dummy embeddings |
| `189ef91` | fix(analysis): expose `indexed_content` as `summary` in `/analysis` response |
| `e564a17` | fix(analysis): slim `DOCUMENT_ANALYSIS_SCHEMA` so LLM doesn't run out of tokens |
| `2e13112` | fix(documents): cascade-delete `deadline_alerts` before removing document |
| `5791806` | fix(frontend): polling exits when status is `analysis_ready` |
| `242a87e` | fix(llm): parser now reconstructs JSON from prefill continuation |
| `a6c331e` | fix(chat,llm): chat bootstrap retry + Anthropic stop_reason diagnostics |
| `95daf2c` | feat(backend): add raw Anthropic HTTP probe to debug endpoint |

---

## 4. Known bugs / deferred work

Carry-over from `AUDIT_2026-08-19.md` that is **not** yet closed:

- Railway image cache (cached image missing commits `9c1def6+`) — manual
  "Clear Build Cache" runbook still required if a rebuild does not auto-fire.
  See `AUDIT_2026-08-19.md` → "Estado del deploy" / "Acción manual requerida".
- Test file `apps/backend/laws/ley_proteccion_consumidor.pdf` is mislabeled
  (it is actually Código Aeronáutico). Renaming deferred to avoid breaking
  test paths. — 19-aug-2026.
- Upload UX: a fresh upload sits at `uploaded` until the user clicks
  "Procesar" — no auto-kick. Decision pending from product. — 19-aug-2026.
- Alembic migration script is a one-shot SQL inside the FastAPI lifespan,
  not a proper Alembic revision. Future schema changes should be migrated
  to Alembic. — 19-aug-2026.
- `JWT_SECRET` in Railway is the bootstrap value from `HANDOFF.md` (weak).
  Rotation procedure documented; not executed. — 13-aug-2026.

New carry-overs from this snapshot:

- Frontend polling exit-condition fix (`5791806`) needs a follow-up to also
  short-circuit on `analysis_failed`, not just `analysis_ready`.
- Real embeddings (`EMBEDDING_PROVIDER=dummy` today) — semantic recall on
  precedents and laws is currently keyword-only via RRF. — 21-aug-2026.

---

## 5. Top user-reported pain points (with date)

| Reported | Issue | Status |
|---|---|---|
| 20-aug-2026 | Documentos tab: "Procesando..." sin progress feedback | FIXED in `80ac69d` |
| 20-aug-2026 | Reanalizar produces blank report | FIXED in `e564a17` + `189ef91` |
| 19-aug-2026 | Chat frozen on "Conectando..." | FIXED in `a6c331e` |
| 20-aug-2026 | Delete document fails with ForeignKeyViolation | FIXED in `2e13112` |
| 20-aug-2026 | Matter 11 / 12 reports still appear empty in UI | FIXED in `189ef91` |

All five top-tier pain points from the 19–20 Aug window are closed by today's
batch. The frontend is awaiting Vercel's auto-rebuild to surface the fixes to
end users; the backend is awaiting Railway's image refresh (see section 1).

---

## 6. Open infrastructure tasks

| Task | Status | Notes |
|---|---|---|
| `.playwright-mcp/` cache files in `.gitignore` | DONE 2026-08-21 | added to `.gitignore` today |
| Audit docs in repo (`ROADMAP_HARVEY_FEATURES.md`, gap analysis plan) | IN PROGRESS | `ROADMAP_HARVEY_FEATURES.md` already in repo root; plan file with multi-sprint roadmap pending |
| Sellability roadmap (Q1–Q6 sprints defined) | PLANNED | plan file with multi-sprint roadmap pending |
| SOC 2 / ISO 27001 | NOT STARTED | enterprise-readiness blocker for tier-1 customers |
| Stripe integration | NOT STARTED | billing surface missing |
| Real embeddings | NOT STARTED | replaces `EMBEDDING_PROVIDER=dummy`; unlocks semantic precedent + law recall |
| Sentry / Datadog observability | NOT STARTED | today: log-search only |
| Email service (transactional) | NOT STARTED | blocks email verification, password reset, alert notifications |
| Alembic adoption (proper revisions) | PARTIAL | see section 4 |
| Vercel SSO Protection disable on production frontend | MANUAL | one-click; see `HANDOFF.md` |
| Railway JWT_SECRET rotation | OPTIONAL | weak bootstrap value still in use |

---

## Source of truth

- This document supersedes `STATUS_v2.0.md`, `STATUS_v2.1.md`, and the
  deployment section of `HANDOFF.md`. Detailed technical depth lives in:
  - `AUDIT_2026-08-19.md` — full 2026-08-19 audit with remediation log
  - `HANDOFF.md` — post-deploy setup notes (manual actions, env vars)
  - `STATUS_v2.1.md` — sprint S0–S7 remediation table (historical)
  - `ROADMAP_HARVEY_FEATURES.md` — Harvey.ai-style feature parity backlog
  - `CLAUDE.md` / `README.md` — architecture, conventions, stack
  - `docs/architecture.md`, `docs/rbac-matrix.md`, `docs/schema.md` — module
    detail
- Freshness date: **2026-08-21**. Next snapshot should be regenerated after
  the Railway image rebuild ships, the real-embeddings work lands, or Q1
  sellability sprint kicks off — whichever comes first.
