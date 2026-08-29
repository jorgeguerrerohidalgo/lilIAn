import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Política de Privacidad — lilIAn",
  description:
    "Cómo lilIAn trata los datos personales de sus usuarios en cumplimiento de la Ley N° 21.719 de Chile.",
};

const VERSION = "v1 · vigente desde 2026-08-29";

export default function PrivacyPolicyPage() {
  return (
    <main lang="es" className="min-h-screen bg-gradient-to-b from-soft to-cream">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12 sm:py-16 space-y-8">
        <header>
          <p className="text-xs uppercase tracking-widest text-ink/50">Documento legal</p>
          <h1 className="mt-2 text-3xl sm:text-4xl font-heading font-bold text-ink tracking-tight">
            Política de Privacidad
          </h1>
          <p className="mt-2 text-sm text-ink/60">{VERSION}</p>
        </header>

        <Section title="1. Identificación del responsable">
          <p>
            <strong>Lilian SpA</strong> (en adelante, &ldquo;lilIAn&rdquo; o &ldquo;la Plataforma&rdquo;),
            RUT 76.XXX.XXX-X, domicilio en Santiago de Chile, es la responsable del tratamiento de los
            datos personales que recolecta a través de su plataforma SaaS de asistencia legal.
          </p>
          <p>
            Para efectos de la Ley N° 21.719 (publicada el 13 de diciembre de 2024, en vigencia general
            desde el 1 de diciembre de 2026), lilIAn actúa como responsable del tratamiento respecto de
            los datos de sus usuarios (abogados y equipos de bufetes) y como encargado del tratamiento
            respecto de los datos que esos usuarios suben a la plataforma sobre sus propios clientes.
          </p>
        </Section>

        <Section title="2. Datos personales que tratamos">
          <p>Tratamos las siguientes categorías de datos:</p>
          <ul>
            <li>
              <strong>Datos de identificación y contacto</strong>: nombre completo, correo electrónico,
              teléfono, organización a la que perteneces.
            </li>
            <li>
              <strong>Datos de autenticación</strong>: hash de contraseña (bcrypt), tokens de sesión
              firmados, dirección IP de inicio de sesión.
            </li>
            <li>
              <strong>Datos de uso de la plataforma</strong>: casos legales creados, documentos cargados,
              consultas realizadas al chat asistente, métricas de uso agregadas.
            </li>
            <li>
              <strong>Datos sensibles (art. 11 Ley 21.719)</strong>: solo cuando el usuario los sube
              voluntariamente, en el contexto de un caso legal (por ejemplo, datos de salud en un
              proceso por accidente laboral). Estos datos se tratan bajo base de licitud de
              consentimiento explícito o, cuando corresponda, para el ejercicio de derechos en sede
              judicial.
            </li>
          </ul>
        </Section>

        <Section title="3. Finalidades y bases de licitud">
          <p>Tratamos tus datos personales para las siguientes finalidades:</p>
          <ol>
            <li>
              <strong>Prestar el servicio contratado</strong> (base de licitud: ejecución de contrato,
              art. 6 Ley 21.719).
            </li>
            <li>
              <strong>Cumplir obligaciones legales y regulatorias</strong> (base de licitud: obligación
              legal, art. 6 Ley 21.719), incluyendo conservación de documentos tributarios y
              respuesta a requerimientos de la Agencia de Protección de Datos Personales.
            </li>
            <li>
              <strong>Mejorar la plataforma</strong> mediante análisis agregados y seudonimizados
              (base de licitud: interés legítimo, art. 6 Ley 21.719). Nunca usamos tus documentos
              para entrenar modelos de terceros.
            </li>
            <li>
              <strong>Marketing transaccional</strong> (correos sobre cambios críticos del servicio,
              boletas, alertas de seguridad): base de licitud, ejecución de contrato. No incluye
              newsletter promocional, el cual requiere consentimiento separado.
            </li>
            <li>
              <strong>Marketing promocional</strong> (newsletter, invitaciones a webinars): base de
              licitud, consentimiento, que puedes revocar en cualquier momento.
            </li>
          </ol>
        </Section>

        <Section title="4. Destinatarios y transferencias internacionales">
          <p>
            Para prestar el servicio compartimos datos — estrictamente los necesarios — con los
            siguientes proveedores (encargados de tratamiento, art. 21 Ley 21.719):
          </p>
          <ul>
            <li>
              <strong>Supabase Inc.</strong> (base de datos PostgreSQL y almacenamiento): datos en
              regiones us-east-1 (AWS). DPA vigente con cláusulas estándar.
            </li>
            <li>
              <strong>OpenAI</strong> (modelos de lenguaje y embeddings): los prompts enviados son
              procesados en infraestructura de OpenAI fuera de Chile. No usamos tus datos para
              entrenar modelos.
            </li>
            <li>
              <strong>Anthropic</strong> (modelos de lenguaje): idénticas garantías que OpenAI. DPA en
              revisión al 2026-08-29 — actualizaremos este documento cuando esté firmado.
            </li>
            <li>
              <strong>Upstash</strong> (Redis gestionado): regiones US-east-1. Solo se almacenan
              tokens revocados y rate-limit counters, no datos de casos.
            </li>
            <li>
              <strong>Stripe</strong> (pagos): solo cuando contratas un plan de pago. Stripe es
              controlador independiente respecto de los datos de tarjeta.
            </li>
            <li>
              <strong>Resend</strong> (email transaccional): solo direcciones de email y metadatos de
              envío, no contenido del caso.
            </li>
            <li>
              <strong>Sentry</strong> (observabilidad): solo trazas de error y eventos técnicos, no
              contenido de casos. Datos scrubbing activo.
            </li>
          </ul>
          <p>
            Cada uno de estos proveedores tiene firmado (o está en proceso de firma) un contrato de
            encargo de tratamiento conforme al art. 21 de la Ley 21.719. No transferimos datos a
            otros terceros sin tu consentimiento, salvo obligación legal.
          </p>
        </Section>

        <Section title="5. Plazos de conservación">
          <p>
            Conservamos tus datos personales mientras mantengas una cuenta activa y durante los plazos
            legales aplicables con posterioridad. Concretamente:
          </p>
          <ul>
            <li>Datos de cuenta: mientras la cuenta esté activa + 12 meses tras su cierre.</li>
            <li>Documentos de casos: mientras el caso esté activo + 5 años (plazo prescripción civil).</li>
            <li>
              Datos de facturación: 6 años desde la emisión del comprobante (Código Tributario).
            </li>
            <li>
              Logs de auditoría: 5 años (cumplimiento Ley 21.719 + SOC 2 readiness).
            </li>
            <li>
              Registro de consentimientos: indefinidamente, como prueba del consentimiento otorgado.
            </li>
          </ul>
        </Section>

        <Section title="6. Tus derechos (ARCO + portabilidad + bloqueo)">
          <p>
            La Ley 21.719 te garantiza los siguientes derechos, todos gratuitos y ejercibles en un
            plazo máximo de 30 días corridos:
          </p>
          <ul>
            <li><strong>Acceso</strong>: confirmar si tratamos tus datos y obtener una copia.</li>
            <li><strong>Rectificación</strong>: corregir datos inexactos o incompletos.</li>
            <li><strong>Supresión</strong>: solicitar la eliminación de tus datos cuando proceda.</li>
            <li><strong>Oposición</strong>: oponerte a un tratamiento específico.</li>
            <li><strong>Portabilidad</strong>: recibir tus datos en formato electrónico estructurado.</li>
            <li><strong>Bloqueo</strong>: suspender temporalmente el tratamiento mientras se resuelve otra solicitud.</li>
          </ul>
          <p>
            Para ejercerlos, ve a <a href="/dashboard/settings/privacy" className="text-primary underline">Configuración &rarr; Privacidad</a>{" "}
            una vez iniciada sesión, o escríbenos a{" "}
            <a href="mailto:privacidad@lilian.mx" className="text-primary underline">privacidad@lilian.mx</a>.
          </p>
        </Section>

        <Section title="7. Seguridad de los datos">
          <p>
            Implementamos medidas técnicas y organizativas apropiadas conforme al art. 26 de la Ley
            21.719: cifrado en tránsito (TLS 1.3), cifrado en reposo (PostgreSQL cifrado a nivel de
            disco), seudonimización en logs, control de acceso por rol (RBAC de 7 roles),
            autenticación multifactor disponible para administradores, registros de auditoría
            inmutables, y pruebas de penetración anuales.
          </p>
        </Section>

        <Section title="8. Notificación de incidentes">
          <p>
            En caso de una vulneración de seguridad que afecte significativamente tus derechos,
            notificaremos a la Agencia de Protección de Datos Personales en un plazo no mayor a 72
            horas desde su detección, y a ti directamente si los datos comprometidos son sensibles o
            te ponen en riesgo (art. 29 Ley 21.719).
          </p>
        </Section>

        <Section title="9. Decisiones automatizadas">
          <p>
            lilIAn utiliza inteligencia artificial para asistir el trabajo legal, pero <strong>no toma
            decisiones automatizadas con efectos jurídicos significativos</strong> sobre los titulares
            sin intervención humana. El semáforo de riesgo es una sugerencia; la decisión final la toma
            un abogado habilitado. Si en el futuro incorporáramos decisiones automatizadas,，我们将
            realizaremos una Evaluación de Impacto en Protección de Datos (DPIA, art. 25) y te lo
            comunicaremos con antelación.
          </p>
        </Section>

        <Section title="10. Cambios a esta política">
          <p>
            Podemos modificar esta política para reflejar cambios legales, técnicos o de operación.
            Cuando lo hagamos, te avisaremos con al menos 30 días de anticipación por correo
            electrónico y mediante un aviso visible al iniciar sesión. Si los cambios son materiales,
            solicitaremos tu consentimiento nuevamente antes de continuar.
          </p>
          <p className="text-xs text-ink/50">
            Esta política se publica simultáneamente en <a href="/legal/terminos" className="underline">Términos de Uso</a>{" "}
            y <a href="/legal/cookies" className="underline">Política de Cookies</a>, formando un solo cuerpo
            contractual.
          </p>
        </Section>

        <Section title="11. Contacto del Delegado de Protección de Datos">
          <p>
            Conforme al art. 47 de la Ley 21.719, lilIAn designa como punto de contacto principal para
            efectos de protección de datos personales a su Delegado de Protección de Datos (DPO):
          </p>
          <p>
            <strong>Delegado de Protección de Datos — lilIAn</strong>
            <br />
            <a href="mailto:dpo@lilian.mx" className="text-primary underline">dpo@lilian.mx</a>
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
      <div className="space-y-3 text-sm sm:text-base text-ink/80 leading-relaxed [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1 [&_li]:leading-relaxed">
        {children}
      </div>
    </section>
  );
}
