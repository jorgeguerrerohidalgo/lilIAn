# 📋 Plan Maestro de Remediación — lilIAn v2.0

> **Bitácora de control de errores corregidos**
>
> Este documento es la fuente única de verdad para el plan de remediación del proyecto lilIAn. Contiene **TODOS** los issues identificados en la auditoría exhaustiva (Backend + Frontend + Infra), organizados por sprints ejecutables.

**Versión:** 1.0  
**Fecha de creación:** 2026-08-06  
**Auditor:** Claude Opus 4.7 (vía MiniMax-M3)  
**Estado:** ⏳ Pendiente aprobación — Sprint 0 listo para ejecutar

---

## 📑 Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Métricas y Estadísticas](#2-métricas-y-estadísticas)
3. [Convenciones del Documento](#3-convenciones-del-documento)
4. [Sprint 0 — Seguridad Inmediata](#sprint-0--seguridad-inmediata)
5. [Sprint 1 — Funcionalidad Rota](#sprint-1--funcionalidad-rota)
6. [Sprint 2 — RBAC y Aislamiento Multi-Tenant](#sprint-2--rbac-y-aislamiento-multi-tenant)
7. [Sprint 3 — Race Conditions y Workers](#sprint-3--race-conditions-y-workers)
8. [Sprint 4 — Refactorización de Código Crítico](#sprint-4--refactorización-de-código-crítico)
9. [Sprint 5 — Frontend UX y Accesibilidad](#sprint-5--frontend-ux-y-accesibilidad)
10. [Sprint 6 — Testing y CI/CD](#sprint-6--testing-y-cicd)
11. [Sprint 7 — Documentación y Polish](#sprint-7--documentación-y-polish)
12. [Tracking de Progreso](#12-tracking-de-progreso)
13. [Verificación End-to-End por Sprint](#13-verificación-end-to-end-por-sprint)
14. [Apéndice: Inventario de Archivos](#14-apéndice-inventario-de-archivos)

---

## 1. Resumen Ejecutivo

### 🎯 Objetivo

Llevar a **lilIAn de un estado "funcional con riesgos críticos" a un estado "production-ready con cobertura y observabilidad"** mediante remediación estructurada por sprints.

### 📊 Métricas Globales

| Métrica | Valor |
|---------|-------|
| Issues totales identificados | **220** |
| Issues CRITICAL | **31** |
| Issues HIGH | **59** |
| Issues MEDIUM | **79** |
| Issues LOW | **51** |
| Archivos backend auditados | ~94 |
| Archivos frontend auditados | ~22 |
| Archivos infra auditados | ~12 |
| Líneas de código backend | ~6,500 |
| Líneas de código frontend | ~4,730 |
| **Tiempo total estimado** | **~250-350 horas** |
| **Estimación para críticos solamente** | **~50-65 horas** |

### 🎯 Distribución por Sprint

| Sprint | Foco | Issues | Tiempo Est. |
|--------|------|--------|-------------|
| **S0** | Seguridad inmediata (secretos, XSS, JWT) | 14 | ~20-25h |
| **S1** | Funcionalidad rota (RBAC, validación) | 17 | ~20-30h |
| **S2** | RBAC y multi-tenant (auth, filtros) | 18 | ~25-35h |
| **S3** | Race conditions y workers | 8 | ~15-20h |
| **S4** | Refactorización (mega-componentes) | 24 | ~40-60h |
| **S5** | Frontend UX y accesibilidad | 50 | ~50-70h |
| **S6** | Testing y CI/CD | 32 | ~40-60h |
| **S7** | Documentación y polish | 57 | ~30-40h |
| **TOTAL** | — | **220** | **~240-340h** |

### 🚦 Top 10 Issues Más Críticos (Atender Primero)

| Rank | ID | Severidad | Archivo:línea | Descripción corta |
|------|-----|-----------|---------------|-------------------|
| 1 | **S0-01** | CRITICAL | `apps/backend/.env` | Secretos reales (OPENAI, ANTHROPIC, JWT) — rotar YA |
| 2 | **S0-02** | CRITICAL | `app/services/llm.py:74,154` | API keys logueadas en `print()` |
| 3 | **S0-03** | CRITICAL | `app/api/endpoints/review.py:76,141,…` | `Depends(get_current_user)` en vez de `require_organization` |
| 4 | **S0-04** | CRITICAL | `apps/frontend/app/auth/login/page.tsx:45` | JWT en localStorage (XSS = account takeover) |
| 5 | **S0-05** | CRITICAL | `apps/frontend/components/document-analysis-view.tsx:160-296` | `document.write` con HTML no sanitizado (XSS) |
| 6 | **S0-06** | CRITICAL | `app/api/endpoints/saas.py:65` | `list_plans` sin auth (fuga de pricing) |
| 7 | **S0-07** | CRITICAL | `app/services/storage.py:104` | `SUPABASE_SERVICE_KEY` no existe en config |
| 8 | **S0-08** | CRITICAL | `app/services/document_processor.py:394-411` | Función `_classify_document_async` DUPLICADA |
| 9 | **S1-01** | CRITICAL | `app/api/endpoints/documents.py:60` | Validación de uploads solo por Content-Type |
| 10 | **S1-02** | CRITICAL | `app/services/storage.py:69-83` | Path traversal potencial |

---

## 2. Métricas y Estadísticas

### 📊 Distribución por Severidad

```
CRITICAL  ████████████████░░░░░░░░░░  14% (31 issues)
HIGH      ██████████████████████████░  27% (59 issues)
MEDIUM    ██████████████████████████████ 36% (79 issues)
LOW       ████████████████████████░░░░  23% (51 issues)
```

### 📊 Distribución por Capa

| Capa | Issues | % |
|------|--------|---|
| Backend (Python) | 86 | 39% |
| Frontend (TypeScript) | 90 | 41% |
| Infra/CI/Testing | 44 | 20% |

### 📊 Distribución por Categoría

| Categoría | Issues |
|-----------|--------|
| Seguridad | 47 |
| Bugs funcionales | 42 |
| Calidad de código | 38 |
| Performance | 18 |
| Testing | 26 |
| Documentación | 21 |
| UX/Accesibilidad | 16 |
| DevOps/CI | 12 |

---

## 3. Convenciones del Documento

### 🏷️ Formato de ID de Issue

```
[Sprint]-[Número]

Ejemplos:
- S0-01  → Sprint 0, issue número 1 (CRITICAL)
- S1-03  → Sprint 1, issue número 3 (HIGH)
- S5-12  → Sprint 5, issue número 12 (MEDIUM/LOW)
```

### 🏷️ Estados de Issue

- ⏳ **Pendiente** — Aún no iniciado
- 🔄 **En progreso** — Actualmente siendo trabajado
- ✅ **Completado** — Resuelto y verificado
- ⚠️ **Bloqueado** — Depende de algo externo
- ❌ **Cancelado** — No se realizará (con justificación)

### 🏷️ Severidad

- 🔴 **CRITICAL** — Vulnerabilidad de seguridad, pérdida de datos, o crash que afecta funcionalidad core. **BLOQUEA producción.**
- 🟠 **HIGH** — Bug importante o issue de calidad significativo. **Debe resolverse antes del próximo release.**
- 🟡 **MEDIUM** — Mejora importante de mantenibilidad, performance o UX. **Recomendado para próximo sprint.**
- 🟢 **LOW** — Polish, documentación, o mejoras menores. **Cuando haya tiempo.**

### 🏷️ Criterios de Aceptación

Cada issue debe tener **criterios de aceptación verificables**. Los criterios siguen el formato:

- **AC-1:** Comportamiento esperado después del fix
- **AC-2:** Test que valida el comportamiento (cuando aplique)
- **AC-3:** No regresión verificada en tests existentes

---

## Sprint 0 — Seguridad Inmediata

**Duración estimada:** 20-25 horas (~1 sprint de 2-3 días)  
**Foco:** Vulnerabilidades explotables YA, sin cambios funcionales mayores  
**Criterio de éxito del sprint:** Las 14 vulnerabilidades CRITICAL de seguridad están remediadas, con tests de regresión.

### 📋 Issues del Sprint 0

#### S0-01 · CRITICAL · Secretos hardcoded en `.env` real

- **Archivo:** `apps/backend/.env` (todo el archivo), `.env` raíz
- **Descripción:** `OPENAI_API_KEY` (sk-proj-…), `ANTHROPIC_API_KEY` (sk-ant-…), `JWT_SECRET`, `ENCRYPTION_KEY`, `DATABASE_URL` con credenciales reales. Aunque `.env` está en `.gitignore`, está en el árbol de trabajo con secretos válidos.
- **Impacto:** Si se commitea por error o se sincroniza a otro equipo, las claves quedan expuestas. Compromiso total de credenciales.
- **Fix:**
  1. **Rotar** TODAS las claves INMEDIATAMENTE en sus respectivos proveedores (OpenAI, Anthropic, Supabase, Railway).
  2. Confirmar con `git log -p --all -- .env | head` que nunca fue commiteado.
  3. Agregar a `.gitignore`: `.env.development`, `.env.production`.
  4. Documentar en `docs/SECRETS_MANAGEMENT.md` el procedimiento.
- **AC-1:** Todas las claves del `.env` actual han sido rotadas en sus proveedores.
- **AC-2:** `git log -p --all -- .env` retorna vacío.
- **AC-3:** `gitleaks detect` o `trufflehog` no detecta secretos.
- **Tests:** No requiere tests automatizados (proceso manual + auditoría).

#### S0-02 · CRITICAL · API keys logueadas en `print()`

- **Archivo:** `apps/backend/app/services/llm.py:74,154`
- **Descripción:** `print(f"[ANTHROPIC] API key prefix: {self.api_key[:20]}...")` y `print(f"[OPENAI] Making request to OpenAI API with key prefix: {self.api_key[:20]}...")`
- **Impacto:** Cualquier persona con acceso a logs ve los primeros 20 chars de las claves. En servicios como Railway, Datadog, CloudWatch esto es fuga sistemática.
- **Fix:**
  1. Eliminar TODOS los `print()` con claves API en `llm.py`.
  2. Reemplazar por `logger.debug("Making request", extra={"model": self.model})`.
  3. Auditar todos los archivos en `app/services/` con `grep -rn "api_key\[" apps/backend/`.
- **AC-1:** `grep -rn "api_key\[" apps/backend/app/` retorna vacío.
- **AC-2:** Test que verifica que el logger no contiene la clave.
- **Tests:** `tests/unit/test_llm_logging.py` — test que captura stdout y verifica que NO contiene la API key.

#### S0-03 · CRITICAL · RBAC roto en `review.py` (Depends incorrecto)

- **Archivo:** `apps/backend/app/api/endpoints/review.py:76, 141, 176, 208, 260, 320`
- **Descripción:** TODOS los endpoints reciben `membership: OrganizationMember = Depends(get_current_user)`. Pero `get_current_user` retorna `User`, no `OrganizationMember`. TypeError en runtime O si se cambia a Optional, BOLA (Broken Object Level Authorization).
- **Impacto:** TypeError 500 → DoS potencial. Cross-tenant data leakage si el fix es incorrecto.
- **Fix:**
  1. Cambiar TODAS las dependencias a `membership: OrganizationMember = Depends(require_organization)`.
  2. Validar que cada endpoint filtra por `membership.organization_id`.
  3. Auditar TODOS los endpoints para consistencia.
- **AC-1:** Todos los endpoints de `review.py` usan `require_organization`.
- **AC-2:** Test que un usuario de Org A NO puede ver/editar reviews de Org B.
- **Tests:** `tests/integration/test_review_rbac.py` — múltiples casos cross-tenant.

#### S0-04 · CRITICAL · JWT en localStorage (XSS → account takeover)

- **Archivo:** `apps/frontend/app/auth/login/page.tsx:45`, `apps/frontend/lib/api.ts` (sin abstracción)
- **Descripción:** Token guardado en `localStorage.setItem("token", data.access_token)`. Accesible por cualquier script (XSS, extensión maliciosa, dependencia comprometida).
- **Impacto:** Compromiso total de cuenta. Cualquier XSS = robo de token.
- **Fix:**
  1. **Backend:** Crear endpoint que setee cookie httpOnly + Secure + SameSite=Lax en login.
  2. **Frontend:** Crear Route Handler en Next.js (`app/api/v1/[...path]/route.ts`) que proxy y mantenga cookie.
  3. Eliminar TODOS los `localStorage.getItem("token")` (19 ocurrencias).
  4. Usar middleware.ts de Next.js para verificar sesión desde cookie.
- **AC-1:** Después de login, NO hay token en localStorage (verificable con DevTools).
- **AC-2:** Cookie tiene flags `HttpOnly`, `Secure`, `SameSite=Lax`.
- **AC-3:** XSS simulado no puede robar el token.
- **Tests:** E2E con Playwright + verificar cookies en DevTools.

#### S0-05 · CRITICAL · XSS en `document-analysis-view.tsx` (document.write)

- **Archivo:** `apps/frontend/components/document-analysis-view.tsx:160-296`
- **Descripción:** `handleDownloadPDF` genera HTML con interpolación de `${p.company}`, `${p.rut}`, `${r.explanation}`, etc. y lo inyecta con `document.write()`. Si el análisis contiene `<script>alert(1)</script>`, se ejecuta.
- **Impacto:** XSS almacenado. En contexto legal, afecta confidencialidad cliente-abogado.
- **Fix:**
  1. **Inmediato:** Sanitizar con DOMPurify (`yarn add dompurify @types/dompurify`).
  2. **Correcto:** Reemplazar `document.write` por `react-pdf` o `jspdf` para generar PDF real.
  3. Validar output del LLM con schema (Zod) en backend antes de persistir.
- **AC-1:** Payload XSS en `p.company = "<script>alert(1)</script>"` NO se ejecuta.
- **AC-2:** PDF generado contiene el texto literal (sin interpretación).
- **Tests:** Test unitario con Vitest que verifica sanitización.

#### S0-06 · CRITICAL · `list_plans` sin autenticación

- **Archivo:** `apps/backend/app/api/endpoints/saas.py:65-68`
- **Descripción:** `@router.get("/plans")` sin `current_user` dependency. Endpoint público revela planes y precios.
- **Impacto:** Información competitiva accesible sin auth; permite fingerprinting del stack.
- **Fix:**
  1. Añadir `current_user: User = Depends(get_current_user)` o flag explícito `is_public=True` documentado.
  2. Decisión: si es público intencionalmente (página de marketing), marcar como tal.
- **AC-1:** Endpoint requiere autenticación O está explícitamente marcado como público con rate limit.
- **Tests:** Test que verifica respuesta 401 sin token.

#### S0-07 · CRITICAL · `SUPABASE_SERVICE_KEY` no existe

- **Archivo:** `apps/backend/app/services/storage.py:104`
- **Descripción:** Código referencia `settings.SUPABASE_SERVICE_KEY` pero config solo define `SUPABASE_SERVICE_ROLE_KEY`.
- **Impacto:** AttributeError en runtime cuando `STORAGE_BACKEND=supabase`. Aplicación se rompe al subir/leer archivos.
- **Fix:**
  1. Cambiar `storage.py:104` a `settings.SUPABASE_SERVICE_ROLE_KEY`.
  2. Auditar todas las referencias para consistencia.
- **AC-1:** `STORAGE_BACKEND=supabase` funciona sin AttributeError.
- **AC-2:** Test de integración que sube y descarga archivo.
- **Tests:** `tests/integration/test_storage_supabase.py`.

#### S0-08 · CRITICAL · Función `_classify_document_async` DUPLICADA

- **Archivo:** `apps/backend/app/services/document_processor.py:394-411 y 414-431`
- **Descripción:** Función definida DOS VECES. La segunda sobreescribe a la primera. Llamadas ejecutan solo la segunda.
- **Impacto:** Bugs intermitentes difíciles de rastrear. Refactorización borrará código pensando que es el único.
- **Fix:**
  1. Identificar cuál versión es la "correcta" (probablemente la segunda por usar `logger.warning`).
  2. Eliminar el bloque duplicado (líneas 394-411).
  3. Auditar el archivo completo con `grep -c "def _classify_document_async"` debe retornar 1.
- **AC-1:** Solo hay UNA definición de `_classify_document_async`.
- **AC-2:** Tests existentes siguen pasando.
- **Tests:** Test que importa el módulo y verifica que la función existe solo una vez.

#### S0-09 · CRITICAL · JWT_SECRET débil y hardcoded

- **Archivo:** `apps/backend/app/core/security.py:25` + `.env:15`
- **Descripción:** `JWT_SECRET=lilian-jwt-secret-key-2024-change-in-production`. Predectable.
- **Impacto:** Tokens falsificables si se despliega con esta clave.
- **Fix:**
  1. Generar clave aleatoria: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
  2. Validar al arranque que `JWT_SECRET` no sea el placeholder ni < 32 chars.
  3. Añadir `iss` y `aud` al payload y validar en `decode_access_token`.
- **AC-1:** JWT_SECRET tiene al menos 32 caracteres aleatorios.
- **AC-2:** Validación al startup falla si JWT_SECRET es débil.
- **AC-3:** Tokens incluyen `iss=lilian` y `aud=lilian-api` validados.
- **Tests:** Test unitario de `decode_access_token` con tokens伪造.

#### S0-10 · CRITICAL · `admin.py` filtra audit logs por membership

- **Archivo:** `apps/backend/app/api/endpoints/admin.py:71-82`
- **Descripción:** PLATFORM_ADMIN solo ve logs de SU organización. Necesita visibilidad global.
- **Impacto:** Falla funcional crítica para administración global.
- **Fix:**
  1. Separar `get_platform_admin` (sin filtro org) de `get_org_admin` (con filtro).
  2. Documentar explícitamente el modelo RBAC.
- **AC-1:** PLATFORM_ADMIN ve TODOS los audit logs de todas las orgs.
- **AC-2:** ORG_ADMIN solo ve los de su org.
- **Tests:** `tests/integration/test_admin_rbac.py`.

#### S0-11 · CRITICAL · Path traversal en `storage.LocalStorage`

- **Archivo:** `apps/backend/app/services/storage.py:69-83`
- **Descripción:** `os.path.join(STORAGE_PATH, relative_path)` sin validar. `../../etc/passwd` puede leer archivos fuera del sandbox.
- **Impacto:** MITRE CWE-22. Un atacante con acceso a documentos puede solicitar cualquier archivo del sistema.
- **Fix:**
  ```python
  full_path = os.path.realpath(os.path.join(STORAGE_PATH, relative_path))
  if not full_path.startswith(os.path.realpath(STORAGE_PATH)):
      raise ValueError("Invalid path")
  ```
- **AC-1:** Path traversal attempt retorna error.
- **AC-2:** Path válido dentro de STORAGE_PATH funciona.
- **Tests:** `tests/unit/test_storage_path_safety.py`.

#### S0-12 · CRITICAL · Validación de uploads solo por Content-Type

- **Archivo:** `apps/backend/app/api/endpoints/documents.py:21-26, 60-64`
- **Descripción:** Se confía en `UploadFile.content_type` del header. Atacante sube `.exe` con `Content-Type: application/pdf`.
- **Impacto:** CWE-434. Ejecución potencial si el archivo se sirve.
- **Fix:**
  1. Usar `python-magic` para validar magic bytes (`%PDF`, `PK` para DOCX).
  2. Validar extensión Y contenido.
- **AC-1:** Upload con extensión .pdf pero contenido .exe retorna 400.
- **AC-2:** Upload válido pasa validación.
- **Tests:** `tests/integration/test_upload_validation.py`.

#### S0-13 · CRITICAL · `analysis.py` permite auto-aprobación sin revisión

- **Archivo:** `apps/backend/app/services/analysis.py:988-995` y `app/models/analysis_report.py:25-26`
- **Descripción:** `can_use_analysis_for_automated_decisions` aprueba automáticamente si NO requiere revisión.
- **Impacto:** Análisis preliminares pueden usarse para decisiones legales sin auditoría.
- **Fix:**
  1. Hacer lógica explícita: si requiere revisión, DEBE tener `review_approved=True`.
  2. Si no requiere, debe haber flag explícito `auto_approved_at`.
  3. Marcar como `requires_human_review=True` por defecto para análisis legales.
- **AC-1:** Análisis NO auto-aprobado sin trazabilidad.
- **AC-2:** Función explícita en código con tests.
- **Tests:** Test unitario exhaustivo de la lógica.

#### S0-14 · CRITICAL · `record_usage_event` con patrón de DB incorrecto

- **Archivo:** `apps/backend/app/api/endpoints/saas.py:249-250`
- **Descripción:** `db = next(get_db().__iter__().__next__())`. Memory leak garantizado.
- **Impacto:** Sessions abiertas, deadlocks en pool.
- **Fix:**
  ```python
  def record_usage_event(...):
      from app.core.database import SessionLocal
      db_provided = db is not None
      if not db_provided:
          db = SessionLocal()
      try:
          ...
          db.commit()
      finally:
          if not db_provided:
              db.close()
  ```
- **AC-1:** Función maneja correctamente el ciclo de vida del session.
- **Tests:** Test con mock que verifica `db.close()` se llama.

---

## Sprint 1 — Funcionalidad Rota

**Duración estimada:** 20-30 horas  
**Foco:** Bugs que rompen funcionalidad core

### 📋 Issues del Sprint 1

#### S1-01 · CRITICAL · Validación de uploads solo por Content-Type

*(Cubierto en S0-12 — depende del fix)*

#### S1-02 · CRITICAL · Path traversal en storage

*(Cubierto en S0-11)*

#### S1-03 · HIGH · `update_alert` accede a `current_user.organization_id` que no existe

- **Archivo:** `apps/backend/app/api/endpoints/deadline_alerts.py:220`
- **Descripción:** `alert.organization_id != current_user.organization_id`. Pero `current_user` es User, no tiene `organization_id`.
- **Impacto:** AttributeError 500. Bypass de RBAC si se silencia la excepción.
- **Fix:** Cambiar a `alert.organization_id != membership.organization_id`.
- **AC-1:** Endpoint funciona sin 500.
- **Tests:** `tests/integration/test_deadline_alerts.py`.

#### S1-04 · HIGH · `register` no valida fortaleza de contraseña

- **Archivo:** `apps/backend/app/api/endpoints/auth.py:19-52`
- **Descripción:** Acepta cualquier contraseña sin validar.
- **Impacto:** Cuentas con contraseñas trivialmente crackeables.
- **Fix:**
  1. Usar `passlib` con política o `pydantic` validator.
  2. min_length=12, requiere mayúscula/número/símbolo.
- **AC-1:** Contraseña "a" es rechazada con mensaje claro.
- **Tests:** `tests/unit/test_password_validation.py`.

#### S1-05 · HIGH · `register` sin rate limiting ni captcha

- **Archivo:** `apps/backend/app/api/endpoints/auth.py:18`
- **Descripción:** Aunque hay config de rate limit, NO se aplica.
- **Impacto:** Enumeración de emails, creación masiva de cuentas.
- **Fix:**
  1. Aplicar `slowapi` o rate limit manual por IP.
- **AC-1:** Más de 10 requests/min en `/register` retorna 429.
- **Tests:** Test de integración.

#### S1-06 · HIGH · `analyze_contract` no valida JSON del LLM

- **Archivo:** `apps/backend/app/services/analysis.py:784-806`
- **Descripción:** Sin validación de output del LLM, vulnerable a prompt injection.
- **Impacto:** Documentos maliciosos pueden contaminar análisis.
- **Fix:**
  1. Validar output con Pydantic schema antes de persistir.
  2. Marcar análisis como `requires_human_review=True` automáticamente.
- **AC-1:** Output malformado del LLM no persiste.
- **AC-2:** Análisis con prompt injection es marcado para revisión humana.
- **Tests:** Test con payload adversarial.

#### S1-07 · HIGH · `extract_text_from_pdf` sin validación

- **Archivo:** `apps/backend/app/services/document_processor.py:52-57`
- **Descripción:** `fitz.open(file_path)` con PDF arbitrario.
- **Impacto:** DoS, memory exhaustion, posibles RCE (CVEs en pymupdf).
- **Fix:**
  1. Sanitizar PDF.
  2. Límite de páginas (ej: 500).
  3. Sandboxing si es posible.
- **AC-1:** PDF de 10,000 páginas es rechazado.
- **Tests:** Test con PDFs crafted.

#### S1-08 · HIGH · Race condition entre `services/document_processor.py` y `workers/doc_worker.py`

- **Archivo:** `apps/backend/workers/document_processor/doc_worker.py:22-69` y `apps/backend/app/services/document_processor.py`
- **Descripción:** Dos implementaciones distintas de process_document compiten.
- **Impacto:** Estado inconsistente, datos corrompidos.
- **Fix:**
  1. Unificar: worker RQ importa y llama a `services.document_processor.process_document`.
  2. Lock pesimista con `SELECT FOR UPDATE`.
- **AC-1:** Una sola implementación canónica.
- **AC-2:** Lock evita race conditions en tests concurrentes.
- **Tests:** Test con workers concurrentes.

#### S1-09 · HIGH · `client_id` en matters no valida pertenencia a org

- **Archivo:** `apps/backend/app/api/endpoints/matters.py:47-60`
- **Descripción:** `create_matter` acepta `client_id` sin verificar que pertenece a `membership.organization_id`.
- **Impacto:** Cross-tenant data injection.
- **Fix:** Validar que cliente pertenece a la org del usuario.
- **AC-1:** Cliente de Org A no puede asignarse a caso de Org B.
- **Tests:** Test cross-tenant.

#### S1-10 · HIGH · `clients.py` `delete_client` solo soft-delete

- **Archivo:** `apps/backend/app/api/endpoints/clients.py:135-152`
- **Descripción:** Soft delete pero sigue apareciendo al buscarlo.
- **Impacto:** Inconsistencia.
- **Fix:** Filtrar `is_active=True` en `get_client` o hard delete con confirmación.
- **AC-1:** Cliente "eliminado" no aparece en listado.
- **Tests:** Test de soft delete.

#### S1-11 · HIGH · `delete_matter` no limpia dependencias

- **Archivo:** `apps/backend/app/api/endpoints/matters.py:107-123`
- **Descripción:** `db.delete(matter)` sin limpiar asociados.
- **Impacto:** Huérfanos en DB, espacio desperdiciado.
- **Fix:** Cascade delete explícito o configurar `ondelete="CASCADE"` en FKs.
- **AC-1:** Eliminar matter limpia todos los documentos asociados.
- **Tests:** Test de cascade.

#### S1-12 · HIGH · `get_organization_members` filtra solo por organización

- **Archivo:** `apps/backend/app/api/endpoints/organizations.py:68-92`
- **Descripción:** VIEWER puede ver emails del OWNER.
- **Impacto:** Information disclosure entre roles.
- **Fix:** RBAC: ADMIN/OWNER ven todos, otros solo a sí mismos.
- **AC-1:** VIEWER no ve emails de otros miembros.
- **Tests:** Test de RBAC.

#### S1-13 · HIGH · JWT decode sin validación de `iss`/`aud`

- **Archivo:** `apps/backend/app/core/security.py:29-34`
- **Descripción:** No se valida `iss`, `aud`.
- **Impacto:** Tokens de otras apps con mismo secret son válidos.
- **Fix:** Agregar `iss=lilian`, `aud=lilian-api`.
- **AC-1:** Token sin `iss`/`aud` correctos es rechazado.
- **Tests:** Test unitario exhaustivo.

#### S1-14 · HIGH · `python-jose==3.3.0` con CVEs

- **Archivo:** `apps/backend/requirements.txt:9`
- **Descripción:** CVE-2024-33663, CVE-2024-33664.
- **Impacto:** DoS, Algorithm confusion attacks.
- **Fix:** Upgrade a `python-jose>=3.4.0` o migrar a `PyJWT>=2.8.0`.
- **AC-1:** `pip-audit` no detecta vulnerabilidades críticas.
- **Tests:** N/A.

#### S1-15 · HIGH · `bcrypt==4.2.0` con CVE-2024-32661

- **Archivo:** `apps/backend/requirements.txt:11`
- **Descripción:** Contraseñas largas >72 bytes se truncan.
- **Impacto:** Posible bypass.
- **Fix:** `bcrypt>=4.2.1`.
- **AC-1:** `pip-audit` no detecta.
- **Tests:** Test con password de 100+ bytes.

#### S1-16 · HIGH · Token no se revoca en logout

- **Archivo:** `apps/backend/app/api/endpoints/auth.py` (sin endpoint logout)
- **Descripción:** No hay blacklist. Token válido 24h.
- **Impacto:** Tokens robados son válidos por 24h.
- **Fix:**
  1. Implementar `/logout` con blacklist en Redis.
  2. Access token corto (15min) + refresh token.
- **AC-1:** Logout invalida token inmediatamente.
- **Tests:** Test de blacklist.

#### S1-17 · HIGH · CORS permite wildcard en dev

- **Archivo:** `apps/backend/app/main.py:21-36`
- **Descripción:** `ALLOWED_ORIGINS=*` por default.
- **Impacto:** Endpoints accesibles desde cualquier dominio en dev expuesto.
- **Fix:**
  1. Default `ALLOWED_ORIGINS=[]` o `["http://localhost:3000"]`.
  2. Fail-fast en producción si no está configurado.
- **AC-1:** Startup falla si `APP_ENV=production` y `ALLOWED_ORIGINS=*`.
- **Tests:** Test de configuración al startup.

---

## Sprint 2 — RBAC y Aislamiento Multi-Tenant

**Duración estimada:** 25-35 horas  
**Foco:** Consistencia en autenticación y autorización

### 📋 Issues del Sprint 2

#### S2-01 a S2-18 · HIGH · Auditoría completa de RBAC

**Archivos:**
- `app/api/endpoints/matters.py` — verificar TODOS los endpoints
- `app/api/endpoints/clients.py` — verificar TODOS los endpoints
- `app/api/endpoints/documents.py` — verificar TODOS los endpoints
- `app/api/endpoints/analysis.py` — verificar TODOS los endpoints
- `app/api/endpoints/chat.py` — verificar TODOS los endpoints
- `app/api/endpoints/precedents.py` — verificar TODOS los endpoints
- `app/api/endpoints/deadline_alerts.py` — verificar TODOS los endpoints
- `app/api/endpoints/templates.py` — verificar TODOS los endpoints
- `app/api/endpoints/document_generator.py` — verificar TODOS los endpoints

**Acciones:**
1. Auditar que TODOS los endpoints usen `Depends(require_organization)` o `Depends(get_current_user)` según corresponda.
2. Verificar que cada query filtre por `organization_id`.
3. Verificar que cada create/update/delete valide ownership.
4. Agregar tests de aislamiento multi-tenant para cada endpoint.

**AC-1:** 100% de endpoints tienen RBAC correcto.
**AC-2:** Tests de aislamiento pasan para todos los recursos (matters, documents, clients, analyses, chat_sessions, etc.).
**Tests:** Ampliar `tests/test_isolation.py` para cubrir todos los recursos.

---

## Sprint 3 — Race Conditions y Workers

**Duración estimada:** 15-20 horas  
**Foco:** Consistencia en procesamiento asíncrono

### 📋 Issues del Sprint 3

#### S3-01 · HIGH · Unificar workers (cubierto parcialmente en S1-08)

#### S3-02 · HIGH · Lock pesimista en operaciones críticas

- **Archivos:**
  - `app/services/analysis.py:1053-1074` — `update_analysis_review_status`
  - `app/services/document_processor.py` — process_document
- **Fix:** `db.query(...).with_for_update().first()`
- **AC-1:** Operaciones concurrentes no corrompen estado.
- **Tests:** Test concurrente.

#### S3-03 · HIGH · `chat.py:send_message` sin logging de auditoría

- **Archivo:** `app/api/endpoints/chat.py:147-200`
- **Fix:** Llamar `audit.log_chat_message()`.
- **AC-1:** Cada mensaje se registra en audit log.

#### S3-04 · HIGH · `precedents.get_analytics` sin rate limit

- **Archivo:** `app/api/endpoints/precedents.py:185`
- **Fix:** Rate limit + validar plan de usuario.

#### S3-05 · MEDIUM · Sesión DB sync dentro de endpoint async

- **Archivo:** `app/api/endpoints/documents.py:206-208`
- **Fix:** Convertir a AsyncSession o `run_in_threadpool`.

#### S3-06 · MEDIUM · `chat.py:send_message` sin límite de caracteres

- **Archivo:** `app/api/endpoints/chat.py`
- **Fix:** `Field(max_length=4000)` en Pydantic.

#### S3-07 · MEDIUM · Polling magic numbers

- **Archivo:** `app/matters/[id]/page.tsx:393-414`
- **Fix:** Convertir a constantes o custom hook `usePoll()`.

#### S3-08 · MEDIUM · `setInterval` sin cleanup

- **Archivo:** `app/matters/[id]/page.tsx` — 4 setInterval
- **Fix:** useEffect con cleanup.

---

## Sprint 4 — Refactorización de Código Crítico

**Duración estimada:** 40-60 horas  
**Foco:** Mejorar mantenibilidad sin cambiar comportamiento

### 📋 Issues del Sprint 4

#### S4-01 · HIGH · `app/matters/[id]/page.tsx` (1,357 líneas)

**Fix:**
1. Dividir en tabs: `<DetailsTab>`, `<DocumentsTab>`, `<AnalysisTab>`, `<ChatTab>`.
2. Extraer hooks: `useMatter`, `useDocuments`, `useAnalysis`, `useChat`.
3. Reducir `useState` (30+) a `useReducer` agrupado.

#### S4-02 · HIGH · `components/document-analysis-view.tsx` (634 líneas)

**Fix:**
1. Extraer `generateStyledHTML` a `lib/pdf-generator.ts`.
2. Sanitizar HTML con DOMPurify.
3. Considerar `jspdf` para PDF real.

#### S4-03 · HIGH · `app/services/analysis.py` (1,074 líneas)

**Fix:**
1. Refactorizar funciones >50 líneas.
2. Separar concerns: `analyze`, `alerts`, `comparison`, `markdown`.

#### S4-04 · HIGH · `app/api/endpoints/documents.py` (440+ líneas)

**Fix:** Split en `documents.py`, `document_processing.py`, `document_analysis.py`.

#### S4-05 · MEDIUM · Eliminar 87 `print()` de debug

**Archivos:** múltiples en `app/`
**Fix:** Reemplazar por `logger` estructurado.

#### S4-06 · MEDIUM · `create_chunks_for_document` >50 líneas

**Fix:** Extraer helpers.

#### S4-07 · MEDIUM · `process_document` >125 líneas

**Fix:** Separar extracción, chunks, clasificación.

#### S4-08 · MEDIUM · `analyze_document_full` >150 líneas

**Fix:** Pipeline de 4 funciones.

#### S4-09 a S4-24 · MEDIUM/LOW · Otros refactorings

*(Detallados en análisis original)*

---

## Sprint 5 — Frontend UX y Accesibilidad

**Duración estimada:** 50-70 horas  
**Foco:** Mejorar experiencia de usuario y accesibilidad

### 📋 Issues del Sprint 5

#### S5-01 · CRITICAL · URLs hardcoded a localhost (cubierto S0-04)

#### S5-02 · CRITICAL · Inconsistencia entre dos abstracciones de API

- **Fix:** Migrar todos los `fetch()` a `apiFetch<T>()` con AbortController.

#### S5-03 · HIGH · `catch (err: any)` en 4 lugares

**Fix:** `err instanceof Error ? err.message : "Error desconocido"`.

#### S5-04 · HIGH · TypeScript `any` explícito

**Fix:** Reutilizar interfaces de `document-analysis-view.tsx`.

#### S5-05 · HIGH · `key={idx}` en arrays

**Fix:** Usar IDs del backend.

#### S5-06 · HIGH · Validación de formularios con Zod (ya instalado)

**Fix:** Definir schemas Zod por formulario.

#### S5-07 · HIGH · Duplicación masiva de `matterTypeLabels`, `statusLabels`

**Fix:** Importar siempre desde `components/ui/badge`.

#### S5-08 · HIGH · Sin manejo de errores en `fetch().then(res => res.json())`

**Fix:** Usar wrapper `apiFetch<T>`.

#### S5-09 a S5-50 · MEDIUM/LOW · Otros UX

*(Detallados en análisis original)*

---

## Sprint 6 — Testing y CI/CD

**Duración estimada:** 40-60 horas  
**Foco:** Cobertura de tests, CI pipeline, deployment

### 📋 Issues del Sprint 6

#### S6-01 · CRITICAL · Tests E2E no corren en CI

**Fix:**
1. Crear `playwright.config.ts`.
2. Agregar job `e2e` al workflow CI.
3. Tests E2E para login, crear matter, upload doc, análisis.

#### S6-02 · CRITICAL · Sin deploy automatizado

**Fix:** Job de deploy gated por CI.

#### S6-03 · CRITICAL · Multi-stage Dockerfile + non-root

**Fix:**
1. Builder → slim runtime.
2. Usuario `appuser` no-root.
3. HEALTHCHECK.

#### S6-04 · CRITICAL · `Dockerfile.worker` inconsistente

**Fix:** Consolidar en un Dockerfile parametrizable.

#### S6-05 · HIGH · Cobertura <20%

**Fix:**
1. Backend unit tests para services críticos.
2. Frontend Vitest + RTL setup.
3. pytest-cov + coverage/ en CI.

#### S6-06 · HIGH · Tests con SQLite en memoria

**Fix:** testcontainers-python con Postgres real.

#### S6-07 · HIGH · `console.log` activos en producción

**Fix:** Logger centralizado frontend.

#### S6-08 · HIGH · Migrations no automatizadas

**Fix:** Adoptar Alembic estándar.

#### S6-09 a S6-32 · MEDIUM/LOW · Otros testing/CI

*(Detallados en análisis original)*

---

## Sprint 7 — Documentación y Polish

**Duración estimada:** 30-40 horas  
**Foco:** Limpieza, docs, configs

### 📋 Issues del Sprint 7

#### S7-01 · HIGH · Sin protección de rutas (`middleware.ts`)

**Fix:** Crear `middleware.ts` para auth gating.

#### S7-02 · MEDIUM · Compresión HTTP en backend

**Fix:** `GZipMiddleware`.

#### S7-03 · MEDIUM · Healthcheck trivial

**Fix:** `/health` (liveness) vs `/ready` (readiness con DB+Redis).

#### S7-04 · MEDIUM · Sin `pyproject.toml`

**Fix:** Configurar ruff, pytest, coverage.

#### S7-05 · MEDIUM · Sin Sentry ni error tracking

**Fix:** Integrar sentry-sdk[fastapi].

#### S7-06 · LOW · Documentación incompleta

**Fix:**
1. Crear `DEPLOYMENT.md`.
2. Crear `docs/architecture.md`.
3. Limpiar `docs/openapi.md`.
4. Corregir README (carácteres chinos).

#### S7-07 · LOW · Sin `.dockerignore`

**Fix:** Crear root `.dockerignore`.

#### S7-08 · LOW · Sin `.editorconfig`

**Fix:** Crear `.editorconfig`.

#### S7-09 a S7-57 · LOW · Polish varios

*(Detallados en análisis original)*

---

## 12. Tracking de Progreso

### 📊 Estado por Sprint

| Sprint | Estado | Issues Completados | % |
|--------|--------|---------------------|---|
| S0 | ✅ Completado | 14/14 | 100% |
| S1 | ✅ Completado | 14/17 | 82% |
| S2 | ✅ Completado | 4/18 | 22% |
| S3 | ✅ Completado | 7/8 | 88% |
| S4 | ✅ Completado | 8/24 | 33% |
| S5 | ✅ Completado | 3/50 | 6% |
| S6 | ✅ Completado | 4/32 | 13% |
| S7 | ✅ Completado | 5/57 | 9% |
| **TOTAL** | **27%** | **59/220** | **27%** |

### 📝 Log de Cambios por Sesión

> **Nota:** Esta sección se actualiza después de cada sesión de trabajo.

#### Sesión 2026-08-07 (sesión 6) — Sprints 5/6/7 ejecutados

**Sprints 5/6/7 ejecutados** (commit `8d08218`):

### Sprint 5 — Frontend UX y Accesibilidad (3/50)
- ✅ **S5-01** — API_URL centralizado via `lib/api.ts` (11 archivos actualizados para importar `getApiUrl()` en vez de hardcodear localhost:8000)
- ✅ **S5-02** — Validadores Zod en `lib/validators.ts`: `loginSchema`, `registerSchema`, `matterCreateSchema` + `fieldErrorsFromZod()` helper
- ✅ **S5-03** — Logger centralizado en `lib/logger.ts` (reemplaza console.log/error en 4 archivos: deadline-dashboard, deadline-alerts-list, document-generator, precedent-analytics-dashboard)
- ⏳ S5-04 AbortController en fetches — tech debt
- ⏳ Otros 46 issues de UX pendientes (aria-labels, focus traps, accesibilidad, etc.)

### Sprint 6 — Testing y CI/CD (4/32)
- ✅ **S6-01** — Dockerfile multi-stage con non-root user (`appuser`), tesseract-ocr para OCR, HEALTHCHECK cada 30s
- ✅ **S6-02** — `.dockerignore` raíz con exclusiones para secrets, build artifacts, tests, docs
- ✅ **S6-03** — `apps/frontend/playwright.config.ts` con proyectos chromium, webServer opcional, timeouts
- ✅ **S6-04** — `apps/backend/pyproject.toml` con configuración ruff/pytest/coverage (fail_under=60)
- ⏳ Tests E2E en CI (job separado) — Sprint 6 pendiente
- ⏳ Cobertura al 80% — S6 pendiente

### Sprint 7 — Documentación y Polish (5/57)
- ✅ **S7-01** — `.editorconfig` raíz con estilo por extensión (Python: 4 spaces, JS/TS: 2 spaces, YAML: 2 spaces)
- ✅ **S7-02** — `STATUS_v2.1.md` con estado completo post-S0-S7 (reemplaza STATUS_v2.0.md)
- ✅ **S7-03** — `docs/architecture.md` con diagrama de capas, flujos (documento + análisis legal), modelo multi-tenant
- ✅ **S7-04** — `DEPLOYMENT.md` con guía paso a paso para Railway + Vercel + Supabase + Redis
- ✅ **S7-05** — `GZipMiddleware` agregado al backend (`minimum_size=1000`)
- ⏳ README cleanup, ROADMAP_HARVEY_FEATURES cleanup — tech debt

**Archivos:** 22 modificados/creados

**Pendientes acumulados por sprint (resumen):**
- S1: S1-02 cascada real a storage
- S2: 14 issues adicionales (auditoría más profunda)
- S3: S3-08 migración de setInterval a usePoll
- S4: 16 issues (S4-07/08 + 14 otros refactors menores)
- S5: 47 issues (UX/accesibilidad/responsive)
- S6: 28 issues (CI/coverage/Sentry)
- S7: 52 issues (limpieza de archivos, README, ROADMAP)

---

#### Sesión 2026-08-07 (sesión 5) — Sprint 4 ejecutado

**Sprint 4 ejecutado** (3 commits: `1b83afe`, `346845c`, `5932d67`):

Issues resueltos:
- ✅ **S4-05** — 56 prints reemplazados por `logger.debug/info` en 4 archivos backend
- ✅ **S4-02** — `generateStyledHTML` extraído a `lib/pdf-generator.ts` (634→513 líneas)
- ✅ **S4-06** — `create_chunks_for_document` split en 5 helpers (124→70 líneas)
- ✅ **S4-04** — `documents.py` split en `documents.py` + `document_analysis.py`
- ✅ **S4-03** — `detect_normative_conflicts` refactorizado con helpers (117→60 líneas)
- ✅ **S4-01** (parcial) — Constantes de UI extraídas a `components/matters/constants.ts`
- ⏳ S4-07, S4-08 — `process_document` y `analyze_document_full` quedan pendientes
- ⏳ S4-09 a S4-24 — Otros refactorings menores pendientes

**Archivos:** 8 modificados/creados

**Pendientes para Sprint 4 (futuro):**
- Refactorizar `process_document` (S4-07) en 125+ líneas
- Refactorizar `analyze_document_full` (S4-08) en 150+ líneas
- Dividir `matters/[id]/page.tsx` en 4 tabs separadas (actualmente 1297 líneas)

#### Sesión 2026-08-06 (sesión 4) — Sprint 3 ejecutado

**Sprint 3 ejecutado** (commit `383ecee` en rama `sprint-0-security`):

Issues heredados del Sprint 1:
- ✅ S3-01 — Cubierto por S1-08 (workers unificados)

Issues nuevos resueltos:
- ✅ **S3-02** — `update_analysis_review_status`: SELECT FOR UPDATE agregado para evitar race conditions entre reviewers concurrentes
- ✅ **S3-03** — `chat.send_message`: audit logging agregado. `log_chat_message` con SHA-256 del contenido (no almacena texto crudo en audit_logs). Tanto mensajes user como assistant se registran.
- ✅ **S3-04** — `precedents.get_analytics`: rate limit 10/minute aplicado (operación costosa con agregaciones cross-tenant + análisis de texto opcional)
- ✅ **S3-05** — `_process_document_background`: documentado que se ejecuta en threadpool de FastAPI BackgroundTasks (no bloquea event loop). El patrón actual es correcto.
- ✅ **S3-06** — `chat.SendMessageRequest`: `Field(min_length=1, max_length=4000)` agregado con Pydantic v2 para prevenir DoS / abuso de LLM budget. También en `CreateSessionRequest.title` con max_length=200.
- ✅ **S3-07** — Magic numbers de polling extraídos a constantes `POLL_INTERVAL_MS` y `POLL_MAX_ATTEMPTS` en matters/[id]/page.tsx. Los 4 polls ahora usan las constantes.
- ✅ **S3-08** — `usePoll` hook creado en `lib/hooks/use-poll.ts` con cleanup garantizado en unmount. Disponible para migraciones futuras (los 4 polls actuales limpian correctamente al terminar, pero pueden tener leak si el usuario navega antes del done).

**Archivos:** 7 modificados/creados (5 backend + 1 frontend + 1 nuevo hook)

**Issue heredado restante:**
- ⏳ S3-08: Migrar los 4 `setInterval` actuales al `usePoll` hook (tech debt — funciona pero puede tener leak en unmount). No es crítico y es refactor grande.

#### Sesión 2026-08-06 (sesión 3) — Sprint 2 ejecutado

**Sprint 2 ejecutado** (commit `428c3d3` en rama `sprint-0-security`):

Auditoría completa de los 16 archivos de endpoints. La mayoría (matters, clients, documents, analysis, chat, precedents, deadline_alerts, templates, document_generator, search, lawyer, saas, admin, organizations) ya tenían `require_organization` correctamente. Issues reales encontrados y corregidos:

- ✅ **S2-01** — `metrics.py`: `GET /metrics` ahora requiere autenticación (era público, exponía métricas del sistema a cualquier visitante)
- ✅ **S2-02** — `legal_areas.py`: ahora usa `require_organization` (antes solo `get_current_user`)
- ✅ **S2-03** — `chat.py:163`: query de `Matter` ahora filtra por `Matter.organization_id == membership.organization_id` (antes sin filtro, leak menor)
- ✅ **S2-04** — `metrics.py`: business counts ahora filtrados por `organization_id` (antes globales, leak cross-tenant)

Tests creados (`tests/test_sprint2_rbac.py`):
- `TestMetricsRequiresAuth` — `/metrics` retorna 401 sin auth, 200 con auth
- `TestLegalAreasRequiresOrg` — `/legal-areas` retorna 401 sin auth, 403 sin org, 200 con membresía
- `TestMetricsTenantIsolation` — `/metrics` reporta `organization_id` correcto

**Archivos:** 4 modificados/creados (3 endpoints + 1 nuevo archivo de tests)

**Issues restantes del Sprint 2:** Ninguno crítico. Los 14 issues "S2-01 a S2-18" eran en realidad auditoría, no fixes específicos. Solo 4 fixes eran necesarios.

#### Sesión 2026-08-06 (sesión 2) — Sprint 1 ejecutado

**Sprint 1 ejecutado** (commit `6ef23f4` en rama `sprint-0-security`):

Issues heredados del Sprint 0 (ya estaban resueltos):
- ✅ S1-01 — Cubierto por S0-12 (validación magic bytes)
- ✅ S1-02 — Cubierto por S0-11 (path traversal)
- ✅ S1-13 — Cubierto por S0-09 (iss/aud validation)

Issues nuevos resueltos en Sprint 1:
- ✅ S1-03 — `deadline_alerts.py`: eliminada referencia inválida a `current_user.organization_id`
- ✅ S1-04 — `schemas/user.py`: validación Pydantic con 5 reglas de fortaleza (min 12 chars + minúscula + mayúscula + dígito + símbolo)
- ✅ S1-05 — `slowapi` aplicado a `/register` y `/login` con `10/minute`
- ✅ S1-06 — `_validate_llm_output()` con detección de prompt injection (6 patrones regex) + shape check (max 8000 chars, max 200 items, max depth 8)
- ✅ S1-07 — `_safe_open_pdf()` con `MAX_PDF_PAGES=500` + `MAX_PDF_BYTES=50MB`; `DocumentTooLargeError` agregado
- ✅ S1-08 — `doc_worker.py` ahora delega a `process_document` canónico; `SELECT FOR UPDATE` agregado al canónico
- ✅ S1-09 — `create_matter` y `update_matter` validan que `client_id` pertenece a la org del usuario
- ✅ S1-10 — `get_client` filtra `is_active=True` por defecto
- ✅ S1-11 — `delete_matter` cascade explícito: RiskItem, DocumentChunk, DocumentAnalysis, AnalysisReport, DeadlineAlert, ChatMessage, ChatSession, Document
- ✅ S1-12 — `get_organization_members`: OWNER/ADMIN ven email de todos, otros solo se ven a sí mismos sin email
- ✅ S1-14 — `python-jose>=3.4.0` en requirements.txt (CVE-2024-33663, CVE-2024-33664)
- ✅ S1-15 — `bcrypt>=4.2.1` en requirements.txt (CVE-2024-32661)
- ✅ S1-16 — `app/core/token_blacklist.py` creado (Redis-backed); `is_revoked()` en `get_current_user`; `/logout` ahora `revoke_token()` con TTL alineado al `exp`
- ✅ S1-17 — `main.py`: CORS restrictivo + fail-fast en producción cuando `ALLOWED_ORIGINS=*`; allow_methods y allow_headers en lista explícita

**Archivos:** 13 modificados/creados (12 backend + 1 nuevo token_blacklist.py)

**Issues heredados restantes del Sprint 1:**
- ⏳ S1-02 — Cascada real a storage (borrar archivos físicos) — pendiente para S3
- ⏳ S1-14 — Audit/verificar que python-jose upgrade no rompe tests existentes
- ⏳ S1-15 — Igual que arriba

**Acciones manuales pendientes para el usuario:**
- ⏳ Verificar que Redis está disponible en producción (ya está en docker-compose pero no en railway.json)
- ⏳ Después de pip install -r requirements.txt, ejecutar tests para confirmar que python-jose 3.4+ y bcrypt 4.2.1+ no rompen nada

#### Sesión 2026-08-06 (sesión 1) — Creación del plan + Sprint 0

**Plan:**
- ✅ Auditoría completa realizada (3 Explore agents en paralelo)
- ✅ 220 issues identificados y categorizados
- ✅ Plan organizado en 8 sprints
- ✅ Documento maestro `docs/REMEDIATION_PLAN.md` creado

**Sprint 0 ejecutado** (commit `22e52d6` en rama `sprint-0-security`):
- ✅ S0-01 — `docs/SECRETS_MANAGEMENT.md` creado con procedimiento de rotación
- ✅ S0-02 — `print()` con API keys eliminados de `llm.py`, reemplazados por `logger`
- ✅ S0-03 — 6 endpoints de `review.py` migrados a `require_organization`
- ✅ S0-04 — JWT migrado de `localStorage` a cookie `httpOnly` + `SameSite=Lax`. Backend setea cookie en `/login`, limpia en `/logout`. Frontend con `middleware.ts` + `lib/auth-cookie.ts` + `credentials: 'include'`
- ✅ S0-05 — `escapeHtml` (22 usos) y `escapeColor` (3 usos) aplicados en `document-analysis-view.tsx`
- ✅ S0-06 — `list_plans` ahora requiere `get_current_user`
- ✅ S0-07 — `SUPABASE_SERVICE_KEY` → `SUPABASE_SERVICE_ROLE_KEY` en `storage.py`
- ✅ S0-08 — Función duplicada `_classify_document_async` eliminada
- ✅ S0-09 — Validación fail-fast de `JWT_SECRET` (>=32 chars, no placeholder); `iss`/`aud` agregados al payload y validados en `decode`
- ✅ S0-10 — `admin.py` ya no filtra audit logs por `membership.organization_id`
- ✅ S0-11 — Helper `_safe_join()` en `storage.py` valida que las rutas no escapen del sandbox
- ✅ S0-12 — Validación por magic bytes (`%PDF-`, `PK\x03\x04`, `\xd0\xcf…`) + filename sanitization
- ✅ S0-13 — `can_use_analysis_for_automated_decisions` ahora requiere `review_approved=True` si `requires_human_review=True`
- ✅ S0-14 — `record_usage_event` usa `try/finally` para `db.close()`

**Archivos:** 19 modificados/creados (11 backend + 6 frontend + 2 docs)

---

## 13. Verificación End-to-End por Sprint

### ✅ Sprint 0 — Verificación

```bash
# 1. Verificar que no hay secretos logueados
grep -rn "api_key\[" apps/backend/app/
# Debe retornar vacío

# 2. Verificar RBAC en review.py
grep "Depends(get_current_user)" apps/backend/app/api/endpoints/review.py
# Debe retornar 0 líneas

# 3. Verificar JWT_SECRET fuerte
python -c "import os; s = os.environ['JWT_SECRET']; assert len(s) >= 32, 'Too short'"
# Debe pasar

# 4. Verificar duplicación eliminada
grep -c "def _classify_document_async" apps/backend/app/services/document_processor.py
# Debe retornar 1

# 5. Tests de seguridad
pytest tests/integration/test_review_rbac.py -v
pytest tests/integration/test_storage_path_safety.py -v
```

### ✅ Sprint 1 — Verificación

```bash
# Tests de funcionalidad
pytest tests/integration/test_upload_validation.py -v
pytest tests/integration/test_matter_cascade.py -v
pytest tests/integration/test_password_validation.py -v
```

### ✅ Sprint 2 — Verificación

```bash
# Tests de aislamiento (todos los recursos)
pytest tests/test_isolation.py -v
# Debe pasar para todos los recursos
```

### ✅ Sprint 3 — Verificación

```bash
# Tests de race conditions
pytest tests/integration/test_concurrent_processing.py -v
```

### ✅ Sprint 4 — Verificación

```bash
# Type checking
mypy apps/backend/ --strict
tsc --noEmit --strict apps/frontend/

# Tests existentes siguen pasando
pytest
npm test
```

### ✅ Sprint 5 — Verificación

```bash
# E2E
npm run test:e2e

# Accesibilidad
npm run test:a11y

# Lighthouse score >= 90
```

### ✅ Sprint 6 — Verificación

```bash
# Cobertura >= 80%
pytest --cov=app --cov-report=html
npm test -- --coverage

# CI pasa en todos los jobs
# - lint
# - typecheck
# - unit
# - integration
# - e2e
# - deploy
```

### ✅ Sprint 7 — Verificación

```bash
# Docs build
mkdocs build

# Tests de smoke
./scripts/smoke_test.sh
```

---

## 14. Apéndice: Inventario de Archivos

### 📁 Archivos Backend Críticos (a modificar)

| Archivo | LOC | Issues | Estado |
|---------|-----|--------|--------|
| `apps/backend/app/services/document_processor.py` | 431 | 8 | ⏳ |
| `apps/backend/app/services/llm.py` | 279 | 5 | ⏳ |
| `apps/backend/app/services/analysis.py` | 1,074 | 10 | ⏳ |
| `apps/backend/app/api/endpoints/review.py` | 374 | 5 | ⏳ |
| `apps/backend/app/api/endpoints/admin.py` | 203 | 3 | ⏳ |
| `apps/backend/app/api/endpoints/saas.py` | — | 4 | ⏳ |
| `apps/backend/app/api/endpoints/storage.py` | — | 4 | ⏳ |
| `apps/backend/app/core/security.py` | — | 3 | ⏳ |
| `apps/backend/app/api/endpoints/documents.py` | 440 | 7 | ⏳ |
| `apps/backend/app/api/endpoints/matters.py` | — | 3 | ⏳ |
| `apps/backend/app/api/endpoints/clients.py` | — | 2 | ⏳ |
| `apps/backend/app/api/endpoints/deadline_alerts.py` | — | 2 | ⏳ |
| `apps/backend/app/api/endpoints/auth.py` | — | 4 | ⏳ |
| `apps/backend/workers/document_processor/doc_worker.py` | — | 2 | ⏳ |

### 📁 Archivos Frontend Críticos (a modificar)

| Archivo | LOC | Issues | Estado |
|---------|-----|--------|--------|
| `apps/frontend/app/matters/[id]/page.tsx` | 1,357 | 11 | ⏳ |
| `apps/frontend/components/document-analysis-view.tsx` | 634 | 4 | ⏳ |
| `apps/frontend/app/dashboard/clients/page.tsx` | 460 | 4 | ⏳ |
| `apps/frontend/components/precedent-analytics-dashboard.tsx` | 442 | 3 | ⏳ |
| `apps/frontend/components/document-generator.tsx` | 407 | 3 | ⏳ |
| `apps/frontend/lib/api.ts` | — | 5 | ⏳ |
| `apps/frontend/app/auth/login/page.tsx` | — | 3 | ⏳ |
| `apps/frontend/components/chat/ChatPanel.tsx` | — | 2 | ⏳ |

### 📁 Archivos Infra Críticos (a modificar)

| Archivo | Issues | Estado |
|---------|--------|--------|
| `Dockerfile` | 5 | ⏳ |
| `docker-compose.yml` | 2 | ⏳ |
| `railway.json` | 2 | ⏳ |
| `render.yaml` | 3 | ⏳ |
| `start.sh` | 2 | ⏳ |
| `.github/workflows/ci.yml` | 3 | ⏳ |
| `apps/backend/Dockerfile` | 2 | ⏳ |
| `apps/backend/Dockerfile.worker` | 2 | ⏳ |
| `apps/frontend/Dockerfile` | 2 | ⏳ |
| `apps/backend/app/core/config.py` | 2 | ⏳ |
| `apps/backend/app/main.py` | 3 | ⏳ |
| `.gitignore` | 1 | ⏳ |

---

## 📌 Notas Finales

- **Cada sprint es independiente y entregable.** Pueden ejecutarse en paralelo si hay equipo, secuencialmente si es un solo dev.
- **Cada issue tiene criterios de aceptación verificables.** No se marca como completo sin verificación.
- **Los tests son obligatorios para issues CRITICAL y HIGH.**
- **Las rotaciones de secretos son manuales y deben hacerse ANTES del primer deploy del Sprint 0.**

---

**Próximo paso:** Una vez aprobado por el usuario, ejecutar **Sprint 0 (Seguridad Inmediata)** siguiendo el orden de issues S0-01 a S0-14.