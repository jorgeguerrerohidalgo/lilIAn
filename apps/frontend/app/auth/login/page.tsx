"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui";
import { Input } from "@/components/ui";
import { Card } from "@/components/ui";
import { safeRedirect } from "@/lib/validators";
import { useToast } from "@/lib/toast";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // S5-fix: honor the `?next=` query param that the auth middleware
  // attaches when redirecting unauthenticated users. Falls back to
  // /dashboard. safeRedirect() rejects open-redirect attempts.
  const nextPath = safeRedirect(searchParams.get("next"), "/dashboard");
  // S1.1: support `?verify=<email>` so the link in the verification
  // email can land here with a one-click resend already primed.
  const verifyEmail = searchParams.get("verify");
  // S1.5: error toasts (Spanish, with Reintentar where it makes sense).
  const toast = useToast();
  const [email, setEmail] = useState(verifyEmail ?? "");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [loading, setLoading] = useState(false);
  // S1.1: when the backend returns 403 "verify your email", we show
  // a resend CTA inline so the user doesn't have to remember their
  // email to start the recovery flow.
  const [pendingVerification, setPendingVerification] = useState(false);
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setPendingVerification(false);
    setLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      // S5-fix: call the same-origin BFF route /api/auth/login instead
      // of the backend directly. The BFF proxies to the backend AND
      // re-issues the HttpOnly cookie on the frontend's domain, so
      // Next.js middleware can see the user is authenticated.
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData,
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
          // S1.1: backend refused because the email isn't verified.
          setPendingVerification(true);
          throw new Error(
            data.detail ||
              "Debes verificar tu correo antes de iniciar sesión.",
          );
        }
        throw new Error(data.detail || "Error al iniciar sesión");
      }

      await res.json();
      router.push(nextPath);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error al iniciar sesión";
      setErrors({ form: message });
      // S1.5: fire a toast (Spanish) with a Reintentar CTA so transient
      // backend failures are recoverable without a page refresh.
      toast.show({
        tone: "error",
        title: "No pudimos iniciar sesión",
        body: message,
        onRetry: () => {
          void handleSubmit({
            preventDefault: () => {},
          } as React.FormEvent);
        },
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResendState("sending");
    try {
      await fetch("/api/v1/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setResendState("sent");
    } catch {
      setResendState("error");
    }
  };

  return (
    <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          {/* Logo */}
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
          <h2 className="text-2xl font-heading font-bold text-ink">Iniciar sesión</h2>
          <p className="text-ink/60 mt-2">Accede a tu cuenta de LILIAN</p>
        </div>

        {errors.form && (
          <div
            id="login-form-error"
            role="alert"
            aria-live="assertive"
            className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl mb-6 text-sm"
          >
            {errors.form}
          </div>
        )}

        {/* S1.1: when the user is blocked at login because their email
            is not verified, surface a "resend verification" CTA right
            under the form so recovery is one click. */}
        {pendingVerification && (
          <div
            role="region"
            aria-label="Recuperar verificación de correo"
            className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-4 rounded-xl mb-6 text-sm space-y-3"
          >
            <p>
              ¿No recibiste el correo o se perdió? Te lo reenviamos a{" "}
              <strong>{email}</strong>.
            </p>
            <Button
              type="button"
              variant="primary"
              size="sm"
              loading={resendState === "sending"}
              disabled={resendState === "sent"}
              onClick={handleResend}
              className="w-full"
            >
              {resendState === "sent"
                ? "Enlace reenviado"
                : "Reenviar enlace de verificación"}
            </Button>
            {resendState === "error" && (
              <p role="alert" className="text-xs text-coral-dark">
                No pudimos reenviar el correo. Inténtalo nuevamente.
              </p>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <Input
            label="Email"
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@email.com"
            autoComplete="email"
            required
            aria-required="true"
            aria-describedby={errors.form ? "login-form-error" : undefined}
            aria-invalid={errors.email ? true : undefined}
          />

          <Input
            label="Contraseña"
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            required
            aria-required="true"
            aria-describedby={errors.form ? "login-form-error" : undefined}
            aria-invalid={errors.password ? true : undefined}
          />

          <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">
            {loading ? "Iniciando sesión..." : "Iniciar sesión"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink/60">
          ¿No tienes cuenta?{" "}
          <Link href="/auth/register" className="text-coral font-semibold hover:text-coral-dark">
            Regístrate
          </Link>
        </p>
      </Card>
    </main>
  );
}

// useSearchParams() must be inside a Suspense boundary in App Router.
// We wrap the form in <Suspense> at the page-export level so the hook
// works during static generation and during dynamic client navigation.
export default function LoginPage() {
  return (
    <Suspense fallback={
      <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center p-4">
        <div className="text-ink/60">Cargando…</div>
      </main>
    }>
      <LoginForm />
    </Suspense>
  );
}
