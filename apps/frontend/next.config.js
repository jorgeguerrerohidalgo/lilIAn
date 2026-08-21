/** @type {import('next').NextConfig} */
const backendOrigin = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const securityHeaders = [
  // Content Security Policy — strict baseline.
  // - 'self' only for scripts (Next.js inlines a hydration bootstrap on
  //   `/` route; we allow 'unsafe-inline' for compatibility until we
  //   wire per-request nonces). For inline styles, Tailwind + Next.js
  //   both ship runtime-injected <style> tags, so 'unsafe-inline' is
  //   unavoidable on style-src.
  // - connect-src allows the backend (Railway) plus Sentry ingest if
  //   SENTRY_DSN is set later.
  // - frame-ancestors 'none' blocks iframe embedding (X-Frame-Options
  //   is set to DENY for legacy browsers).
  // - object-src 'none' disables Flash/Java applets.
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      `connect-src 'self' ${backendOrigin} https://*.sentry.io`,
      "frame-ancestors 'none'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
  // HSTS — force HTTPS for one year, including subdomains. Preload-ready.
  {
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains; preload",
  },
  // Block MIME sniffing.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Block framing entirely (CSP frame-ancestors is the modern equivalent
  // but legacy browsers still need this).
  { key: "X-Frame-Options", value: "DENY" },
  // Referer leakage control.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Disable powerful features we don't use.
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
];

const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
  async headers() {
    return [
      {
        // Apply to everything served by Next.js (pages, _next assets, API).
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

module.exports = nextConfig;
