import { NextResponse, type NextRequest } from "next/server";

/**
 * Cookie-aware route gate (S0-04).
 *
 * The HttpOnly `lilian_auth_token` cookie is set by the backend on
 * successful login. This middleware redirects unauthenticated users away
 * from protected routes. Note that this is an *informational* gate only:
 * the backend still validates the JWT and is the source of truth.
 */
const AUTH_COOKIE = "lilian_auth_token";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/matters",
  "/documents",
  "/precedents",
];

const PUBLIC_AUTH_PATHS = ["/auth/login", "/auth/register"];

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function isAuthPath(pathname: string): boolean {
  return PUBLIC_AUTH_PATHS.some((prefix) => pathname.startsWith(prefix));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasAuth = request.cookies.get(AUTH_COOKIE)?.value;

  // Already authenticated users hitting /auth/* are bounced to dashboard.
  if (hasAuth && isAuthPath(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  if (isProtectedPath(pathname) && !hasAuth) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/matters/:path*",
    "/documents/:path*",
    "/precedents/:path*",
    "/auth/:path*",
  ],
};