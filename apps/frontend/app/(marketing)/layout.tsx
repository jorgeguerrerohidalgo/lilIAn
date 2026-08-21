import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "lilIAn",
    template: "%s — lilIAn",
  },
  description:
    "Plataforma legaltech chilena asistida por IA: analiza contratos, detecta riesgos y prepárate para decisiones legales con apoyo inteligente.",
};

/**
 * Layout for the public marketing surface (landing, pricing, about…).
 *
 * Differs from ``app/dashboard/layout.tsx`` in that it does NOT mount
 * the auth-gated chrome (sidebar, user menu). Public visitors should
 * see a clean, brand-led shell with one header and one footer.
 */
export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-soft to-cream">
      <main id="main-content">{children}</main>
    </div>
  );
}
