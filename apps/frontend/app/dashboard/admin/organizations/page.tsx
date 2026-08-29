"use client";

/**
 * /dashboard/admin/organizations — Fase 3b (multi-tenant admin UI).
 *
 * Cross-tenant list of every organization on the platform, gated by
 * the server-side ``get_platform_admin_membership`` check on the
 * backend. Mirrors the visual rhythm of ``/dashboard/admin/audit-logs``:
 * a header + filter row + a single data table.
 *
 * Filters: search (by name substring), status (``active`` /
 * ``suspended`` / ``all``). Pagination is simple ``limit`` + ``offset``
 * with a "next page" button — the backend does not return a total count
 * yet, so we over-fetch by one row to detect the end of the list.
 *
 * Per-row actions:
 *   - Ver detalle → /dashboard/admin/organizations/[id]
 *     (the detail page is intentionally NOT implemented in this sprint;
 *     the link is wired so the route is discoverable when we ship it.)
 *   - Suspender / Activar → POST /admin/organizations/{id}/{suspend,activate}.
 *     The backend reuses ``get_platform_admin_membership`` so the
 *     mutation is safe to call from this client.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Badge, Button } from "@/components/ui";
import { toastFromError, useToast } from "@/lib/toast";

interface AdminOrganization {
  id: number;
  name: string;
  type: string;
  status: string;
  plan_id: string | null;
  created_at: string;
  user_count: number;
  matter_count: number;
}

type StatusFilter = "all" | "active" | "suspended";

const PAGE_SIZE = 50;

export default function AdminOrganizationsPage() {
  const toast = useToast();
  const [orgs, setOrgs] = useState<AdminOrganization[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [offset, setOffset] = useState(0);
  const [reachedEnd, setReachedEnd] = useState(false);

  const fetchOrgs = async (nextOffset: number) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      // The backend endpoint does not currently support search/limit/offset
      // query params — we just fetch all orgs and filter client-side. This
      // matches the scale we expect at this stage of the pilot.
      const res = await fetch(`/api/v1/admin/organizations?${params.toString()}`, {
        credentials: "include",
      });
      if (res.status === 403) {
        setForbidden(true);
        setOrgs([]);
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.show(toastFromError({detail: data.detail}, `Error ${res.status}`));
        setOrgs([]);
        return;
      }
      const data = (await res.json()) as AdminOrganization[];
      const filtered = search.trim()
        ? data.filter((o) =>
            o.name.toLowerCase().includes(search.trim().toLowerCase()),
          )
        : data;
      const slice = filtered.slice(nextOffset, nextOffset + PAGE_SIZE);
      setOrgs(slice);
      setReachedEnd(nextOffset + slice.length >= filtered.length);
    } catch (err) {
      toast.show(toastFromError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setOffset(0);
    void fetchOrgs(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, search]);

  const summary = useMemo(() => {
    const total = orgs.length;
    const active = orgs.filter((o) => o.status === "active").length;
    const suspended = orgs.filter((o) => o.status === "suspended").length;
    return { total, active, suspended };
  }, [orgs]);

  async function handleToggle(org: AdminOrganization) {
    const action = org.status === "active" ? "suspend" : "activate";
    const endpoint = `/api/v1/admin/organizations/${org.id}/${action}`;
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "include",
      });
      if (res.status === 403) {
        toast.show({
          tone: "error",
          title: "Sin permisos",
          body: "No tienes permisos para modificar organizaciones.",
        });
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.show(toastFromError({detail: data.detail}, `Error ${res.status}`));
        return;
      }
      toast.show({
        tone: "success",
        title: action === "suspend" ? "Organización suspendida" : "Organización activada",
        body: `«${org.name}» ahora está ${action === "suspend" ? "suspendida" : "activa"}.`,
      });
      void fetchOrgs(offset);
    } catch (err) {
      toast.show(toastFromError(err));
    }
  }

  if (forbidden) {
    return (
      <main id="main-content" className="mx-auto max-w-6xl px-4 md:px-6 py-6 md:py-8" lang="es">
        <header className="mb-6">
          <h1 className="text-xl md:text-2xl font-semibold text-slate-900">Organizaciones</h1>
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

  return (
    <main
      id="main-content"
      className="mx-auto max-w-6xl px-4 md:px-6 py-6 md:py-8"
      lang="es"
    >
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            Organizaciones
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Todas las organizaciones registradas en Lilian. Solo
            administradores de plataforma.
          </p>
        </div>
        <Link href="/dashboard/admin/organizations/new">
          <Button variant="primary" size="md">
            <PlusIcon />
            Nueva organización
          </Button>
        </Link>
      </header>

      <section
        className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3"
        aria-label="Filtros"
      >
        <label className="text-sm sm:col-span-2">
          <span className="block font-medium text-slate-700">Buscar</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nombre…"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-slate-700">Estado</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="all">Todos</option>
            <option value="active">Activas</option>
            <option value="suspended">Suspendidas</option>
          </select>
        </label>
      </section>

      <section
        className="mb-4 flex flex-wrap gap-2 text-xs text-slate-600"
        aria-label="Resumen"
      >
        <SummaryPill label="Mostradas" value={summary.total} />
        <SummaryPill label="Activas" value={summary.active} />
        <SummaryPill label="Suspendidas" value={summary.suspended} />
      </section>

      {loading ? (
        <div className="text-sm text-slate-500" role="status" aria-live="polite">
          Cargando organizaciones…
        </div>
      ) : orgs.length === 0 ? (
        <div className="rounded-md border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No hay organizaciones que coincidan con los filtros.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left">
                <tr>
                  <th className="px-4 py-2 font-semibold text-slate-700">Nombre</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Tipo</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Plan</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Estado</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Usuarios</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Casos</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orgs.map((org) => (
                  <tr key={org.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 text-slate-900 font-medium">
                      {org.name}
                    </td>
                    <td className="px-4 py-2 text-slate-700">
                      {org.type}
                    </td>
                    <td className="px-4 py-2 text-slate-700">
                      {org.plan_id ?? (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <Badge
                        variant={org.status === "active" ? "green" : "amber"}
                      >
                        {org.status === "active" ? "Activa" : "Suspendida"}
                      </Badge>
                    </td>
                    <td className="px-4 py-2 text-slate-700">{org.user_count}</td>
                    <td className="px-4 py-2 text-slate-700">{org.matter_count}</td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-2">
                        <Link
                          href={`/dashboard/admin/organizations/${org.id}`}
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          Ver detalle
                        </Link>
                        <Button
                          variant={org.status === "active" ? "outline" : "primary"}
                          size="sm"
                          onClick={() => handleToggle(org)}
                        >
                          {org.status === "active" ? "Suspender" : "Activar"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <footer className="mt-6 flex items-center justify-between text-xs text-slate-500">
        <span>
          Mostrando {orgs.length} organizaciones (máx {PAGE_SIZE} por página).
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0 || loading}
            onClick={() => {
              const next = Math.max(0, offset - PAGE_SIZE);
              setOffset(next);
              void fetchOrgs(next);
            }}
          >
            ← Anterior
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={reachedEnd || loading}
            onClick={() => {
              const next = offset + PAGE_SIZE;
              setOffset(next);
              void fetchOrgs(next);
            }}
          >
            Siguiente →
          </Button>
        </div>
      </footer>
    </main>
  );
}

function SummaryPill({ label, value }: { label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1">
      <span className="text-slate-500">{label}:</span>
      <span className="font-semibold text-slate-900">{value}</span>
    </span>
  );
}

function PlusIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
    </svg>
  );
}