# SaaS multi-tenant completo — admin / team / self-service

## Context

Lilian tiene **backend multi-tenant ya implementado** (roles `PLATFORM_ADMIN`, `OWNER`, `ADMIN`, `LAWYER`, `COMPANY_USER`, `CLIENT`, `VIEWER`; tabla `organizations` + `organization_member` + `invitation`; helpers `require_organization`, `get_platform_admin_membership`). Tiene además **Stripe billing end-to-end** y **página `/dashboard/billing`** funcional.

Pero la **UI no expone la mayoría de esa funcionalidad** y faltan endpoints críticos. Resultado: desde el punto de vista del usuario, Lilian parece una herramienta de un solo usuario cerrada, sin gestión de equipo ni de cuenta. **No es vendible así.**

Diagnóstico completo (verificado leyendo código):

**Backend — huecos críticos:**
- ❌ `POST /organizations/invitations/accept` **NO EXISTE** (mencionado en docstring, no implementado) → las invitaciones enviadas no se pueden consumir → **bug funcional que rompe el flujo de "invita a tu equipo"**
- ❌ `PATCH /auth/me` — usuario no puede editar nombre/teléfono
- ❌ `POST /auth/change-password`, `forgot-password`, `reset-password` — sin recuperación
- ❌ `DELETE` + `PATCH /organizations/me/members/{id}` — OWNER no puede remover ni cambiar rol
- ❌ `POST /admin/organizations` — PLATFORM_ADMIN no puede crear orgs para clientes
- ❌ `POST /admin/organizations/{org_id}/users` — PLATFORM_ADMIN no puede crear usuario admin de cliente
- ❌ `DELETE /organizations/me/invitations/{id}` — no se pueden revocar invitaciones

**Frontend — huecos críticos:**
- ❌ `/dashboard/team` (gestión de miembros) — **no existe**
- ❌ `/dashboard/invitations` (lista de invitaciones pendientes) — **no existe**
- ❌ `/dashboard/settings` (editar perfil, cambiar contraseña) — **no existe**
- ❌ `/auth/accept-invitation` (consumir link de invitación) — **no existe**
- ❌ `/auth/forgot-password`, `/auth/reset-password` — **no existe**
- ❌ Topbar sin dropdown de usuario (avatar no es clickeable)
- ❌ Sidebar sin items "Mi equipo" / "Configuración" / "Invitaciones"
- ❌ `/dashboard/admin/*` solo tiene audit-logs; no hay UI de PLATFORM_ADMIN para crear orgs/usuarios

**Outcome esperado tras el plan:**
1. El PLATFORM_ADMIN puede crear una organización cliente (con su primer OWNER) desde la UI
2. El OWNER puede invitar miembros, asignar roles, remover gente, ver invitaciones pendientes
3. Los usuarios invitados aceptan vía link del email y caen en la org correcta
4. Cualquier usuario puede editar su perfil y cambiar contraseña
5. Password recovery end-to-end (forgot → email con link → reset)
6. La suscripción se ve y se gestiona desde el sidebar (no escondida)
7. El sidebar refleja el rol: PLATFORM_ADMIN ve opciones admin, OWNER ve team, todos ven billing

---

## Plan de implementación — 5 fases

### Fase 0 — Critical bug fix (1 commit)

**Objetivo:** que las invitaciones que ya se envían se puedan consumir. Hoy `POST /organizations/me/invitations` crea el row pero nadie lo acepta.

**Backend:**
- `apps/backend/app/api/endpoints/organizations.py`: agregar `POST /organizations/invitations/accept`
  - Body: `InvitationAcceptRequest{token}`
  - Verifica: `token exists, status=PENDING, expires_at > now()`
  - Crea o reutiliza User (si email ya existe) — pero ojo: si email existe, no debe cambiar el `User.email_verified`; debe crear el `OrganizationMember` con el `role` de la invitación
  - Marca `Invitation.status=ACCEPTED, accepted_at=now(), accepted_by_user_id`
  - Devuelve `{email, organization_id, role, requires_verification: bool}` — si el usuario nuevo, le decimos al frontend que lo redirija a verify-email
  - Idempotente: si la invitación ya está ACCEPTED, devolver el mismo payload
- `apps/backend/app/schemas/invitation.py`: crear este schema (NO existe actualmente)

**Verificación:** crear invitación con token A, llamar accept con A → row updated, member creado. Repetir con A → mismo payload (idempotente).

---

### Fase 1 — Backend: gestión de equipo + admin (3-4 commits)

**Objetivo:** todos los endpoints que la UI de team/admin necesitan.

**1a — Membership management (apps/backend/app/api/endpoints/organizations.py):**
- `PATCH /organizations/me/members/{user_id}` — cambiar rol. OWNER puede cambiar a LAWYER/ADMIN/COMPANY_USER/VIEWER; **OWNER no puede promover ni degradar a sí mismo ni a otro OWNER** (prevenir lockout).
- `DELETE /organizations/me/members/{user_id}` — remover miembro. OWNER no puede removerse a sí mismo. ADMIN puede remover a no-OWNERs.
- `DELETE /organizations/me/invitations/{invitation_id}` — revocar invitación pendiente (solo PENDING).

**1b — Self-service (apps/backend/app/api/endpoints/auth.py):**
- `PATCH /auth/me` — body `UserUpdate{full_name?, phone?}`. NO permite cambiar email (eso requiere re-verificación, fuera de scope de esta fase).
- `POST /auth/change-password` — body `ChangePasswordRequest{current_password, new_password}`. Validar current con `verify_password`. Rate-limit.
- `POST /auth/forgot-password` — body `ForgotPasswordRequest{email}`. Genera `password_reset_token` (opaque, expira 1h), envía email con link a `/auth/reset-password?token=...`. **No revela si el email existe** (siempre 202 Accepted).
- `POST /auth/reset-password` — body `ResetPasswordRequest{token, new_password}`. Valida token + expira, hashea nueva contraseña, limpia token.
- `schemas/auth.py` (nuevo): estos schemas.
- `models/user.py`: agregar `password_reset_token`, `password_reset_expires_at` (nullable).
- `services/email.py`: agregar template `password_reset` (mismo patrón que `email_verification`).
- Migración `add_password_reset_fields.py` (idempotente).

**1c — PLATFORM_ADMIN onboarding (apps/backend/app/api/endpoints/admin.py):**
- `POST /admin/organizations` — body `CreateOrganizationForClientRequest{organization_name, owner_email, owner_full_name, plan_name}`. Crea org, crea User (email_verified=True porque es admin-created), crea OrganizationMember(OWNER), opcionalmente crea Subscription si `plan_name` no es "free". Envía email de bienvenida al nuevo OWNER.
- `POST /admin/users/{user_id}/reset-password` — fuerza reset password (genera link, envía email). Útil para soporte.
- `POST /admin/users/{user_id}/suspend` — setea `UserStatus.SUSPENDED`. Login falla.
- `POST /admin/users/{user_id}/reactivate`.
- `POST /admin/users/{user_id}/impersonate` — **login-as para soporte**. Genera un JWT corto (1h) firmado con un flag `impersonated_by=admin_id`, redirige a `/dashboard` con ese token en cookie. Toda acción del usuario impersonado se loggea con `action="admin.impersonated_action"` en `AuditLog`. UI: botón "Entrar como este usuario" en `/dashboard/admin/users/{id}` con confirmación explícita ("Vas a actuar en nombre del usuario. Se registrará en audit log.").

---

### Fase 2 — Frontend: team management + settings + accept-invitation (4-5 commits)

**Objetivo:** el OWNER/ADMIN puede gestionar su equipo desde la UI.

**2a — `/dashboard/team` (apps/frontend/app/dashboard/team/page.tsx):**
- Server Component que carga `/api/v1/organizations/me/members` y `/api/v1/organizations/me/invitations` en paralelo.
- Tabs: "Miembros" (default) / "Invitaciones pendientes".
- Tab Miembros: tabla con email / nombre / rol / fecha de ingreso / acciones (cambiar rol, remover). Solo OWNER/ADMIN ven acciones.
- Tab Invitaciones: tabla con email / rol invitado / invitado por / expira / acciones (revocar, reenviar).
- Botón "Invitar" abre `InviteTeamModal` (existente) en modo multi-invite (permitir varios emails seguidos).

**2b — `/dashboard/settings` (apps/frontend/app/dashboard/settings/page.tsx):**
- Form de edición de perfil (full_name, phone). Submit → `PATCH /auth/me`.
- Sección "Cambiar contraseña" con form separado. Submit → `POST /auth/change-password`.
- (En fase posterior) Sección "Eliminar cuenta" / "Sesiones activas" / "Notificaciones".

**2c — `/auth/accept-invitation` (apps/frontend/app/auth/accept-invitation/page.tsx):**
- Recibe `?token=...`, `POST /organizations/invitations/accept`.
- Tres estados: aceptando / aceptado (muestra org + rol, CTA a login) / error (link expirado / usado, CTA a register).
- Si el usuario ya estaba autenticado, después de aceptar lo redirige a `/dashboard` (su nueva org). Si no, lo manda a `/auth/login` con `?next=/dashboard` y mensaje "Fuiste agregado a {org_name}".

**2d — `/auth/forgot-password` + `/auth/reset-password` (apps/frontend/app/auth/{forgot-password,reset-password}/page.tsx):**
- `/auth/forgot-password`: input email, submit → "Si el email existe, recibirás un link".
- `/auth/reset-password`: recibe `?token=...`, form password + confirm, submit → success → login.

**2e — Sidebar/topbar (apps/frontend/components/layout/dashboard-layout.tsx):**
- Agregar items:
  - "Mi equipo" → `/dashboard/team` (visible para todos los roles con membresía)
  - "Configuración" → `/dashboard/settings`
- Topbar: hacer avatar clickeable con dropdown:
  - Mi perfil (link a `/dashboard/settings`)
  - Mi plan (link a `/dashboard/billing`)
  - Cerrar sesión

**Verificación:** E2E del flujo: OWNER invite → email llega → click → accept-invitation → registro/login → user ve team → cambia rol de un miembro → ve cambios reflejados en `/dashboard`.

---

### Fase 3 — Frontend: PLATFORM_ADMIN UI (2-3 commits)

**Objetivo:** PLATFORM_ADMIN puede onboardear clientes enterprise desde la UI.

**3a — `/dashboard/admin/organizations/new` (apps/frontend/app/dashboard/admin/organizations/new/page.tsx):**
- Form: nombre organización + email del primer OWNER + nombre del OWNER + plan (free / lawyer / law_firm / company / enterprise).
- Submit → `POST /admin/organizations`.
- Muestra resumen post-creación con link al portal del nuevo OWNER y link al login-as (si está implementado en fase 4).

**3b — `/dashboard/admin/organizations` (lista) — solo si no existe:**
- Tabla de todas las orgs (similar a `/dashboard/admin/audit-logs`). Acciones: ver detalle, suspend/activate, impersonar (fase 4).

**3c — `/dashboard/admin/users/{id}` (detalle):**
- Vista de usuario cross-tenant: mostrar membresías, suscripción, organizaciones donde está. Acciones: reset password, suspend/reactivate.

**Verificación:** PLATFORM_ADMIN entra a `/dashboard/admin/organizations/new` → crea una org para un cliente ficticio → recibe confirmación.

---

### Fase 4 — Frontend: password recovery + email polish (1-2 commits)

**Objetivo:** cerrar el ciclo de cuenta.

**4a — Links en login (`apps/frontend/app/auth/login/page.tsx`):**
- Agregar "¿Olvidaste tu contraseña?" debajo del form → link a `/auth/forgot-password`.

**4b — Email templates ya existen en `services/email.py`** (`password_reset` es nuevo en fase 1b, los demás ya están). Verificar que `email_verification` template use el link correcto a `/auth/accept-invitation` cuando aplica (en realidad no — es solo para verificación de cuenta propia, no de invitación. Las invitaciones tienen su propio flujo).

**4c — `/dashboard/billing` ya tiene CTAs "Cambiar de plan" y "Administrar suscripción"** — verificar que se ven bien desde el nuevo sidebar/topbar.

---

### Fase 5 — Polish (opcional, post-MVP)

- Decorator backend `@require_role(MemberRole.X)` (DRY)
- Tarea programada que expire invitaciones (`PENDING` → `EXPIRED`)
- AuditLog en mutaciones críticas (`suspend_organization`, `remove_member`, `accept_invitation`)
- `POST /saas/subscription/cancel` propio (sin depender de Stripe Portal)
- Drip email post-acceso (24h) usando el servicio ya implementado
- Enforcer RBAC transversal (la matriz en `docs/rbac-matrix.md` está documentada pero no enforced)

---

## Archivos críticos a modificar

**Backend (Fase 0-1):**
- `apps/backend/app/api/endpoints/organizations.py` — agregar 4 endpoints (accept-invitation, patch-member, delete-member, delete-invitation)
- `apps/backend/app/api/endpoints/auth.py` — agregar 4 endpoints (patch-me, change-password, forgot-password, reset-password)
- `apps/backend/app/api/endpoints/admin.py` — agregar 4 endpoints (create-org-for-client, reset-password-user, suspend-user, reactivate-user)
- `apps/backend/app/models/user.py` — agregar columnas password_reset_*
- `apps/backend/app/schemas/auth.py` (nuevo) — schemas de auth self-service
- `apps/backend/app/schemas/invitation.py` (nuevo) — schema accept-invitation
- `apps/backend/app/services/email.py` — agregar template `password_reset`
- `apps/backend/migrations/add_password_reset_fields.py` (nuevo) — migración idempotente

**Frontend (Fase 2-3):**
- `apps/frontend/app/dashboard/team/page.tsx` (nuevo)
- `apps/frontend/app/dashboard/settings/page.tsx` (nuevo)
- `apps/frontend/app/auth/accept-invitation/page.tsx` (nuevo)
- `apps/frontend/app/auth/forgot-password/page.tsx` (nuevo)
- `apps/frontend/app/auth/reset-password/page.tsx` (nuevo)
- `apps/frontend/app/dashboard/admin/organizations/new/page.tsx` (nuevo)
- `apps/frontend/app/dashboard/admin/organizations/page.tsx` (nuevo, si no existe)
- `apps/frontend/app/dashboard/admin/users/[id]/page.tsx` (nuevo)
- `apps/frontend/components/layout/dashboard-layout.tsx` — agregar items team/settings, hacer avatar clickeable
- `apps/frontend/components/modals/invite-team-modal.tsx` — soporte multi-invite
- `apps/frontend/app/auth/login/page.tsx` — agregar link "¿Olvidaste tu contraseña?"
- `apps/frontend/components/team/` (nuevo) — sub-componentes: `<MemberRow>`, `<InvitationRow>`, `<ChangeRoleSelect>`

---

## Verification end-to-end

Una vez deployadas las 5 fases, el flujo completo debe ser:

1. **PLATFORM_ADMIN** (`admin@lilian.cl`):
   - Login → ve `/dashboard/admin/audit-logs` + nuevo item "Organizaciones"
   - Va a `/dashboard/admin/organizations/new` → crea "Bufete Pérez & Asoc." con plan "law_firm", owner "perez@bufete.cl"
   - Verifica que el nuevo OWNER recibió email con link de bienvenida

2. **OWNER perez@bufete.cl** (nuevo, primer login):
   - Login con magic link del email (o password reset)
   - Va a `/dashboard/billing` → ve plan "law_firm" activo
   - Va a `/dashboard/team` → 0 miembros (solo él)
   - Click "Invitar" → invita "abogado1@bufete.cl" como LAWYER
   - "abogado1" recibe email → click → `/auth/accept-invitation` → completa registro/login → ve el caso demo del bufete

3. **abogado1** (LAWYER):
   - Sidebar muestra "Mi equipo" + "Configuración" + "Facturación"
   - Ve `/dashboard/team` pero sin acciones (es LAWYER, no OWNER/ADMIN)
   - Ve `/dashboard/settings` → puede cambiar su nombre y teléfono
   - Ve `/dashboard/billing` → ve plan y usage

4. **perez@bufete.cl**:
   - Ve "abogado1" en `/dashboard/team` con rol LAWYER
   - Le cambia el rol a ADMIN → abogado1 ahora ve acciones de admin
   - Ve la invitación ya no aparece (porque fue aceptada)

5. **Cualquier usuario**:
   - Click en avatar → dropdown con "Mi perfil" / "Mi plan" / "Cerrar sesión"
   - "Olvidaste contraseña?" desde login → email → reset → login funciona

---

## Estimación de esfuerzo

| Fase | Esfuerzo | Dependencias |
|---|---|---|
| 0 (accept-invitation backend) | 30 min | — |
| 1 (backend admin + team CRUD + self-service) | 3-4 h | 0 |
| 2 (frontend team + settings + accept-invitation + auth recovery) | 5-6 h | 1 |
| 3 (frontend PLATFORM_ADMIN org creation) | 2-3 h | 1 |
| 4 (polish + links + email verify) | 1-2 h | 2, 3 |
| 5 (polish post-MVP) | 4-8 h | todo |

**Para vender el producto:** Fases 0-4 son suficientes (~12-16 horas). Fase 5 puede esperar a tener clientes reales.
