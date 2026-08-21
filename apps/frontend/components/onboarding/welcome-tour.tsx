"use client";

/**
 * WelcomeTour — S1.2.
 *
 * A 3-step first-run overlay for new users. Pure CSS-only positioning
 * (no external tooltip library) — three portal-rendered cards highlight
 * the relevant UI areas one at a time:
 *
 *   1. "Sube un contrato"        → apunta a /matters/new
 *   2. "Pulsa Analizar"           → apunta a la pestaña Documentos de un caso
 *   3. "Revisa tu reporte"        → apunta a la pestaña Análisis IA
 *
 * Persistence: a single boolean is recorded in localStorage under the
 * "lilian.welcomeTour.completed" key. Render is gated on:
 *   - key present in localStorage as "false", OR
 *   - never set
 * Re-completing the tour (clicking "Saltar tour") sets it to "true",
 * which permanently suppresses the overlay across all subsequent visits.
 *
 * Why a portal: the highlights span the sidebar and the page header.
 * Using createPortal lets the overlay render in document.body without
 * fighting with parent z-index / overflow.
 *
 * Why CSS-only (no library): saves a dependency, fits within the
 * "no new heavy deps" Sprint 1 constraint.
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

const STORAGE_KEY = "lilian.welcomeTour.completed";

interface Step {
  id: number;
  /** Spanish title shown above the body. */
  title: string;
  /** Spanish description. Keep under ~140 chars per card. */
  body: string;
  /** Short label rendered in the step header breadcrumb. */
  breadcrumb: string;
  /**
   * Anchor hint. The tour renders a soft highlight rectangle by reading
   * the bounding rect of `data-tour-target` elements via CSS — when
   * the target doesn't exist yet (e.g. the user is on /dashboard and we
   * want to point at a matter sub-route), we fall back to a centred
   * "open this page" card.
   */
  targetSelector?: string;
  /**
   * If the target element isn't on the current page, we render a
   * centred card with this CTA link so the user can navigate.
   */
  cta?: { href: string; label: string };
}

const STEPS: Step[] = [
  {
    id: 1,
    breadcrumb: "Paso 1 de 3",
    title: "Sube un contrato",
    body:
      "Crea un caso y arrastra tu PDF o DOCX. La IA extrae cláusulas, fechas y partes automáticamente.",
    targetSelector: '[data-tour-target="new-matter"]',
    cta: { href: "/matters/new", label: "Crear mi primer caso" },
  },
  {
    id: 2,
    breadcrumb: "Paso 2 de 3",
    title: "Pulsa Analizar",
    body:
      "Una vez subido el documento, abre la pestaña «Documentos» del caso y lanza el análisis con un clic.",
    targetSelector: '[data-tour-target="matters-list"]',
    cta: { href: "/matters", label: "Ver mis casos" },
  },
  {
    id: 3,
    breadcrumb: "Paso 3 de 3",
    title: "Revisa tu reporte",
    body:
      "Riesgos, plazos y referencias legales quedan listos en la pestaña «Análisis IA». Puedes exportar el reporte a PDF.",
    targetSelector: '[data-tour-target="report-area"]',
    cta: { href: "/precedents", label: "Explorar reportes" },
  },
];

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

function readTargetRect(selector: string | undefined): Rect | null {
  if (!selector || typeof document === "undefined") return null;
  const el = document.querySelector(selector);
  if (!(el instanceof HTMLElement)) return null;
  const r = el.getBoundingClientRect();
  // Reject elements not currently visible (zero size / off-screen) so
  // the fallback centered card is used instead of a phantom rect.
  if (r.width < 12 || r.height < 12) return null;
  if (r.bottom < 0 || r.right < 0) return null;
  return {
    top: r.top + window.scrollY,
    left: r.left + window.scrollX,
    width: r.width,
    height: r.height,
  };
}

export function useWelcomeTourAutoStart() {
  /** Hook for the consuming layout to know whether the tour is currently
   *  active — useful if you want to disable nav, but not required.
   */
  return useWelcomeTourState().active;
}

interface TourState {
  active: boolean;
  step: number;
  show: () => void;
  dismiss: () => void;
  finish: () => void;
  next: () => void;
  back: () => void;
  stepData: Step | null;
  targetRect: Rect | null;
}

export function useWelcomeTourState(): TourState {
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);
  const [targetRect, setTargetRect] = useState<Rect | null>(null);

  // Auto-start: read localStorage on mount and seed an initial localStorage
  // entry so the date of first visit is recoverable in the future.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const completed = window.localStorage.getItem(STORAGE_KEY);
    if (!completed) {
      // First visit ever — show the tour.
      window.localStorage.setItem(STORAGE_KEY, "false");
      setActive(true);
      setStep(0);
    }
  }, []);

  // Re-read the target rect whenever the step changes or the layout
  // shifts (e.g. a webfont swap, sidebar hover expanding). We use rAF
  // + a resize listener so the highlight stays glued to the target.
  useEffect(() => {
    if (!active) {
      setTargetRect(null);
      return;
    }
    const measure = () => {
      const data = STEPS[step] ?? null;
      setTargetRect(readTargetRect(data?.targetSelector));
    };
    measure();
    let raf = requestAnimationFrame(measure);
    const onResize = () => {
      raf = requestAnimationFrame(measure);
    };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [active, step]);

  const finish = () => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, "true");
    }
    setActive(false);
  };

  const show = () => {
    setStep(0);
    setActive(true);
  };

  const next = () => {
    if (step < STEPS.length - 1) {
      setStep((s) => s + 1);
    } else {
      finish();
    }
  };

  const back = () => {
    setStep((s) => Math.max(0, s - 1));
  };

  return {
    active,
    step,
    show,
    dismiss: finish,
    finish,
    next,
    back,
    stepData: active ? STEPS[step] ?? null : null,
    targetRect,
  };
}

/**
 * WelcomeTourOverlay
 *
 * Render the tour card itself. Render this from inside DashboardLayout
 * (or any layout that knows the user is authenticated). The overlay
 * uses createPortal to mount at document.body, escaping any parent's
 * z-index / overflow stack.
 */
export function WelcomeTourOverlay({ state }: { state: TourState }) {
  const { active, stepData, targetRect, next, back, finish } = state;
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Only render on the client — createPortal needs document.body.
  if (!mounted || !active || !stepData) return null;

  const isLast = stepData.id === STEPS.length;

  // Position the card directly under the highlighted target when we
  // have a rect; otherwise pin it centred on the viewport with a
  // larger card that includes a navigation CTA.
  const cardPositionStyle: React.CSSProperties = targetRect
    ? {
        top: Math.max(16, targetRect.top + targetRect.height + 16),
        left: Math.max(16, targetRect.left),
        maxWidth: 360,
      }
    : {
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        maxWidth: 420,
      };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={`tour-step-${stepData.id}-title`}
      className="fixed inset-0 z-[1000]"
    >
      {/* Scrim with a punched-out highlight. The cut-out uses
          box-shadow negative spread (the largest single-DOM, no-SVG
          way to carve a hole) so keyboard tab still works inside the
          highlighted area below the dialog. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-ink/60"
        style={
          targetRect
            ? {
                clipPath: `polygon(
                  0 0, 100% 0, 100% 100%, 0 100%, 0 0,
                  ${targetRect.left}px ${targetRect.top}px,
                  ${targetRect.left + targetRect.width}px ${targetRect.top}px,
                  ${targetRect.left + targetRect.width}px ${targetRect.top + targetRect.height}px,
                  ${targetRect.left}px ${targetRect.top + targetRect.height}px,
                  ${targetRect.left}px ${targetRect.top}px
                )`,
              }
            : undefined
        }
      />

      {/* Highlight ring around the target — purely decorative. */}
      {targetRect && (
        <div
          aria-hidden="true"
          className="absolute rounded-2xl ring-4 ring-coral pointer-events-none"
          style={{
            top: targetRect.top - 6,
            left: targetRect.left - 6,
            width: targetRect.width + 12,
            height: targetRect.height + 12,
          }}
        />
      )}

      {/* Card */}
      <div
        className="absolute rounded-2xl bg-white shadow-2xl border border-border p-6"
        style={cardPositionStyle}
      >
        <p className="text-xs font-bold uppercase tracking-widest text-coral">
          {stepData.breadcrumb}
        </p>
        <h3
          id={`tour-step-${stepData.id}-title`}
          className="mt-1 text-xl font-heading font-bold text-ink"
        >
          {stepData.title}
        </h3>
        <p className="mt-3 text-sm text-ink/70 leading-relaxed">
          {stepData.body}
        </p>

        {/* When the highlighted target isn't on the current page,
            surface a navigation CTA — otherwise the user gets a polite
            intro without a clickable next step. */}
        {stepData.cta && (
          <a
            href={stepData.cta.href}
            className="mt-5 block w-full text-center rounded-xl bg-ink text-white py-2.5 text-sm font-semibold hover:bg-ink/90"
          >
            {stepData.cta.label}
          </a>
        )}

        <div className="mt-6 flex items-center justify-between">
          <button
            type="button"
            onClick={finish}
            className="text-sm text-ink/50 hover:text-ink underline-offset-2 hover:underline"
          >
            Saltar tour
          </button>
          <div className="flex items-center gap-2">
            {stepData.id > 1 && (
              <button
                type="button"
                onClick={back}
                className="rounded-xl border border-border px-3 py-2 text-sm font-semibold text-ink/70 hover:bg-soft"
              >
                Atrás
              </button>
            )}
            <button
              type="button"
              onClick={next}
              className="rounded-xl bg-coral px-4 py-2 text-sm font-semibold text-white hover:bg-coral-dark"
            >
              {isLast ? "Ir a la app" : "Siguiente"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/**
 * WelcomeTour — convenience composition that bundles useState + overlay.
 *
 * Most callers should use this rather than the bare state hook + overlay.
 * Example:
 *
 *   const tour = useWelcomeTour();
 *   return (
 *     <>
 *       <main>{children}</main>
 *       <WelcomeTourOverlay state={tour} />
 *     </>
 *   );
 */
export function useWelcomeTour(): TourState {
  return useWelcomeTourState();
}

export const __TEST_ONLY__ = { STORAGE_KEY, STEPS };
