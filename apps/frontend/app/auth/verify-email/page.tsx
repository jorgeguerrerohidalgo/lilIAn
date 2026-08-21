"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";

type Status = "verifying" | "success" | "error";

function VerifyEmailInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>("verifying");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMessage(
        "Falta el token en el enlace. Pega la URL completa del correo o solicita uno nuevo.",
      );
      return;
    }

    let cancelled = false;
    const run = async () => {
      try {
        const res = await fetch("/api/v1/auth/verify-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

        if (cancelled) return;

        if (res.ok) {
          setStatus("success");
        } else {
          const data = await res.json().catch(() => ({}));
          setStatus("error");
          setErrorMessage(
            data.detail ||
              "No pudimos verificar tu correo. El enlace puede haber expirado o ya fue usado.",
          );
        }
      } catch {
        if (!cancelled) {
          setStatus("error");
          setErrorMessage("No pudimos contactar al servidor. Inténtalo de nuevo.");
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main
      id="main-content"
      className="min-h-screen bg-soft flex items-center justify-center p-4"
    >
      <Card className="w-full max-w-md p-8">
        <div className="text-center">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
              <span className="text-2xl font-heading font-bold text-white">L</span>
            </div>
            <div className="text-left">
              <h1 className="text-2xl font-heading font-bold text-ink tracking-tight">
                lil<span className="text-coral">I</span>An
              </h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">
                Legal AI
              </p>
            </div>
          </div>

          {status === "verifying" && (
            <>
              <h2 className="text-2xl font-heading font-bold text-ink">Verificando…</h2>
              <p className="text-ink/60 mt-3">
                Estamos confirmando tu correo. Esto toma unos segundos.
              </p>
            </>
          )}

          {status === "success" && (
            <>
              <div
                role="status"
                aria-live="polite"
                className="text-2xl font-heading font-bold text-emerald-700"
              >
                ¡Listo!
              </div>
              <p className="text-ink/80 mt-3">
                Tu correo fue verificado. Ya puedes iniciar sesión.
              </p>
              <Button
                type="button"
                variant="primary"
                size="lg"
                className="mt-6 w-full"
                onClick={() => router.push("/auth/login")}
              >
                Ir a iniciar sesión
              </Button>
            </>
          )}

          {status === "error" && (
            <>
              <h2 className="text-2xl font-heading font-bold text-coral-dark">
                No pudimos verificar tu correo
              </h2>
              <div
                role="alert"
                aria-live="assertive"
                className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl mt-6 text-sm"
              >
                {errorMessage}
              </div>
              <div className="mt-6 space-y-3">
                <Link
                  href="/auth/register"
                  className="block w-full py-3 rounded-xl bg-ink text-white font-semibold hover:bg-ink/90"
                >
                  Volver al registro
                </Link>
                <Link
                  href="/auth/login"
                  className="block w-full py-3 rounded-xl border border-ink/20 text-ink font-semibold hover:bg-ink/5"
                >
                  Iniciar sesión
                </Link>
              </div>
            </>
          )}
        </div>
      </Card>
    </main>
  );
}

// useSearchParams() requires Suspense at the page-export boundary.
export default function VerifyEmailPage() {
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
      <VerifyEmailInner />
    </Suspense>
  );
}
