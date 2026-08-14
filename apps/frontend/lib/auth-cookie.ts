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

/**
 * Comprueba si la cookie de autenticación está presente en el browser.
 *
 * Solo funciona en el cliente (no SSR). Retorna ``false`` durante
 * server-side rendering.
 *
 * @returns ``true`` si la cookie existe, ``false`` en caso contrario.
 */
export function hasAuthCookie(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie.split("; ").some((c) => c.startsWith(`${AUTH_COOKIE_NAME}=`));
}

/**
 * Lee un token legacy desde localStorage. Código nuevo NO debe usar esto.
 *
 * Los componentes que aún llamen ``localStorage.getItem("token")`` se
 * migrarán a auth basada en cookies en sprints posteriores.
 *
 * @returns Token legacy (``"token"`` o ``"access_token"``) o ``null``.
 */
export function getLegacyToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    window.localStorage.getItem("token") ||
    window.localStorage.getItem("access_token")
  );
}

/**
 * Limpia todas las copias locales del token de auth. Llamar tras logout.
 *
 * No-op en SSR.
 */
export function clearLegacyTokens(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("token");
  window.localStorage.removeItem("access_token");
}