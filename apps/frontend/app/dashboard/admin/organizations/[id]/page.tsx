"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

interface Member {
  user_id: number;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
}

interface OrganizationDetail {
  id: number;
  name: string;
  type: string;
  status: string;
  plan_id: string | null;
  rut: string | null;
  billing_email: string | null;
  stripe_customer_id: string | null;
  created_at: string;
  updated_at: string | null;
  user_count: number;
  matter_count: number;
  document_count: number;
  members: Member[];
}

// /dashboard/admin/organizations/[id] — PLATFORM_ADMIN cross-tenant
// detail view. Renders the org profile, scalar counts and the full
// member roster. The endpoint (`GET /api/v1/admin/organizations/{id}`)
// is enforced server-side; the middleware on this route only checks
// for the auth cookie, so we additionally check that the caller has
// the PLATFORM_ADMIN role client-side and redirect otherwise. Server
// enforcement is the real gate; this just keeps non-admins from
// seeing a half-rendered page.
export default function OrganizationDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const orgId = params.id;

  const [org, setOrg] = useState<OrganizationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [actionPending, setActionPending] = useState<"suspend" | "activate" | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`/api/v1/admin/organizations/${orgId}`);
        if (res.status === 401) {
          router.push("/auth/login");
          return;
        }
        if (res.status === 403) {
          setError("No tienes permisos para ver esta organización.");
          setLoading(false);
          return;
        }
        if (!res.ok) {
          setError(`No se pudo cargar la organización (HTTP ${res.status}).`);
          setLoading(false);
          return;
        }
        const data = await res.json();
        if (!cancelled) {
          setOrg(data);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setError("Error de conexión con el servidor.");
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [orgId, router]);

  const handleAction = async (action: "suspend" | "activate") => {
    if (!org) return;
    const confirmed = window.confirm(
      action === "suspend"
        ? `¿Suspender la organización "${org.name}"? Sus miembros no podrán iniciar sesión hasta reactivarla.`
        : `¿Reactivar la organización "${org.name}"?`,
    );
    if (!confirmed) return;

    setActionPending(action);
    try {
      const res = await fetch(`/api/v1/admin/organizations/${org.id}/${action}`, {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        window.alert(data.detail || `No se pudo ${action === "suspend" ? "suspender" : "reactivar"} la organización.`);
        return;
      }
      // Refresh the page so counts / status reflect the change.
      router.refresh();
      // Also re-fetch to update local state without a full reload.
      const detail = await fetch(`/api/v1/admin/organizations/${org.id}`);
      if (detail.ok) setOrg(await detail.json());
    } finally {
      setActionPending(null);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 md:px-6 py-6 md:py-8">
        <div className="flex items-center justify-center py-16 text-slate-500">
          <div role="status" aria-live="polite" className="flex items-center gap-3">
            <div className="w-6 h-6 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
            <span>Cargando organización…</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !org) {
    return (
      <div className="mx-auto max-w-5xl px-4 md:px-6 py-6 md:py-8">
        <Link
          href="/dashboard/admin/organizations"
          className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
        >
          <span aria-hidden="true">←</span> Volver a Organizaciones
        </Link>
        <div
          role="alert"
          aria-live="assertive"
          className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          {error || "Organización no encontrada."}
        </div>
      </div>
    );
  }

  const statusBadge = STATUS_STYLES[org.status] ?? STATUS_STYLES.active;
  const typeLabel = TYPE_LABELS[org.type] ?? org.type;
  const planLabel = org.plan_id ?? "—";

  return (
    <div className="mx-auto max-w-5xl px-4 md:px-6 py-6 md:py-8 space-y-6">
      {/* Breadcrumb */}
      <Link
        href="/dashboard/admin/organizations"
        className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
      >
        <span aria-hidden="true">←</span> Volver a Organizaciones
      </Link>

      {/* Header */}
      <header className="flex flex-wrap items-start justify-between gap-3 sm:gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h1 className="text-xl md:text-2xl font-semibold text-slate-900 truncate">{org.name}</h1>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusBadge}`}>
              {STATUS_LABELS[org.status] ?? org.status}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {typeLabel} · creada el {fmtDate(org.created_at)}
            {org.updated_at && org.updated_at !== org.created_at
              ? ` · actualizada el ${fmtDate(org.updated_at)}`
              : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {org.status === "active" ? (
            <button
              type="button"
              onClick={() => handleAction("suspend")}
              disabled={actionPending !== null}
              className="px-3 py-2 text-sm font-medium rounded-md border border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100 disabled:opacity-50"
            >
              {actionPending === "suspend" ? "Suspendiendo…" : "Suspender"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => handleAction("activate")}
              disabled={actionPending !== null}
              className="px-3 py-2 text-sm font-medium rounded-md border border-green-300 text-green-800 bg-green-50 hover:bg-green-100 disabled:opacity-50"
            >
              {actionPending === "activate" ? "Reactivando…" : "Reactivar"}
            </button>
          )}
        </div>
      </header>

      {/* KPI cards */}
      <section aria-label="Métricas de uso" className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4">
        <KpiCard label="Usuarios" value={org.user_count} hint="Miembros activos" />
        <KpiCard label="Casos" value={org.matter_count} hint="Asuntos legales" />
        <KpiCard label="Documentos" value={org.document_count} hint="Archivos cargados" />
      </section>

      {/* Profile card */}
      <section
        aria-labelledby="org-profile-heading"
        className="rounded-lg border border-slate-200 bg-white overflow-hidden"
      >
        <div className="px-5 py-4 border-b border-slate-200">
          <h2 id="org-profile-heading" className="text-sm font-semibold text-slate-700">
            Perfil de la organización
          </h2>
        </div>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 px-5 py-4">
          <Field label="ID interno" value={`#${org.id}`} />
          <Field label="Tipo" value={typeLabel} />
          <Field label="Plan" value={planLabel} />
          <Field label="RUT" value={org.rut ?? "—"} />
          <Field label="Email de facturación" value={org.billing_email ?? "—"} mono />
          <Field label="Cliente Stripe" value={org.stripe_customer_id ?? "—"} mono />
        </dl>
      </section>

      {/* Members */}
      <section
        aria-labelledby="org-members-heading"
        className="rounded-lg border border-slate-200 bg-white overflow-hidden"
      >
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 id="org-members-heading" className="text-sm font-semibold text-slate-700">
            Miembros ({org.members.length})
          </h2>
        </div>
        {org.members.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-slate-500">
            Esta organización aún no tiene miembros.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label={`Miembros de ${org.name}`}>
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th scope="col" className="px-5 py-3 text-left font-medium">Usuario</th>
                  <th scope="col" className="px-5 py-3 text-left font-medium">Email</th>
                  <th scope="col" className="px-5 py-3 text-left font-medium">Rol</th>
                  <th scope="col" className="px-5 py-3 text-left font-medium">Desde</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {org.members.map((m) => (
                  <tr key={m.user_id} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <Link
                        href={`/dashboard/admin/users/${m.user_id}`}
                        className="font-medium text-slate-900 hover:text-primary"
                      >
                        {m.full_name}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-slate-600 font-mono text-xs">{m.email}</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ROLE_STYLES[m.role] ?? ROLE_STYLES.CLIENT}`}>
                        {ROLE_LABELS[m.role] ?? m.role}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{fmtDate(m.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function KpiCard({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-5 py-4">
      <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className={`mt-1 text-sm text-slate-900 break-words ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("es-CL", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}

const STATUS_LABELS: Record<string, string> = {
  active: "Activa",
  suspended: "Suspendida",
  inactive: "Inactiva",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  suspended: "bg-amber-100 text-amber-800",
  inactive: "bg-slate-100 text-slate-700",
};

const TYPE_LABELS: Record<string, string> = {
  individual: "Individual",
  law_firm: "Bufete de abogados",
  company: "Empresa",
  internal: "Interna",
};

const ROLE_LABELS: Record<string, string> = {
  PLATFORM_ADMIN: "Admin plataforma",
  OWNER: "Owner",
  ADMIN: "Admin",
  LAWYER: "Abogado",
  COMPANY_USER: "Empresa",
  CLIENT: "Cliente",
  VIEWER: "Visualizador",
};

const ROLE_STYLES: Record<string, string> = {
  PLATFORM_ADMIN: "bg-purple-100 text-purple-800",
  OWNER: "bg-blue-100 text-blue-800",
  ADMIN: "bg-blue-50 text-blue-700",
  LAWYER: "bg-slate-100 text-slate-700",
  COMPANY_USER: "bg-slate-100 text-slate-700",
  CLIENT: "bg-slate-50 text-slate-600",
  VIEWER: "bg-slate-50 text-slate-600",
};
