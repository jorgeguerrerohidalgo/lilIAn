// Sentry server-side init (S4.7).
// Runs on the Next.js Node server (server components, route handlers).
// Mirrors the client-side config but loads the server bundle so
// stack traces reference Node, not the browser.

const SENTRY_DSN = process.env.SENTRY_DSN;
const SENTRY_ENVIRONMENT = process.env.SENTRY_ENVIRONMENT || process.env.APP_ENV || "development";

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
