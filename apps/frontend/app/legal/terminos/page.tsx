import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Términos de Uso — lilIAn",
  description: "Términos que rigen el uso de la plataforma lilIAn.",
};

const VERSION = "v1 · vigente desde 2026-08-29";

export default function TermsPage() {
  return (
    <main lang="es" className="min-h-screen bg-gradient-to-b from-soft to-cream">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16 space-y-8">
        <header>
          <p className="text-xs uppercase tracking-widest text-ink/50">Documento legal</p>
          <h1 className="mt-2 text-3xl sm:text-4xl font-heading font-bold text-ink tracking-tight">
            Términos de Uso
          </h1>
          <p className="mt-2 text-sm text-ink/60">{VERSION}</p>
        </header>

        <Section title="1. Aceptación">
          <p>
            Al crear una cuenta o utilizar lilIAn, aceptas estos Términos de Uso, nuestra{" "}
            <a href="/legal/privacy" className="text-primary underline">Política de Privacidad</a> y
            nuestra <a href="/legal/cookies" className="text-primary underline">Política de Cookies</a>.
            Si no estás de acuerdo, no uses la plataforma.
          </p>
        </Section>

        <Section title="2. Naturaleza del servicio">
          <p>
            lilIAn es una <strong>herramienta de asistencia</strong> para profesionales del derecho.
            Toda sugerencia, resumen, análisis o documento generado por la plataforma es
            <strong> material de apoyo</strong>; la responsabilidad profesional final recae
            exclusivamente en el abogado habilitado que utiliza la plataforma.
          </p>
          <p>
            lilIAn no ejerce el derecho, no actúa como abogado y no entrega asesoría legal personalizada.
            Nada en la plataforma sustituye el juicio profesional de un abogado inscrito en el
            Colegio de Abogados de Chile o la jurisdicción que corresponda.
          </p>
        </Section>

        <Section title="3. Cuenta y elegibilidad">
          <p>
            Para usar lilIAn debes: (a) tener al menos 18 años; (b) ser abogado habilitado,
            estudiante de derecho bajo supervisión, o personal autorizado de un bufete/empresa cliente;
            (c) proporcionar información veraz al registrarte; (d) mantener la confidencialidad de tus
            credenciales.
          </p>
          <p>
            Si eres menor de 16 años, no puedes usar la plataforma sin autorización de tu
            representante legal, conforme al art. 14 de la Ley 21.719.
          </p>
        </Section>

        <Section title="4. Planes y pagos">
          <p>
            Ofrecemos un plan gratuito limitado y planes de pago. Los precios, límites y características
            de cada plan están publicados en <a href="/pricing" className="text-primary underline">/pricing</a>.
            Los pagos se procesan a través de Stripe; al contratar un plan aceptas también los términos
            de Stripe.
          </p>
          <p>
            Puedes cancelar tu plan de pago en cualquier momento desde tu panel de facturación. La
            cancelación es efectiva al final del ciclo de facturación en curso.
          </p>
        </Section>

        <Section title="5. Uso aceptable">
          <p>Está prohibido usar lilIAn para:</p>
          <ul>
            <li>Subir documentos que no tienes derecho a tratar (sin autorización del titular).</li>
            <li>Intentar eludir las medidas de seguridad o realizar ingeniería inversa.</li>
            <li>Usar la plataforma para actividades ilegales, fraude, o cualquier uso que viole la Ley 21.719.</li>
            <li>Compartir credenciales con terceros no autorizados.</li>
            <li>Extraer sistemáticamente datos o modelos de la plataforma (scraping, probing).</li>
          </ul>
          <p>
            Podemos suspender o terminar tu cuenta si detectamos uso que viola estos términos, previa
            notificación salvo que la urgencia lo impida.
          </p>
        </Section>

        <Section title="6. Propiedad intelectual">
          <p>
            La plataforma, sus modelos, prompts, interfaz y código son propiedad de lilIAn SpA o sus
            licenciantes. Los <strong>documentos que tú subes</strong> siguen siendo tuyos; nos
            otorgas una licencia limitada para procesarlos y, cuando uses planes con
            almacenamiento compartido dentro de tu organización, para que tu equipo los acceda
            conforme a los permisos que configures.
          </p>
          <p>
            Los <strong>análisis, informes y documentos generados</strong> por la plataforma para ti
            son tuyos y de tu organización.
          </p>
        </Section>

        <Section title="7. Confidencialidad profesional">
          <p>
            lilIAn entiende la naturaleza confidencial del trabajo legal. Implementamos medidas
            para mantener la confidencialidad de la información que tratas: cifrado en tránsito y
            reposo, control de acceso por organización, registros de auditoría, y obligación
            contractual de confidencialidad para nuestros empleados y subprocesadores.
          </p>
          <p>
            La plataforma no usa tus documentos ni los datos que contienen para entrenar modelos de
            terceros, conforme a nuestra <a href="/legal/privacy" className="text-primary underline">Política de Privacidad</a>.
          </p>
        </Section>

        <Section title="8. Limitación de responsabilidad">
          <p>
            lilIAn se entrega &ldquo;tAL CUAL&rdquo;. Hasta el máximo permitido por la ley chilena, no somos
            responsables por daños indirectos, lucro cesante o pérdida de datos causados por (a)
            mal uso de la plataforma, (b) decisiones tomadas con base en sugerencias automatizadas sin
            revisión humana, (c) indisponibilidad temporal del servicio, (d) eventos fuera de
            nuestro control razonable.
          </p>
          <p>
            Nuestra responsabilidad agregada por cualquier reclamo no excederá el monto total que nos
            hayas pagado en los 12 meses anteriores al hecho que originó el reclamo.
          </p>
        </Section>

        <Section title="9. Suspensión y terminación">
          <p>
            Puedes cerrar tu cuenta en cualquier momento desde Configuración &rarr; Privacidad
            (ejercicio del derecho de supresión, Ley 21.719 art. 17). Conservaremos los datos por los
            plazos legales mínimos descritos en nuestra Política de Privacidad.
          </p>
          <p>
            Podemos suspender o terminar el servicio si: (a) violas estos Términos; (b) no pagas un
            plan de pago; (c) lo requiere una autoridad competente.
          </p>
        </Section>

        <Section title="10. Ley aplicable y jurisdicción">
          <p>
            Estos términos se rigen por las leyes de la República de Chile. Cualquier controversia
            se somete a los tribunales de Santiago de Chile, sin perjuicio de los derechos del
            consumidor que la ley chilena reconoce en favor del usuario.
          </p>
        </Section>

        <Section title="11. Cambios">
          <p>
            Podemos modificar estos Términos para reflejar cambios legales, técnicos o comerciales.
            Te avisaremos con al menos 30 días de anticipación por correo electrónico y un aviso
            visible al iniciar sesión. Si los cambios son materiales, podrás cerrar tu cuenta sin
            penalización antes de la fecha de entrada en vigencia.
          </p>
        </Section>

        <Section title="12. Contacto">
          <p>
            ¿Dudas sobre estos Términos? Escríbenos a{" "}
            <a href="mailto:legal@lilian.mx" className="text-primary underline">legal@lilian.mx</a>.
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
      <div className="space-y-3 text-sm sm:text-base text-ink/80 leading-relaxed [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_li]:leading-relaxed">
        {children}
      </div>
    </section>
  );
}
