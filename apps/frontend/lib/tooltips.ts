/**
 * Tooltip copy registry — S6.2.
 *
 * Single source of truth for every in-app tooltip string. Keeps the
 * strings in one place so we can audit wording, run i18n later, and avoid
 * the "twenty copies of the same sentence across files" anti-pattern.
 *
 * All copy is Spanish — matching the rest of the Lilian UI.
 */

export const TOOLTIPS = {
  uploadContract:
    "Sube un PDF, .docx o .txt. Se procesa automáticamente.",
  startAnalysis:
    "Genera un informe ejecutivo con riesgos, plazos y referencias legales.",
  reAnalyze:
    "Vuelve a ejecutar el análisis IA. Útil después de subir más documentos.",
  exportPdf:
    "Descarga el informe como PDF o Markdown para enviarlo al cliente.",
  findDeadlines:
    "Genera alertas de fechas límite con la IA.",
  chatInput:
    "Pregúntale lo que quieras sobre tu caso. Tiene acceso a tus documentos.",
  pendingAnalyses: "Análisis sin revisar.",
  currentPlan: "Tu suscripción y límites de uso.",
  newCase: "Crea un caso y agrupa aquí todos los documentos relacionados.",
  inviteTeam: "Envía una invitación por correo para unirse a tu organización.",
  supportWidget: "Contacta al equipo de soporte. Respondemos en menos de 24h.",
  billingUpgrade: "Ver planes y cambiar tu suscripción.",
  sampleContract: "Carga un contrato de ejemplo para probar el análisis.",
  exportMarkdown:
    "Copia el informe en Markdown para pegarlo en tu correo o documento.",
  manageSubscription: "Abre el portal de Stripe para actualizar tu tarjeta.",
} as const;

export type TooltipKey = keyof typeof TOOLTIPS;
