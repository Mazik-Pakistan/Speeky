import { defineConfig, devices } from "@playwright/test";

/**
 * UI regression + accessibility audit.
 *
 * Points at the already-running dev server rather than starting its own — the
 * backend, frontend and voice agent run locally during development, and spawning
 * a second Next server would fight the first for port 3000.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
