import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// axe on every gallery page (UI kit 4: the Verified rung's first check). The gallery is built
// first, with `uv run citemark gallery`; GALLERY points elsewhere if it was built elsewhere.
const gallery = resolve(process.env.GALLERY ?? resolve(__dirname, "../../build/gallery"));
const pages: { path: string }[] = JSON.parse(readFileSync(resolve(gallery, "pages.json"), "utf8"));
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

test("the gallery has pages", () => {
  expect(pages.length).toBeGreaterThan(1);
});

for (const { path } of pages) {
  test(`axe finds nothing on ${path}`, async ({ page, context }) => {
    await context.route(/^https?:/, (route) => route.abort()); // a gallery page needs nothing from the network
    await page.goto(pathToFileURL(resolve(gallery, path)).href);
    const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
    const found = violations.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`);
    expect(found).toEqual([]);
  });
}
