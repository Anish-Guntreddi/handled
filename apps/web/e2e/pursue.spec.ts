import { expect, test } from "@playwright/test";
import { login } from "./helpers";

// Core value prop smoke test: the filing pipeline page loads and shows the
// pipeline list. Doesn't drive a filing through all 4 steps (extract →
// match → recommend → build) — that needs seeded opportunity/filing data
// this suite doesn't create — but catches "the page is broken" regressions.
test("Pursue shows the filing pipeline", async ({ page }) => {
  await login(page);

  const orgMatch = page.url().match(/\/orgs\/([^/]+)/);
  test.skip(!orgMatch, "Demo account has no org yet — run `make seed` on this environment first.");
  const orgId = orgMatch![1];

  await page.goto(`/orgs/${orgId}/workspace/pursue`);
  await expect(page.getByText("Your pipeline")).toBeVisible();
});
