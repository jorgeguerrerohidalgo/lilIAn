"use client";

import { useState, useEffect } from "react";
import { getApiUrl } from "@/lib/api";
import { logger } from "../lib/logger";


const API_URL = getApiUrl();

interface AnalyticsData {
  summary: {
    total_precedents: number;
    year_range: { min: number; max: number };
    unique_courts: number;
    unique_areas: number;
  };
  volume_by_year: Array<{ year: number; count: number }>;
  volume_by_court: Array<{ court: string; count: number }>;
  volume_by_legal_area: Array<{ legal_area: string; count: number }>;
  court_matter_heatmap: Array<{ court: string; legal_area: string; count: number }>;
  top_voces: Array<{ voice: string; count: number }>;
  top_ponentes: Array<{ ponente: string; count: number }>;
  temporal_evolution: Record<string, Array<{ year: number; count: number }>>;
  text_analysis: { top_keywords: Array<{ word: string; frequency: number }> };
}

interface FilterOptions {
  courts: string[];
  legal_areas: string[];
  year_range: { min: number; max: number };
}

export function PrecedentAnalyticsDashboard() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter states
  const [selectedCourt, setSelectedCourt] = useState<string>("");
  const [selectedArea, setSelectedArea] = useState<string>("");
  const [yearFrom, setYearFrom] = useState<string>("");
  const [yearTo, setYearTo] = useState<string>("");
  const [includeTextAnalysis, setIncludeTextAnalysis] = useState(false);

  useEffect(() => {
    fetchFilters();
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [selectedCourt, selectedArea, yearFrom, yearTo, includeTextAnalysis]);

  const fetchFilters = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/precedents/analytics/filters`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setFilters(data);
        if (data.year_range?.min) setYearFrom(data.year_range.min.toString());
        if (data.year_range?.max) setYearTo(data.year_range.max.toString());
      }
    } catch (err) {
      logger.error("Error fetching filters:", err);
    }
  };

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const params = new URLSearchParams();
      if (selectedCourt) params.append("court", selectedCourt);
      if (selectedArea) params.append("legal_area", selectedArea);
      if (yearFrom) params.append("year_from", yearFrom);
      if (yearTo) params.append("year_to", yearTo);
      params.append("include_text_analysis", includeTextAnalysis.toString());

      const res = await fetch(
        `/api/v1/precedents/analytics?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (res.ok) {
        const data = await res.json();
        setAnalytics(data);
      } else {
        setError("Error al cargar analytics");
      }
    } catch (err) {
      setError("Error de conexión");
      logger.error("Error fetching analytics:", err);
    } finally {
      setLoading(false);
    }
  };

  // Get max count for scaling
  const maxYearCount = analytics
    ? Math.max(...analytics.volume_by_year.map((y) => y.count), 1)
    : 1;

  const maxCourtCount = analytics
    ? Math.max(...analytics.volume_by_court.map((c) => c.count), 1)
    : 1;

  return (
    <div className="space-y-6" aria-live="polite">
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-lg font-semibold mb-2">
          Análisis de Tendencias Jurisprudenciales
        </h2>
        <p className="text-slate-600 text-sm">
          Estadísticas y patrones de comportamiento judicial basados en los precedentes registrados.
        </p>
      </div>

      {/* Filters */}
      <fieldset className="bg-white rounded-xl border border-slate-200 p-6">
        <legend className="font-medium mb-4 px-1">Filtros</legend>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label htmlFor="pad-court" className="block text-sm text-slate-600 mb-1">
              Tribunal
            </label>
            <select
              id="pad-court"
              value={selectedCourt}
              onChange={(e) => setSelectedCourt(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm"
            >
              <option value="">Todos</option>
              {filters?.courts.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="pad-area" className="block text-sm text-slate-600 mb-1">
              Área Legal
            </label>
            <select
              id="pad-area"
              value={selectedArea}
              onChange={(e) => setSelectedArea(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm"
            >
              <option value="">Todas</option>
              {filters?.legal_areas.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="pad-year-from" className="block text-sm text-slate-600 mb-1">
              Año Desde
            </label>
            <input
              id="pad-year-from"
              type="number"
              value={yearFrom}
              onChange={(e) => setYearFrom(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm"
              placeholder="Ej: 2020"
            />
          </div>
          <div>
            <label htmlFor="pad-year-to" className="block text-sm text-slate-600 mb-1">
              Año Hasta
            </label>
            <input
              id="pad-year-to"
              type="number"
              value={yearTo}
              onChange={(e) => setYearTo(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm"
              placeholder="Ej: 2024"
            />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm" htmlFor="pad-text-analysis">
            <input
              id="pad-text-analysis"
              type="checkbox"
              checked={includeTextAnalysis}
              onChange={(e) => setIncludeTextAnalysis(e.target.checked)}
              className="rounded"
            />
            Incluir análisis de texto
          </label>
        </div>
      </fieldset>

      {loading && (
        <div className="text-center py-12" role="status" aria-live="polite">
          <div className="animate-spin h-8 w-8 border-3 border-slate-200 border-t-slate-700 rounded-full mx-auto" aria-hidden="true" />
          <p className="text-gray-500 mt-2">Cargando analytics...</p>
          <span className="sr-only">Cargando analytics...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
          {error}
        </div>
      )}

      {analytics && !loading && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <p className="text-sm text-gray-500">Total Precedentes</p>
              <p className="text-3xl font-bold text-slate-900">
                {analytics.summary.total_precedents}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <p className="text-sm text-gray-500">Tribunales</p>
              <p className="text-3xl font-bold text-slate-900">
                {analytics.summary.unique_courts}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <p className="text-sm text-gray-500">Áreas Legales</p>
              <p className="text-3xl font-bold text-slate-900">
                {analytics.summary.unique_areas}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <p className="text-sm text-gray-500">Rango de Años</p>
              <p className="text-lg font-bold text-slate-900">
                {analytics.summary.year_range.min || "—"} —{" "}
                {analytics.summary.year_range.max || "—"}
              </p>
            </div>
          </div>

          {/* Volume by Year */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="font-semibold mb-4">Volumen por Año</h3>
            <div
              className="flex items-end gap-2 h-48"
              role="img"
              aria-label={`Gráfico de barras: Volumen por año. Total ${analytics.volume_by_year.reduce((acc, y) => acc + y.count, 0)} precedentes`}
            >
              {analytics.volume_by_year.map((item) => (
                <div key={item.year} className="flex-1 flex flex-col items-center">
                  <div
                    className="w-full bg-slate-700 rounded-t"
                    style={{
                      height: `${(item.count / maxYearCount) * 100}%`,
                      minHeight: item.count > 0 ? "4px" : "0",
                    }}
                    aria-hidden="true"
                  />
                  <span className="text-xs text-gray-500 mt-1">{item.year}</span>
                  <span className="text-xs font-medium">{item.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Volume by Court */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-semibold mb-4">Top Tribunales</h3>
              <div className="space-y-3">
                {analytics.volume_by_court.slice(0, 10).map((item, i) => (
                  <div key={item.court}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="truncate pr-2">{item.court}</span>
                      <span className="font-medium">{item.count}</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        role="progressbar"
                        aria-valuenow={item.count}
                        aria-valuemin={0}
                        aria-valuemax={maxCourtCount}
                        aria-label={`${item.court}: ${item.count} precedentes`}
                        className="h-full bg-slate-700 rounded-full"
                        style={{ width: `${(item.count / maxCourtCount) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Volume by Legal Area */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-semibold mb-4">Por Área Legal</h3>
              <div className="space-y-2">
                {analytics.volume_by_legal_area.map((item) => (
                  <div
                    key={item.legal_area}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <span className="text-sm font-medium capitalize">
                      {item.legal_area}
                    </span>
                    <span className="text-sm text-slate-600">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Top Ponentes */}
          {analytics.top_ponentes.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-semibold mb-4">Ministros más Activos</h3>
              <div className="flex flex-wrap gap-2">
                {analytics.top_ponentes.slice(0, 10).map((item) => (
                  <span
                    key={item.ponente}
                    className="px-3 py-1.5 bg-slate-100 rounded-full text-sm"
                  >
                    {item.ponente} ({item.count})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Top Voces */}
          {analytics.top_voces.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-semibold mb-4">Temas Más Frecuentes</h3>
              <div className="flex flex-wrap gap-2">
                {analytics.top_voces.slice(0, 15).map((item) => (
                  <span
                    key={item.voice}
                    className="px-3 py-1.5 bg-purple-50 text-purple-700 rounded-full text-sm"
                  >
                    {item.voice} ({item.count})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Court × Matter Heatmap */}
          {analytics.court_matter_heatmap.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-semibold mb-4">Especialización por Tribunal</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th scope="col" className="text-left py-2 px-3 font-medium">Tribunal</th>
                      {analytics.volume_by_legal_area.slice(0, 6).map((area) => (
                        <th key={area.legal_area} scope="col" className="py-2 px-3 font-medium text-center">
                          {area.legal_area}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.volume_by_court.slice(0, 8).map((court) => {
                      const courtData = analytics.court_matter_heatmap.filter(
                        (h) => h.court === court.court
                      );
                      const maxCount = Math.max(
                        ...courtData.map((d) => d.count),
                        1
                      );
                      return (
                        <tr key={court.court} className="border-t">
                          <th scope="row" className="py-2 px-3 truncate max-w-[200px] text-left font-normal">
                            {court.court}
                          </th>
                          {analytics.volume_by_legal_area.slice(0, 6).map((area) => {
                            const cell = courtData.find(
                              (h) => h.legal_area === area.legal_area
                            );
                            const count = cell?.count || 0;
                            const intensity = count / maxCount;
                            return (
                              <td
                                key={area.legal_area}
                                className="py-2 px-3 text-center"
                                aria-label={`${court.court}, ${area.legal_area}: ${count} casos`}
                              >
                                <span
                                  className="inline-block w-8 h-8 rounded flex items-center justify-center text-xs"
                                  style={{
                                    backgroundColor: `rgba(59, 130, 246, ${intensity * 0.8 + 0.1})`,
                                    color: intensity > 0.5 ? "white" : "gray-700",
                                  }}
                                  aria-hidden="true"
                                >
                                  {count}
                                </span>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Temporal Evolution */}
          {Object.keys(analytics.temporal_evolution).length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-semibold mb-4">Evolución Temporal por Área</h3>
              <div className="space-y-4">
                {analytics.volume_by_legal_area.slice(0, 5).map((area) => {
                  const data = analytics.temporal_evolution[area.legal_area] || [];
                  const maxCount = Math.max(...data.map((d) => d.count), 1);
                  return (
                    <div key={area.legal_area}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium capitalize">{area.legal_area}</span>
                      </div>
                      <div className="flex items-end gap-1 h-20">
                        {data.map((item) => (
                          <div
                            key={item.year}
                            className="flex-1 flex flex-col items-center"
                          >
                            <div
                              className="w-full bg-sky-500 rounded-t"
                              style={{
                                height: `${(item.count / maxCount) * 100}%`,
                                minHeight: item.count > 0 ? "2px" : "0",
                              }}
                            />
                            <span className="text-xs text-gray-400 mt-0.5">
                              {item.year}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Text Analysis */}
          {includeTextAnalysis &&
            analytics.text_analysis?.top_keywords?.length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="font-semibold mb-4">Palabras Clave en Decisiones</h3>
                <div className="flex flex-wrap gap-2">
                  {analytics.text_analysis.top_keywords.slice(0, 25).map((item) => (
                    <span
                      key={item.word}
                      className="px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-full text-sm"
                    >
                      {item.word} ({(item.frequency * 100).toFixed(1)}%)
                    </span>
                  ))}
                </div>
              </div>
            )}
        </>
      )}
    </div>
  );
}
