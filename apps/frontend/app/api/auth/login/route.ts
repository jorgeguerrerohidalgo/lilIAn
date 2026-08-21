import { NextResponse, type NextRequest } from "next/server";
import { getApiUrl } from "@/lib/api";
import { ERR_BFF } from "@/lib/i18n/es";

/**
 * BFF route (S5-fix): proxies the backend's /api/v1/auth/login and
 * rewrites the HttpOnly ``lilian_auth_token`` cookie onto the
 * frontend's own domain.
 *
 * Why this exists:
 *   - The browser cookie jar is **per-host**. The backend (Railway)
 *     can only set cookies for ``*.railway.app``. The frontend (Vercel)
 *     runs on ``*.vercel.app`` and the two domains share no parent.
 *   - The login fetch is cross-origin and uses ``credentials: include``,
 *     so the backend can authenticate the user. But the cookie it sets
 *     is **only** sent to ``*.railway.app``; it is never attached to
 *     requests targeting ``*.vercel.app`` — including the page
 *     navigation that the login form triggers via ``router.push()``.
 *   - Without a cookie on the frontend's domain, the Next.js
 *     middleware (which runs at the Vercel edge) cannot tell that the
 *     user is authenticated and bounces them back to /auth/login.
 *
 * This route is the standard BFF (Backend-for-Frontend) pattern: the
 * browser talks to its own same-origin endpoint, the endpoint talks to
 * the real backend, and the cookie is set on the frontend's domain so
 * the middleware can read it.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AUTH_COOKIE = "lilian_auth_token";

export async function POST(request: NextRequest) {
  const apiUrl = getApiUrl();
  if (!apiUrl) {
    return NextResponse.json(
      { detail: ERR_BFF.apiUrlNotConfigured },
      { status: 500 },
    );
  }

  // Re-send the body verbatim. The backend expects application/x-www-form-urlencoded.
  const body = await request.text();

  let backendRes: Response;
  try {
    backendRes = await fetch(`${apiUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      cache: "no-store",
    });
  } catch (err) {
    return NextResponse.json(
      { detail: ERR_BFF.backendUnreachable },
      { status: 502 },
    );
  }

  // Pass through the body + status from the backend, but rewrite the
  // Set-Cookie header so the cookie lives on the frontend's domain.
  const backendBody = await backendRes.text();
  const upstreamSetCookie = backendRes.headers.get("set-cookie");
  // Vercel always terminates TLS, so cookies there must be `Secure`.
  // Detect via `VERCEL=1` (set automatically by Vercel) in addition to
  // the request scheme — covers edge cases where Next.js sees `http:`
  // behind a proxy. Local dev over HTTP stays non-Secure so Chrome does
  // not silently drop the cookie.
  const isHttps =
    request.nextUrl.protocol === "https:" || process.env.VERCEL === "1";

  const headers = new Headers();
  // Copy content-type so the client gets a JSON body.
  const ct = backendRes.headers.get("content-type");
  if (ct) headers.set("content-type", ct);

  if (backendRes.ok && upstreamSetCookie) {
    // Pull the JWT value with a regex instead of naively splitting on `;`
    // and slicing the first segment. The naive approach broke whenever the
    // upstream Set-Cookie started with extra attributes in the first
    // segment, producing a corrupted Authorization header downstream and
    // a /api/v1/auth/me 401 that bounced users back to /auth/login.
    const match = upstreamSetCookie.match(/lilian_auth_token=([^;]+)/);
    const value = match ? match[1] : "";

    const cookieAttrs = [
      `${AUTH_COOKIE}=${value}`,
      "Path=/",
      "HttpOnly",
      "SameSite=Lax",
      `Max-Age=86400`,
      isHttps ? "Secure" : "",
    ]
      .filter(Boolean)
      .join("; ");

    headers.append("set-cookie", cookieAttrs);
  }

  return new NextResponse(backendBody, {
    status: backendRes.status,
    headers,
  });
}
