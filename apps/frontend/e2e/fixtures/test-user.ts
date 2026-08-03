import type { APIRequestContext, Page } from "@playwright/test";

export const API_BASE = process.env.E2E_API_URL || "http://localhost:8000";

export type TestUser = {
  email: string;
  password: string;
  fullName: string;
  accessToken: string;
};

/**
 * Creates a fresh user via the API and returns credentials + bearer token.
 * Goes through the backend directly so the test is not coupled to the UI register flow.
 */
export async function createTestUser(
  request: APIRequestContext,
  overrides: Partial<{ email: string; password: string; fullName: string }> = {},
): Promise<TestUser> {
  const email = overrides.email ?? `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@lilian.test`;
  const password = overrides.password ?? "TestPassword123!";
  const fullName = overrides.fullName ?? "E2E Test User";

  const registerRes = await request.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email, password, full_name: fullName },
  });
  if (!registerRes.ok()) {
    throw new Error(`Failed to register test user: ${registerRes.status()} ${await registerRes.text()}`);
  }

  const loginRes = await request.post(`${API_BASE}/api/v1/auth/login`, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    form: { username: email, password },
  });
  if (!loginRes.ok()) {
    throw new Error(`Failed to login test user: ${loginRes.status()} ${await loginRes.text()}`);
  }
  const { access_token } = await loginRes.json();

  return { email, password, fullName, accessToken: access_token };
}

/**
 * Sets the auth token in localStorage and navigates to the dashboard.
 * The frontend reads `token` from localStorage on protected pages.
 */
export async function loginViaUi(page: Page, email: string, password: string) {
  await page.goto("/auth/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: /iniciar sesi[oó]n/i }).click();
}

/**
 * Skips the UI login form by seeding localStorage with a valid token,
 * useful when a test only cares about the post-login surface.
 */
export async function loginByStorage(page: Page, token: string) {
  await page.addInitScript((t) => {
    window.localStorage.setItem("token", t as string);
  }, token);
  await page.goto("/dashboard");
}