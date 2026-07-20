"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Matter {
  id: number;
  title: string;
  matter_type: string;
  status: string;
  urgency: string;
  created_at: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const matterTypeLabels: Record<string, string> = {
  contract_review: "Revisión de contrato",
  lease: "Arriendo",
  labor: "Laboral",
  company: "Empresas",
  data_protection: "Protección de datos",
  consumer: "Consumidor",
  family: "Familia",
  debt: "Deudas",
  other: "Otro",
};

const statusLabels: Record<string, string> = {
  new: "Nuevo",
  processing: "Procesando",
  analysis_ready: "Análisis listo",
  pending_human_review: "Pendiente revisión",
  missing_information: "Info incompleta",
  contact_client: "Contactar cliente",
  in_progress: "En gestión",
  closed: "Cerrado",
  archived: "Archivado",
};

// Trust & Authority palette
const statusColors: Record<string, string> = {
  new: "bg-slate-100 text-slate-700",
  processing: "bg-amber-100 text-amber-800",
  analysis_ready: "bg-emerald-100 text-emerald-700",
  pending_human_review: "bg-purple-100 text-purple-700",
  missing_information: "bg-orange-100 text-orange-700",
  contact_client: "bg-sky-100 text-sky-700",
  in_progress: "bg-indigo-100 text-indigo-700",
  closed: "bg-gray-100 text-gray-600",
  archived: "bg-gray-200 text-gray-500",
};

const urgencyColors: Record<string, string> = {
  low: "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  urgent: "bg-red-100 text-red-700",
};

// Icons
function PlusIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function BriefcaseIcon() {
  return (
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 7.5l-2 4.166a2.25 2.25 0 01-2.155 2.154H7.911a2.25 2.25 0 01-2.154-2.155l.917-4.166m-1.173-2.833V3.75a2.25 2.25 0 012.25-2.25h9.75a2.25 2.25 0 012.25 2.25v1.833m-1.173-2.833l-1.173 2.833m1.173 2.833v8.25M18 18H6a2.25 2.25 0 01-2.25-2.25V6.75A2.25 2.25 0 013.75 4.5h16.5A2.25 2.25 0 0122.5 6.75v8.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6" />
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.25a2.25 2.25 0 00-2.25-2.25H5a2.25 2.25 0 00-2.25 2.25v10.5a2.25 2.25 0 002.25 2.25h14.5a2.25 2.25 0 002.25-2.25v-2.25" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-8 h-8 border-3 border-slate-200 border-t-slate-700 rounded-full animate-spin" />
    </div>
  );
}

export default function DashboardPage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;

    fetch(`${API_URL}/api/v1/matters`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => res.json())
      .then((data) => {
        setMatters(data || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Stats for summary cards
  const stats = [
    {
      label: "Total casos",
      value: matters.length,
      icon: <BriefcaseIcon />,
      color: "text-slate-600",
    },
    {
      label: "En proceso",
      value: matters.filter((m) => m.status === "processing" || m.status === "in_progress").length,
      icon: <DocumentIcon />,
      color: "text-amber-600",
    },
    {
      label: "Listos para revisión",
      value: matters.filter((m) => m.status === "analysis_ready").length,
      icon: <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
      color: "text-emerald-600",
    },
    {
      label: "Urgentes",
      value: matters.filter((m) => m.urgency === "high" || m.urgency === "urgent").length,
      icon: <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m-9.303 3.496c.866-2.297 2.792-3.503 4.303-3.496l1.5-.001c1.5 0 3.104.523 4.303 2.496M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
      color: "text-red-600",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
            Mis casos
          </h1>
          <p className="text-slate-500 mt-1">
            Gestiona tus casos legales y documentos
          </p>
        </div>
        <Link
          href="/matters/new"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-slate-900 text-white rounded-lg font-medium text-sm hover:bg-slate-800 active:scale-95 transition-all duration-200 shadow-sm"
        >
          <PlusIcon />
          Nuevo caso
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow duration-200"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{stat.label}</p>
                <p className={`text-3xl font-semibold mt-1 ${stat.color}`}>
                  {stat.value}
                </p>
              </div>
              <div className={`${stat.color} opacity-20`}>
                {stat.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Cases List */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Casos recientes</h2>
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : matters.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <BriefcaseIcon />
            </div>
            <h3 className="text-lg font-medium text-slate-900 mb-2">
              No tienes casos aún
            </h3>
            <p className="text-slate-500 mb-6 max-w-sm mx-auto">
              Comienza creando tu primer caso legal para gestionar documentos y análisis
            </p>
            <Link
              href="/matters/new"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-slate-900 text-white rounded-lg font-medium text-sm hover:bg-slate-800 transition-colors"
            >
              <PlusIcon />
              Crear primer caso
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {matters.map((matter) => (
              <Link
                key={matter.id}
                href={`/matters/${matter.id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="font-medium text-slate-900 truncate group-hover:text-slate-700">
                      {matter.title}
                    </h3>
                    <span className={`shrink-0 px-2 py-0.5 text-xs font-medium rounded-full ${statusColors[matter.status] || "bg-slate-100 text-slate-600"}`}>
                      {statusLabels[matter.status] || matter.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-slate-500">
                      {matterTypeLabels[matter.matter_type] || matter.matter_type}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-slate-400">
                      {new Date(matter.created_at).toLocaleDateString("es-CL", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                    {(matter.urgency === "high" || matter.urgency === "urgent") && (
                      <>
                        <span className="text-slate-300">•</span>
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${urgencyColors[matter.urgency]}`}>
                          {matter.urgency === "urgent" ? "Urgente" : "Alta prioridad"}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <ChevronRightIcon />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
