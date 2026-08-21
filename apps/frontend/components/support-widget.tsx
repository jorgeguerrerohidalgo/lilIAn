"use client";

/**
 * SupportWidget — S6.5.
 *
 * Floating chat bubble in the bottom-right (Intercom/Crisp pattern).
 * Opens a small panel with a "Contactar soporte" form (subject + body),
 * pre-fills the email from the currently authenticated user, and POSTs
 * to ``/api/v1/support/tickets``. On success shows the
 * "Recibido, te contactaremos en 24h" toast and clears the form.
 *
 * Dismissable: clicking the X collapses the widget; reopening re-shows
 * the bubble. The collapsed state is held in ``sessionStorage`` so the
 * widget doesn't keep re-popping during a single session, but a fresh
 * tab/session will show it again — which is what we want for "live chat
 * is available".
 *
 * Why we don't try to do real-time chat here: out of scope for the
 * first cut. The form is enough for the "I need help" flow; we can
 * bolt on Intercom/Crisp later without changing this UI.
 */

import { useCallback, useEffect, useId, useState } from "react";
import { useToast } from "@/lib/toast";

const SESSION_DISMISS_KEY = "lilian.support-widget.dismissed";

export interface SupportWidgetProps {
  /** Pre-fills the email field when the user is signed in. */
  defaultEmail?: string;
  /** Override the bubble position (defaults to bottom-right). */
  position?: "bottom-right" | "bottom-left";
}

export function SupportWidget({
  defaultEmail = "",
  position = "bottom-right",
}: SupportWidgetProps) {
  const [open, setOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [email, setEmail] = useState(defaultEmail);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleId = useId();
  const { show: showToast } = useToast();

  // Hydrate session-level dismiss flag.
  useEffect(() => {
    setHydrated(true);
    try {
      setDismissed(window.sessionStorage.getItem(SESSION_DISMISS_KEY) === "true");
    } catch {
      // ignore
    }
  }, []);

  const persistDismiss = useCallback(() => {
    try {
      window.sessionStorage.setItem(SESSION_DISMISS_KEY, "true");
    } catch {
      // ignore
    }
  }, []);

  const closePanel = useCallback(() => {
    setOpen(false);
    setError(null);
  }, []);

  const handleOpen = useCallback(() => {
    setOpen(true);
    // If the user re-opens, allow it again within the same session.
    try {
      window.sessionStorage.removeItem(SESSION_DISMISS_KEY);
    } catch {
      // ignore
    }
    setDismissed(false);
  }, []);

  const handleDismissBubble = useCallback(() => {
    setDismissed(true);
    persistDismiss();
  }, [persistDismiss]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!subject.trim() || !body.trim() || !email.trim()) {
      setError("Completa todos los campos para enviar tu mensaje.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/v1/support/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject: subject.trim(),
          body: body.trim(),
          user_email: email.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = (data && (data.detail || data.message)) || "No pudimos enviar tu mensaje.";
        throw new Error(typeof detail === "string" ? detail : "No pudimos enviar tu mensaje.");
      }
      showToast({
        tone: "success",
        title: "Recibido, te contactaremos en 24h",
        body: "Nuestro equipo te responderá al correo que indicaste.",
      });
      setSubject("");
      setBody("");
      closePanel();
    } catch (err) {
      const message = err instanceof Error ? err.message : "No pudimos enviar tu mensaje.";
      setError(message);
      showToast({ tone: "error", title: "Error", body: message });
    } finally {
      setSubmitting(false);
    }
  }

  if (!hydrated) return null;

  // Position classes for the bubble + panel anchor.
  // We stack above the in-app chat widget (which lives at
  // ``bottom-6 right-6``) so they don't overlap when both are open.
  const positionClass = position === "bottom-right"
    ? "right-5 bottom-24"
    : "left-5 bottom-5";

  if (dismissed) return null;

  return (
    <div
      className={`fixed z-40 ${positionClass}`}
      data-support-widget
    >
      {open ? (
        <div
          role="dialog"
          aria-modal="false"
          aria-labelledby={titleId}
          className="w-[360px] max-w-[calc(100vw-2.5rem)] rounded-2xl bg-white shadow-2xl border border-slate-200 flex flex-col"
          style={{ maxHeight: "min(560px, calc(100vh - 6rem))" }}
        >
          <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-2 bg-indigo-600 text-white rounded-t-2xl">
            <div>
              <h2 id={titleId} className="text-sm font-semibold">
                Soporte de Lilian
              </h2>
              <p className="text-xs text-indigo-100 mt-0.5">
                Te respondemos en menos de 24h.
              </p>
            </div>
            <button
              type="button"
              onClick={closePanel}
              aria-label="Cerrar soporte"
              className="rounded-md p-1 text-indigo-100 hover:bg-indigo-500 hover:text-white"
            >
              <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3 p-4 overflow-y-auto">
            <div>
              <label htmlFor="support-email" className="block text-xs font-medium text-slate-700 mb-1">
                Tu correo
              </label>
              <input
                id="support-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@correo.cl"
                disabled={submitting}
                className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="support-subject" className="block text-xs font-medium text-slate-700 mb-1">
                Asunto
              </label>
              <input
                id="support-subject"
                type="text"
                required
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="¿En qué te ayudamos?"
                disabled={submitting}
                className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="support-body" className="block text-xs font-medium text-slate-700 mb-1">
                Mensaje
              </label>
              <textarea
                id="support-body"
                required
                rows={4}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Cuéntanos con detalle qué necesitas."
                disabled={submitting}
                className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none resize-none"
              />
            </div>

            {error && (
              <div role="alert" className="rounded-md bg-red-50 border border-red-200 px-2 py-1 text-xs text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              aria-busy={submitting}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {submitting ? "Enviando…" : "Enviar mensaje"}
            </button>

            <button
              type="button"
              onClick={handleDismissBubble}
              className="text-xs text-slate-500 hover:text-slate-700 self-center"
            >
              No volver a mostrar en esta sesión
            </button>
          </form>
        </div>
      ) : (
        <button
          type="button"
          onClick={handleOpen}
          aria-label="Abrir chat de soporte"
          className="flex items-center gap-2 rounded-full bg-indigo-600 text-white px-4 py-3 shadow-lg hover:bg-indigo-700 hover:shadow-xl transition-all"
        >
          <ChatIcon />
          <span className="text-sm font-semibold">Contactar soporte</span>
        </button>
      )}
    </div>
  );
}

function ChatIcon() {
  return (
    <svg aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4 1.5c.621 0 1.125-.504 1.125-1.125S12.871 9 12.25 9 11.125 9.504 11.125 10.125 11.629 11.25 12.25 11.25zm0 0h.008m-4.5 4.5h7.5m-7.5 3h7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
