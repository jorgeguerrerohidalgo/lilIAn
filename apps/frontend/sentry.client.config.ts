// Sentry client-side init (S4.7).
// Runs on the browser. When SENTRY_DSN is unset the SDK is a no-op so
// we never ship reports in development. The build also checks that
// this file is present and well-formed during `next build` (the SDK
// self-disables when its DSN is undefined).

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;
const SENTRY_ENVIRONMENT = process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development";

if (SENTRY_DSN) {
  // Lazy-load to avoid impacting bundle size when Sentry is disabled.
  void import("@sentry/nextjs").then((Sentry) => {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: SENTRY_ENVIRONMENT,
      // Sample 10% of page-load transactions in production. Increase
      // via NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE when needed.
      tracesSampleRate: Number(
        process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || "0.1",
      ),
      // Don't send PII unless explicitly turned on.
      sendDefaultPii: false,
    });
  });
}
