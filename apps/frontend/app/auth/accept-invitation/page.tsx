"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";

/**
 * S6.3 / Phase 2c — consume an invitation token.
 *
 * The backend (`POST /api/v1/organizations/invitations/accept`) requires
 * the receiver to be signed in — `Depends(get_current_user)` enforces
 * that the user accepting the invite is the one whose email appears on
 * the row. If they aren't, the backend returns 403 ("Esta invitación
 * fue enviada a otro correo"). If they aren't logged in at all, the
 * dependency raises 401 before the handler runs.
 *
 * Flow:
 *   1. Read `?token=` from the URL (the email links here with the token).
 *   2. POST the token with `credentials: "include"` so the BFF forwards
 *      the `lilian_auth_token` cookie as a Bearer header.
 *   3. Three visual states (verifying / success / error) plus a 401
 *      branch that redirects through `/auth/login` or `/auth/register`
 *      carrying the token so the user lands back here after auth.
 */

type Status = "verifying" | "success" | "error" | "needs-auth";

interface InvitationAccepted {
  invitation_id: number;
  organization_id: number;
  organization_name: string;
  role: string;
  user_id: number;
  email: string;
  email_already_registered: boolean;
  requires_verification: boolean;
}

interface AcceptError {
  status: number;
  message: string;
}

// Backend role enum values (MemberRole) — we surface a Spanish label so
// the success card reads naturally. Unknown values fall back to the raw
// token so a future role addition still renders something useful.
const ROLE_LABEL: Record<string, string> = {
  OWNER: "Dueño",
  ADMIN: "Administrador/a",
  LAWYER: "Abogado/a",
  COMPANY_USER: "Usuario de empresa",
  CLIENT: "Cliente",
  VIEWER: "Visualizador",
  PLATFORM_ADMIN: "Administrador de plataforma",
};

function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
}

function AcceptInvitationInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [status, setStatus] = useState<Status>("verifying");
  const [accepted, setAccepted] = useState<InvitationAccepted | null>(null);
  const [errorInfo, setErrorInfo] = useState<AcceptError | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorInfo({
        status: 400,
        message:
          "Falta el token en el enlace. Pega la URL completa del correo o solicita uno nuevo.",
      });
      return;
    }

    let cancelled = false;
    const run = async () => {
      try {
        const res = await fetch("/api/v1/organizations/invitations/accept", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ token }),
        });

        if (cancelled) return;

        if (res.ok) {
          const data = (await res.json()) as InvitationAccepted;
          setAccepted(data);
          setStatus("success");
          return;
        }

        // 401: not authenticated. Carry the token forward so the user
        // lands back here after login/register without losing the invite.
        if (res.status === 401) {
          setStatus("needs-auth");
          return;
        }

        // 410 / 400 / 403 / etc — show the backend detail in Spanish.
        const data = await res.json().catch(() => ({}));
        setErrorInfo({
          status: res.status,
          message:
            data.detail ||
            "No pudimos aceptar la invitación. El enlace puede haber expirado o ya fue usado.",
        });
        setStatus("error");
      } catch {
        if (!cancelled) {
          setErrorInfo({
            status: 0,
            message: "No pudimos contactar al servidor. Inténtalo de nuevo.",
          });
          setStatus("error");
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // -------------------------------------------------------------------
  // 401 — send the user through login/register, preserving the token.
  // -------------------------------------------------------------------
  if (status === "needs-auth" && token) {
    const nextPath = `/auth/accept-invitation?token=${encodeURIComponent(token)}`;
    return (
      <main
        id="main-content"
        className="min-h-screen bg-soft flex items-center justify-center px-4 py-8 md:py-4"
      >
        <Card className="w-full max-w-md p-5 md:p-8">
          <div className="text-center">
            <div className="flex items-center justify-center gap-3 mb-5 md:mb-6">
              <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
                <span className="text-xl md:text-2xl font-heading font-bold text-white">L</span>
              </div>
              <div className="text-left">
                <h1 className="text-xl md:text-2xl font-heading font-bold text-ink tracking-tight">
                  lil<span className="text-coral">I</span>An
                </h1>
                <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">
                  Legal AI
                </p>
              </div>
            </div>
            <h2 className="text-xl md:text-2xl font-heading font-bold text-ink">Inicia sesión para continuar</h2>
            <p className="text-ink/60 mt-3">
              Para aceptar esta invitación necesitas iniciar sesión o crear tu cuenta.
              Te enviaremos de vuelta a esta pantalla automáticamente.
            </p>

            <div className="mt-6 space-y-3">
              <Button
                type="button"
                variant="primary"
                size="lg"
                className="w-full"
                onClick={() =>
                  router.push(
                    `/auth/login?next=${encodeURIComponent(nextPath)}`,
                  )
                }
              >
                Iniciar sesión
              </Button>
              <Button
                type="button"
                variant="outline"
                size="lg"
                className="w-full"
                onClick={() =>
                  router.push(
                    `/auth/register?invite=${encodeURIComponent(token)}`,
                  )
                }
              >
                Crear cuenta nueva
              </Button>
            </div>
          </div>
        </Card>
      </main>
    );
  }

  // -------------------------------------------------------------------
  // Default render — verifying / success / error in one card.
  // -------------------------------------------------------------------
  return (
    <main
      id="main-content"
      className="min-h-screen bg-soft flex items-center justify-center px-4 py-8 md:py-4"
    >
      <Card className="w-full max-w-md p-5 md:p-8">
        <div className="text-center">
          <div className="flex items-center justify-center gap-3 mb-5 md:mb-6">
            <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
              <span className="text-xl md:text-2xl font-heading font-bold text-white">L</span>
            </div>
            <div className="text-left">
              <h1 className="text-xl md:text-2xl font-heading font-bold text-ink tracking-tight">
                lil<span className="text-coral">I</span>An
              </h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">
                Legal AI
              </p>
            </div>
          </div>

          {status === "verifying" && (
            <>
              <h2 className="text-xl md:text-2xl font-heading font-bold text-ink">Procesando invitación…</h2>
              <p className="text-ink/60 mt-3">
                Estamos agregando tu cuenta a la organización. Esto toma unos segundos.
              </p>
              <div
                role="status"
                aria-live="polite"
                className="mt-6 mx-auto w-10 h-10 rounded-full border-4 border-ink/10 border-t-coral animate-spin"
              />
            </>
          )}

          {status === "success" && accepted && (
            <>
              <div
                role="status"
                aria-live="polite"
                className="text-xl md:text-2xl font-heading font-bold text-emerald-700"
              >
                ¡Bienvenido/a a {accepted.organization_name}!
              </div>
              <p className="text-ink/80 mt-3">
                Tu rol dentro de la organización es{" "}
                <strong className="text-ink">{roleLabel(accepted.role)}</strong>.
              </p>

              {/* S2c: optional banner when the backend flagged that the
                  user's email still needs verification. We link to the
                  existing verify-email screen so they don't lose the
                  post-accept context. */}
              {accepted.requires_verification && (
                <div
                  role="region"
                  aria-label="Verificación de correo pendiente"
                  className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-xl mt-6 text-sm text-left"
                >
                  <p>
                    Tu correo necesita verificación antes de acceder a funciones
                    completas.
                  </p>
                  <Link
                    href={`/auth/verify-email?verify=${encodeURIComponent(accepted.email)}`}
                    className="block mt-2 font-semibold text-coral hover:text-coral-dark"
                  >
                    Verificar ahora →
                  </Link>
                </div>
              )}

              <div className="mt-6 space-y-3">
                {accepted.email_already_registered ? (
                  <Button
                    type="button"
                    variant="primary"
                    size="lg"
                    className="w-full"
                    onClick={() => router.push("/dashboard")}
                  >
                    Ir al dashboard
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="primary"
                    size="lg"
                    className="w-full"
                    onClick={() =>
                      router.push(
                        `/auth/register?invite=${encodeURIComponent(
                          token ?? "",
                        )}&email=${encodeURIComponent(accepted.email)}`,
                      )
                    }
                  >
                    Crear cuenta y unirme
                  </Button>
                )}
                <Link
                  href="/auth/login"
                  className="block w-full py-3 rounded-xl border border-ink/20 text-ink font-semibold hover:bg-ink/5"
                >
                  Ir a iniciar sesión
                </Link>
              </div>
            </>
          )}

          {status === "error" && errorInfo && (
            <>
              <h2 className="text-xl md:text-2xl font-heading font-bold text-coral-dark">
                No pudimos aceptar la invitación
              </h2>
              <div
                role="alert"
                aria-live="assertive"
                className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl mt-6 text-sm"
              >
                {errorInfo.message}
              </div>

              <div className="mt-6 space-y-3">
                {/* 410 Gone / 400 with "expirado" — invite is past its
                    14-day window. Recover by requesting a new link
                    through the password-reset flow (same code path on
                    the backend) or by asking the inviter to re-send. */}
                {(errorInfo.status === 410 ||
                  /expirad/i.test(errorInfo.message)) && (
                  <Link
                    href="/auth/forgot-password"
                    className="block w-full py-3 rounded-xl bg-ink text-white font-semibold hover:bg-ink/90"
                  >
                    Solicitar nuevo enlace
                  </Link>
                )}
                <a
                  href="mailto:ventas@lilian.cl"
                  className="block w-full py-3 rounded-xl border border-ink/20 text-ink font-semibold hover:bg-ink/5"
                >
                  Contactar soporte
                </a>
                <Link
                  href="/"
                  className="block w-full py-3 rounded-xl text-ink/60 font-semibold hover:text-ink"
                >
                  Ir al inicio
                </Link>
              </div>
            </>
          )}
        </div>
      </Card>
    </main>
  );
}

// useSearchParams() must live inside a Suspense boundary in App Router.
export default function AcceptInvitationPage() {
  return (
    <Suspense
      fallback={
        <main
          id="main-content"
          className="min-h-screen bg-soft flex items-center justify-center px-4 py-8 md:py-4"
        >
          <div className="text-ink/60">Cargando…</div>
        </main>
      }
    >
      <AcceptInvitationInner />
    </Suspense>
  );
}