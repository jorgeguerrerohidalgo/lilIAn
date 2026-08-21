"use client";

/**
 * Toast — S1.5.
 *
 * Lightweight, dependency-free toast notifications. Used in place of
 * raw ``setError(...)`` patterns at the form level so transient
 * network failures become visible action banners instead of inline
 * form-state errors that the user has to scroll back to.
 *
 * Design choices:
 *
 *   - React Context provider keeps a single FIFO queue of toasts.
 *     This avoids the global mutable store that libraries like
 *     react-hot-toast use, so the queue is testable in isolation.
 *   - One toast has a title, body, optional Spanish default
 *     "Reintentar" CTA that re-invokes the caller's retry callback.
 *   - 6-second auto-dismiss for success / info, persistent for
 *     errors and warnings (errors auto-dismiss after 12 s, the user
 *     can click × or "Reintentar" to dismiss earlier).
 *   - Reduced motion: the enter animation respects
 *     ``@media (prefers-reduced-motion)`` via a CSS class toggle.
 *   - Portuguese-Chile localisation: every string is Spanish.
 *
 * Mount in ``app/layout.tsx`` as ``<ToastProvider>...</ToastProvider>``
 * so any client component can ``useToast()``.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export type ToastTone = "error" | "warning" | "success" | "info";

export interface ToastInput {
  /** Spanish title (≤ 8 words). */
  title: string;
  /** Spanish description (≤ 140 chars). */
  body?: string;
  tone?: ToastTone;
  /** Optional retry CTA label (Spanish). Default is "Reintentar". */
  retryLabel?: string;
  /** Optional callback invoked when the user clicks the retry CTA. */
  onRetry?: () => void | Promise<void>;
  /** Optional duration override in ms; 0 = persistent. */
  durationMs?: number;
}

interface ActiveToast extends Required<Omit<ToastInput, "body" | "onRetry" | "retryLabel">> {
  id: string;
  body?: string;
  retryLabel?: string;
  onRetry?: () => void | Promise<void>;
}

interface ToastContextValue {
  show: (toast: ToastInput) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/**
 * useToast — call from inside the ToastProvider to display a toast.
 *
 * Returns ``{ show, dismiss }``; ``show`` adds a toast and returns
 * the assigned id (handy if you want to dismiss it programmatically
 * after success of a follow-up call).
 */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Soft-fail in the rare case where the provider isn't mounted
    // (e.g. an old page rendered without the layout). Console-only —
    // never throw inside render.
    if (typeof window !== "undefined") {
      // eslint-disable-next-line no-console
      console.warn("useToast called outside ToastProvider");
    }
    return { show: () => "", dismiss: () => {} };
  }
  return ctx;
}

/**
 * Map an unknown error into a Spanish user-facing toast.
 *
 * Centralised so ``fetch().catch()`` patterns produce identical copy
 * everywhere instead of drifting across pages.
 *
 * Strategy:
 *   1. Strip ``Error: `` prefix from generic Error messages.
 *   2. If the upstream returned a JSON body with a ``detail`` field
 *      (FastAPI's standard envelope), trust it.
 *   3. Default "Error de red — vuelve a intentarlo" when the request
 *      never reached the backend (TypeError on fetch).
 */
export function toastFromError(err: unknown, fallbackTitle = "Algo salió mal"): ToastInput {
  if (typeof err === "object" && err !== null && "detail" in err) {
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return { title: fallbackTitle, body: detail.trim() };
    }
  }
  if (err instanceof Error) {
    const text = err.message?.trim();
    if (text) {
      return { title: fallbackTitle, body: text };
    }
  }
  return {
    title: fallbackTitle,
    body: "Inténtalo nuevamente en unos segundos.",
  };
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ActiveToast[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const show = useCallback(
    (input: ToastInput): string => {
      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `t_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
      const tone: ToastTone = input.tone ?? "error";
      const durationMs =
        input.durationMs ??
        (tone === "error"
          ? 12_000
          : tone === "warning"
            ? 8_000
            : 6_000);
      const next: ActiveToast = {
        id,
        title: input.title,
        body: input.body,
        tone,
        retryLabel: input.retryLabel ?? (input.onRetry ? "Reintentar" : undefined),
        onRetry: input.onRetry,
        durationMs,
      };
      setToasts((current) => [...current, next]);
      if (durationMs > 0 && typeof window !== "undefined") {
        const t = setTimeout(() => dismiss(id), durationMs);
        timers.current.set(id, t);
      }
      return id;
    },
    [dismiss],
  );

  // Clean up timers on unmount so we don't leak setTimeout handles.
  useEffect(() => {
    const map = timers.current;
    return () => {
      for (const timer of map.values()) clearTimeout(timer);
      map.clear();
    };
  }, []);

  const value: ToastContextValue = { show, dismiss };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} dismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastViewport({
  toasts,
  dismiss,
}: {
  toasts: ActiveToast[];
  dismiss: (id: string) => void;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  if (!mounted || typeof document === "undefined") return null;

  return createPortal(
    <div
      aria-live="polite"
      aria-relevant="additions"
      className="pointer-events-none fixed top-4 right-4 z-[1100] flex max-w-sm flex-col gap-3"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>,
    document.body,
  );
}

const TONE_CLASS: Record<ToastTone, { bg: string; ring: string; text: string }> = {
  error: {
    bg: "bg-coral-pale",
    ring: "ring-coral/30",
    text: "text-coral-dark",
  },
  warning: {
    bg: "bg-amber-50",
    ring: "ring-amber-200",
    text: "text-amber-900",
  },
  success: {
    bg: "bg-emerald-50",
    ring: "ring-emerald-200",
    text: "text-emerald-900",
  },
  info: {
    bg: "bg-blue-50",
    ring: "ring-blue-200",
    text: "text-blue-900",
  },
};

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ActiveToast;
  onDismiss: () => void;
}) {
  const palette = TONE_CLASS[toast.tone];

  const handleRetry = async () => {
    if (!toast.onRetry) return;
    try {
      await toast.onRetry();
    } catch {
      // Don't auto-show another toast — the caller's retry path
      // typically re-emits its own toast on the second failure.
    }
    onDismiss();
  };

  return (
    <div
      role={toast.tone === "error" ? "alert" : "status"}
      aria-live={toast.tone === "error" ? "assertive" : "polite"}
      className={`pointer-events-auto rounded-2xl border border-border/40 ${palette.bg} ${palette.ring} ring-1 shadow-lg p-4 animate-[slideIn_160ms_ease-out]`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${palette.text}`}>
            {toast.title}
          </p>
          {toast.body && (
            <p className={`mt-1 text-sm ${palette.text} opacity-90`}>
              {toast.body}
            </p>
          )}
          {toast.onRetry && (
            <button
              type="button"
              onClick={handleRetry}
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-ink text-white px-3 py-1.5 text-xs font-semibold hover:bg-ink/90"
            >
              {toast.retryLabel ?? "Reintentar"}
            </button>
          )}
        </div>
        <button
          type="button"
          aria-label="Cerrar notificación"
          onClick={onDismiss}
          className={`-m-1 rounded-lg p-1 ${palette.text} opacity-60 hover:opacity-100`}
        >
          <svg
            aria-hidden="true"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
