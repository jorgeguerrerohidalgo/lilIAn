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

const urgencyColors: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  urgent: "bg-red-100 text-red-800",
};

const statusColors: Record<string, string> = {
  new: "bg-blue-100 text-blue-800",
  processing: "bg-yellow-100 text-yellow-800",
  analysis_ready: "bg-green-100 text-green-800",
  pending_human_review: "bg-purple-100 text-purple-800",
  missing_information: "bg-orange-100 text-orange-800",
  contact_client: "bg-cyan-100 text-cyan-800",
  in_progress: "bg-indigo-100 text-indigo-800",
  closed: "bg-gray-100 text-gray-800",
  archived: "bg-gray-200 text-gray-600",
};

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
        setMatters(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Mis casos</h1>
          <p className="text-gray-600 mt-1">
            Gestiona tus casos legales y documentos
          </p>
        </div>
        <Link
          href="/matters/new"
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          Nuevo caso
        </Link>
      </div>

      {loading ? (
        <p className="text-gray-600">Cargando casos...</p>
      ) : matters.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border p-12 text-center">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No tienes casos aún</h3>
          <p className="text-gray-600 mb-6">Comienza creando tu primer caso legal</p>
          <Link
            href="/matters/new"
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            Crear primer caso
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Caso</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Urgencia</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {matters.map((matter) => (
                <tr key={matter.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <Link href={`/matters/${matter.id}`} className="text-primary-600 hover:text-primary-700 font-medium">
                      {matter.title}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {matterTypeLabels[matter.matter_type] || matter.matter_type}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[matter.status] || "bg-gray-100 text-gray-800"}`}>
                      {statusLabels[matter.status] || matter.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${urgencyColors[matter.urgency] || "bg-gray-100 text-gray-800"}`}>
                      {matter.urgency}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(matter.created_at).toLocaleDateString("es-CL")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
