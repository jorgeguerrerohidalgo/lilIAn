import { test, expect } from "@playwright/test";
import { createTestUser, loginByStorage } from "../fixtures/test-user";

test.describe("Create matter", () => {
  test("creates a contract_review matter end-to-end through the UI", async ({ page, request }) => {
    const user = await createTestUser(request);
    await loginByStorage(page, user.accessToken);

    await page.goto("/matters/new");

    await expect(page.getByRole("heading", { name: /crear nuevo caso/i })).toBeVisible();

    const title = `E2E Matter ${Date.now()}`;
    await page.getByLabel(/t[ií]tulo del caso/i).fill(title);
    await page.getByLabel(/materia legal/i).selectOption("contract_review");
    await page.getByLabel(/descripci[oó]n/i).fill("Contrato de prestación de servicios con cláusula de término anticipado onerosa.");
    await page.getByLabel(/urgencia/i).selectOption("high");
    await page.getByLabel(/contraparte/i).fill("Servicios Legales SpA");

    await page.getByRole("button", { name: /^crear caso$/i }).click();

    await page.waitForURL(/\/matters\/\d+$/);
    const matterId = page.url().split("/").pop();
    expect(matterId).toMatch(/^\d+$/);

    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await expect(page.getByText(/urgencia: high/i)).toBeVisible();
    await expect(page.getByText(/contraparte:.*servicios legales spa/i)).toBeVisible();

    const meRes = await request.get(`${process.env.E2E_API_URL || "http://localhost:8000"}/api/v1/matters/${matterId}`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
    });
    expect(meRes.ok()).toBeTruthy();
    const matter = await meRes.json();
    expect(matter.title).toBe(title);
    expect(matter.matter_type).toBe("contract_review");
    expect(matter.urgency).toBe("high");
    expect(matter.counterparty_name).toBe("Servicios Legales SpA");
  });

  test("rejects submission when required title is empty", async ({ page, request }) => {
    const user = await createTestUser(request);
    await loginByStorage(page, user.accessToken);

    await page.goto("/matters/new");
    await page.getByRole("button", { name: /^crear caso$/i }).click();

    await expect(page).toHaveURL(/\/matters\/new/);
    await expect(page.getByLabel(/t[ií]tulo del caso/i)).toHaveJSProperty("validity.valid", false);
  });
});