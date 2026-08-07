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

function emit(level: LogLevel, message: string, meta?: Record<string, unknown>) {
  if (!ENABLED && level !== "error") return;
  const ts = new Date().toISOString();
  const payload = meta ? ` ${JSON.stringify(meta)}` : "";
  const line = `[${ts}] [${level.toUpperCase()}] ${message}${payload}`;
  if (level === "error" || level === "warn") {
    // eslint-disable-next-line no-console
    console.error(line);
  } else {
    // eslint-disable-next-line no-console
    console.warn(line);
  }
}

export const logger = {
  debug: (msg: string, meta?: Record<string, unknown>) => emit("debug", msg, meta),
  info: (msg: string, meta?: Record<string, unknown>) => emit("info", msg, meta),
  warn: (msg: string, meta?: Record<string, unknown>) => emit("warn", msg, meta),
  error: (msg: string, meta?: Record<string, unknown>) => emit("error", msg, meta),
};