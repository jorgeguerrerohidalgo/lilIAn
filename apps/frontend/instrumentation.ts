// Next.js instrumentation hook (S4.7).
// Next.js 14 looks for this file at the root of the project (or
// ``src/instrumentation.ts`` if you use a src dir). When present,
// the runtime calls the exported ``register`` function exactly once
// on startup, both on the Edge and Node.js runtimes. We use it to
// bootstrap Sentry so the SDK captures errors from the very first
// request, including any middleware that runs before our app code.

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  } else if (process.env.NEXT_RUNTIME === "edge") {
    // The edge bundle is configured in sentry.edge.config.ts so we
    // can keep server-side handlers pointed at the Node SDK.
    await import("./sentry.edge.config");
  }
}
