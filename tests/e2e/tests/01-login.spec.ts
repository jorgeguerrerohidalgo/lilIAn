import { test, expect } from "@playwright/test";
import { createTestUser, loginViaUi } from "../fixtures/test-user";

test.describe("Login", () => {
  test("happy path: user logs in with valid credentials and lands on dashboard", async ({ page, request }) => {
    const user = await createTestUser(request);

    await loginViaUi(page, user.email, user.password);

    await page.waitForURL(/\/dashboard/);
    await expect(page).toHaveURL(/\/dashboard/);

    const token = await page.evaluate(() => window.localStorage.getItem("token"));
    expect(token).toBeTruthy();
    expect(token).toBe(user.accessToken);
  });

  test("rejects invalid password and keeps user on login page", async ({ page, request }) => {
    const user = await createTestUser(request);

    await page.goto("/auth/login");
    await page.getByLabel("Email").fill(user.email);
    await page.getByLabel("Contraseña").fill("wrong-password");
    await page.getByRole("button", { name: /iniciar sesi[oó]n/i }).click();

    await expect(page.getByText(/email o contraseña incorrectos/i)).toBeVisible();
    await expect(page).toHaveURL(/\/auth\/login/);

    const token = await page.evaluate(() => window.localStorage.getItem("token"));
    expect(token).toBeNull();
  });

  test("redirects unauthenticated user away from dashboard", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(page).toHaveURL(/\/auth\/login/);
  });
});