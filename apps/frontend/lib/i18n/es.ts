/**
 * Constantes de cadenas en español usadas en el lado de servidor (BFF) y
 * en componentes compartidos. La UI dentro de los componentes ya está en
 * español — aquí solo centralizamos los strings que aparecen en varios
 * archivos o que vienen de la capa de red (errores de BFF, validaciones).
 *
 * No es un sistema i18n completo: la app es monolingüe en español.
 */

export const ERR_BFF = {
  /** El servidor no tiene configurada la URL del backend. */
  apiUrlNotConfigured: "URL de API no configurada",
  /** El backend no responde (timeout, DNS, red). */
  backendUnreachable: "No se puede contactar al backend",
  /** Path construido por el catch-all que contiene segmentos prohibidos. */
  invalidPath: "Ruta inválida",
  /** Método HTTP no soportado por el proxy. */
  methodNotAllowed: (method: string): string => `Método ${method} no permitido`,
} as const;

export const TOUR = {
  storageKey: "lilian.welcomeTour.completed",
  steps: {
    newMatter: {
      breadcrumb: "Paso 1 de 3",
      title: "Sube un contrato",
      body:
        "Crea un caso y arrastra tu PDF o DOCX. La IA extrae cláusulas, fechas y partes automáticamente.",
    },
    analyze: {
      breadcrumb: "Paso 2 de 3",
      title: "Pulsa Analizar",
      body:
        "Una vez subido el documento, abre la pestaña «Documentos» del caso y lanza el análisis con un clic.",
    },
    report: {
      breadcrumb: "Paso 3 de 3",
      title: "Revisa tu reporte",
      body:
        "Riesgos, plazos y referencias legales quedan listos en la pestaña «Análisis IA». Puedes exportar el reporte a PDF.",
    },
  },
} as const;

export const VALIDATION = {
  email: "Ingresa un correo electrónico válido",
  passwordMin: "La contraseña debe tener al menos 8 caracteres",
  passwordStrong:
    "La contraseña debe incluir mayúsculas, minúsculas, números y un símbolo",
  required: "Este campo es obligatorio",
} as const;
