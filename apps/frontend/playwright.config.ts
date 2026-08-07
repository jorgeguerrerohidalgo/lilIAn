/**
 * S6-03: Playwright configuration for the lilIAn frontend.
 *
 * The existing E2E specs in ``tests/e2e/tests/`` were orphan (no config,
 * no npm script). This file wires them up so contributors can run
 * ``npx playwright test`` and CI can drive the suite.
 *
 * Local usage:
 *   1. cd apps/frontend
 *   2. npm install --save-dev @playwright/test
 *   3. npx playwright install --with-deps chromium
 *   4. npm run test:e2e
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.PORT ?? 3000;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "../../tests/e2e/tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // In CI we expect the backend + frontend to already be running.
  // Locally developers can use ``webServer`` to launch the dev server.
  webServer: process.env.CI
    ? undefined
    : {
        command: "npm run dev",
        url: BASE_URL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});