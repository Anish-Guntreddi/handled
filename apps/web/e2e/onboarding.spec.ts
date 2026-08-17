import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("onboarding wizard renders the company profile step", async ({ page }) => {
  await login(page);

  const orgMatch = page.url().match(/\/orgs\/([^/]+)/);
  test.skip(!orgMatch, "Demo account has no org yet — run `make seed` on this environment first.");
  const orgId = orgMatch![1];

  await page.goto(`/orgs/${orgId}/onboarding`);
  await expect(page.getByPlaceholder("Acme Robotics, Inc.")).toBeVisible();
});
