"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const matterTypes = [
  { value: "contract_review", label: "Revisión de contrato" },
  { value: "lease", label: "Arriendo" },
  { value: "labor", label: "Laboral" },
  { value: "company", label: "Empresas" },
  { value: "data_protection", label: "Protección de datos" },
  { value: "consumer", label: "Consumidor" },
  { value: "family", label: "Familia" },
  { value: "debt", label: "Deudas" },
  { value: "other", label: "Otro" },
];

const urgencyOptions = [
  { value: "low", label: "Baja" },
  { value: "medium", label: "Media" },
  { value: "high", label: "Alta" },
  { value: "urgent", label: "Urgente" },
];

export default function NewMatterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    matter_type: "contract_review",
    description: "",
    urgency: "medium",
    counterparty_name: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/auth/login");
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/matters`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Error al crear el caso");
      }

      const data = await res.json();
      router.push(`/matters/${data.id}`);
    } catch (err: any) {
      setError(err.message || "Error al crear el caso");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Crear nuevo caso</h1>
        <p className="text-gray-600 mt-1">
          Ingresa la información básica de tu caso legal
        </p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
              Título del caso *
            </label>
            <input
              type="text"
              id="title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Ej: Revisión contrato de prestación de servicios"
              required
            />
          </div>

          <div>
            <label htmlFor="matter_type" className="block text-sm font-medium text-gray-700 mb-1">
              Materia legal *
            </label>
            <select
              id="matter_type"
              value={form.matter_type}
              onChange={(e) => setForm({ ...form, matter_type: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            >
              {matterTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
              Descripción
            </label>
            <textarea
              id="description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={4}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Describe brevemente tu situación legal..."
            />
          </div>

          <div>
            <label htmlFor="urgency" className="block text-sm font-medium text-gray-700 mb-1">
              Urgencia *
            </label>
            <select
              id="urgency"
              value={form.urgency}
              onChange={(e) => setForm({ ...form, urgency: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            >
              {urgencyOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="counterparty_name" className="block text-sm font-medium text-gray-700 mb-1">
              Contraparte (opcional)
            </label>
            <input
              type="text"
              id="counterparty_name"
              value={form.counterparty_name}
              onChange={(e) => setForm({ ...form, counterparty_name: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Nombre de la otra parte involucrada"
            />
          </div>

          <div className="bg-primary-50 p-4 rounded-lg">
            <p className="text-sm text-primary-800">
              <strong>Nota:</strong> Este análisis es preliminar y no reemplaza la revisión
              profesional de un abogado habilitado en Chile.
            </p>
          </div>

          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-4 py-2 border rounded-lg hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? "Creando..." : "Crear caso"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
