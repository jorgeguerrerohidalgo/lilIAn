import { test, expect } from "@playwright/test";
import { API_BASE, createTestUser, loginByStorage } from "../fixtures/test-user";

/**
 * Analysis tests are inherently slow because the backend runs LLM work in the background
 * and the UI polls every 5s for up to 5 minutes.
 *
 * We seed a fresh matter and then go directly through the API to:
 *   1. request an analysis
 *   2. poll the API until the report is ready
 * then visit the matter page to confirm the UI renders the report sections.
 */

async function createMatterWithAccess(request: any, token: string, type: string) {
  const res = await request.post(`${API_BASE}/api/v1/matters`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { title: `E2E Analysis ${Date.now()}`, matter_type: type, urgency: "medium" },
  });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function waitForAnalysisReport(request: any, token: string, matterId: number, timeoutMs = 300_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const res = await request.get(`${API_BASE}/api/v1/analysis/matters/${matterId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok()) {
      const reports = await res.json();
      if (Array.isArray(reports) && reports.length > 0) {
        return reports[0];
      }
    }
    await new Promise((r) => setTimeout(r, 5_000));
  }
  throw new Error(`Analysis did not complete within ${timeoutMs}ms for matter ${matterId}`);
}

test.describe("View analysis", () => {
  test("analysis report renders the executive summary and risks sections", async ({ page, request }) => {
    const user = await createTestUser(request);
    const matter = await createMatterWithAccess(request, user.accessToken, "contract_review");

    const trigger = await request.post(`${API_BASE}/api/v1/analysis`, {
      headers: { Authorization: `Bearer ${user.accessToken}`, "Content-Type": "application/json" },
      data: { matter_id: matter.id },
    });
    expect([202, 200]).toContain(trigger.status());

    const report = await waitForAnalysisReport(request, user.accessToken, matter.id);
    expect(report.status).toBe("completed");
    expect(report.id).toBeTruthy();

    await loginByStorage(page, user.accessToken);
    await page.goto(`/matters/${matter.id}`);
    await page.getByRole("button", { name: /^an[aá]lisis ia$/i }).click();

    await expect(page.getByText(/informe de an[aá]lisis/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/resumen ejecutivo/i)).toBeVisible();
    await expect(page.getByText(/nota legal/i).first()).toBeVisible();

    const detailRes = await request.get(`${API_BASE}/api/v1/analysis/reports/${report.id}`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
    });
    expect(detailRes.ok()).toBeTruthy();
    const detail = await detailRes.json();
    expect(detail.summary).toBeTruthy();
  });

  test("analysis tab shows empty state when no report exists", async ({ page, request }) => {
    const user = await createTestUser(request);
    const matter = await createMatterWithAccess(request, user.accessToken, "other");

    await loginByStorage(page, user.accessToken);
    await page.goto(`/matters/${matter.id}`);
    await page.getByRole("button", { name: /^an[aá]lisis ia$/i }).click();

    await expect(page.getByRole("button", { name: /solicitar nuevo an[aá]lisis/i })).toBeVisible();
    await expect(page.getByText(/no hay an[aá]lisis disponible/i)).toBeVisible();
  });
});