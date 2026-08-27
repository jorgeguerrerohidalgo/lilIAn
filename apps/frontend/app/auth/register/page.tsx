"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui";
import { Input } from "@/components/ui";
import { Card } from "@/components/ui";

// S2-02: a paying user lands here from the pricing page with a plan
// already selected (e.g. /auth/register?plan=lawyer). We surface that
// intent in the UI so they know what they signed up for, and stash it
// in sessionStorage so the post-verification /dashboard/billing page
// can offer them a one-click upgrade.
const VALID_PLANS = new Set(["free", "lawyer", "law_firm", "company", "enterprise"]);
const PLAN_LABEL: Record<string, string> = {
  free: "Gratis",
  lawyer: "Abogado",
  law_firm: "Bufete",
  company: "Empresa",
  enterprise: "Corporativo",
};

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const planFromQuery = searchParams.get("plan") || "";
  const planName = VALID_PLANS.has(planFromQuery) ? planFromQuery : "";
  const planLabel = planName ? PLAN_LABEL[planName] : null;

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<{
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
    form?: string;
  }>({});
  const [loading, setLoading] = useState(false);
  // S1.1: when set we render the "Revisa tu email" confirmation screen
  // instead of immediately redirecting to /auth/login. The email link
  // itself targets /auth/verify-email?token=… which then POSTs to
  // /api/v1/auth/verify-email and routes the user into the app.
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent">("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (password !== confirmPassword) {
      setErrors({ confirmPassword: "Las contraseñas no coinciden" });
      return;
    }

    if (password.length < 12) {
      setErrors({ password: "La contraseña debe tener al menos 12 caracteres" });
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`/api/v1/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Error al registrar");
      }

      // S2-02: remember the chosen plan through the email-verification
      // round-trip. After they click the email link and land in the
      // dashboard, the billing page can offer a one-click upgrade to
      // the same plan without asking them to pick again.
      if (planName && typeof window !== "undefined") {
        try {
          window.sessionStorage.setItem("lilian_selected_plan", planName);
        } catch {
          // sessionStorage may be disabled (private mode). Not fatal —
          // the user can re-pick on /pricing.
        }
      }

      // S1.1: backend has created the user and dispatched (or stub-logged)
      // the verification email. Show the confirmation screen instead of
      // bouncing to login — the user cannot sign in until their email
      // is verified, so directing them to a login screen they can't use
      // would be a dead end.
      setPendingEmail(email);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al registrar";
      setErrors({ form: message });
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (!pendingEmail) return;
    setResendState("sending");
    try {
      await fetch("/api/v1/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: pendingEmail }),
      });
      setResendState("sent");
    } catch {
      setResendState("idle");
    }
  };

  // -----------------------------------------------------------------
  // Confirmation screen — shown after a successful registration.
  // -----------------------------------------------------------------
  if (pendingEmail) {
    return (
      <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center px-4 py-8 md:py-4">
        <Card className="w-full max-w-md p-5 md:p-8">
          <div className="text-center mb-6 md:mb-8">
            <div className="flex items-center justify-center gap-3 mb-5 md:mb-6">
              <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
                <span className="text-xl md:text-2xl font-heading font-bold text-white">L</span>
              </div>
              <div className="text-left">
                <h1 className="text-xl md:text-2xl font-heading font-bold text-ink tracking-tight">
                  lil<span className="text-coral">I</span>An
                </h1>
                <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">Legal AI</p>
              </div>
            </div>
            <h2 className="text-xl md:text-2xl font-heading font-bold text-ink">Revisa tu email</h2>
            <p className="text-ink/60 mt-3">
              Te enviamos un enlace de confirmación a{" "}
              <strong className="text-ink">{pendingEmail}</strong>.
              Haz clic en él para activar tu cuenta.
            </p>
          </div>

          <div className="space-y-4">
            <Button
              type="button"
              variant="primary"
              size="lg"
              loading={resendState === "sending"}
              disabled={resendState === "sent"}
              onClick={handleResend}
              className="w-full"
            >
              {resendState === "sent" ? "Enlace reenviado" : "Reenviar enlace de verificación"}
            </Button>

            {resendState === "sent" && (
              <p
                role="status"
                aria-live="polite"
                className="text-sm text-center text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3"
              >
                Si la cuenta existe, ya te enviamos un nuevo enlace.
              </p>
            )}

            {/* S2-02: after they verify their email we'll route them to
                /dashboard/billing with a one-click upgrade. The link
                below gets them there directly with the plan pre-selected
                in sessionStorage so /dashboard/billing can pick it up. */}
            {planName && planName !== "free" && (
              <Link
                href={`/pricing?resume=${encodeURIComponent(planName)}`}
                className="block text-center text-sm text-coral hover:text-coral-dark font-semibold"
              >
                Ver planes de pago
              </Link>
            )}

            <Link
              href="/auth/login"
              className="block text-center text-sm text-ink/60 hover:text-ink"
            >
              Volver a iniciar sesión
            </Link>
          </div>
        </Card>
      </main>
    );
  }

  // -----------------------------------------------------------------
  // Registration form (initial state).
  // -----------------------------------------------------------------
  return (
    <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center px-4 py-8 md:py-4">
      <Card className="w-full max-w-md p-5 md:p-8">
        <div className="text-center mb-6 md:mb-8">
          {/* Logo */}
          <div className="flex items-center justify-center gap-3 mb-5 md:mb-6">
            <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
              <span className="text-xl md:text-2xl font-heading font-bold text-white">L</span>
            </div>
            <div className="text-left">
              <h1 className="text-xl md:text-2xl font-heading font-bold text-ink tracking-tight">
                lil<span className="text-coral">I</span>An
              </h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">Legal AI</p>
            </div>
          </div>
          <h2 className="text-xl md:text-2xl font-heading font-bold text-ink">Crear cuenta</h2>
          <p className="text-ink/60 mt-2">
            {planLabel
              ? <>Vas a activar el plan <strong className="text-ink">{planLabel}</strong>.</>
              : "Regístrate en LILIAN"}
          </p>
          {planName && planName !== "free" && (
            <div className="mt-4 mx-auto inline-flex items-center gap-2 bg-coral-pale border border-coral/20 text-coral-dark px-3 py-1.5 rounded-full text-xs font-semibold">
              <span aria-hidden="true">●</span>
              Plan {planLabel} — pago después de verificar tu email
            </div>
          )}
        </div>

        {errors.form && (
          <div
            id="register-form-error"
            role="alert"
            aria-live="assertive"
            className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl mb-6 text-sm"
          >
            {errors.form}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <Input
            label="Nombre completo"
            type="text"
            id="fullName"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Tu nombre completo"
            autoComplete="name"
            required
            aria-required="true"
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.fullName ? true : undefined}
          />

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
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.email ? true : undefined}
          />

          <Input
            label="Contraseña"
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Mínimo 12 caracteres, con mayúscula, número y símbolo"
            autoComplete="new-password"
            required
            aria-required="true"
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.password ? true : undefined}
          />

          <Input
            label="Confirmar contraseña"
            type="password"
            id="confirmPassword"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            required
            aria-required="true"
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.confirmPassword ? true : undefined}
          />

          <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">
            {loading ? "Creando cuenta..." : "Crear cuenta"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink/60">
          ¿Ya tienes cuenta?{" "}
          <Link href="/auth/login" className="text-coral font-semibold hover:text-coral-dark">
            Inicia sesión
          </Link>
        </p>
      </Card>
    </main>
  );
}
