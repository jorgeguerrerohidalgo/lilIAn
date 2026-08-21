"use client";

/**
 * SampleDataBanner — S4.2.
 *
 * Shown to tenants who haven't uploaded anything yet. Offers a
 * one-click way to load demo matters + documents so the user can
 * explore the platform before uploading real files.
 *
 * The banner is gated by:
 *   - The user is authenticated (parent component checks).
 *   - The user has zero matters (parent passes ``hasNoMatters``).
 *   - The user has not dismissed the banner today (localStorage key
 *     ``lilian.sample-data-banner.dismissed-at``).
 *
 * The seed is idempotent on the backend: if the user dismisses and
 * later clicks the button again, the server returns the existing
 * counts instead of duplicating rows.
 */

import { useEffect, useState } from "react";

interface SampleDataBannerProps {
  hasNoMatters: boolean;
  onSeeded?: () => void;
}

const STORAGE_KEY = "lilian.sample-data-banner.dismissed-at";

function wasDismissedRecently(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const dismissedAt = new Date(raw);
    if (Number.isNaN(dismissedAt.valueOf())) return false;
    // Hide for 24h after dismissal.
    const MS_24H = 24 * 60 * 60 * 1000;
    return Date.now() - dismissedAt.valueOf() < MS_24H;
  } catch {
    return false;
  }
}

export function SampleDataBanner({ hasNoMatters, onSeeded }: SampleDataBannerProps) {
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasNoMatters) {
      setVisible(false);
      return;
    }
    setVisible(!wasDismissedRecently());
  }, [hasNoMatters]);

  if (!visible) return null;

  const handleSeed = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/onboarding/sample-data", {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "No se pudieron cargar los datos de ejemplo");
        return;
      }
      setVisible(false);
      onSeeded?.();
    } catch {
      setError("Error de red al cargar los datos");
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, new Date().toISOString());
    } catch {
      // ignore quota / private-mode errors
    }
    setVisible(false);
  };

  return (
    <section
      role="region"
      aria-labelledby="sample-data-banner-title"
      className="rounded-lg border border-indigo-200 bg-gradient-to-br from-indigo-50 to-white p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <h2
            id="sample-data-banner-title"
            className="text-base font-semibold text-indigo-900"
          >
            ¿Quieres explorar antes de subir tus propios archivos?
          </h2>
          <p className="mt-1 text-sm text-indigo-700">
            Carga tres casos de ejemplo (arriendo, laboral y consumidor) con
            informes generados. Podrás revisarlos, ejecutar el chat y exportar
            a PDF igual que con un caso real.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSeed}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? "Cargando…" : "Cargar ejemplos"}
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            disabled={loading}
            className="rounded-lg border border-indigo-200 px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
            aria-label="Ocultar este mensaje"
          >
            Ahora no
          </button>
        </div>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-xs text-red-600">
          {error}
        </p>
      ) : null}
    </section>
  );
}
