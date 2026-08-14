import type { APIRequestContext, Page, BrowserContext } from "@playwright/test";

/**
 * S6-B1: Test-user fixture aligned with the post-S0-04 HttpOnly cookie
 * auth model. The auth token is no longer persisted to localStorage
 * (that was an XSS vector), so we cannot seed it directly. Instead we
 * either:
 *   - exercise the UI login form (loginViaUi), or
 *   - copy the cookie set by the backend into a fresh context
 *     (loginViaCookie).
 */

export const API_BASE = process.env.E2E_API_URL || "http://localhost:8000";
export const FRONTEND_BASE = process.env.E2E_BASE_URL || "http://localhost:3000";

export const AUTH_COOKIE_NAME = "lilian_auth_token";

export type TestUser = {
  email: string;
  password: string;
  fullName: string;
  accessToken: string;
};

/**
 * Build a unique email so tests can run in parallel without colliding.
 */
export function uniqueEmail(prefix = "e2e"): string {
  const stamp = Date.now();
  const rand = Math.random().toString(36).slice(2, 8);
  return `${prefix}-${stamp}-${rand}@lilian.test`;
}

/**
 * Generates a fresh user via the API. Goes through the backend directly
 * so we are not coupled to the UI register form.
 */
export async function createTestUser(
  request: APIRequestContext,
  overrides: Partial<{ email: string; password: string; fullName: string }> = {},
): Promise<TestUser> {
  const email = overrides.email ?? uniqueEmail("e2e");
  const password = overrides.password ?? "TestPassword123!";
  const fullName = overrides.fullName ?? "E2E Test User";

  const registerRes = await request.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email, password, full_name: fullName },
  });
  if (!registerRes.ok()) {
    throw new Error(
      `Failed to register test user: ${registerRes.status()} ${await registerRes.text()}`,
    );
  }

  const loginRes = await request.post(`${API_BASE}/api/v1/auth/login`, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    form: { username: email, password },
  });
  if (!loginRes.ok()) {
    throw new Error(
      `Failed to login test user: ${loginRes.status()} ${await loginRes.text()}`,
    );
  }
  const { access_token } = await loginRes.json();

  return { email, password, fullName, accessToken: access_token };
}

/**
 * Logs in through the UI by filling the form on /auth/login. After
 * submission the backend sets an HttpOnly cookie and the app navigates
 * to /dashboard.
 */
export async function loginViaUi(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/auth/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: /iniciar sesi[oó]n/i }).click();
}

/**
 * Skips the UI login by issuing a real login request and copying the
 * auth cookie that the backend set on the API response into the
 * browser context. Use this when a test only cares about the
 * post-login surface and we want to skip the form interaction.
 */
export async function loginViaCookie(
  context: BrowserContext,
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<void> {
  const loginRes = await request.post(`${API_BASE}/api/v1/auth/login`, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    form: { username: email, password },
  });
  if (!loginRes.ok()) {
    throw new Error(
      `Failed to login test user: ${loginRes.status()} ${await loginRes.text()}`,
    );
  }

  // FastAPI/Starlette sets the cookie on the response. Pull it from the
  // Set-Cookie header so the test browser can authenticate subsequent
  // requests without going through the UI.
  const setCookie = loginRes.headers()["set-cookie"] ?? "";
  const match = setCookie.match(new RegExp(`(${AUTH_COOKIE_NAME}=[^;]+)`));
  if (!match) {
    throw new Error(
      `Login response did not set ${AUTH_COOKIE_NAME} cookie. Got: ${setCookie}`,
    );
  }
  const cookieValue = match[1];

  await context.addCookies([
    {
      name: AUTH_COOKIE_NAME,
      value: cookieValue.split("=")[1],
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
}