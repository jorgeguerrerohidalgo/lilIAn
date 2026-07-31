"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface AlertsSummary {
  total: number;
  overdue: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  by_matter: { matter_id: number; matter_title: string; count: number }[];
}

interface DeadlineAlert {
  id: number;
  matter_id: number;
  matter_title: string;
  title: string;
  event_type: string;
  due_date: string;
  days_remaining: number | null;
  is_overdue: boolean;
  urgency: string;
  status: string;
}

export function DeadlineDashboard() {
  const [summary, setSummary] = useState<AlertsSummary | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<DeadlineAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const [summaryRes, alertsRes] = await Promise.all([
        fetch("/api/v1/alerts/summary", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/api/v1/alerts?limit=10", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (summaryRes.ok) {
        setSummary(await summaryRes.json());
      }
      if (alertsRes.ok) {
        const data = await alertsRes.json();
        setRecentAlerts(data.filter((a: DeadlineAlert) => a.status === "pending"));
      }
    } catch (error) {
      console.error("Error fetching dashboard:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-3 border-slate-200 border-t-slate-700 rounded-full animate-spin" />
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="text-center py-12 text-slate-500">
        No hay datos disponibles
      </div>
    );
  }

  const urgencyStats = [
    { key: "critical", label: "Críticos", color: "text-red-600", bg: "bg-red-50", count: summary.critical },
    { key: "high", label: "Altos", color: "text-orange-600", bg: "bg-orange-50", count: summary.high },
    { key: "medium", label: "Medios", color: "text-amber-600", bg: "bg-amber-50", count: summary.medium },
    { key: "low", label: "Bajos", color: "text-sky-600", bg: "bg-sky-50", count: summary.low },
  ];

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 text-white rounded-xl p-5">
          <p className="text-3xl font-semibold">{summary.total}</p>
          <p className="text-slate-400 text-sm mt-1">Total alertas</p>
        </div>
        <div className="bg-red-600 text-white rounded-xl p-5">
          <p className="text-3xl font-semibold">{summary.overdue}</p>
          <p className="text-red-100 text-sm mt-1">Vencidos</p>
        </div>
        {urgencyStats.slice(0, 2).map((stat) => (
          <div key={stat.key} className={`${stat.bg} rounded-xl p-5 border border-slate-200`}>
            <p className={`text-3xl font-semibold ${stat.color}`}>{stat.count}</p>
            <p className={`${stat.color} text-sm mt-1 opacity-75`}>{stat.label}</p>
          </div>
        ))}
      </div>

      {/* By Matter */}
      {summary.by_matter.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="font-semibold text-slate-900 mb-3">Alertas por Caso</h3>
          <div className="space-y-2">
            {summary.by_matter.map((item) => (
              <Link
                key={item.matter_id}
                href={`/matters/${item.matter_id}?tab=alerts`}
                className="flex items-center justify-between p-2.5 hover:bg-slate-50 rounded-lg transition-colors"
              >
                <span className="text-slate-700">{item.matter_title}</span>
                <span className="px-2.5 py-1 bg-slate-100 text-slate-700 text-sm font-medium rounded-full">
                  {item.count}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Recent Alerts */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="font-semibold text-slate-900 mb-3">Próximos Vencimientos</h3>
        {recentAlerts.length === 0 ? (
          <p className="text-slate-500 text-center py-4">No hay alertas pendientes</p>
        ) : (
          <div className="space-y-2">
            {recentAlerts.slice(0, 5).map((alert) => (
              <Link
                key={alert.id}
                href={`/matters/${alert.matter_id}?tab=alerts`}
                className="flex items-center justify-between p-3 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <div>
                  <p className="font-medium text-slate-900">{alert.title}</p>
                  <p className="text-sm text-slate-500">{alert.matter_title}</p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-medium ${
                    alert.is_overdue ? "text-red-600" : alert.days_remaining !== null && alert.days_remaining <= 7 ? "text-orange-600" : "text-slate-600"
                  }`}>
                    {alert.is_overdue ? "Vencido" : alert.days_remaining !== null ? `${alert.days_remaining}d` : "—"}
                  </p>
                  <p className="text-xs text-slate-400">
                    {new Date(alert.due_date).toLocaleDateString("es-CL")}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
