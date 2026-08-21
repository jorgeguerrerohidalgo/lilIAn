"use client";

/**
 * InviteTeamModal — S6.3.
 *
 * Modal launched from the sidebar "Invitar a tu equipo" button. Collects
 * an email + role, POSTs to ``/api/v1/organizations/me/invitations``,
 * shows a success toast, and closes. On failure shows an error toast
 * with the human message.
 *
 * Why a portal: same reason as the welcome tour — the modal needs to
 * escape any parent stacking / overflow context and render on top of
 * the chat widget.
 *
 * Why controlled form: the form has three pieces of state (email,
 * role, submit-pending). Local ``useState`` is the simplest fit; no
 * React-Hook-Form dep needed.
 */

import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { useToast } from "@/lib/toast";

export interface InviteTeamModalProps {
  open: boolean;
  onClose: () => void;
  /** Optional inviter display name (otherwise pulled from /me). */
  inviterName?: string;
}

const ROLE_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: "LAWYER", label: "Abogado/a", description: "Acceso completo a casos y análisis." },
  { value: "ADMIN", label: "Administrador/a", description: "Puede invitar y gestionar el equipo." },
  { value: "COMPANY_USER", label: "Usuario/a de empresa", description: "Acceso a los casos compartidos con su organización." },
  { value: "VIEWER", label: "Solo lectura", description: "Puede revisar pero no modificar." },
];

export function InviteTeamModal({ open, onClose, inviterName }: InviteTeamModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("LAWYER");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleId = useId();
  const { show: showToast } = useToast();

  // Reset on open / close transitions.
  useEffect(() => {
    if (!open) {
      setError(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !submitting) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, submitting, onClose]);

  if (!open || typeof document === "undefined") return null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) {
      setError("Ingresa el correo de tu colega.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/v1/organizations/me/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), role }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = (data && (data.detail || data.message)) || "No pudimos enviar la invitación.";
        throw new Error(typeof detail === "string" ? detail : "No pudimos enviar la invitación.");
      }
      showToast({
        tone: "success",
        title: "Invitación enviada",
        body: `Le avisaremos a ${email} por correo.`,
      });
      setEmail("");
      setRole("LAWYER");
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "No pudimos enviar la invitación.";
      setError(message);
      showToast({ tone: "error", title: "Error", body: message });
    } finally {
      setSubmitting(false);
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-xl bg-white shadow-2xl">
        <div className="flex items-start justify-between px-6 pt-6 pb-2">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-slate-900">
              Invitar a tu equipo
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {inviterName
                ? `${inviterName} enviará una invitación por correo.`
                : "Enviaremos una invitación por correo."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Cerrar"
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <svg aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-6 pb-6 pt-2">
          <div>
            <label htmlFor="invite-email" className="block text-sm font-medium text-slate-700 mb-1">
              Correo electrónico
            </label>
            <input
              id="invite-email"
              type="email"
              required
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colega@bufete.cl"
              disabled={submitting}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="invite-role" className="block text-sm font-medium text-slate-700 mb-1">
              Rol
            </label>
            <select
              id="invite-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              disabled={submitting}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none"
            >
              {ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">
              {ROLE_OPTIONS.find((o) => o.value === role)?.description}
            </p>
          </div>

          {error && (
            <div role="alert" className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              aria-busy={submitting}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {submitting ? "Enviando…" : "Enviar invitación"}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
