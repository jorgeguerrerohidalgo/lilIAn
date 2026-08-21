// Sentry edge-runtime init (S4.7).
// Runs on the Vercel edge for middleware. Required by
// ``@sentry/nextjs`` when middleware is enabled and Sentry is active.

const SENTRY_DSN = process.env.SENTRY_DSN;
const SENTRY_ENVIRONMENT = process.env.SENTRY_ENVIRONMENT || "development";

if (SENTRY_DSN) {
  void import("@sentry/nextjs").then((Sentry) => {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: SENTRY_ENVIRONMENT,
      tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE || "0.1"),
      sendDefaultPii: false,
    });
  });
}
