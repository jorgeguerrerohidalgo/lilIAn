"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

// Persisted shape in localStorage. We avoid sending anything to the
// server until the user opts in — strictly necessary cookies (auth
// token, CSRF) are set by the backend regardless and don't appear here.
type ConsentState = {
  /** True once the user has interacted with the banner (even to reject). */
  decided: boolean;
  /** Map of scope -> granted. Only opted-in scopes appear here. */
  scopes: Record<string, boolean>;
};

const STORAGE_KEY = "lilian.cookie-consent.v1";

const SCOPE_LABELS: Record<string, { title: string; description: string }> = {
  analytics: {
    title: "Analítica",
    description: "Métricas agregadas y seudonimizadas que nos ayudan a mejorar la plataforma.",
  },
};

function readState(): ConsentState {
  if (typeof window === "undefined") return { decided: false, scopes: {} };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { decided: false, scopes: {} };
    return JSON.parse(raw) as ConsentState;
  } catch {
    return { decided: false, scopes: {} };
  }
}

function writeState(next: ConsentState) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // LocalStorage may be disabled (private mode). Silent fail — the
    // banner reappears next visit, which is harmless.
  }
}

/**
 * Ley 21.719 / GDPR-aligned cookie consent banner.
 *
 * Strictly necessary cookies (auth, CSRF, theme) are always on and not
 * shown here. Anything analytics/marketing-related is opt-in.
 *
 * Renders nothing on the server to avoid hydration mismatch.
 */
export function CookieBanner() {
  const [state, setState] = useState<ConsentState | null>(null);
  const [showCustomize, setShowCustomize] = useState(false);

  useEffect(() => {
    setState(readState());
  }, []);

  // Don't render until we know the user's preference (avoids flash on
  // returning visitors who already decided).
  if (!state || state.decided) return null;

  const acceptAll = () => {
    const next: ConsentState = {
      decided: true,
      scopes: Object.fromEntries(Object.keys(SCOPE_LABELS).map((k) => [k, true])),
    };
    writeState(next);
    setState(next);
  };

  const rejectAll = () => {
    const next: ConsentState = { decided: true, scopes: {} };
    writeState(next);
    setState(next);
  };

  const saveCustom = (scopes: Record<string, boolean>) => {
    const next: ConsentState = { decided: true, scopes };
    writeState(next);
    setState(next);
    setShowCustomize(false);
  };

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label="Consentimiento de cookies"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-ink/10 bg-surface shadow-[0_-8px_24px_rgba(15,23,42,0.08)]"
    >
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 sm:py-5">
        {!showCustomize ? (
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
            <div className="flex-1 text-sm text-ink/80 leading-relaxed">
              <strong className="font-semibold text-ink">Usamos cookies para mejorar lilIAn.</strong>{" "}
              Las cookies estrictamente necesarias (sesión, seguridad) están siempre activas y no
              requieren consentimiento. Las cookies de analítica solo se activan si las aceptas.{" "}
              <Link href="/legal/cookies" className="text-coral font-semibold underline">
                Más información
              </Link>
              .
            </div>
            <div className="flex flex-wrap gap-2 sm:shrink-0">
              <button
                type="button"
                onClick={() => setShowCustomize(true)}
                className="px-3 py-2 text-sm font-semibold text-ink/70 hover:text-ink hover:bg-soft rounded-lg transition-colors"
              >
                Configurar
              </button>
              <button
                type="button"
                onClick={rejectAll}
                className="px-3 py-2 text-sm font-semibold text-ink border border-ink/20 hover:bg-soft rounded-lg transition-colors"
              >
                Rechazar no esenciales
              </button>
              <button
                type="button"
                onClick={acceptAll}
                className="px-4 py-2 text-sm font-semibold text-white bg-coral hover:bg-coral-dark rounded-lg transition-colors"
              >
                Aceptar todo
              </button>
            </div>
          </div>
        ) : (
          <CustomizePanel
            initialScopes={state.scopes}
            onCancel={() => setShowCustomize(false)}
            onSave={saveCustom}
          />
        )}
      </div>
    </div>
  );
}

function CustomizePanel({
  initialScopes,
  onCancel,
  onSave,
}: {
  initialScopes: Record<string, boolean>;
  onCancel: () => void;
  onSave: (scopes: Record<string, boolean>) => void;
}) {
  const [scopes, setScopes] = useState<Record<string, boolean>>(initialScopes);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-ink">Configura tu consentimiento</h2>
        <p className="text-xs text-ink/60 mt-1">
          Activa o desactiva cada categoría. Las cookies estrictamente necesarias no se pueden
          desactivar porque la plataforma no funciona sin ellas.
        </p>
      </div>
      <ul className="space-y-2">
        {Object.entries(SCOPE_LABELS).map(([key, meta]) => (
          <li key={key} className="flex items-start gap-3 p-3 border border-ink/10 rounded-lg">
            <input
              id={`cookie-scope-${key}`}
              type="checkbox"
              checked={!!scopes[key]}
              onChange={(e) => setScopes((prev) => ({ ...prev, [key]: e.target.checked }))}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-ink/30 text-coral focus:ring-coral/40"
            />
            <label htmlFor={`cookie-scope-${key}`} className="text-sm text-ink/80 leading-snug cursor-pointer">
              <strong className="font-semibold text-ink">{meta.title}</strong>
              <br />
              <span className="text-ink/60">{meta.description}</span>
            </label>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2 justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-2 text-sm font-semibold text-ink/70 hover:text-ink hover:bg-soft rounded-lg transition-colors"
        >
          Volver
        </button>
        <button
          type="button"
          onClick={() => onSave(scopes)}
          className="px-4 py-2 text-sm font-semibold text-white bg-coral hover:bg-coral-dark rounded-lg transition-colors"
        >
          Guardar preferencias
        </button>
      </div>
    </div>
  );
}
