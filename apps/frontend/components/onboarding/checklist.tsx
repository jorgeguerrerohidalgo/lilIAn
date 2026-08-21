"use client";

/**
 * OnboardingChecklist — S6.4.
 *
 * A persistent banner shown at the top of /dashboard until every item is
 * checked. State lives entirely in ``localStorage`` so the component is
 * idempotent on every navigation and survives page refresh without any
 * backend round-trip.
 *
 * Items map to the most common "first-session" actions we want every
 * new user to complete within their first session. Each item has a
 * manual ``markDone(key)`` helper the page can call when the user
 * actually does the action (we keep the marking client-driven because
 * the user's intent — "yes, I've done this" — is the only thing that
 * makes sense for onboarding).
 *
 * Completion celebration: when all six are checked we fire a one-time
 * "¡Listo, ya sabes usar Lilian!" toast and then collapse the panel so
 * it stops taking up prime real estate.
 *
 * Dismiss: the user can hide the panel any time via the X button. The
 * state is recorded so it stays hidden across reloads.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useToast } from "@/lib/toast";

const STORAGE_KEY = "lilian.onboarding.checklist.v1";
const DISMISS_KEY = "lilian.onboarding.checklist.dismissed";

export type ChecklistKey =
  | "uploadContract"
  | "runAnalysis"
  | "reviewDeadlines"
  | "askChat"
  | "exportPdf"
  | "inviteColleague";

export interface ChecklistState {
  uploadContract: boolean;
  runAnalysis: boolean;
  reviewDeadlines: boolean;
  askChat: boolean;
  exportPdf: boolean;
  inviteColleague: boolean;
}

const DEFAULT_STATE: ChecklistState = {
  uploadContract: false,
  runAnalysis: false,
  reviewDeadlines: false,
  askChat: false,
  exportPdf: false,
  inviteColleague: false,
};

interface Item {
  key: ChecklistKey;
  label: string;
  cta: { href: string; label: string };
}

const ITEMS: Item[] = [
  { key: "uploadContract", label: "Sube tu primer contrato", cta: { href: "/matters/new", label: "Subir" } },
  { key: "runAnalysis", label: "Ejecuta un análisis IA", cta: { href: "/matters", label: "Ir a mis casos" } },
  { key: "reviewDeadlines", label: "Revisa las alertas de plazos (Tiempos)", cta: { href: "/matters", label: "Ver plazos" } },
  { key: "askChat", label: "Haz una pregunta al chat", cta: { href: "/matters", label: "Abrir chat" } },
  { key: "exportPdf", label: "Exporta el informe como PDF", cta: { href: "/matters", label: "Ver informe" } },
  { key: "inviteColleague", label: "Invita a un colega", cta: { href: "#invite-team", label: "Invitar" } },
];

function loadState(): ChecklistState {
  if (typeof window === "undefined") return DEFAULT_STATE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    const parsed = JSON.parse(raw) as Partial<ChecklistState>;
    return { ...DEFAULT_STATE, ...parsed };
  } catch {
    return DEFAULT_STATE;
  }
}

function persistState(state: ChecklistState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    // Notify other tabs / components on the same page.
    window.dispatchEvent(new CustomEvent("lilian:checklist-updated", { detail: state }));
  } catch {
    // localStorage may be disabled — fail silently.
  }
}

function loadDismissed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(DISMISS_KEY) === "true";
  } catch {
    return false;
  }
}

function persistDismissed() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(DISMISS_KEY, "true");
  } catch {
    // ignore
  }
}

export function useOnboardingChecklist() {
  const [state, setState] = useState<ChecklistState>(DEFAULT_STATE);

  // Initial load + listen for cross-component updates.
  useEffect(() => {
    setState(loadState());
    function onUpdate(event: Event) {
      const detail = (event as CustomEvent<ChecklistState>).detail;
      if (detail) setState(detail);
    }
    function onStorage(event: StorageEvent) {
      if (event.key === STORAGE_KEY && event.newValue) {
        try {
          setState({ ...DEFAULT_STATE, ...JSON.parse(event.newValue) });
        } catch {
          // ignore
        }
      }
    }
    window.addEventListener("lilian:checklist-updated", onUpdate);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("lilian:checklist-updated", onUpdate);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const markDone = useCallback((key: ChecklistKey) => {
    setState((prev) => {
      if (prev[key]) return prev;
      const next = { ...prev, [key]: true };
      persistState(next);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setState(DEFAULT_STATE);
    persistState(DEFAULT_STATE);
  }, []);

  return { state, markDone, reset };
}

export interface OnboardingChecklistProps {
  /** Controlled state — optional. When omitted, the component owns its own state. */
  state?: ChecklistState;
  /** Controlled markDone — required when ``state`` is provided. */
  onMarkDone?: (key: ChecklistKey) => void;
}

export function OnboardingChecklist({ state: controlledState, onMarkDone }: OnboardingChecklistProps = {}) {
  const internal = useOnboardingChecklist();
  const { show: showToast } = useToast();
  const [dismissed, setDismissed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  // Hydration safety — we don't render anything on the server because
  // localStorage is browser-only.
  useEffect(() => {
    setHydrated(true);
    setDismissed(loadDismissed());
  }, []);

  const state = controlledState ?? internal.state;
  const markDone = onMarkDone ?? internal.markDone;
  const completedCount = useMemo(() => Object.values(state).filter(Boolean).length, [state]);
  const allDone = completedCount === ITEMS.length;

  // Celebration toast: fire exactly once when all six flip to true.
  useEffect(() => {
    if (!hydrated) return;
    if (!allDone) return;
    const flagKey = "lilian.onboarding.checklist.celebrated";
    let celebrated = false;
    try {
      celebrated = window.sessionStorage.getItem(flagKey) === "true";
    } catch {
      // ignore
    }
    if (celebrated) return;
    try {
      window.sessionStorage.setItem(flagKey, "true");
    } catch {
      // ignore
    }
    showToast({
      tone: "success",
      title: "¡Listo, ya sabes usar Lilian!",
      body: "Has completado los primeros pasos. Sigue explorando cuando quieras.",
    });
  }, [allDone, hydrated, showToast]);

  if (!hydrated) return null;
  if (dismissed) return null;

  return (
    <section
      aria-label="Lista de primeros pasos"
      data-onboarding-checklist
      className="rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-white p-5 shadow-sm"
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <h2 className="text-base font-semibold text-indigo-900">Primeros pasos con Lilian</h2>
          <p className="text-sm text-indigo-700/80 mt-1">
            Completa los {ITEMS.length} pasos para sacarle el máximo provecho. Progreso:{" "}
            <span className="font-semibold">{completedCount} / {ITEMS.length}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setDismissed(true);
              persistDismissed();
            }}
            aria-label="Cerrar lista de primeros pasos"
            className="rounded-md p-1 text-indigo-400 hover:bg-indigo-100 hover:text-indigo-700"
          >
            <svg aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full rounded-full bg-indigo-100 overflow-hidden mb-4" aria-hidden="true">
        <div
          className="h-full bg-indigo-500 transition-all duration-300 ease-out"
          style={{ width: `${(completedCount / ITEMS.length) * 100}%` }}
        />
      </div>

      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {ITEMS.map((item) => {
          const done = state[item.key];
          return (
            <li
              key={item.key}
              className={`flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors ${
                done
                  ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                  : "border-slate-200 bg-white text-slate-700 hover:border-indigo-300"
              }`}
            >
              <button
                type="button"
                onClick={() => markDone(item.key)}
                aria-pressed={done}
                aria-label={done ? `Desmarcar: ${item.label}` : `Marcar como hecho: ${item.label}`}
                className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
                  done
                    ? "border-emerald-500 bg-emerald-500 text-white"
                    : "border-slate-300 bg-white text-transparent hover:border-indigo-400"
                }`}
              >
                {done ? (
                  <svg aria-hidden="true" className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : null}
              </button>
              <div className="flex-1 min-w-0">
                <p className={`text-sm ${done ? "line-through opacity-70" : ""}`}>{item.label}</p>
              </div>
              {!done && (
                <Link
                  href={item.cta.href}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 whitespace-nowrap"
                >
                  {item.cta.label}
                </Link>
              )}
            </li>
          );
        })}
      </ul>

      {allDone && (
        <p className="mt-4 text-xs text-emerald-700">
          ¡Buen trabajo! Ya dominas el flujo principal de Lilian.
        </p>
      )}
    </section>
  );
}
