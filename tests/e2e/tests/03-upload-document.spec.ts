import path from "node:path";
import { test, expect } from "@playwright/test";
import { API_BASE, createTestUser, loginByStorage } from "../fixtures/test-user";

test.describe("Upload document", () => {
  test("uploads a PDF to a matter and shows it in the documents list", async ({ page, request }) => {
    const user = await createTestUser(request);

    const matterRes = await request.post(`${API_BASE}/api/v1/matters`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
      data: {
        title: `E2E Doc Upload ${Date.now()}`,
        matter_type: "contract_review",
        urgency: "medium",
      },
    });
    expect(matterRes.ok()).toBeTruthy();
    const matter = await matterRes.json();

    await loginByStorage(page, user.accessToken);
    await page.goto(`/matters/${matter.id}`);
    await page.getByRole("button", { name: /^documentos$/i }).click();

    const fileInput = page.locator("#file-upload");
    await fileInput.setInputFiles(path.resolve(__dirname, "../fixtures/sample.pdf"));

    await expect(page.getByText(/documento subido exitosamente/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("sample.pdf")).toBeVisible();

    const docsRes = await request.get(`${API_BASE}/api/v1/documents/matters/${matter.id}/documents`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
    });
    expect(docsRes.ok()).toBeTruthy();
    const docs = await docsRes.json();
    expect(docs).toHaveLength(1);
    expect(docs[0].original_filename).toBe("sample.pdf");
    expect(docs[0].mime_type).toBe("application/pdf");
  });

  test("uploads a TXT file successfully", async ({ page, request }) => {
    const user = await createTestUser(request);

    const matterRes = await request.post(`${API_BASE}/api/v1/matters`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
      data: {
        title: `E2E TXT Upload ${Date.now()}`,
        matter_type: "labor",
        urgency: "low",
      },
    });
    expect(matterRes.ok()).toBeTruthy();
    const matter = await matterRes.json();

    await loginByStorage(page, user.accessToken);
    await page.goto(`/matters/${matter.id}`);
    await page.getByRole("button", { name: /^documentos$/i }).click();

    await page.locator("#file-upload").setInputFiles(path.resolve(__dirname, "../fixtures/sample-contract.txt"));

    await expect(page.getByText(/documento subido exitosamente/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("sample-contract.txt")).toBeVisible();
  });
});