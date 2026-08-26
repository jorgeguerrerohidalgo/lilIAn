/**
 * /dashboard/admin/organizations/new — Fase 3a (PLATFORM_ADMIN onboarding).
 *
 * PLATFORM_ADMIN entry point to onboard a new client organization
 * directly from the UI. The page is a Server Component that gates on
 * the ``PLATFORM_ADMIN`` role server-side (read from
 * ``GET /api/v1/auth/me``), then hands the form over to a Client
 * Component for the interactive submit flow.
 *
 * Auth gate
 * ---------
 * The backend rejects non-PLATFORM_ADMIN callers with 403 on the
 * actual onboarding endpoint (``POST /api/v1/admin/organizations``).
 * We mirror that check here so a non-admin who lands on this URL sees
 * a friendly message instead of the form silently failing. We do NOT
 * redirect — the user is shown the reason and a link back to the
 * dashboard, so support conversations don't have to chase hidden
 * redirects.
 *
 * Note: the catch-all BFF at ``app/api/v1/[...path]/route.ts`` is
 * same-origin from the server, so a ``fetch`` from a Server Component
 * travels without any CORS ceremony. The auth cookie is forwarded
 * verbatim to the backend (and re-emitted as ``Authorization: Bearer``
 * because the backend uses ``OAuth2PasswordBearer``).
 */

import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { NewOrganizationForm } from "./new-organization-form";

export const metadata: Metadata = {
  title: "Crear organización — lilIAn",
  description:
    "Onboarding manual de una organización cliente (PLATFORM_ADMIN).",
};

interface MeResponse {
  id: number;
  email: string;
  full_name: string;
  roles: string[];
}

async function fetchMe(): Promise<MeResponse | null> {
  // Build an absolute URL so the same-origin fetch works in both
  // server and node-runtime contexts. The catch-all BFF re-emits
  // the cookie as Bearer, so /me just works.
  const cookieStore = await cookies();
  const token = cookieStore.get("lilian_auth_token")?.value;
  if (!token) return null;

  const baseUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  try {
    const res = await fetch(`${baseUrl}/api/v1/auth/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as MeResponse;
  } catch {
    return null;
  }
}

export default async function NewOrganizationPage() {
  const me = await fetchMe();
  const isPlatformAdmin = !!me?.roles.includes("PLATFORM_ADMIN");

  if (!isPlatformAdmin) {
    return (
      <main
        id="main-content"
        className="mx-auto max-w-2xl px-6 py-12"
        lang="es"
      >
        <div
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50 p-6"
        >
          <h1 className="text-xl font-semibold text-amber-900">
            No tienes permisos para crear organizaciones
          </h1>
          <p className="mt-2 text-sm text-amber-800">
            Esta página está reservada para administradores de plataforma
            (PLATFORM_ADMIN). Si crees que deberías tener acceso, contacta al
            equipo de soporte.
          </p>
          {me ? (
            <p className="mt-2 text-xs text-amber-700">
              Sesión actual: {me.email} — roles:{" "}
              {me.roles.length > 0 ? me.roles.join(", ") : "(ninguno)"}
            </p>
          ) : (
            <p className="mt-2 text-xs text-amber-700">
              No se pudo identificar la sesión actual.
            </p>
          )}
          <div className="mt-4 flex gap-3">
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100"
            >
              Volver al dashboard
            </Link>
            <Link
              href="/dashboard/admin/audit-logs"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700"
            >
              Ver registros de auditoría
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return <NewOrganizationForm />;
}
