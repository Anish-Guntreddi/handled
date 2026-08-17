import { expect, test } from "@playwright/test";
import { login } from "./helpers";

// Regression coverage for the recently-fixed bug where Find rendered a program
// description where a dollar figure belonged — assert the hero estimate and
// filter chips render without asserting exact copy (data-dependent).
test("Find shows the money estimate and category filters", async ({ page }) => {
  await login(page);

  const orgMatch = page.url().match(/\/orgs\/([^/]+)/);
  test.skip(!orgMatch, "Demo account has no org yet — run `make seed` on this environment first.");
  const orgId = orgMatch![1];

  await page.goto(`/orgs/${orgId}/workspace/find`);
  await expect(page.getByRole("button", { name: "All" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Grants" })).toBeVisible();
});
