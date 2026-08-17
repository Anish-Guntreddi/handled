import { defineConfig, devices } from "@playwright/test";

// Runs post-deploy against a real deployed environment (staging or production),
// never against a synthetic CI build — see docs/deployment plan. Point
// PLAYWRIGHT_BASE_URL at the target before running: e.g.
//   PLAYWRIGHT_BASE_URL=https://dev--captureos.netlify.app pnpm test:e2e
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
