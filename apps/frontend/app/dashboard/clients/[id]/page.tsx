"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { getApiUrl } from "../lib/api";


const API_URL = getApiUrl();

interface Client {
  id: number;
  name: string;
  company_name: string | null;
  rut: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Matter {
  id: number;
  title: string;
  matter_type: string;
  status: string;
  urgency: string;
  created_at: string;
}

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
  processing: "En procesamiento",
  analysis_ready: "Análisis listo",
  pending_human_review: "Pendiente revisión",
  missing_information: "Info faltante",
  contact_client: "Contactar cliente",
  in_progress: "En progreso",
  closed: "Cerrado",
  archived: "Archivado",
};

const urgencyColors: Record<string, string> = {
  low: "bg-gray-100 text-gray-700",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-orange-100 text-orange-700",
  urgent: "bg-red-100 text-red-700",
};

export default function ClientDetailPage() {
  const router = useRouter();
  const params = useParams();
  const clientId = params.id as string;

  const [client, setClient] = useState<Client | null>(null);
  const [matters, setMatters] = useState<Matter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/auth/login");
      return;
    }
    fetchClient();
    fetchMatters();
  }, [clientId, router]);

  const getToken = () => localStorage.getItem("token") || "";

  const fetchClient = async () => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/clients/${clientId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.ok) {
      const data = await res.json();
      setClient(data);
    } else {
      setError("Cliente no encontrado");
    }
  };

  const fetchMatters = async () => {
    setLoading(true);
    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/matters?client_id=${clientId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.ok) {
      const data = await res.json();
      setMatters(data);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-gray-500">Cargando...</div>
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="p-6">
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">
          {error || "Cliente no encontrado"}
        </div>
        <button
          onClick={() => router.back()}
          className="mt-4 text-primary-600 hover:text-primary-700"
        >
          ← Volver
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/dashboard/clients")}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{client.name}</h1>
            {client.company_name && (
              <p className="text-gray-600">{client.company_name}</p>
            )}
          </div>
        </div>
        <button
          onClick={() => router.push(`/matters/new?client_id=${client.id}`)}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nuevo Caso
        </button>
      </div>

      {/* Client Info Card */}
      <div className="bg-white rounded-xl shadow-sm border p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Información del Cliente</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {client.rut && (
            <div>
              <p className="text-sm text-gray-500">RUT</p>
              <p className="font-medium">{client.rut}</p>
            </div>
          )}
          {client.email && (
            <div>
              <p className="text-sm text-gray-500">Email</p>
              <p className="font-medium">{client.email}</p>
            </div>
          )}
          {client.phone && (
            <div>
              <p className="text-sm text-gray-500">Teléfono</p>
              <p className="font-medium">{client.phone}</p>
            </div>
          )}
          {client.address && (
            <div className="md:col-span-2">
              <p className="text-sm text-gray-500">Dirección</p>
              <p className="font-medium">{client.address}</p>
            </div>
          )}
          {client.notes && (
            <div className="md:col-span-2">
              <p className="text-sm text-gray-500">Notas</p>
              <p className="font-medium">{client.notes}</p>
            </div>
          )}
        </div>
      </div>

      {/* Matters Section */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold">Casos ({matters.length})</h2>
        </div>

        {matters.length === 0 ? (
          <div className="p-8 text-center">
            <svg
              className="w-16 h-16 mx-auto text-gray-300 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="text-gray-500 mb-4">Este cliente aún no tiene casos</p>
            <button
              onClick={() => router.push(`/matters/new?client_id=${client.id}`)}
              className="text-primary-600 hover:text-primary-700"
            >
              Crear el primer caso
            </button>
          </div>
        ) : (
          <div className="divide-y">
            {matters.map((matter) => (
              <div
                key={matter.id}
                className="p-4 hover:bg-gray-50 cursor-pointer"
                onClick={() => router.push(`/matters/${matter.id}`)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="font-medium text-gray-900">{matter.title}</h3>
                    <p className="text-sm text-gray-500">
                      {matterTypeLabels[matter.matter_type] || matter.matter_type}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        urgencyColors[matter.urgency] || urgencyColors.medium
                      }`}
                    >
                      {matter.urgency}
                    </span>
                    <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full text-xs">
                      {statusLabels[matter.status] || matter.status}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
