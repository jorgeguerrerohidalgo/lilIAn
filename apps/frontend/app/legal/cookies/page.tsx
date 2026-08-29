import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Política de Cookies — lilIAn",
  description: "Cómo lilIAn usa cookies y tecnologías similares.",
};

const VERSION = "v1 · vigente desde 2026-08-29";

export default function CookiesPage() {
  return (
    <main lang="es" className="min-h-screen bg-gradient-to-b from-soft to-cream">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16 space-y-8">
        <header>
          <p className="text-xs uppercase tracking-widest text-ink/50">Documento legal</p>
          <h1 className="mt-2 text-3xl sm:text-4xl font-heading font-bold text-ink tracking-tight">
            Política de Cookies
          </h1>
          <p className="mt-2 text-sm text-ink/60">{VERSION}</p>
        </header>

        <Section title="¿Qué son las cookies?">
          <p>
            Las cookies son pequeños archivos de texto que un sitio web almacena en tu navegador.
            Usamos cookies y tecnologías similares (localStorage, sessionStorage) para que la
            plataforma funcione correctamente y para entender cómo se usa.
          </p>
        </Section>

        <Section title="Cookies que usamos">
          <h3 className="font-semibold text-ink mt-4 mb-2">Estrictamente necesarias</h3>
          <p>
            Sin estas cookies la plataforma no funciona. <strong>No requieren consentimiento</strong>{" "}
            conforme al art. 17 de la Ley 21.719, porque son necesarias para la ejecución del
            contrato de prestación del servicio:
          </p>
          <ul>
            <li><code className="text-xs bg-soft px-1 rounded">lilian_auth_token</code> — token de sesión HttpOnly que mantiene tu login.</li>
            <li><code className="text-xs bg-soft px-1 rounded">csrf_token</code> — token anti-falsificación de peticiones.</li>
            <li>Preferencias de UI (modo claro/oscuro, idioma).</li>
          </ul>

          <h3 className="font-semibold text-ink mt-6 mb-2">Analíticas (opt-in)</h3>
          <p>
            Solo se activan si las aceptas en el banner de cookies:
          </p>
          <ul>
            <li>Métricas agregadas y seudonimizadas de uso de la plataforma.</li>
            <li>Detección de errores y rendimiento (Sentry, en configuración privacy-friendly).</li>
          </ul>

          <h3 className="font-semibold text-ink mt-6 mb-2">Marketing (opt-in)</h3>
          <p>
            No usamos cookies de marketing de terceros al día de hoy. Si en el futuro incorporamos
            herramientas de marketing (ej. Meta Pixel, Google Ads), las listaremos aquí y
            solicitaremos consentimiento por separado.
          </p>
        </Section>

        <Section title="¿Cómo cambiar mis preferencias?">
          <p>
            Puedes aceptar, rechazar o configurar cookies desde el banner que aparece en tu primera
            visita. También puedes actualizar tus preferencias en cualquier momento desde{" "}
            <a href="/dashboard/settings/privacy" className="text-primary underline">
              Configuración &rarr; Privacidad
            </a>{" "}
            una vez que hayas iniciado sesión, o mediante la configuración de cookies de tu
            navegador.
          </p>
        </Section>

        <Section title="Cookies de terceros">
          <p>
            Algunos servicios externos que usamos pueden depositar sus propias cookies. Te recomendamos
            revisar las políticas de esos proveedores:
          </p>
          <ul>
            <li><a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="underline">Stripe (pagos)</a></li>
            <li><a href="https://sentry.io/privacy/" target="_blank" rel="noopener noreferrer" className="underline">Sentry (errores)</a></li>
          </ul>
        </Section>

        <Section title="¿Por qué usamos cookies?">
          <p>Las cookies estrictamente necesarias nos permiten:</p>
          <ul>
            <li>Mantener tu sesión iniciada.</li>
            <li>Protegerte contra CSRF y otros ataques.</li>
            <li>Recordar tus preferencias.</li>
          </ul>
          <p>
            Las cookies de analítica (opt-in) nos permiten mejorar el producto identificando
            fricciones y errores. <strong>Nunca</strong> usamos cookies para rastrearte en otros
            sitios web.
          </p>
        </Section>

        <Section title="Más información">
          <p>
            Para entender cómo tratamos tus datos personales, lee nuestra{" "}
            <a href="/legal/privacy" className="text-primary underline">Política de Privacidad</a>.
            Para dudas sobre cookies, escríbenos a{" "}
            <a href="mailto:privacidad@lilian.mx" className="text-primary underline">privacidad@lilian.mx</a>.
          </p>
        </Section>

        <footer className="pt-8 mt-8 border-t border-ink/10 text-xs text-ink/50">
          Última actualización: 29 de agosto de 2026. Versión {VERSION}.
        </footer>
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-heading font-semibold text-ink">{title}</h2>
      <div className="space-y-3 text-sm sm:text-base text-ink/80 leading-relaxed [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_li]:leading-relaxed [&_code]:bg-soft [&_code]:px-1 [&_code]:rounded [&_code]:text-xs">
        {children}
      </div>
    </section>
  );
}
