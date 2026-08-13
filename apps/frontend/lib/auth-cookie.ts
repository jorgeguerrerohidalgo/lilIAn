/**
 * Cookie-based auth helper for the lilian frontend (S0-04).
 *
 * The backend sets an HttpOnly cookie (`lilian_auth_token`) on successful
 * login. JavaScript cannot read HttpOnly cookies directly, so:
 *
 *   - The browser sends the cookie automatically on same-origin requests.
 *   - For cross-origin (NEXT_PUBLIC_API_URL pointing at Railway), the
 *     frontend must also include ``credentials: 'include'`` and the
 *     backend must allow credentials with a specific origin (not ``*``).
 *   - For localStorage migration: components that still hold the legacy
 *     ``localStorage.token`` (or ``access_token``) value will keep working
 *     until they are migrated. New code must NOT read these.
 */

export const AUTH_COOKIE_NAME = "lilian_auth_token";

/** Returns true when the auth cookie is present (browser-side only). */
export function hasAuthCookie(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie.split("; ").some((c) => c.startsWith(`${AUTH_COOKIE_NAME}=`));
}

/**
 * Read a legacy token from localStorage. New code MUST NOT use this.
 * Existing components still calling ``localStorage.getItem("token")`` will
 * be migrated to cookie-based auth in subsequent sprints.
 */
export function getLegacyToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    window.localStorage.getItem("token") ||
    window.localStorage.getItem("access_token")
  );
}

/** Clear every local copy of the auth token. Call after logout. */
export function clearLegacyTokens(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("token");
  window.localStorage.removeItem("access_token");
}