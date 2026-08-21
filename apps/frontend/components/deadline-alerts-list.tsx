"use client";

import { useState, useEffect } from "react";
import { getApiUrl } from "@/lib/api";
import { logger } from "../lib/logger";


const API_URL = getApiUrl();

interface DeadlineAlert {
  id: number;
  matter_id: number;
  matter_title: string;
  document_id: number | null;
  title: string;
  description: string | null;
  event_type: string;
  due_date: string;
  days_remaining: number | null;
  is_overdue: boolean;
  urgency: "critical" | "high" | "medium" | "low";
  status: string;
  source_event: string | null;
  legal_reference: string | null;
  consequence: string | null;
  created_at: string;
}

interface Props {
  matterId: number;
}

const urgencyConfig = {
  critical: { bg: "bg-coral-pale", border: "border-coral/20", badge: "bg-coral-pale text-coral-dark", label: "CRÍTICO" },
  high: { bg: "bg-amber-pale", border: "border-amber/20", badge: "bg-amber-pale text-amber", label: "ALTO" },
  medium: { bg: "bg-amber-pale", border: "border-amber/20", badge: "bg-amber-pale text-amber", label: "MEDIO" },
  low: { bg: "bg-blue-pale", border: "border-blue/20", badge: "bg-blue-pale text-blue", label: "BAJO" },
};

const statusConfig = {
  pending: { label: "Pendiente", color: "text-ink2" },
  acknowledged: { label: "Visto", color: "text-blue" },
  resolved: { label: "Resuelto", color: "text-green" },
  dismissed: { label: "Descartado", color: "text-ink/40" },
};

const eventTypeLabels: Record<string, string> = {
  vencimiento: "Vencimiento",
  aviso_previo: "Aviso Previo",
  renovacion: "Renovación",
  prescripcion: "Prescripción",
  pago: "Pago",
  garantia: "Garantía",
  firma: "Límite para Firmar",
  plazo_sin_penalidad: "Plazo sin Penalidad",
};

export function DeadlineAlertsList({ matterId }: Props) {
  const [alerts, setAlerts] = useState<DeadlineAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "pending" | "overdue">("all");
  const [updating, setUpdating] = useState<number | null>(null);

  useEffect(() => {
    fetchAlerts();
  }, [matterId]);

  const fetchAlerts = async () => {
    try {
      logger.info("Fetching alerts for matter:", matterId, "API_URL:", API_URL);
      const res = await fetch(`/api/v1/alerts/matters/${matterId}`);
      logger.info("Alerts response:", res.status, res.ok);
      if (res.ok) {
        const data = await res.json();
        logger.info("Alerts data:", data);
        setAlerts(data);
      }
    } catch (error) {
      logger.error("Error fetching alerts:", error);
    } finally {
      setLoading(false);
    }
  };

  const updateAlert = async (alertId: number, status: string) => {
    setUpdating(alertId);
    try {
      const res = await fetch(`/api/v1/alerts/${alertId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status }),
      });
      if (res.ok) {
        setAlerts((prev) =>
          prev.map((a) => (a.id === alertId ? { ...a, status } : a))
        );
      }
    } catch (error) {
      logger.error("Error updating alert:", error);
    } finally {
      setUpdating(null);
    }
  };

  const filteredAlerts = alerts.filter((alert) => {
    if (filter === "pending") return alert.status === "pending" && !alert.is_overdue;
    if (filter === "overdue") return alert.is_overdue || alert.status === "pending";
    return true;
  });

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("es-CL", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="w-6 h-6 border-2 border-soft border-t-ink rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4" aria-live="polite">
      {/* Filters */}
      <div role="group" aria-label="Filtrar alertas por estado" className="flex gap-2">
        <button
          onClick={() => setFilter("all")}
          aria-pressed={filter === "all"}
          className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
            filter === "all" ? "bg-ink text-white" : "bg-soft text-ink2 hover:bg-border"
          }`}
        >
          Todos ({alerts.length})
        </button>
        <button
          onClick={() => setFilter("pending")}
          aria-pressed={filter === "pending"}
          className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
            filter === "pending" ? "bg-ink text-white" : "bg-soft text-ink2 hover:bg-border"
          }`}
        >
          Pendientes
        </button>
        <button
          onClick={() => setFilter("overdue")}
          aria-pressed={filter === "overdue"}
          className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
            filter === "overdue" ? "bg-coral text-white" : "bg-coral-pale text-coral-dark hover:bg-coral/10"
          }`}
        >
          Vencidos
        </button>
      </div>

      {/* Alerts list */}
      {filteredAlerts.length === 0 ? (
        <div className="text-center py-10 text-ink/60">
          <p className="font-medium text-ink/80">Sin alertas</p>
          <p className="mt-1 text-sm">
            {filter === "all"
              ? "Cuando el análisis detecte plazos o vencimientos, aparecerán aquí."
              : "No hay alertas en este filtro. Prueba con «Todos» o vuelve después de un nuevo análisis."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAlerts.map((alert) => {
            const config = urgencyConfig[alert.urgency] || urgencyConfig.medium;
            const status = statusConfig[alert.status as keyof typeof statusConfig] || statusConfig.pending;

            return (
              <div
                key={alert.id}
                role="article"
                aria-labelledby={`alert-title-${alert.id}`}
                className={`${config.bg} border ${config.border} rounded-lg p-4`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${config.badge}`}>
                        {config.label}
                      </span>
                      <span className="text-xs text-ink/60">
                        {eventTypeLabels[alert.event_type] || alert.event_type}
                      </span>
                      {alert.is_overdue && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded bg-coral-pale text-coral-dark">
                          VENCIDO
                        </span>
                      )}
                    </div>
                    <h4 id={`alert-title-${alert.id}`} className="font-medium text-ink">{alert.title}</h4>
                    {alert.description && (
                      <p className="text-sm text-ink2 mt-1">{alert.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-sm">
                      <span className="text-ink/60">
                        Vence:{" "}
                        <time dateTime={alert.due_date}>
                          <strong className={alert.is_overdue ? "text-coral" : "text-ink2"}>
                            {formatDate(alert.due_date)}
                          </strong>
                        </time>
                      </span>
                      {alert.days_remaining !== null && (
                        <span className={alert.days_remaining < 0 ? "text-coral" : "text-ink/60"}>
                          {alert.days_remaining < 0
                            ? `${Math.abs(alert.days_remaining)} días vencido`
                            : `${alert.days_remaining} días restantes`}
                        </span>
                      )}
                    </div>
                    {alert.legal_reference && (
                      <p className="text-xs text-ink/40 mt-1 italic">
                        Ref: {alert.legal_reference}
                      </p>
                    )}
                    {alert.consequence && (
                      <p className="text-xs text-coral mt-1 font-medium">
                        ⚠️ {alert.consequence}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-1">
                    {alert.status === "pending" && (
                      <>
                        <button
                          onClick={() => updateAlert(alert.id, "acknowledged")}
                          disabled={updating === alert.id}
                          aria-label={`Marcar alerta "${alert.title}" como vista`}
                          className="px-2 py-1 text-xs bg-blue-pale text-blue rounded hover:bg-blue/10 disabled:opacity-50 transition-colors"
                        >
                          {updating === alert.id ? "..." : "Visto"}
                        </button>
                        <button
                          onClick={() => updateAlert(alert.id, "resolved")}
                          disabled={updating === alert.id}
                          aria-label={`Resolver alerta "${alert.title}"`}
                          className="px-2 py-1 text-xs bg-green-pale text-green rounded hover:bg-green/10 disabled:opacity-50 transition-colors"
                        >
                          Resolver
                        </button>
                        <button
                          onClick={() => updateAlert(alert.id, "dismissed")}
                          disabled={updating === alert.id}
                          aria-label={`Descartar alerta "${alert.title}"`}
                          className="px-2 py-1 text-xs bg-soft text-ink/60 rounded hover:bg-border disabled:opacity-50 transition-colors"
                        >
                          Descartar
                        </button>
                      </>
                    )}
                    {alert.status === "acknowledged" && (
                      <button
                        onClick={() => updateAlert(alert.id, "resolved")}
                        disabled={updating === alert.id}
                        aria-label={`Resolver alerta "${alert.title}"`}
                        className="px-2 py-1 text-xs bg-green-pale text-green rounded hover:bg-green/10 disabled:opacity-50 transition-colors"
                      >
                        Resolver
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
