import type { Page } from "@playwright/test";

/**
 * S6-B1: shared helpers used by the legacy orphan suite living under
 * ``tests/e2e/tests/``. Mirrors the helpers under
 * ``apps/frontend/tests/e2e/fixtures/`` so the two suites stay in
 * lockstep.
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
 */
export async function readAuthCookie(page: Page): Promise<string | null> {
  const cookies = await page.context().cookies();
  const cookie = cookies.find((c) => c.name === "lilian_auth_token");
  return cookie ? cookie.value : null;
}

/**
 * Clears all cookies and storage for the current context.
 */
export async function resetContext(page: Page): Promise<void> {
  await page.context().clearCookies();
  await page.evaluate(() => {
    try {
      window.localStorage.clear();
      window.sessionStorage.clear();
    } catch {
      // Storage can throw in cross-origin frames; safe to ignore here.
    }
  });
}