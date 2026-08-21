/**
 * Frontend Sentry helper (S4.7).
 *
 * Mirrors the backend ``capture_exception_with_context`` API. When
 * Sentry is not initialized (no DSN configured) this is a no-op so
 * the rest of the app continues to work.
 *
 * Use this in client-side error boundaries, async handlers that
 * swallow errors, and any UI code that wants to attach breadcrumbs
 * to subsequent events.
 */

type SentryLike = {
  captureException: (error: unknown) => void;
  setContext: (key: string, context: Record<string, unknown>) => void;
  setTag: (key: string, value: string) => void;
  setUser: (user: { id: string; email?: string } | null) => void;
};

let cachedSentry: SentryLike | null | undefined;

async function getSentry(): Promise<SentryLike | null> {
  if (cachedSentry !== undefined) return cachedSentry;
  // The SDK is large; only load it when the DSN is configured.
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) {
    cachedSentry = null;
    return null;
  }
  try {
    const mod = await import("@sentry/nextjs");
    cachedSentry = mod as unknown as SentryLike;
    return cachedSentry;
  } catch {
    cachedSentry = null;
    return null;
  }
}

export interface CaptureContext {
  /** Logical area the error came from (e.g. "matter.detail"). */
  area?: string;
  /** Free-form extra fields. */
  extra?: Record<string, unknown>;
  /** User email if available. */
  userEmail?: string;
}

/**
 * Capture an exception with structured context. Safe to call from any
 * client-side code path — including render-time error boundaries.
 */
export async function captureExceptionWithContext(
  error: unknown,
  context: CaptureContext = {},
): Promise<void> {
  const sentry = await getSentry();
  if (!sentry) {
    if (typeof console !== "undefined") {
      // eslint-disable-next-line no-console
      console.error("[lilian.sentry:disabled]", error, context);
    }
    return;
  }
  sentry.setTag("area", context.area || "unknown");
  sentry.setContext("lilian", {
    area: context.area,
    ...context.extra,
  });
  if (context.userEmail) {
    sentry.setUser({ id: "anon", email: context.userEmail });
  }
  sentry.captureException(error);
}
