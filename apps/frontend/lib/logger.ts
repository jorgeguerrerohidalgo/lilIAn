/**
 * Centralized logger for the lilIAn frontend (S5-03).
 *
 * Replaces scattered ``console.log`` / ``console.error`` calls with a
 * thin wrapper that is a no-op in production (controlled by
 * ``NEXT_PUBLIC_ENABLE_LOGS``) but writes to ``stderr`` in development
 * so error tracking works.
 *
 * IMPORTANT: never log tokens, cookies, or PII through this API.
 */

type LogLevel = "debug" | "info" | "warn" | "error";

const ENABLED = process.env.NODE_ENV !== "production";

function formatValue(v: unknown): string {
  if (v === null) return "null";
  if (v === undefined) return "undefined";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (v instanceof Error) {
    return `${v.name}: ${v.message}`;
  }
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function emit(level: LogLevel, message: string, meta?: unknown) {
  if (!ENABLED && level !== "error") return;
  const ts = new Date().toISOString();
  let payload = "";
  if (meta !== undefined) {
    if (Array.isArray(meta)) {
      payload = meta.map(formatValue).join(" ");
    } else {
      payload = formatValue(meta);
    }
  }
  const line = `[${ts}] [${level.toUpperCase()}] ${message}${payload ? " " + payload : ""}`;
  if (level === "error" || level === "warn") {
    // eslint-disable-next-line no-console
    console.error(line);
  } else {
    // eslint-disable-next-line no-console
    console.warn(line);
  }
}

/**
 * Logger centralizado del frontend lilIAn.
 *
 * Sustituye los ``console.log`` / ``console.error`` dispersos por una
 * API que es no-op en producción (controlada por
 * ``NEXT_PUBLIC_ENABLE_LOGS``) pero escribe en ``stderr`` en dev.
 * Los errores siempre se emiten (incluso en producción) para que las
 * herramientas de monitorización los capturen.
 *
 * IMPORTANTE: nunca loguear tokens, cookies ni PII con esta API.
 */
export const logger = {
  /**
   * Nivel debug: mensajes de diagnóstico, deshabilitados en producción.
   *
   * @param msg - Mensaje principal.
   * @param meta - Metadatos opcionales (objeto, array o varios args).
   */
  debug: (msg: string, ...meta: unknown[]) => emit("debug", msg, meta.length === 0 ? undefined : meta.length === 1 ? meta[0] : meta),
  /**
   * Nivel info: eventos informativos de negocio.
   *
   * @param msg - Mensaje principal.
   * @param meta - Metadatos opcionales (objeto, array o varios args).
   */
  info: (msg: string, ...meta: unknown[]) => emit("info", msg, meta.length === 0 ? undefined : meta.length === 1 ? meta[0] : meta),
  /**
   * Nivel warn: situaciones anómalas que no impiden el funcionamiento.
   *
   * @param msg - Mensaje principal.
   * @param meta - Metadatos opcionales (objeto, array o varios args).
   */
  warn: (msg: string, ...meta: unknown[]) => emit("warn", msg, meta.length === 0 ? undefined : meta.length === 1 ? meta[0] : meta),
  /**
   * Nivel error: errores recuperables. Siempre se emite, incluso en prod.
   *
   * @param msg - Mensaje principal.
   * @param meta - Metadatos opcionales (objeto, array o varios args).
   */
  error: (msg: string, ...meta: unknown[]) => emit("error", msg, meta.length === 0 ? undefined : meta.length === 1 ? meta[0] : meta),
};
