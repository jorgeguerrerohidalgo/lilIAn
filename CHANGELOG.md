# Changelog

Todos los cambios notables de lilIAn se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

Tipos de cambios:

- **Added** — funcionalidades nuevas
- **Changed** — cambios en funcionalidades existentes
- **Deprecated** — funcionalidades que se eliminaran proximamente
- **Removed** — funcionalidades eliminadas
- **Fixed** — correccion de bugs
- **Security** — cambios de seguridad (incluye remediaciones)

---

## [Unreleased]

### Added
- Documentacion principal renovada: README raiz, `apps/backend/README.md`, `apps/frontend/README.md`
- Archivo `LICENSE` (MIT)
- Este `CHANGELOG.md` siguiendo Keep a Changelog 1.1.0
- Mejoras de documentacion planificadas en Sprint 7 batch 1 (S7-09..18)

---

## [2.1.0] - 2026-08-14

Baseline consolidado de los Sprints 0 a 7. Cubre seguridad, refactorizacion, infraestructura, accesibilidad y caracteristicas estilo Harvey.ai.

### Sprint 0 — Auditoria inicial
- Auditoria de seguridad y arquitectura sobre la base v2.0

### Sprint 1 — Seguridad y resiliencia
- **Security**: prevencion de CORS wildcard (S1-17)
- **Security**: cascade storage para evitar duplicacion de archivos (S1-02)
- **Fixed**: logging estructurado en proveedores LLM (OpenAI / Anthropic)
- **Fixed**: reduccion de delays de retry de 5s a 1s para LLM y embeddings
- **Fixed**: eliminacion de `response_format` en flujo Anthropic (OpenAI-only)

### Sprint 2 — RBAC y aislamiento multi-tenant
- **Security**: auditoria RBAC y filtro `organization_id` en todos los endpoints (S2)
- **Added**: 11 tests de aislamiento cross-tenant
- **Fixed**: previene fuga de datos entre organizaciones

### Sprint 3 — Frontend hardening
- **Changed**: migracion de `setInterval` a hook `usePoll` (S3-08)
- **Changed**: patrones de fetching y refresh mas consistentes en UI

### Sprint 4 — Refactorizacion del pipeline RAG
- **Changed**: S4-07 `process_document` dividido en helpers enfocados (#24)
- **Changed**: S4-11 / S4-12 markdown/clause splitting
- **Changed**: S4-13/14/15 — template parser, validation flow, chunking pipeline
- **Added**: S4-16 busqueda hibrida con Reciprocal Rank Fusion
- **Added**: S4-17 review gate dispatcher
- **Changed**: S4-18/19/20 — analytics, chat, risk dashboard
- **Changed**: S4-21 `search_chunks_by_embedding` pipeline
- **Changed**: S4-22/23/24 — clause value, alerts summary, document extraction
- **Changed**: S4-07 a S4-10 refactors de funciones grandes

### Sprint 5 — Accesibilidad WCAG 2.1 AA
- **Added**: fieldset/legend, htmlFor explicito, skip-to-content, reduced-motion
- **Added**: accesibilidad en modales y loading states
- **Added**: `aria-current` + `aria-label` en navegacion
- **Added**: `role=alert` / `aria-live` en mensajes de error y exito
- **Added**: `aria-hidden` en 69 SVGs decorativos
- **Added**: `aria-busy` en boton submit de nuevo caso
- **Added**: quick wins, modales, semantica y regiones
- **Added**: chat accesible, tablist con flechas, charts, alerts
- **Added**: risk score disclosure, link semantico, search accesible

### Sprint 6 — Lint e infraestructura
- **Changed**: lint Python (ruff): 906 -> 0 errores
- **Added**: `pyproject.toml` centralizando configuracion de ruff, pytest, coverage
- **Added**: Dockerfiles para backend y worker
- **Added**: docker-compose para desarrollo local

### Sprint 7 — Documentacion y operacional (en curso)
- **Added**: README raiz profesional con badges, features, quickstart, arquitectura (S7-09..12)
- **Added**: READMEs por subproyecto: `apps/backend/README.md`, `apps/frontend/README.md` (S7-13..15)
- **Added**: `CHANGELOG.md` (S7-16)
- **Added**: archivo `LICENSE` (MIT) (S7-17)
- **Added**: badge de version, WCAG 2.1 AA, multi-tenant

---

## [2.0.0] - 2026-07-19

Release mayor de la plataforma lilIAn.

### Added
- Sistema RAG con busqueda hibrida (Reciprocal Rank Fusion)
- Workflow de revision de analisis (`draft` -> `approved` / `rejected`)
- Review gate para decisiones automatizadas que requieren aprobacion humana
- Citaciones navegables con `EvidenceBundle`
- Idempotencia en procesamiento de documentos
- Storage abstracto (Supabase Storage o filesystem local)
- Dataset golden para evaluacion del RAG
- `TenantContext` como dependencia inyectable de FastAPI
- Busqueda de precedentes legales
- Integracion de precedentes en analisis de casos
- Chat legal mejorado
- Deteccion de conflictos normativos
- Analisis de tendencias jurisprudenciales

### Security
- RBAC implementado en todos los endpoints (7 roles)
- Aislamiento multi-tenant completo
- Modelo `Review` para auditoria de decisiones automatizadas

### Changed
- RLS policies deshabilitadas (incompatibles con `auth.uid()`)
- Endpoints de debug removidos

### Fixed
- Secretos removidos de `docker-compose.yml`
- Estabilidad general del pipeline de procesamiento documental

---

## Tipos de version

- **MAJOR** (X.0.0): cambios incompatibles con la API o arquitectura
- **MINOR** (x.Y.0): nuevas funcionalidades compatibles hacia atras
- **PATCH** (x.y.Z): correcciones compatibles hacia atras

Los sprints autonomos no rompen la API y se acumulan en versiones `MINOR` hasta su estabilizacion.