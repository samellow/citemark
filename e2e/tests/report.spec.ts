import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

import { expect, test } from "@playwright/test";

// The report's one script (PRD 8.1), on the gallery's sample report: a filter over the question
// list. How the report reads without it is report-file.spec.ts's. The sample's failed questions
// are Q017 (correct answers and right place) and Q023 (correct answers and wrongly said "not
// covered"); Q004 is folded.
const gallery = resolve(process.env.GALLERY ?? resolve(__dirname, "../../build/gallery"));
const sample = pathToFileURL(resolve(gallery, "report/sample--light.html")).href;

test.beforeEach(async ({ context }) => {
  await context.route(/^https?:/, (route) => route.abort()); // the report opens offline
});

test("the filter shows all, the failed ones, or those that failed one measure", async ({ page }) => {
  await page.goto(sample);
  const filter = page.locator("[data-filter]");
  await expect(filter).toBeVisible();
  await filter.getByRole("button", { name: "Failed", exact: true }).click();
  await expect(page.locator("#Q017")).toBeVisible();
  await expect(page.locator(".cm-passes")).toBeHidden();
  await filter.getByRole("button", { name: "Looked in the right place" }).click();
  await expect(page.locator("#Q017")).toBeVisible();
  await expect(page.locator("#Q023")).toBeHidden();
  await expect(filter.getByRole("button", { name: "Looked in the right place" })).toHaveAttribute("aria-pressed", "true");
  await filter.getByRole("button", { name: "All", exact: true }).click();
  await expect(page.locator("#Q023")).toBeVisible();
  await expect(page.locator(".cm-passes")).toBeVisible();
});

test("a measure's count filters the list every time it's followed", async ({ page }) => {
  await page.goto(sample);
  const count = page.locator('.cm-measure-right_place a[href="#show-right_place"]');
  await count.click();
  await expect(page.locator("#Q023")).toBeHidden();
  await page.locator("[data-filter]").getByRole("button", { name: "All", exact: true }).click();
  await expect(page.locator("#Q023")).toBeVisible();
  await count.click(); // the address already holds #show-right_place, so no hashchange
  await expect(page.locator("#Q023")).toBeHidden();
});

test("a link to a question the filter hides shows every question again", async ({ page }) => {
  await page.goto(sample);
  await page.locator("[data-filter]").getByRole("button", { name: "Looked in the right place" }).click();
  await expect(page.locator("#Q023")).toBeHidden();
  await page.locator('.cm-fix-questions a[href="#Q023"]').click();
  await expect(page.locator("#Q023")).toBeVisible();
  await expect(page.locator("#Q023")).toBeInViewport();
  // Filtered again, the same link is followed again: the address already holds #Q023, so no hashchange
  await page.locator("[data-filter]").getByRole("button", { name: "Looked in the right place" }).click();
  await expect(page.locator("#Q023")).toBeHidden();
  await page.locator('.cm-fix-questions a[href="#Q023"]').click();
  await expect(page.locator("#Q023")).toBeVisible();
});

test("a link to a folded question unfolds it", async ({ page }) => {
  await page.goto(`${sample}#Q004`);
  await expect(page.locator(".cm-passes")).toHaveAttribute("open", "");
  await expect(page.locator("#Q004")).toBeVisible();
});

test("printing unfolds every question, and closes them again after", async ({ page }) => {
  await page.goto(sample);
  await page.evaluate(() => window.dispatchEvent(new Event("beforeprint")));
  await expect(page.locator(".cm-passes")).toHaveAttribute("open", "");
  await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  await expect(page.locator(".cm-passes")).not.toHaveAttribute("open");
});
