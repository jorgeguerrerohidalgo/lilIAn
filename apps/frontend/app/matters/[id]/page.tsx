"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

interface Matter {
  id: number;
  title: string;
  matter_type: string;
  description: string;
  status: string;
  urgency: string;
  counterparty_name: string;
  created_at: string;
  updated_at: string;
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

export default function MatterDetailPage() {
  const params = useParams();
  const [matter, setMatter] = useState<Matter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "/auth/login";
      return;
    }

    fetch(`${API_URL}/api/v1/matters/${params.id}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Caso no encontrado");
        return res.json();
      })
      .then((data) => {
        setMatter(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Error al cargar el caso");
        setLoading(false);
      });
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-600">Cargando caso...</p>
      </div>
    );
  }

  if (error || !matter) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold text-red-600 mb-4">
          {error || "Caso no encontrado"}
        </h2>
        <Link href="/matters" className="text-primary-600 hover:text-primary-700">
          Volver a casos
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <Link href="/dashboard" className="text-sm text-gray-600 hover:text-primary-600 mb-2 inline-block">
          ← Volver al dashboard
        </Link>
        <h1 className="text-3xl font-bold text-gray-900">{matter.title}</h1>
        <div className="flex gap-3 mt-3">
          <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusColors[matter.status] || "bg-gray-100 text-gray-800"}`}>
            {statusLabels[matter.status] || matter.status}
          </span>
          <span className={`px-3 py-1 text-sm font-medium rounded-full ${urgencyColors[matter.urgency] || "bg-gray-100 text-gray-800"}`}>
            Urgencia: {matter.urgency}
          </span>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">Detalles del caso</h2>
            <dl className="space-y-3">
              <div className="flex">
                <dt className="w-40 text-gray-500">Tipo:</dt>
                <dd className="text-gray-900">
                  {matterTypeLabels[matter.matter_type] || matter.matter_type}
                </dd>
              </div>
              {matter.counterparty_name && (
                <div className="flex">
                  <dt className="w-40 text-gray-500">Contraparte:</dt>
                  <dd className="text-gray-900">{matter.counterparty_name}</dd>
                </div>
              )}
              <div className="flex">
                <dt className="w-40 text-gray-500">Creado:</dt>
                <dd className="text-gray-900">
                  {new Date(matter.created_at).toLocaleDateString("es-CL", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </dd>
              </div>
              <div className="flex">
                <dt className="w-40 text-gray-500">Última actualización:</dt>
                <dd className="text-gray-900">
                  {new Date(matter.updated_at).toLocaleDateString("es-CL", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </dd>
              </div>
            </dl>
          </div>

          {matter.description && (
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <h2 className="text-lg font-semibold mb-4">Descripción</h2>
              <p className="text-gray-700 whitespace-pre-wrap">{matter.description}</p>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">Acciones</h2>
            <div className="space-y-3">
              <button className="w-full px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
                Subir documentos
              </button>
              <button className="w-full px-4 py-2 border rounded-lg hover:bg-gray-50">
                Solicitar análisis IA
              </button>
              <button className="w-full px-4 py-2 border rounded-lg hover:bg-gray-50">
                Chatear sobre el caso
              </button>
            </div>
          </div>

          <div className="bg-primary-50 rounded-xl p-6">
            <p className="text-sm text-primary-800">
              <strong>Nota legal:</strong> Este análisis es preliminar y no reemplaza
              la revisión profesional de un abogado habilitado en Chile.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
