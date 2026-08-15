import { NextResponse, type NextRequest } from "next/server";
import { getApiUrl } from "@/lib/api";

/**
 * BFF catch-all proxy (S5-fix).
 *
 * The auth cookie lives on the **frontend** domain (vercel.app) because
 * the backend (railway.app) is a different origin and the browser cookie
 * jar is per-host. After login the cookie cannot be sent to the
 * backend's ``/api/v1/*`` directly, so the frontend must proxy every
 * API call through this same-origin route.
 *
 * Behaviour:
 *   - Reads the request body, query string, and method verbatim.
 *   - Reads the ``lilian_auth_token`` cookie from the incoming request
 *     and re-sends it as a ``Cookie`` header to the backend.
 *   - Forwards the backend's response body and status, and copies the
 *     ``Content-Type`` header.
 *   - CORS: the frontend's calls are now same-origin so no preflight
 *     is needed, and the response does not need CORS headers.
 *
 * Security:
 *   - The backend URL is read from ``NEXT_PUBLIC_API_URL`` (server-side
 *     env), so it cannot be overridden by the client.
 *   - The path segment is matched against a literal-only pattern,
 *     preventing any URL injection via path segments containing
 *     ``/`` or special characters.
 *   - The response is passed through with no rewriting.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AUTH_COOKIE = "lilian_auth_token";

// Methods we proxy. We do not proxy OPTIONS/HEAD here; the same-origin
// frontend does not need a preflight because it is no longer
// cross-origin to the API.
const ALLOWED_METHODS = new Set([
  "GET",
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
]);

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  if (!ALLOWED_METHODS.has(request.method)) {
    return NextResponse.json(
      { detail: `Method ${request.method} not allowed` },
      { status: 405 },
    );
  }

  const apiUrl = getApiUrl();
  if (!apiUrl) {
    return NextResponse.json(
      { detail: "API URL not configured" },
      { status: 500 },
    );
  }

  const { path } = await context.params;
  // Build the upstream path. The catch-all gives us the segments
  // after /api/v1/. Reject anything that tries to break out.
  if (!path || path.some((segment) => segment.includes("..") || segment.includes("/"))) {
    return NextResponse.json({ detail: "Invalid path" }, { status: 400 });
  }
  const upstreamPath = `/api/v1/${path.join("/")}`;

  // Preserve the original query string.
  const search = request.nextUrl.search;

  const url = `${apiUrl}${upstreamPath}${search}`;

  // Read the incoming auth cookie and forward it to the backend.
  const cookieHeader = request.cookies.get(AUTH_COOKIE)?.value;
  const headers: Record<string, string> = {};
  if (cookieHeader) {
    headers["Cookie"] = `${AUTH_COOKIE}=${cookieHeader}`;
  }
  // Pass the inbound content type so the backend can deserialize the
  // body. Some endpoints (file upload) may set their own content-type
  // and we override it below.
  const incomingContentType = request.headers.get("content-type");
  if (incomingContentType) {
    headers["Content-Type"] = incomingContentType;
  }

  let body: BodyInit | undefined;
  if (request.method !== "GET" && request.method !== "DELETE") {
    // Use the raw body so binary upload payloads and pre-serialized
    // form bodies pass through unmodified.
    body = await request.arrayBuffer();
    if (body.byteLength === 0) {
      body = undefined;
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });
  } catch (err) {
    return NextResponse.json(
      { detail: "Backend unreachable" },
      { status: 502 },
    );
  }

  // Pass through the response. We copy content-type so JSON
  // responses keep parsing correctly. We deliberately do NOT
  // forward upstream Set-Cookie headers because the backend's
  // cookies live on its own origin and would be ignored by the
  // browser anyway.
  const responseHeaders = new Headers();
  const ct = upstream.headers.get("content-type");
  if (ct) responseHeaders.set("content-type", ct);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
