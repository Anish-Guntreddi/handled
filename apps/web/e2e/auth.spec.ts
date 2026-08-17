import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test.describe("authentication", () => {
  test("unauthenticated visitors are redirected off /dashboard to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("the login/register toggle switches which fields are shown", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Sign in to your account" })).toBeVisible();
    await expect(page.getByLabel("Full name")).not.toBeVisible();

    await page.getByRole("button", { name: "Need an account? Sign up" }).click();

    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
    await expect(page.getByLabel("Full name")).toBeVisible();
  });

  test("the demo account signs in and lands on an authenticated page", async ({ page }) => {
    await login(page);
    // Returning users land in the workspace, new/no-org users on the dashboard —
    // either way, /login itself should no longer be showing.
    await expect(page).not.toHaveURL(/\/login/);
  });
});
