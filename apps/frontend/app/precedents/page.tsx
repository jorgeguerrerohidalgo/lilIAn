"use client";

import { useEffect, useState } from "react";
import { PrecedentAnalyticsDashboard } from "@/components/precedent-analytics-dashboard";

// /precedents — landing surface for searching the Chilean legal corpus.
// Backed by /api/v1/corpus/search which uses hybrid RAG (embedding +
// keyword) with optional hierarchical and temporal filters.
//
// Filters available (all optional):
//   - legal_area : labour | civil | criminal | commercial | tax | ...
//   - law_code   : specific BCN id (e.g. "1984" for Codigo Penal)
//   - libro      : book name (only meaningful for Codigos)
//   - capitulo   : chapter name
//   - as_of      : temporal versionado — "¿qué establecía esta ley en X fecha?"
export default function PrecedentsPage() {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({
    legal_area: "",
    law_code: "",
    libro: "",
    capitulo: "",
    as_of: "",
  });
  const [results, setResults] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [norms, setNorms] = useState<Array<{ bcn_id: string; titulo: string; legal_area: string }>>([]);

  // Catalog dropdown. Fetched once on mount; cheap (one row per norm).
  useEffect(() => {
    fetch("/api/v1/corpus/norms")
      .then(async (r) => {
        if (!r.ok) return;
        const data = await r.json();
        setNorms(data);
      })
      .catch(() => {/* ignore */});
  }, []);

  const search = async () => {
    if (!query || query.length < 3) {
      setError("La búsqueda debe tener al menos 3 caracteres.");
      return;
    }
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ q: query });
    if (filters.legal_area) params.set("legal_area", filters.legal_area);
    if (filters.law_code) params.set("law_code", filters.law_code);
    if (filters.libro) params.set("libro", filters.libro);
    if (filters.capitulo) params.set("capitulo", filters.capitulo);
    if (filters.as_of) params.set("as_of", filters.as_of);
    try {
      const res = await fetch(`/api/v1/corpus/search?${params.toString()}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || `Error ${res.status}`);
        setResults([]);
        return;
      }
      const data = await res.json();
      setResults(data.chunks || []);
    } catch (err) {
      setError("Error de red al consultar el corpus.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-heading font-bold text-ink">Corpus legal chileno</h1>
        <p className="mt-1 text-sm text-ink/60">
          Búsqueda RAG con filtros por jerarquía, área legal y versionado temporal.
        </p>
      </header>

      {/* Filters */}
      <section
        aria-labelledby="filters-heading"
        className="rounded-xl border border-ink/10 bg-surface p-4 md:p-5 space-y-3"
      >
        <h2 id="filters-heading" className="text-sm font-semibold text-ink">Filtros</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <input
            type="text"
            placeholder="Buscar en el corpus (mín. 3 caracteres)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") search(); }}
            className="md:col-span-2 lg:col-span-3 w-full rounded-lg border border-ink/20 px-3 py-2 text-sm"
          />
          <select
            aria-label="Filtrar por área legal"
            value={filters.legal_area}
            onChange={(e) => setFilters({ ...filters, legal_area: e.target.value })}
            className="rounded-lg border border-ink/20 px-3 py-2 text-sm"
          >
            <option value="">Todas las áreas</option>
            <option value="laboral">Laboral</option>
            <option value="civil">Civil</option>
            <option value="penal">Penal</option>
            <option value="comercial">Comercial</option>
            <option value="tributario">Tributario</option>
            <option value="data_protection">Protección de datos</option>
          </select>
          <select
            aria-label="Filtrar por norma"
            value={filters.law_code}
            onChange={(e) => setFilters({ ...filters, law_code: e.target.value })}
            className="rounded-lg border border-ink/20 px-3 py-2 text-sm"
          >
            <option value="">Todas las normas</option>
            {norms.map((n) => (
              <option key={n.bcn_id} value={n.bcn_id}>
                {n.titulo.length > 60 ? `${n.titulo.slice(0, 60)}…` : n.titulo}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Libro (ej. PRIMERO)"
            value={filters.libro}
            onChange={(e) => setFilters({ ...filters, libro: e.target.value })}
            className="rounded-lg border border-ink/20 px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Capítulo"
            value={filters.capitulo}
            onChange={(e) => setFilters({ ...filters, capitulo: e.target.value })}
            className="rounded-lg border border-ink/20 px-3 py-2 text-sm"
          />
          <input
            type="date"
            aria-label="Vigente a la fecha"
            value={filters.as_of}
            onChange={(e) => setFilters({ ...filters, as_of: e.target.value })}
            className="rounded-lg border border-ink/20 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={search}
            disabled={loading}
            className="rounded-lg bg-primary text-white px-4 py-2 text-sm font-semibold hover:bg-primary-light disabled:opacity-50"
          >
            {loading ? "Buscando…" : "Buscar"}
          </button>
        </div>
        {error && (
          <p role="alert" className="text-xs text-red-700">{error}</p>
        )}
      </section>

      {/* Results */}
      {results.length > 0 && (
        <ol className="space-y-3" aria-label="Resultados">
          {results.map((r, idx) => {
            const item = r as Record<string, unknown>;
            return (
              <li
                key={`${String(item.chunk_id)}-${idx}`}
                className="rounded-xl border border-ink/10 bg-surface p-4 md:p-5"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-ink">
                    {String(item.law_name ?? "—")}
                  </h3>
                  <span className="text-xs text-ink/50">
                    {String(item.article_number ?? "")}
                    {item.jerarquia_path ? ` · ${String(item.jerarquia_path)}` : ""}
                  </span>
                </div>
                <p className="text-sm text-ink/80 whitespace-pre-line">
                  {String(item.content ?? "").slice(0, 600)}
                  {String(item.content ?? "").length > 600 ? "…" : ""}
                </p>
              </li>
            );
          })}
        </ol>
      )}

      <PrecedentAnalyticsDashboard />
    </div>
  );
}
