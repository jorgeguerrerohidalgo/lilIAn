import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";

export const metadata: Metadata = {
  title: "Agentes especializados en derecho chileno",
  description:
    "Biblioteca de agentes de IA pre-construidos para la práctica legal en Chile: revisión de arriendos, finiquitos, cartas de despido, cobranza y más.",
};

interface DomainAgent {
  name: string;
  slug: string;
  description: string;
  category: string;
  tool_ids: string[];
  typical_matter_type: string;
  legal_areas: string[];
  estimated_minutes: number;
  system_prompt: string;
}

interface AgentLibraryResponse {
  agents: DomainAgent[];
}

async function fetchAgentLibrary(): Promise<DomainAgent[]> {
  // The endpoint is public (no auth), so we can fetch from the server
  // directly during build/SSR. Falls back to a static empty list if
  // the backend is unreachable during local dev.
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${baseUrl}/api/v1/agents/library`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return [];
    }
    const data = (await res.json()) as AgentLibraryResponse;
    return data.agents ?? [];
  } catch {
    return [];
  }
}

const CATEGORY_LABELS: Record<string, string> = {
  civil: "Civil",
  laboral: "Laboral",
  comercial: "Comercial",
};

export default async function AgentsGalleryPage() {
  const agents = await fetchAgentLibrary();

  return (
    <main id="main-content" className="min-h-screen bg-gradient-to-b from-soft to-cream">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <header className="flex items-center justify-between mb-12">
          <Link href="/" className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-lg">
              <span className="text-3xl font-heading font-bold text-white">L</span>
            </div>
            <div>
              <h1 className="text-2xl font-heading font-bold text-ink tracking-tight">
                lil<span className="text-coral">I</span>An
              </h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">
                Legal AI v2
              </p>
            </div>
          </Link>
          <nav className="flex gap-3">
            <Link href="/agents">
              <Button variant="ghost">Agentes</Button>
            </Link>
            <Link href="/pricing">
              <Button variant="ghost">Precios</Button>
            </Link>
            <Link href="/auth/login">
              <Button variant="ghost">Iniciar sesión</Button>
            </Link>
            <Link href="/auth/register">
              <Button variant="primary">Registrarse</Button>
            </Link>
          </nav>
        </header>

        <section className="py-12 text-center">
          <p className="text-xs font-bold uppercase tracking-widest text-coral mb-3">
            Diferenciación chilena
          </p>
          <h2 className="text-4xl md:text-5xl font-heading font-bold text-ink mb-6 tracking-tight">
            Agentes especializados en derecho chileno
          </h2>
          <p className="text-xl text-ink/60 mb-4 max-w-2xl mx-auto">
            Elige el agente que mejor se ajusta a tu caso. Cada uno trae
            un prompt afinado, los artículos de la ley que aplican y un
            flujo de trabajo optimizado para la práctica legal en Chile.
          </p>
          <p className="text-sm text-ink/40">
            {agents.length} agentes disponibles · sin costo en el plan
            inicial
          </p>
        </section>

        <section className="py-12 grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <Card
              key={agent.slug}
              className="text-left p-6 flex flex-col h-full"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold uppercase tracking-widest text-coral">
                  {CATEGORY_LABELS[agent.category] ?? agent.category}
                </span>
                <span className="text-xs text-ink/40">
                  ~{agent.estimated_minutes} min
                </span>
              </div>
              <h3 className="text-xl font-heading font-bold text-ink mb-2">
                {agent.name}
              </h3>
              <p className="text-ink/60 text-sm mb-4 flex-1">
                {agent.description}
              </p>
              <div className="flex flex-wrap gap-1.5 mb-4">
                {(agent.legal_areas ?? []).map((area) => (
                  <span
                    key={area}
                    className="text-[10px] uppercase tracking-wide bg-blue-pale text-blue px-2 py-1 rounded-full"
                  >
                    {area}
                  </span>
                ))}
              </div>
              <Link href={`/matters/new?agent=${agent.slug}`}>
                <Button variant="primary" size="md" className="w-full">
                  Usar este agente
                </Button>
              </Link>
            </Card>
          ))}
        </section>

        {agents.length === 0 && (
          <section className="py-16">
            <Card className="bg-white p-8 text-center">
              <p className="text-ink/60">
                La biblioteca de agentes se está cargando. Si no aparecen
                aquí, asegúrate de tener el backend en línea.
              </p>
            </Card>
          </section>
        )}

        <section className="py-12 text-center">
          <Card className="bg-ink text-white p-8">
            <p className="text-lg font-medium mb-2">
              ¿Necesitas un agente a medida?
            </p>
            <p className="text-white/70 text-sm mb-4">
              Estamos sumando nuevos agentes cada sprint. Cuéntanos qué
              área del derecho quieres automatizar.
            </p>
            <Link href="/auth/register">
              <Button variant="primary">Crear cuenta gratis</Button>
            </Link>
          </Card>
        </section>

        <footer className="py-8 text-center text-ink/40 text-sm">
          <p>lilIAn - Plataforma legaltech chilena asistida por IA</p>
        </footer>
      </div>
    </main>
  );
}
