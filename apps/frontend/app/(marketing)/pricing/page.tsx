import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, Button, Badge } from "@/components/ui";

export const metadata: Metadata = {
  title: "Planes y precios — lilIAn",
  description:
    "Elige el plan de Lilian que se ajusta a tu estudio o empresa. Empieza gratis con 10 documentos al mes y sube de plan cuando lo necesites.",
};

/**
 * Public, anonymous pricing page.
 *
 * Why this lives under the ``(marketing)`` route group:
 * - The dashboard layout (``app/dashboard/layout.tsx``) mounts auth-gated
 *   chrome. Anonymous visitors must not see that chrome.
 * - The marketing layout only wraps with the brand shell so the page
 *   renders without a redirect to /auth/login.
 *
 * Plan copy is hard-coded intentionally:
 * - The DB-backed ``GET /api/v1/saas/plans/public`` endpoint exists for
 *   the in-app "Cambiar plan" UI, but the public pricing page should
 *   never depend on the API being up. If the backend is restarting, the
 *   marketing site still has to render.
 * - Stripe Price IDs are never displayed here (those are server-only).
 */

const PLANS: ReadonlyArray<{
  id: "free" | "lawyer" | "law_firm" | "company" | "enterprise";
  name: string;
  tagline: string;
  price: string;
  priceSuffix: string;
  highlight?: string;
  features: ReadonlyArray<string>;
  cta: { label: string; href: string };
  badge?: string;
}> = [
  {
    id: "free",
    name: "Gratis",
    tagline: "Para probar Lilian sin compromiso.",
    price: "$0",
    priceSuffix: "CLP / mes",
    features: [
      "10 documentos al mes",
      "5 análisis con IA al mes",
      "1 usuario",
      "Soporte por correo",
    ],
    cta: { label: "Comenzar gratis", href: "/auth/register?plan=free" },
  },
  {
    id: "lawyer",
    name: "Abogado",
    tagline: "Para abogados independientes con un volumen moderado.",
    price: "$19.990",
    priceSuffix: "CLP / mes",
    highlight: "Más popular",
    features: [
      "500 documentos al mes",
      "200 análisis con IA al mes",
      "1 usuario",
      "Soporte por correo prioritario",
      "Exportar informe a PDF",
    ],
    cta: { label: "Elegir Abogado", href: "/auth/register?plan=lawyer" },
    badge: "Recomendado",
  },
  {
    id: "law_firm",
    name: "Bufete",
    tagline: "Para equipos pequeños que comparten casos.",
    price: "$59.990",
    priceSuffix: "CLP / mes",
    features: [
      "2.000 documentos al mes",
      "800 análisis con IA al mes",
      "5 usuarios",
      "Soporte por correo prioritario",
      "Panel de métricas del bufete",
    ],
    cta: { label: "Elegir Bufete", href: "/auth/register?plan=law_firm" },
  },
  {
    id: "company",
    name: "Empresa",
    tagline: "Para departamentos legales con alto volumen.",
    price: "$149.990",
    priceSuffix: "CLP / mes",
    features: [
      "5.000 documentos al mes",
      "2.000 análisis con IA al mes",
      "20 usuarios",
      "Soporte por chat",
      "Auditoría y reportes gerenciales",
    ],
    cta: { label: "Elegir Empresa", href: "/auth/register?plan=company" },
  },
  {
    id: "enterprise",
    name: "Corporativo",
    tagline: "Soluciones a medida para grandes equipos y holdings.",
    price: "Consultar",
    priceSuffix: "Plan personalizado",
    features: [
      "Documentos ilimitados",
      "Análisis ilimitados",
      "Usuarios ilimitados",
      "SLA dedicado y soporte 24/7",
      "SSO y SCIM opcional",
      "Despliegue on-prem disponible",
    ],
    cta: { label: "Hablar con ventas", href: "/auth/register?plan=enterprise" },
  },
];

export default function PricingPage() {
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Brand header */}
      <header className="flex items-center justify-between mb-12">
        <Link href="/" className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
            <span className="text-2xl font-heading font-bold text-white">L</span>
          </div>
          <div>
            <h1 className="text-xl font-heading font-bold text-ink tracking-tight">
              lil<span className="text-coral">I</span>An
            </h1>
            <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">
              Legal AI
            </p>
          </div>
        </Link>
        <nav className="flex gap-3">
          <Link href="/auth/login">
            <Button variant="ghost">Iniciar sesión</Button>
          </Link>
          <Link href="/auth/register">
            <Button variant="primary">Registrarse</Button>
          </Link>
        </nav>
      </header>

      {/* Page heading */}
      <section className="text-center max-w-2xl mx-auto mb-12">
        <Badge className="mb-4">Planes transparentes</Badge>
        <h2 className="text-4xl md:text-5xl font-heading font-bold text-ink mb-4 tracking-tight">
          Elige el plan que crece contigo
        </h2>
        <p className="text-lg text-ink/60">
          Desde el primer documento hasta un holding completo. Cancela o
          cambia de plan cuando quieras, sin contratos forzosos.
        </p>
      </section>

      {/* Plan grid */}
      <section
        aria-label="Lista de planes"
        className="grid md:grid-cols-2 lg:grid-cols-3 gap-6"
      >
        {PLANS.map((plan) => {
          const isHighlight = Boolean(plan.highlight);
          return (
            <Card
              key={plan.id}
              className={
                isHighlight
                  ? "p-6 ring-2 ring-coral shadow-xl relative flex flex-col"
                  : "p-6 flex flex-col"
              }
            >
              {plan.badge && (
                <Badge className="absolute -top-3 left-6 bg-coral text-white border-coral-dark">
                  {plan.badge}
                </Badge>
              )}
              <CardContent className="flex-1 flex flex-col gap-4">
                <div>
                  <h3 className="text-2xl font-heading font-bold text-ink">
                    {plan.name}
                  </h3>
                  <p className="text-sm text-ink/60 mt-1">{plan.tagline}</p>
                </div>

                <div className="flex items-baseline gap-1">
                  <span
                    className={
                      plan.id === "enterprise"
                        ? "text-3xl font-heading font-bold text-ink"
                        : "text-4xl font-heading font-bold text-ink"
                    }
                  >
                    {plan.price}
                  </span>
                  <span className="text-sm text-ink/50">{plan.priceSuffix}</span>
                </div>

                <ul className="space-y-2 flex-1">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm">
                      <CheckIcon />
                      <span className="text-ink/80">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.cta.href}
                  className="block"
                  aria-label={`${plan.cta.label} (ir a registro)`}
                >
                  <Button
                    variant={isHighlight ? "primary" : "secondary"}
                    size="lg"
                    className="w-full"
                  >
                    {plan.cta.label}
                  </Button>
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </section>

      {/* FAQ-lite */}
      <section className="mt-20 max-w-3xl mx-auto">
        <h3 className="text-2xl font-heading font-bold text-ink text-center mb-8">
          Preguntas frecuentes
        </h3>
        <div className="space-y-6">
          <FaqItem
            q="¿Qué métodos de pago aceptan?"
            a="Tarjeta de crédito y débito a través de Stripe. También podemos emitir factura para transferencia bancaria en planes Empresa y Corporativo."
          />
          <FaqItem
            q="¿Puedo cambiar de plan en cualquier momento?"
            a="Sí. Sube o baja de plan cuando quieras desde tu panel de facturación. El cobro se prorratea automáticamente."
          />
          <FaqItem
            q="¿Qué pasa si supero el límite de documentos?"
            a="Te avisamos antes de llegar al tope. Si lo superas, puedes subir de plan o esperar al siguiente ciclo. Nunca perdemos tus documentos."
          />
          <FaqItem
            q="¿Necesito tarjeta para empezar?"
            a="No. El plan Gratis no requiere tarjeta y puedes usarlo todo el tiempo que quieras."
          />
        </div>
      </section>

      <footer className="py-8 mt-16 text-center text-ink/40 text-sm">
        <p>
          lilIAn — Plataforma legaltech chilena asistida por IA. Los
          análisis son preliminares y no reemplazan la revisión
          profesional de un abogado habilitado en Chile.
        </p>
      </footer>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      className="w-4 h-4 text-green mt-0.5 flex-shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      strokeWidth={2.5}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function FaqItem({ q, a }: { q: string; a: string }) {
  return (
    <details className="group bg-white border border-border rounded-xl p-4 open:shadow-sm">
      <summary className="cursor-pointer flex items-center justify-between gap-4 font-heading font-semibold text-ink">
        <span>{q}</span>
        <svg
          aria-hidden="true"
          className="w-5 h-5 text-ink/40 transition-transform group-open:rotate-180"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </summary>
      <p className="mt-3 text-ink/70 text-sm leading-relaxed">{a}</p>
    </details>
  );
}
