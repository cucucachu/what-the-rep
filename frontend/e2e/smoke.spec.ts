import { expect, test } from "@playwright/test";

test("home page renders the app heading", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /what the rep/i }),
  ).toBeVisible();
});
