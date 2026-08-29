"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Button } from "@/components/ui";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { Badge } from "@/components/ui";
import { Tooltip } from "@/components/ui";
import { TOOLTIPS } from "@/lib/tooltips";

/**
 * Billing page (S2.05).
 *
 * Shows the tenant's current plan, next-invoice date, usage vs limits,
 * and the actions to (a) upgrade via Stripe Checkout and (b) manage
 * payment via the Stripe Billing Portal.
 *
 * Two flows:
 * - Self-service upgrade: tenant clicks "Cambiar de plan" -> backend
 *   creates a Stripe Checkout session -> we redirect to Stripe's hosted
 *   page -> user pays -> Stripe redirects back to this page with
 *   ?checkout=success and the webhook marks the Subscription active.
 * - Self-service cancel / card update: "Administrar suscripción"
 *   opens the Stripe Billing Portal in a new tab.
 */

type Subscription = {
  id: number;
  plan_name: string;
  status: string;
  documents_limit: number;
  analyses_limit: int_or_str;
  users_limit: int_or_str;
  monthly_price: int_or_str;
  started_at: string;
  renews_at: string | null;
  cancelled_at: string | null;
  documents_used: number;
  analyses_used: number;
  users_used: number;
  stripe_customer_id: string | null;
  cancel_at_period_end: boolean;
  trial_ends_at: string | null;
};

// Sentinel type alias — Stripe limits are int but we accept "0" / -1
// (unlimited) and the field may come back as a number anyway.
type int_or_str = number | string;

type Usage = {
  plan_name: string;
  documents_used: number;
  documents_limit: number;
  analyses_used: number;
  analyses_limit: number;
};

type Invoice = {
  id: string;
  number: string | null;
  created: string;
  amount_paid: number;
  currency: string;
  status: string | null;
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
};

const PLAN_LABEL: Record<string, string> = {
  free: "Gratis",
  lawyer: "Abogado",
  law_firm: "Bufete",
  company: "Empresa",
  enterprise: "Corporativo",
};

const VALID_PLANS = ["lawyer", "law_firm", "company", "enterprise"] as const;

function BillingPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const checkout = searchParams.get("checkout");
  const resumedPlan = searchParams.get("resume");

  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionInFlight, setActionInFlight] = useState<"checkout" | "portal" | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      // All three endpoints are part of /api/v1/saas/* and run on the
      // BFF catch-all, so we hit them same-origin and the auth cookie
      // travels automatically.
      const [subRes, usageRes, invRes] = await Promise.all([
        fetch("/api/v1/saas/subscription", { credentials: "include" }),
        fetch("/api/v1/saas/usage", { credentials: "include" }),
        fetch("/api/v1/saas/invoices", { credentials: "include" }),
      ]);

      if (subRes.ok) {
        const data = await subRes.json();
        setSubscription(data);
      } else if (subRes.status === 401) {
        router.push("/auth/login?next=/dashboard/billing");
        return;
      } else {
        // 503 (Stripe not configured) and other non-fatal errors: keep
        // the rest of the page working but show a notice.
        setError("No se pudo cargar tu suscripción.");
      }

      if (usageRes.ok) {
        setUsage(await usageRes.json());
      }
      if (invRes.ok) {
        setInvoices(await invRes.json());
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // S2-02: after a user signs up with a chosen plan, we stashed it in
  // sessionStorage. Pick it up here, auto-prompt the upgrade flow, and
  // clear the slot so a stale value doesn't fire next visit.
  useEffect(() => {
    if (checkout === "success") return; // already paid
    if (resumedPlan && VALID_PLANS.includes(resumedPlan as typeof VALID_PLANS[number])) {
      startCheckout(resumedPlan);
      try {
        if (typeof window !== "undefined") {
          window.sessionStorage.removeItem("lilian_selected_plan");
        }
      } catch {
        // ignore
      }
    }
  }, [resumedPlan, checkout]);

  const startCheckout = async (planName: string) => {
    setActionInFlight("checkout");
    setError(null);
    try {
      const res = await fetch("/api/v1/saas/checkout", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_name: planName,
          success_path: "/dashboard/billing?checkout=success",
          cancel_path: "/dashboard/billing?checkout=cancelled",
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 503) {
          throw new Error(
            data.detail || "El cobro con tarjeta no está disponible en este momento."
          );
        }
        throw new Error(data.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      if (data?.url) {
        window.location.assign(data.url);
      } else {
        throw new Error("Stripe no devolvió una URL de pago.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No pudimos iniciar el pago.");
    } finally {
      setActionInFlight(null);
    }
  };

  const openPortal = async () => {
    setActionInFlight("portal");
    setError(null);
    try {
      const res = await fetch("/api/v1/saas/billing-portal", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 404) {
          throw new Error(
            "Aún no tienes un cliente de Stripe. Completa una compra primero."
          );
        }
        if (res.status === 503) {
          throw new Error("El portal de facturación no está disponible en este momento.");
        }
        throw new Error(data.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      if (data?.url) {
        window.open(data.url, "_blank", "noopener,noreferrer");
      } else {
        throw new Error("Stripe no devolvió una URL de portal.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No pudimos abrir el portal.");
    } finally {
      setActionInFlight(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-soft rounded" />
          <div className="h-32 bg-soft rounded-xl" />
          <div className="h-64 bg-soft rounded-xl" />
        </div>
      </div>
    );
  }

  const planKey = (subscription?.plan_name || usage?.plan_name || "free").toLowerCase();
  const planLabel = PLAN_LABEL[planKey] || planKey;
  const isFree = planKey === "free";

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      <header>
        <h1 className="text-2xl md:text-3xl font-heading font-bold text-ink tracking-tight">
          Facturación y plan
        </h1>
        <p className="text-ink/60 mt-2 text-sm md:text-base">
          Gestiona tu plan, método de pago y facturas.
        </p>
      </header>

      {/* Checkout banner */}
      {checkout === "success" && (
        <div
          role="status"
          aria-live="polite"
          className="bg-green-pale border border-green/20 text-green-800 px-4 py-3 rounded-xl text-sm"
        >
          ¡Listo! Tu pago fue confirmado. La activación puede tardar unos segundos.
        </div>
      )}
      {checkout === "cancelled" && (
        <div
          role="status"
          aria-live="polite"
          className="bg-amber-pale border border-amber/20 text-amber-800 px-4 py-3 rounded-xl text-sm"
        >
          Cancelaste el pago. Tu plan actual no cambió.
        </div>
      )}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl text-sm"
        >
          {error}
        </div>
      )}

      {/* Plan summary */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle>Plan actual</CardTitle>
              <p className="text-ink/60 mt-1">
                {isFree
                  ? "Estás en el plan gratuito. Sube de plan para desbloquear más documentos y análisis."
                  : "Tu suscripción está activa."}
              </p>
            </div>
            <Badge variant={isFree ? "neutral" : "coral"} className="text-sm">
              {planLabel}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
            <Stat
              label="Documentos este mes"
              value={`${usage?.documents_used ?? 0} / ${
                usage?.documents_limit === -1
                  ? "∞"
                  : usage?.documents_limit ?? "—"
              }`}
            />
            <Stat
              label="Análisis este mes"
              value={`${usage?.analyses_used ?? 0} / ${
                usage?.analyses_limit === -1
                  ? "∞"
                  : usage?.analyses_limit ?? "—"
              }`}
            />
            <Stat
              label="Próxima fecha de cobro"
              value={
                subscription?.renews_at
                  ? new Date(subscription.renews_at).toLocaleDateString("es-CL")
                  : "—"
              }
            />
            <Stat
              label="Estado"
              value={
                subscription?.cancel_at_period_end
                  ? "Cancelará al final del ciclo"
                  : subscription?.status || "Activo"
              }
            />
          </dl>

          <div className="flex flex-wrap gap-3 mt-6">
            {isFree ? (
              <Tooltip label={TOOLTIPS.billingUpgrade} side="bottom">
              <Link href="/pricing">
                <Button variant="primary" size="md">
                  Cambiar de plan
                </Button>
              </Link>
              </Tooltip>
            ) : (
              <>
                <Tooltip label={TOOLTIPS.billingUpgrade} side="bottom">
                <Link href="/pricing">
                  <Button variant="secondary" size="md">
                    Cambiar de plan
                  </Button>
                </Link>
                </Tooltip>
                <Tooltip label={TOOLTIPS.manageSubscription} side="bottom">
                <Button
                  variant="outline"
                  size="md"
                  onClick={openPortal}
                  loading={actionInFlight === "portal"}
                  disabled={!subscription?.stripe_customer_id || actionInFlight !== null}
                >
                  Administrar suscripción
                </Button>
                </Tooltip>
              </>
            )}
          </div>

          {subscription?.trial_ends_at && (
            <p className="mt-4 text-xs text-amber-700 bg-amber-pale border border-amber/20 rounded-lg px-3 py-2 inline-block">
              Prueba gratuita hasta el{" "}
              {new Date(subscription.trial_ends_at).toLocaleDateString("es-CL")}.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Invoices */}
      <Card>
        <CardHeader>
          <CardTitle>Historial de pagos</CardTitle>
        </CardHeader>
        <CardContent>
          {invoices.length === 0 ? (
            <p className="text-sm text-ink/60">
              {isFree
                ? "Aún no tienes pagos. Sube de plan para empezar."
                : "No se encontraron facturas. Si acabas de pagar, espera unos segundos."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-ink/60">
                    <th className="py-2 pr-4 font-semibold">Fecha</th>
                    <th className="py-2 pr-4 font-semibold">Número</th>
                    <th className="py-2 pr-4 font-semibold">Monto</th>
                    <th className="py-2 pr-4 font-semibold">Estado</th>
                    <th className="py-2 font-semibold">Boleta</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="border-b border-border/50">
                      <td className="py-3 pr-4 text-ink">
                        {new Date(inv.created).toLocaleDateString("es-CL")}
                      </td>
                      <td className="py-3 pr-4 text-ink/80">
                        {inv.number || "—"}
                      </td>
                      <td className="py-3 pr-4 text-ink font-medium">
                        {formatMoney(inv.amount_paid, inv.currency)}
                      </td>
                      <td className="py-3 pr-4">
                        <Badge variant={inv.status === "paid" ? "green" : "amber"}>
                          {inv.status || "—"}
                        </Badge>
                      </td>
                      <td className="py-3">
                        {inv.invoice_pdf ? (
                          <a
                            href={inv.invoice_pdf}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-coral hover:text-coral-dark font-semibold"
                          >
                            Descargar PDF
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Need help? */}
      <Card>
        <CardHeader>
          <CardTitle>¿Necesitas ayuda?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-ink/70">
          <p>
            Si tu tarjeta fue rechazada o necesitas cambiar de método de
            pago, usa el botón <strong>Administrar suscripción</strong>
            {" "}arriba. Para planes Empresa o Corporativo, escríbenos a{" "}
            <a
              href="mailto:ventas@lilian.cl"
              className="text-coral font-semibold hover:text-coral-dark"
            >
              ventas@lilian.cl
            </a>
            .
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-ink/50 font-semibold">
        {label}
      </dt>
      <dd className="text-ink font-medium mt-1">{value}</dd>
    </div>
  );
}

function formatMoney(amount: number, currency: string): string {
  // Stripe stores amounts in the smallest currency unit (cents for USD,
  // pesos for CLP). CLP has no decimals; for other currencies we keep
  // two decimals. Good enough for the UI; Stripe's PDF is the source
  // of truth.
  const isZeroDecimal = new Set(["CLP", "JPY", "KRW", "VND", "XAF"]);
  const display = isZeroDecimal.has(currency.toUpperCase())
    ? amount
    : amount / 100;
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: currency.toUpperCase() || "CLP",
    maximumFractionDigits: isZeroDecimal.has(currency.toUpperCase()) ? 0 : 2,
  }).format(display);
}

export default function BillingPage() {
  // Suspense boundary required for useSearchParams in app router.
  return (
    <Suspense fallback={null}>
      <BillingPageInner />
    </Suspense>
  );
}
