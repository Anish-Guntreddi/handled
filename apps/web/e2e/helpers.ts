import type { Page } from "@playwright/test";

// Seeded via `make seed` (apps/api/captureos/scripts/seed.py) — must exist on
// whatever environment PLAYWRIGHT_BASE_URL points at.
export const DEMO_EMAIL = "demo@captureos.dev";
export const DEMO_PASSWORD = "demo-password-123";

export async function login(page: Page, email = DEMO_EMAIL, password = DEMO_PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}
