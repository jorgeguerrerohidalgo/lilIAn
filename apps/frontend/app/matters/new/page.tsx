"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";


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
  const searchParams = useSearchParams();
  const clientIdFromUrl = searchParams.get("client_id");

  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<{
    title?: string;
    matter_type?: string;
    description?: string;
    urgency?: string;
    client_id?: string;
    form?: string;
  }>({});
  const [clientName, setClientName] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    matter_type: "contract_review",
    description: "",
    urgency: "medium",
    counterparty_name: "",
    client_id: clientIdFromUrl ? parseInt(clientIdFromUrl) : undefined,
  });

  useEffect(() => {
    if (clientIdFromUrl) {
      fetch(`/api/v1/clients/${clientIdFromUrl}`)
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          if (data) setClientName(data.name);
        })
        .catch(() => {});
    }
  }, [clientIdFromUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setLoading(true);

    try {
      const res = await fetch(`/api/v1/matters`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
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
      setErrors({ form: err.message || "Error al crear el caso" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Crear nuevo caso
        </h1>
        <p className="text-slate-500 mt-1">
          Ingresa la información básica de tu caso legal
        </p>
      </div>

      {errors.form && (
        <div
          id="matter-form-error"
          role="alert"
          aria-live="assertive"
          className="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200"
        >
          {errors.form}
        </div>
      )}

      {clientName && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <p className="text-sm text-slate-700">
            <strong>Cliente:</strong> {clientName}
          </p>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-slate-700 mb-1.5">
              Título del caso *
            </label>
            <input
              type="text"
              id="title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              aria-describedby={errors.form ? "matter-form-error" : undefined}
              aria-invalid={errors.title ? true : undefined}
              className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-slate-400 transition-all"
              placeholder="Ej: Revisión contrato de prestación de servicios"
              required
              aria-required="true"
            />
          </div>

          <div>
            <label htmlFor="matter_type" className="block text-sm font-medium text-slate-700 mb-1.5">
              Materia legal *
            </label>
            <select
              id="matter_type"
              value={form.matter_type}
              onChange={(e) => setForm({ ...form, matter_type: e.target.value })}
              aria-describedby={errors.form ? "matter-form-error" : undefined}
              aria-invalid={errors.matter_type ? true : undefined}
              className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-slate-400 transition-all bg-white"
              required
              aria-required="true"
            >
              {matterTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="description" className="block text-sm font-medium text-slate-700 mb-1.5">
              Descripción
            </label>
            <textarea
              id="description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              aria-describedby={errors.form ? "matter-form-error" : undefined}
              aria-invalid={errors.description ? true : undefined}
              rows={3}
              className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-slate-400 transition-all resize-none"
              placeholder="Describe brevemente tu situación legal..."
            />
          </div>

          <div>
            <label htmlFor="urgency" className="block text-sm font-medium text-slate-700 mb-1.5">
              Urgencia *
            </label>
            <select
              id="urgency"
              value={form.urgency}
              onChange={(e) => setForm({ ...form, urgency: e.target.value })}
              aria-describedby={errors.form ? "matter-form-error" : undefined}
              aria-invalid={errors.urgency ? true : undefined}
              className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-slate-400 transition-all bg-white"
              required
              aria-required="true"
            >
              {urgencyOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="counterparty_name" className="block text-sm font-medium text-slate-700 mb-1.5">
              Contraparte (opcional)
            </label>
            <input
              type="text"
              id="counterparty_name"
              value={form.counterparty_name}
              onChange={(e) => setForm({ ...form, counterparty_name: e.target.value })}
              aria-describedby={errors.form ? "matter-form-error" : undefined}
              aria-invalid={errors.client_id ? true : undefined}
              className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-slate-400 transition-all"
              placeholder="Nombre de la otra parte involucrada"
            />
          </div>

          <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
            <p className="text-sm text-slate-600">
              <strong>Nota:</strong> Este análisis es preliminar y no reemplaza la revisión
              profesional de un abogado habilitado en Chile.
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-4 py-2.5 border border-slate-200 rounded-lg text-slate-600 font-medium text-sm hover:bg-slate-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              aria-busy={loading}
              aria-live="polite"
              className="px-5 py-2.5 bg-slate-900 text-white rounded-lg font-medium text-sm hover:bg-slate-800 disabled:opacity-50 transition-colors"
            >
              {loading ? "Creando..." : "Crear caso"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
