import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against a running stack -- by default the isolated E2E stack from
 * docker-compose.e2e.yml (frontend on :3001, its own `talent_e2e` database), never the dev
 * database. See e2e/README.md.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.artifacts/results",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { outputFolder: "./e2e/.artifacts/report", open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3001",
    locale: "ar-EG",
    viewport: { width: 1280, height: 800 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } }],
});
