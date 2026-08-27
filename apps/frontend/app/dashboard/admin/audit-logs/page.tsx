"use client";

/**
 * /dashboard/admin/audit-logs — S4.6
 *
 * Paginated table of platform-wide audit events. The endpoint
 * (``GET /api/v1/admin/audit-logs``) is gated behind ``PLATFORM_ADMIN``
 * server-side, so this page is a thin client that just renders the
 * JSON stream. Non-admin users see a 403 envelope; we show that as a
 * friendly message instead of an unhelpful traceback.
 *
 * Filters: action (string), entity_type (string), days (1 / 7 / 30),
 * limit (50 / 100 / 500). The backend enforces the dates and the
 * limit — the client just passes the query string through.
 */

import { useEffect, useState } from "react";
import { toastFromError, useToast } from "@/lib/toast";

interface AuditLog {
  id: number;
  organization_id: number | null;
  user_id: number | null;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  ip_address: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

const ACTIONS = [
  "all",
  "login",
  "logout",
  "document_upload",
  "document_delete",
  "analysis_generate",
  "report_view",
  "report_export",
  "matter_create",
  "matter_status_change",
  "share.create",
  "share.view",
] as const;

const ENTITY_TYPES = [
  "all",
  "document",
  "analysis_report",
  "matter",
  "user",
  "chat_session",
] as const;

export default function AuditLogsPage() {
  const toast = useToast();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState<typeof ACTIONS[number]>("all");
  const [entityType, setEntityType] = useState<typeof ENTITY_TYPES[number]>("all");
  const [days, setDays] = useState<number>(7);
  const [limit, setLimit] = useState<number>(100);

  async function fetchLogs() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (action !== "all") params.set("action_filter", action);
      if (entityType !== "all") params.set("entity_type", entityType);
      params.set("days", String(days));
      params.set("limit", String(limit));
      const res = await fetch(`/api/v1/admin/audit-logs?${params.toString()}`);
      if (res.status === 403) {
        setError("No tienes permisos para ver los registros de auditoría. Esta página está reservada para administradores de plataforma.");
        setLogs([]);
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastFromError(toast, data.detail || `Error ${res.status}`);
        setLogs([]);
        return;
      }
      const data = (await res.json()) as AuditLog[];
      setLogs(data);
    } catch (err) {
      toast.show(toastFromError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, entityType, days, limit]);

  const fmtDate = (iso: string): string => {
    try {
      return new Date(iso).toLocaleString("es-CL", {
        dateStyle: "short",
        timeStyle: "medium",
      });
    } catch {
      return iso;
    }
  };

  return (
    <main
      id="main-content"
      className="mx-auto max-w-6xl px-6 py-8"
      lang="es"
    >
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">
          Registros de auditoría
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Eventos relevantes para cumplimiento normativo (SOC 2, ISO 27001).
          Visible solo para administradores de plataforma.
        </p>
      </header>

      <section
        className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4"
        aria-label="Filtros"
      >
        <label className="text-sm">
          <span className="block font-medium text-slate-700">Acción</span>
          <select
            value={action}
            onChange={(e) => setAction(e.target.value as typeof ACTIONS[number])}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-medium text-slate-700">Entidad</span>
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value as typeof ENTITY_TYPES[number])}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            {ENTITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-medium text-slate-700">Periodo</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value={1}>Último día</option>
            <option value={7}>Última semana</option>
            <option value={30}>Último mes</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-medium text-slate-700">Límite</span>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={500}>500</option>
          </select>
        </label>
      </section>

      {error ? (
        <div
          role="alert"
          className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
        >
          {error}
        </div>
      ) : loading ? (
        <div className="text-sm text-slate-500" role="status" aria-live="polite">
          Cargando registros…
        </div>
      ) : logs.length === 0 ? (
        <div className="rounded-md border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No hay eventos para los filtros seleccionados.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left">
                <tr>
                  <th className="px-4 py-2 font-semibold text-slate-700">Fecha</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Acción</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Entidad</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Org</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Usuario</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">IP</th>
                  <th className="px-4 py-2 font-semibold text-slate-700">Detalles</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-4 py-2 text-slate-600">
                      {fmtDate(log.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                        {log.action}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-700">
                      {log.entity_type ?? "—"}
                      {log.entity_id !== null ? ` #${log.entity_id}` : ""}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-700">
                      {log.organization_id ?? "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-700">
                      {log.user_id ?? "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-500">
                      {log.ip_address ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-slate-600">
                      {log.metadata
                        ? Object.entries(log.metadata)
                            .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                            .join(", ")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <footer className="mt-6 text-xs text-slate-500">
        Mostrando hasta {limit} eventos de los últimos {days} días. Usa los
        filtros para acotar.
      </footer>
    </main>
  );
}
