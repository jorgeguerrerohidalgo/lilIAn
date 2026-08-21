import type { Metadata } from "next";
import { headers } from "next/headers";

/**
 * /share/[token] — public, read-only view of an analysis report.
 *
 * S4.5. The page is fully server-side: it fetches the report straight
 * from the backend using the token in the URL, then renders a static
 * HTML summary. No cookies, no auth, no client-side fetches — the
 * page itself is the gift the lawyer sends to the client.
 *
 * The backend endpoint is ``GET /api/v1/shares/<token>``. It returns
 * the report body when the token is valid and not expired.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface SharedReport {
  report_id: number;
  matter_id: number;
  matter_title: string;
  summary: string | null;
  facts: string | null;
  next_steps: string | null;
  disclaimer: string | null;
  confidence: string | null;
  created_at: string | null;
  model_provider: string | null;
  model_name: string | null;
}

interface PageProps {
  params: { token: string };
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  // The metadata is generated before we know if the token is valid,
  // so we degrade gracefully: the title is the brand name, the
  // canonical tells the recipient where they are.
  return {
    title: "Lilian — Informe compartido",
    description: "Análisis de caso legal generado con IA. Compartido por un abogado.",
    robots: { index: false, follow: false },
  };
}

async function fetchSharedReport(token: string): Promise<{
  report: SharedReport | null;
  error: string | null;
}> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    return { report: null, error: "Servicio no disponible" };
  }
  // Build the absolute URL to the backend. The token is a path
  // segment, not a query string, so it does not need URL encoding.
  const url = `${apiUrl.replace(/\/$/, "")}/api/v1/shares/${encodeURIComponent(token)}`;
  try {
    // Forward the request-id header if the upstream supplied one — this
    // makes cross-service tracing easier.
    const incomingHeaders = headers();
    const incomingRequestId = incomingHeaders.get("x-request-id");
    const resp = await fetch(url, {
      cache: "no-store",
      headers: incomingRequestId ? { "x-request-id": incomingRequestId } : undefined,
    });
    if (resp.ok) {
      const data = (await resp.json()) as SharedReport;
      return { report: data, error: null };
    }
    if (resp.status === 410) {
      return { report: null, error: "Este enlace ha expirado" };
    }
    if (resp.status === 401) {
      return { report: null, error: "Enlace inválido" };
    }
    if (resp.status === 404) {
      return { report: null, error: "El informe ya no está disponible" };
    }
    return { report: null, error: "No se pudo cargar el informe" };
  } catch {
    return { report: null, error: "No se pudo contactar al servicio" };
  }
}

export default async function SharePage({ params }: PageProps) {
  const { report, error } = await fetchSharedReport(params.token);

  if (!report) {
    return (
      <main
        id="main-content"
        className="mx-auto max-w-2xl px-6 py-16"
        lang="es"
      >
        <header className="mb-8">
          <h1 className="text-2xl font-semibold text-slate-900">Lilian</h1>
          <p className="text-sm text-slate-500">Plataforma legaltech chilena</p>
        </header>
        <section
          role="alert"
          className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-slate-900">
            No se puede mostrar el informe
          </h2>
          <p className="mt-2 text-sm text-slate-700">
            {error || "El enlace puede haber expirado o sido revocado."}
          </p>
          <p className="mt-4 text-xs text-slate-500">
            Si crees que es un error, contacta directamente a quien te envió el enlace.
          </p>
        </section>
      </main>
    );
  }

  const fmtDate = (iso: string | null): string => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("es-CL", {
        dateStyle: "long",
        timeStyle: "short",
      });
    } catch {
      return iso;
    }
  };

  return (
    <main
      id="main-content"
      className="mx-auto max-w-3xl px-6 py-12"
      lang="es"
    >
      <header className="mb-10 border-b border-slate-200 pb-8">
        <p className="text-xs uppercase tracking-wider text-slate-500">
          Informe compartido
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">
          {report.matter_title}
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          {report.created_at ? `Generado el ${fmtDate(report.created_at)}` : null}
          {report.model_provider && report.model_name
            ? ` · ${report.model_provider} ${report.model_name}`
            : null}
        </p>
      </header>

      <article className="prose prose-slate max-w-none">
        {report.summary ? (
          <section>
            <h2 className="text-xl font-semibold text-slate-900">Resumen</h2>
            <p className="mt-2 whitespace-pre-wrap text-slate-800">{report.summary}</p>
          </section>
        ) : null}

        {report.facts ? (
          <section className="mt-8">
            <h2 className="text-xl font-semibold text-slate-900">Hechos relevantes</h2>
            <p className="mt-2 whitespace-pre-wrap text-slate-800">{report.facts}</p>
          </section>
        ) : null}

        {report.next_steps ? (
          <section className="mt-8">
            <h2 className="text-xl font-semibold text-slate-900">Próximos pasos</h2>
            <p className="mt-2 whitespace-pre-wrap text-slate-800">{report.next_steps}</p>
          </section>
        ) : null}

        {report.disclaimer ? (
          <section className="mt-10 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <strong className="block font-semibold">Aviso</strong>
            <p className="mt-1 whitespace-pre-wrap">{report.disclaimer}</p>
          </section>
        ) : null}
      </article>

      <footer className="mt-12 border-t border-slate-200 pt-6 text-xs text-slate-500">
        <p>
          Este informe fue generado con asistencia de IA y compartido por un abogado
          que usa <strong>Lilian</strong>. Las conclusiones deben ser revisadas por
          un profesional antes de tomar decisiones.
        </p>
      </footer>
    </main>
  );
}
