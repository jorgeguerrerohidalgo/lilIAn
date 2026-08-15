import type { Page, Expect } from "@playwright/test";

/**
 * S6-B1: shared helpers for the E2E suite.
 *
 * Keep this file focused on small, reusable utilities. Anything that
 * grows past a handful of lines or starts to need fixtures of its own
 * should move into a dedicated helper module so the suite stays
 * readable.
 */

/**
 * Wait for the URL to match a regex, but fail loudly with context
 * instead of timing out silently.
 */
export async function waitForUrl(page: Page, pattern: RegExp, timeoutMs = 10_000): Promise<void> {
  await page.waitForURL(pattern, { timeout: timeoutMs });
}

/**
 * Returns the value of the auth cookie if present, otherwise null.
 * Useful for assertions about session state.
 */
export async function readAuthCookie(page: Page): Promise<string | null> {
  const cookies = await page.context().cookies();
  const cookie = cookies.find((c) => c.name === "lilian_auth_token");
  return cookie ? cookie.value : null;
}

/**
 * Clears all cookies and storage for the current context. Use between
 * tests to avoid leaking sessions.
 */
export async function resetContext(page: Page): Promise<void> {
  await page.context().clearCookies();
  await page.evaluate(() => {
    try {
      window.localStorage.clear();
      window.sessionStorage.clear();
    } catch {
      // Storage access can throw in cross-origin frames; safe to ignore
      // since the test already runs against the right origin.
    }
  });
}

/**
 * Convenience assertion wrapper: "page is on the login page".
 */
export function expectOnLoginPage(expect: typeof import("@playwright/test").expect, page: Page) {
  return expect(page).toHaveURL(/\/auth\/login/);
}

/**
 * Convenience assertion wrapper: "page is on the dashboard".
 */
export function expectOnDashboard(expect: typeof import("@playwright/test").expect, page: Page) {
  return expect(page).toHaveURL(/\/dashboard/);
}