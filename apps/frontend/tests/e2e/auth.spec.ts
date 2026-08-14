import { test, expect } from "@playwright/test";
import {
  createTestUser,
  loginViaUi,
  uniqueEmail,
} from "./fixtures/test-user";
import {
  expectOnDashboard,
  expectOnLoginPage,
  readAuthCookie,
} from "./fixtures/test-helpers";

/**
 * S6-B1: smoke coverage for the auth surface.
 *
 * The login flow is the gateway to every other feature in the app, so
 * we cover three critical paths here:
 *
 *   1. A new user can register, log in, and land on /dashboard.
 *   2. The backend rejects bad passwords without leaking session state.
 *   3. An unauthenticated user hitting /dashboard is bounced to /auth/login.
 *
 * Selectors use the accessible name (`getByLabel`, `getByRole`) so the
 * tests double as a basic accessibility check.
 */

test.describe("Auth flow", () => {
  test("registers, logs in via the UI, and lands on the dashboard", async ({ page, request }) => {
    // Register a fresh user via the API so the test does not depend on
    // the register form's behavior (covered separately if we add it).
    const user = await createTestUser(request);

    await loginViaUi(page, user.email, user.password);

    // Successful login must redirect to /dashboard and the backend must
    // have set the HttpOnly auth cookie.
    await expectOnDashboard(expect, page);
    const cookie = await readAuthCookie(page);
    expect(cookie, "lilian_auth_token cookie should be set after login").toBeTruthy();

    // The dashboard exposes a heading in the layout — assert that the
    // post-login shell is actually mounted instead of just trusting the URL.
    await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
  });

  test("rejects an invalid password and keeps the user on /auth/login", async ({ page, request }) => {
    const user = await createTestUser(request);

    await page.goto("/auth/login");
    await page.getByLabel("Email").fill(user.email);
    await page.getByLabel("Contraseña").fill("definitely-not-the-password");
    await page.getByRole("button", { name: /iniciar sesi[oó]n/i }).click();

    // The login page surfaces backend errors inside a role="alert" region.
    await expect(page.getByRole("alert")).toBeVisible();
    await expectOnLoginPage(expect, page);

    // No auth cookie should be set on a failed login.
    const cookie = await readAuthCookie(page);
    expect(cookie).toBeNull();
  });

  test("redirects unauthenticated users away from /dashboard", async ({ page }) => {
    await page.goto("/dashboard");

    await expectOnLoginPage(expect, page);
  });

  test("register page accepts a brand-new email and redirects to login", async ({ page, request }) => {
    const email = uniqueEmail("register");

    await page.goto("/auth/register");
    await page.getByLabel("Nombre completo").fill("E2E Register User");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Contraseña").fill("TestPassword123!");
    await page.getByLabel("Confirmar contraseña").fill("TestPassword123!");
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    // Registration success navigates to /auth/login?registered=true
    await page.waitForURL(/\/auth\/login/, { timeout: 10_000 });

    // The user we just registered must be able to log in.
    const loginRes = await request.post("/api/v1/auth/login", {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      form: { username: email, password: "TestPassword123!" },
    });
    expect(loginRes.ok()).toBe(true);
  });
});