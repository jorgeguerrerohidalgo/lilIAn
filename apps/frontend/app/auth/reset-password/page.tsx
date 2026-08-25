"use client";

/**
 * /auth/reset-password — Fase 2d.
 *
 * Public page that completes the password-recovery flow. Reads
 * ``?token=…`` from the URL and POSTs { token, new_password } to
 * /api/v1/auth/reset-password.
 *
 * Error model:
 *   - missing token → renders the "invalid link" state immediately.
 *   - 400 / 410 from the backend (token expired, already used, unknown)
 *     → renders the same "invalid link" state with a CTA to request a
 *     new one. We don't distinguish the failure modes on purpose so an
 *     attacker can't probe token validity.
 *
 * useSearchParams() requires a Suspense boundary at the page-export
 * level, so the actual form lives in <ResetPasswordForm /> and the
 * default export wraps it.
 */

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";
import { Input } from "@/components/ui";
import { useToast } from "@/lib/toast";
import { passwordSchema } from "@/lib/validators";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { show: showToast } = useToast();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<{
    newPassword?: string;
    confirmPassword?: string;
    form?: string;
  }>({});
  const [submitting, setSubmitting] = useState(false);
  // Success state — after a valid reset we show a confirmation screen
  // and bounce to /auth/login with a friendly message.
  const [completed, setCompleted] = useState(false);

  // -----------------------------------------------------------------
  // Submit — POST /auth/reset-password
  // -----------------------------------------------------------------
  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});

    if (!token) {
      setErrors({ form: "Link inválido. Solicita uno nuevo desde la página de recuperación." });
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrors({ confirmPassword: "Las contraseñas no coinciden" });
      return;
    }

    // Reuse the same Zod schema as register to mirror the backend's
    // _validate_password_strength rules.
    const parsed = passwordSchema.safeParse(newPassword);
    if (!parsed.success) {
      const firstIssue = parsed.error.issues[0]?.message ?? "Contraseña inválida.";
      setErrors({ newPassword: firstIssue });
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/v1/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail =
          typeof data?.detail === "string"
            ? data.detail
            : "No pudimos restablecer tu contraseña.";
        throw new Error(detail);
      }

      setCompleted(true);
      showToast({
        tone: "success",
        title: "Contraseña restablecida",
        body: "Ya puedes iniciar sesión con tu nueva contraseña.",
      });
      // Bounce to login after a short pause so the user sees the toast.
      window.setTimeout(() => {
        router.push("/auth/login?reset=1");
      }, 1500);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No pudimos restablecer tu contraseña.";
      setErrors({ form: message });
      showToast({ tone: "error", title: "Error", body: message });
    } finally {
      setSubmitting(false);
    }
  }

  // -----------------------------------------------------------------
  // Invalid token — no token in the URL.
  // -----------------------------------------------------------------
  if (!token) {
    return (
      <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center p-4">
        <Card className="w-full max-w-md p-8">
          <div className="text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-coral-pale border border-coral/20 flex items-center justify-center mb-5">
              <svg
                aria-hidden="true"
                className="w-6 h-6 text-coral-dark"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
            </div>
            <h1 className="text-2xl font-heading font-bold text-ink">Link inválido</h1>
            <p className="text-ink/60 mt-3">
              Este enlace de recuperación no es válido. Pega la URL completa del correo o solicita uno nuevo.
            </p>
            <div className="mt-8 space-y-3">
              <Link
                href="/auth/forgot-password"
                className="block w-full py-3 rounded-xl bg-ink text-white font-semibold hover:bg-ink/90"
              >
                Solicitar nuevo link
              </Link>
              <Link
                href="/auth/login"
                className="block w-full py-3 rounded-xl border border-ink/20 text-ink font-semibold hover:bg-ink/5"
              >
                Volver a iniciar sesión
              </Link>
            </div>
          </div>
        </Card>
      </main>
    );
  }

  // -----------------------------------------------------------------
  // Success — show a friendly confirmation while we route to /login.
  // -----------------------------------------------------------------
  if (completed) {
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
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <h1 className="text-2xl font-heading font-bold text-ink">Contraseña restablecida</h1>
            <p className="text-ink/60 mt-3">
              Te estamos llevando al inicio de sesión para que entres con tu nueva contraseña.
            </p>
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
          <h2 className="text-2xl font-heading font-bold text-ink">Crear nueva contraseña</h2>
          <p className="text-ink/60 mt-2">
            Elige una contraseña con al menos 12 caracteres, mayúscula, minúscula, número y símbolo.
          </p>
        </div>

        {errors.form && (
          <div
            id="reset-form-error"
            role="alert"
            aria-live="assertive"
            className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl mb-6 text-sm"
          >
            {errors.form}
            {errors.form.includes("Token") || errors.form.includes("inv") || errors.form.includes("expir") ? (
              <div className="mt-2">
                <Link
                  href="/auth/forgot-password"
                  className="text-coral-dark underline font-semibold"
                >
                  ¿Solicitar nuevo link?
                </Link>
              </div>
            ) : null}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <Input
            label="Nueva contraseña"
            type="password"
            id="reset-new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Mínimo 12 caracteres, con mayúscula, número y símbolo"
            autoComplete="new-password"
            required
            aria-required="true"
            error={errors.newPassword}
            aria-invalid={errors.newPassword ? true : undefined}
          />

          <Input
            label="Confirmar contraseña"
            type="password"
            id="reset-confirm-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            required
            aria-required="true"
            error={errors.confirmPassword}
            aria-invalid={errors.confirmPassword ? true : undefined}
          />

          <Button type="submit" variant="primary" size="lg" loading={submitting} className="w-full">
            {submitting ? "Guardando..." : "Guardar nueva contraseña"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink/60">
          <Link href="/auth/login" className="text-coral font-semibold hover:text-coral-dark">
            Volver a iniciar sesión
          </Link>
        </p>
      </Card>
    </main>
  );
}

// useSearchParams() must be inside a Suspense boundary in App Router.
export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <main
          id="main-content"
          className="min-h-screen bg-soft flex items-center justify-center p-4"
        >
          <div className="text-ink/60">Cargando…</div>
        </main>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
