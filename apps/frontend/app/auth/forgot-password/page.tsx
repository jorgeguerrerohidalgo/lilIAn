"use client";

/**
 * /auth/forgot-password — Fase 2d.
 *
 * Public page: collects an email and POSTs to /api/v1/auth/forgot-password.
 * The backend always answers 202 (never reveals whether the address is
 * registered), so the UI also intentionally shows the same neutral
 * success message regardless of the response. The only thing the user
 * sees on success is a confirmation panel + a link back to /auth/login.
 *
 * No auth required — sits in the /(public)/auth tree.
 */

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";
import { Input } from "@/components/ui";
import { useToast } from "@/lib/toast";

export default function ForgotPasswordPage() {
  const { show: showToast } = useToast();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError("Ingresa tu correo electrónico.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/v1/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
        credentials: "include",
      });

      // The endpoint returns 202 even when the email is unknown — that's
      // the point of this flow. Treat any 2xx as success; surface non-2xx
      // (e.g. 429 rate-limit) so the user knows something went wrong.
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = typeof data?.detail === "string" ? data.detail : "No pudimos procesar tu solicitud.";
        throw new Error(detail);
      }

      setSubmitted(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No pudimos procesar tu solicitud.";
      setError(message);
      showToast({ tone: "error", title: "Error", body: message });
    } finally {
      setSubmitting(false);
    }
  }

  // -----------------------------------------------------------------
  // Confirmation panel — shown after a successful submit. We always
  // render the same neutral copy so an attacker can't infer which
  // emails are registered based on the response.
  // -----------------------------------------------------------------
  if (submitted) {
    return (
      <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center p-4">
        <Card className="w-full max-w-md p-8">
          <div className="text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center mb-5">
              <svg
                aria-hidden="true"
                className="w-6 h-6 text-emerald-700"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h1 className="text-2xl font-heading font-bold text-ink">Revisa tu correo</h1>
            <p className="text-ink/60 mt-3">
              Si el email está registrado, recibirás un link en los próximos minutos.
            </p>
            <p className="text-ink/60 mt-2 text-sm">
              Si no llega, revisa tu carpeta de spam o intenta nuevamente.
            </p>
            <div className="mt-8 space-y-3">
              <Link
                href="/auth/login"
                className="block w-full py-3 rounded-xl bg-ink text-white font-semibold hover:bg-ink/90"
              >
                Volver a iniciar sesión
              </Link>
              <button
                type="button"
                onClick={() => {
                  setSubmitted(false);
                  setEmail("");
                }}
                className="block w-full py-3 rounded-xl border border-ink/20 text-ink font-semibold hover:bg-ink/5"
              >
                Enviar otro correo
              </button>
            </div>
          </div>
        </Card>
      </main>
    );
  }

  return (
    <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
              <span className="text-2xl font-heading font-bold text-white">L</span>
            </div>
            <div className="text-left">
              <h1 className="text-2xl font-heading font-bold text-ink tracking-tight">
                lil<span className="text-coral">I</span>An
              </h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">Legal AI</p>
            </div>
          </div>
          <h2 className="text-2xl font-heading font-bold text-ink">Recuperar contraseña</h2>
          <p className="text-ink/60 mt-2">
            Te enviaremos un link para restablecer tu contraseña
          </p>
        </div>

        {error && (
          <div
            id="forgot-form-error"
            role="alert"
            aria-live="assertive"
            className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl mb-6 text-sm"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <Input
            label="Email"
            type="email"
            id="forgot-email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@email.com"
            autoComplete="email"
            required
            aria-required="true"
            aria-describedby={error ? "forgot-form-error" : undefined}
            aria-invalid={error ? true : undefined}
          />

          <Button type="submit" variant="primary" size="lg" loading={submitting} className="w-full">
            {submitting ? "Enviando..." : "Enviar link de recuperación"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink/60">
          ¿Recordaste tu contraseña?{" "}
          <Link href="/auth/login" className="text-coral font-semibold hover:text-coral-dark">
            Inicia sesión
          </Link>
        </p>
      </Card>
    </main>
  );
}
