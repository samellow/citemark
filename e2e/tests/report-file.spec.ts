import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

// QA promise 12: the report reads offline and without JavaScript, and always prints in light.
// Checked on the gallery's sample report as `report build` writes one, with no theme forced, so
// the reader's light or dark setting reaches it. Only its made-up label differs from a real
// report's file, and print leaves that off. The sample's failed questions are Q017 and Q023, and
// Q004 is among the folded passes.
const gallery = resolve(process.env.GALLERY ?? resolve(__dirname, "../../build/gallery"));
const sample = (name: string) => pathToFileURL(resolve(gallery, "report", name)).href;
const SENT = sample("sample.html");
const FACES = [
  // the five faces the report inlines (static/fonts/README.md)
  ["IBM Plex Sans Condensed", 600],
  ["IBM Plex Sans", 400],
  ["IBM Plex Sans", 600],
  ["IBM Plex Mono", 400],
  ["IBM Plex Mono", 500],
] as const;
const PARTS = [".cm-cert", ".cm-verdict", ".cm-measures", ".cm-trace", ".cm-fix", ".cm-questions", ".cm-compare", ".cm-method", ".cm-signed"];
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];
// A4 less the @page side margins, in CSS pixels: narrower than Letter's, so what fits A4 fits both
const A4_TEXT_WIDTH = Math.floor(((210 - 2 * 14) / 25.4) * 96);
const MOST_COMPARED = 6; // the most setups a report sets side by side (report/inputs.py, MAX_COMPARED)

test.use({ javaScriptEnabled: false });

test.beforeEach(async ({ context }) => {
  await context.route(/^https?:/, (route) => route.abort()); // no network
});

/** Everything the page at `address` asks for besides itself, data URIs aside. */
function watched(page: Page, address: string): string[] {
  const fetched: string[] = [];
  page.on("request", (request) => {
    const asked = request.url();
    if (asked !== address && !asked.startsWith("data:")) fetched.push(asked);
  });
  return fetched;
}

async function shot(page: Page, media: "screen" | "print", colorScheme: "light" | "dark"): Promise<Buffer> {
  await page.emulateMedia({ media, colorScheme });
  return page.screenshot({ fullPage: true, animations: "disabled" });
}

/** Two captures alike, or not; both are attached to the report only when that's wrong. */
async function compare(info: TestInfo, name: string, captures: [Buffer, Buffer], alike: boolean): Promise<void> {
  const [actual, expected] = captures;
  if (actual.equals(expected) !== alike) {
    await info.attach(`${name}.png`, { body: actual, contentType: "image/png" });
    await info.attach(`${name}, compared with.png`, { body: expected, contentType: "image/png" });
  }
  expect(actual.equals(expected), `${name} ${alike ? "should match" : "should differ"}`).toBe(alike);
}

test("it opens from the file alone: nothing else is fetched, and its five faces load from inside it", async ({ page }) => {
  const fetched = watched(page, SENT);
  await page.goto(SENT);
  for (const [family, weight] of FACES) {
    const faces = await page.evaluate(
      ([family, weight]) =>
        document.fonts.load(`${weight} 16px "${family}"`).then(
          (found) => found.map((face) => face.status),
          (error) => [`failed: ${error}`],
        ),
      [family, weight] as const,
    );
    expect(faces, `${family} ${weight}`).toEqual(["loaded"]);
  }
  expect(fetched).toEqual([]);
});

test("it reads in full without JavaScript, the passes behind their own disclosure", async ({ page }) => {
  await page.goto(SENT);
  for (const part of PARTS) await expect(page.locator(part), part).toBeVisible();
  await expect(page.locator("[data-filter]")).toBeHidden();
  await expect(page.locator("#Q017")).toBeVisible();
  await expect(page.locator("#Q023")).toBeVisible();
  await expect(page.locator("#Q004")).toBeHidden();
  await page.locator(".cm-passes > summary").click(); // the browser's own disclosure, no script
  await expect(page.locator("#Q004")).toBeVisible();
});

test("with a dark preference it prints exactly as with a light one", async ({ page }, info) => {
  await page.goto(SENT);
  // On screen the same preference does turn it dark, so the comparison below can tell
  await compare(info, "dark on screen", [await shot(page, "screen", "dark"), await shot(page, "screen", "light")], false);
  const light = await shot(page, "print", "light");
  await compare(info, "printed with a dark preference", [await shot(page, "print", "dark"), light], true);
});

test("forced into either theme, it still prints as the report does", async ({ page }, info) => {
  await page.goto(SENT);
  const light = await shot(page, "print", "light");
  for (const theme of ["light", "dark"] as const) {
    await page.goto(sample(`sample--${theme}.html`));
    await compare(info, `forced ${theme}, printed`, [await shot(page, "print", "dark"), light], true);
  }
});

test.describe("printed", () => {
  test("every question shows, and the fix plan and the questions each start a page", async ({ page }) => {
    await page.goto(SENT);
    await page.emulateMedia({ media: "print" });
    await expect(page.locator("#Q004")).toBeVisible(); // unfolded without the script
    await expect(page.locator(".cm-report-banner")).toBeHidden();
    for (const part of [".cm-fix", ".cm-questions"]) await expect(page.locator(part), part).toHaveCSS("break-before", "page");
  });

  test("nothing is cut off at A4's width, even six setups side by side", async ({ page }) => {
    await page.setViewportSize({ width: A4_TEXT_WIDTH, height: 1000 });
    await page.goto(SENT);
    await page.emulateMedia({ media: "print" });
    // The sample compares two setups; its columns repeated make the widest comparison a report holds
    await page.evaluate((most) => {
      for (const row of document.querySelectorAll(".cm-compare-table tr")) {
        const columns = [...row.children].slice(1);
        for (let at = columns.length; at < most; at++) row.append(columns[at % columns.length].cloneNode(true));
      }
    }, MOST_COMPARED);
    await expect(page.locator(".cm-compare-table thead th")).toHaveCount(MOST_COMPARED);
    const cut = await page.evaluate(() => {
      const root = document.documentElement;
      // A screen reader's own words are clipped on purpose
      const clipped = [...document.querySelectorAll("body *:not(.cm-visually-hidden)")].filter(
        (element) => getComputedStyle(element).overflowX !== "visible" && element.scrollWidth > element.clientWidth + 1,
      );
      return [...(root.scrollWidth > root.clientWidth ? ["the page"] : []), ...clipped.map((element) => element.className)];
    });
    expect(cut).toEqual([]);
  });

  test.describe("with JavaScript on", () => {
    test.use({ javaScriptEnabled: true });

    test("the filter is left off and the questions it hid come back", async ({ page }) => {
      await page.goto(SENT);
      await page.locator("[data-filter]").getByRole("button", { name: "Looked in the right place" }).click();
      await expect(page.locator("#Q023")).toBeHidden();
      await page.emulateMedia({ media: "print" }); // the print styles alone, as a browser without beforeprint
      await expect(page.locator("[data-filter]")).toBeHidden();
      await expect(page.locator("#Q023")).toBeVisible();
      await expect(page.locator("#Q004")).toBeVisible();
    });
  });
});

// axe runs as a script, so it runs with the report's script on too. That script only adds the
// filter to what's read, so what's read without it is checked here as well. At a phone's width
// the comparison scrolls, which is when axe checks the keyboard can reach it.
const SCREENS = { desktop: { width: 1280, height: 720 }, phone: { width: 375, height: 667 } };
for (const colorScheme of ["light", "dark"] as const) {
  for (const [screen, viewport] of Object.entries(SCREENS)) {
    test.describe(`axe, with a ${colorScheme} preference, at ${screen} width`, () => {
      test.use({ javaScriptEnabled: true, colorScheme, viewport });

      test("finds nothing on the report", async ({ page }) => {
        await page.goto(SENT);
        const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
        const found = violations.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`);
        expect(found).toEqual([]);
      });
    });
  }
}
