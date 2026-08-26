"use client";

/**
 * /dashboard/admin/users/[id] — Fase 3b (multi-tenant admin UI).
 *
 * Cross-tenant detail view of a single user. Calls the new
 * ``GET /api/v1/admin/users/{id}`` endpoint that the backend added in
 * the same sprint (returns profile + memberships in one payload).
 *
 * The page is a Client Component because every action here is a
 * stateful mutation:
 *
 *   - **Entrar como este usuario** → POST /admin/users/{id}/impersonate.
 *     The backend returns a short-lived JWT. The frontend sets it as
 *     ``lilian_auth_token`` via ``document.cookie`` (matching the same
 *     attributes the login route uses) and navigates to ``/dashboard``.
 *     A safer backend-served Set-Cookie path was considered but not
 *     shipped — see the post-implementation note for the trade-off.
 *   - **Suspender / Reactivar** → POST /admin/users/{id}/{suspend,
 *     reactivate}. Backend enforces PLATFORM_ADMIN server-side.
 *   - **Reset password** → POST /admin/users/{id}/reset-password.
 *     The backend already sends the password-reset email and returns
 *     ``reset_url`` so the admin can copy it as a fallback. We surface
 *     that URL in a modal with a one-click copy button.
 *
 * The "stop impersonating" CTA is intentionally not offered here: the
 * natural endpoint is to log out from the impersonated session
 * (``/auth/logout``), which the existing topbar logout button already
 * handles.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Badge, Button } from "@/components/ui";
import { AUTH_COOKIE_NAME } from "@/lib/auth-cookie";
import { toastFromError, useToast } from "@/lib/toast";

interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  status: string;
  email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
  organizations: Array<{
    organization_id: number;
    organization_name: string;
    role: string;
  }>;
}

export default function AdminUserDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const toast = useToast();
  const userId = Number.parseInt(params.id, 10);

  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  // Reset-password modal state
  const [resetUrl, setResetUrl] = useState<string | null>(null);
  const [resetExpiresAt, setResetExpiresAt] = useState<string | null>(null);
  const [resetModalOpen, setResetModalOpen] = useState(false);

  const load = useCallback(async () => {
    if (!Number.isFinite(userId)) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setForbidden(false);
    setNotFound(false);
    try {
      const res = await fetch(`/api/v1/admin/users/${userId}`, {
        credentials: "include",
      });
      if (res.status === 403) {
        setForbidden(true);
        setUser(null);
        return;
      }
      if (res.status === 404) {
        setNotFound(true);
        setUser(null);
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastFromError(toast, data.detail || `Error ${res.status}`);
        setUser(null);
        return;
      }
      const data = (await res.json()) as AdminUser;
      setUser(data);
    } catch (err) {
      toastFromError(toast, err);
    } finally {
      setLoading(false);
    }
  }, [userId, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleToggleStatus = async () => {
    if (!user) return;
    const isActive = user.status === "active";
    const action = isActive ? "suspend" : "reactivate";
    setBusy(`status-${action}`);
    try {
      const res = await fetch(`/api/v1/admin/users/${user.id}/${action}`, {
        method: "POST",
        credentials: "include",
      });
      if (res.status === 403) {
        toast.show({
          tone: "error",
          title: "Sin permisos",
          body: "No tienes permisos para modificar usuarios.",
        });
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastFromError(toast, data.detail || `Error ${res.status}`);
        return;
      }
      toast.show({
        tone: "success",
        title: isActive ? "Usuario suspendido" : "Usuario reactivado",
        body: `«${user.email}» ahora está ${isActive ? "suspendido" : "activo"}.`,
      });
      void load();
    } catch (err) {
      toastFromError(toast, err);
    } finally {
      setBusy(null);
    }
  };

  const handleImpersonate = async () => {
    if (!user) return;
    setBusy("impersonate");
    try {
      const res = await fetch(`/api/v1/admin/users/${user.id}/impersonate`, {
        method: "POST",
        credentials: "include",
      });
      if (res.status === 403) {
        toast.show({
          tone: "error",
          title: "Sin permisos",
          body: "No tienes permisos para impersonar usuarios.",
        });
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastFromError(toast, data.detail || `Error ${res.status}`);
        return;
      }
      const data = (await res.json()) as {
        access_token: string;
        expires_in: number;
      };

      // Same-origin write of the auth cookie. We mirror the attributes
      // used by the login BFF route (``Secure`` only on https) so the
      // subsequent ``/dashboard`` render reads the new token through
      // the catch-all.
      const isHttps = window.location.protocol === "https:";
      const cookie = [
        `${AUTH_COOKIE_NAME}=${data.access_token}`,
        `Path=/`,
        `Max-Age=${data.expires_in}`,
        `SameSite=Lax`,
        isHttps ? `Secure` : "",
      ]
        .filter(Boolean)
        .join("; ");
      document.cookie = cookie;

      toast.show({
        tone: "info",
        title: "Sesión iniciada como el usuario",
        body: `Ahora estás navegando como «${user.email}». Toda acción queda registrada en auditoría.`,
        durationMs: 8000,
      });

      // Force a full navigation so the dashboard server components
      // re-render with the impersonated session.
      window.location.href = "/dashboard?impersonated=1";
    } catch (err) {
      toastFromError(toast, err);
    } finally {
      setBusy(null);
    }
  };

  const handleResetPassword = async () => {
    if (!user) return;
    setBusy("reset");
    try {
      const res = await fetch(
        `/api/v1/admin/users/${user.id}/reset-password`,
        {
          method: "POST",
          credentials: "include",
        },
      );
      if (res.status === 403) {
        toast.show({
          tone: "error",
          title: "Sin permisos",
          body: "No tienes permisos para resetear contraseñas.",
        });
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastFromError(toast, data.detail || `Error ${res.status}`);
        return;
      }
      const data = (await res.json()) as {
        reset_url: string;
        expires_at: string;
      };
      setResetUrl(data.reset_url);
      setResetExpiresAt(data.expires_at);
      setResetModalOpen(true);
      toast.show({
        tone: "success",
        title: "Reset de contraseña enviado",
        body: `Se envió un correo a «${user.email}». Si el envío falló, puedes copiar el enlace manualmente.`,
      });
    } catch (err) {
      toastFromError(toast, err);
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <main id="main-content" className="mx-auto max-w-4xl px-6 py-8" lang="es">
        <div className="text-sm text-slate-500" role="status" aria-live="polite">
          Cargando usuario…
        </div>
      </main>
    );
  }

  if (forbidden) {
    return (
      <main id="main-content" className="mx-auto max-w-4xl px-6 py-8" lang="es">
        <header className="mb-6">
          <Link
            href="/dashboard/admin/organizations"
            className="text-sm text-blue hover:underline"
          >
            ← Volver a Organizaciones
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-slate-900">
            Detalle de usuario
          </h1>
        </header>
        <div
          role="alert"
          className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
        >
          No tienes permisos para ver esta página. Está reservada para
          administradores de plataforma.
        </div>
      </main>
    );
  }

  if (notFound || !user) {
    return (
      <main id="main-content" className="mx-auto max-w-4xl px-6 py-8" lang="es">
        <header className="mb-6">
          <Link
            href="/dashboard/admin/organizations"
            className="text-sm text-blue hover:underline"
          >
            ← Volver a Organizaciones
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-slate-900">
            Detalle de usuario
          </h1>
        </header>
        <div className="rounded-md border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No se encontró el usuario #{params.id}.
        </div>
      </main>
    );
  }

  const isActive = user.status === "active";

  return (
    <main
      id="main-content"
      className="mx-auto max-w-4xl px-6 py-8"
      lang="es"
    >
      <header className="mb-6">
        <Link
          href="/dashboard/admin/organizations"
          className="text-sm text-blue hover:underline"
        >
          ← Volver a Organizaciones
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              {user.full_name}
            </h1>
            <p className="mt-1 text-sm text-slate-600">{user.email}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              size="md"
              loading={busy === "impersonate"}
              disabled={!isActive || busy !== null}
              onClick={handleImpersonate}
              title={
                isActive
                  ? "Iniciar sesión como este usuario (1 hora, registrado en auditoría)"
                  : "No se puede impersonar a un usuario inactivo"
              }
            >
              Entrar como este usuario
            </Button>
            <Button
              variant="outline"
              size="md"
              loading={busy === "reset"}
              disabled={busy !== null}
              onClick={handleResetPassword}
            >
              Reset password
            </Button>
            <Button
              variant={isActive ? "danger" : "primary"}
              size="md"
              loading={busy === "status-suspend" || busy === "status-reactivate"}
              disabled={busy !== null}
              onClick={handleToggleStatus}
            >
              {isActive ? "Suspender" : "Reactivar"}
            </Button>
          </div>
        </div>
      </header>

      <section
        aria-label="Información del usuario"
        className="mb-6 rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Información
        </h2>
        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <InfoRow label="Email" value={user.email} />
          <InfoRow label="Nombre" value={user.full_name} />
          <InfoRow
            label="Teléfono"
            value={user.phone ?? <span className="text-slate-400">—</span>}
          />
          <InfoRow
            label="Estado"
            value={
              <Badge variant={isActive ? "green" : "amber"}>
                {isActive ? "Activo" : user.status}
              </Badge>
            }
          />
          <InfoRow
            label="Email verificado"
            value={
              <Badge variant={user.email_verified ? "blue" : "default"}>
                {user.email_verified ? "Verificado" : "Pendiente"}
              </Badge>
            }
          />
          <InfoRow label="Creado" value={formatDate(user.created_at)} />
          <InfoRow
            label="Último login"
            value={
              user.last_login_at ? (
                formatDate(user.last_login_at)
              ) : (
                <span className="text-slate-400">Nunca</span>
              )
            }
          />
        </dl>
      </section>

      <section
        aria-label="Organizaciones del usuario"
        className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Organizaciones
        </h2>
        {user.organizations.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">
            Este usuario no pertenece a ninguna organización.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-slate-100">
            {user.organizations.map((org) => (
              <li
                key={org.organization_id}
                className="flex items-center justify-between gap-3 py-3"
              >
                <div>
                  <Link
                    href={`/dashboard/admin/organizations/${org.organization_id}`}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    {org.organization_name}
                  </Link>
                  <p className="text-xs text-slate-500">#{org.organization_id}</p>
                </div>
                <Badge variant="default">{org.role}</Badge>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="mt-6 text-xs text-slate-500">
        Las acciones quedan registradas en la auditoría de plataforma.
      </footer>

      {resetModalOpen && resetUrl ? (
        <ResetPasswordModal
          resetUrl={resetUrl}
          expiresAt={resetExpiresAt}
          onClose={() => setResetModalOpen(false)}
        />
      ) : null}
    </main>
  );
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-slate-900">{value}</dd>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-CL", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function ResetPasswordModal({
  resetUrl,
  expiresAt,
  onClose,
}: {
  resetUrl: string;
  expiresAt: string | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(resetUrl);
      } else {
        // Fallback for non-secure contexts: select-and-copy via a
        // temporary textarea. ``document.execCommand`` is deprecated
        // but still works in every browser we target as a fallback.
        const textarea = document.createElement("textarea");
        textarea.value = resetUrl;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopied(true);
      toast.show({
        tone: "success",
        title: "Enlace copiado",
        body: "El enlace quedó en tu portapapeles.",
        durationMs: 4000,
      });
    } catch (err) {
      toastFromError(toast, err);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reset-modal-title"
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="reset-modal-title"
          className="text-lg font-semibold text-slate-900"
        >
          Enlace de reset generado
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Comparte este enlace con el usuario si el correo no llegó. Tiene
          una validez de 1 hora.
        </p>
        {expiresAt && (
          <p className="mt-1 text-xs text-slate-500">
            Expira: {formatDate(expiresAt)}
          </p>
        )}

        <div className="mt-4 flex gap-2">
          <input
            type="text"
            value={resetUrl}
            readOnly
            onFocus={(e) => e.currentTarget.select()}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-xs font-mono text-slate-700"
            aria-label="Enlace de reset de contraseña"
          />
          <Button variant="primary" size="md" onClick={handleCopy}>
            {copied ? "Copiado" : "Copiar"}
          </Button>
        </div>

        <div className="mt-6 flex justify-end">
          <Button variant="outline" size="md" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      </div>
    </div>
  );
}