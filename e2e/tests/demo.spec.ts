import { existsSync, readFileSync } from "node:fs";
import { extname, resolve, sep } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Request, type Route } from "@playwright/test";

// The demo page (PRD 8.2) in a browser, on the gallery's made-up sample. Playwright plays the
// server: it serves the gallery's files at a made-up origin and answers POST /ask with the ask box
// the server would send, from the gallery's fragments. The app's own answers, limits and counts
// are tested in Python (tests/integration/test_web.py).
const gallery = resolve(process.env.GALLERY ?? resolve(__dirname, "../../build/gallery"));
const ORIGIN = "http://citemark.test";
const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".woff2": "font/woff2",
  ".svg": "image/svg+xml",
};
const LABEL = "Unofficial demo built on Zulip's open-source help center (Apache-2.0). Not affiliated with Zulip.";
const SEARCHING = "Searching the help center…";
const ANSWERED = readFileSync(resolve(gallery, "demo/ask-answered.fragment.html"), "utf8");
const REFUSED = readFileSync(resolve(gallery, "demo/ask-refused.fragment.html"), "utf8");
const PAGES = ["sample.html", "sample--light.html", "sample--dark.html", "no-run--light.html", "no-run--dark.html"];
const EMAIL = /[\w.+-]+@[\w-]+\.[\w.]+/;
const PHONE = /\+?\d[\d ().-]{7,}\d/;

type Ask = (route: Route, request: Request) => Promise<void>;

/** The gallery at ORIGIN, nothing else reachable, and POST /ask answered by `ask`. */
async function serve(context: BrowserContext, ask?: Ask): Promise<Request[]> {
  const asked: Request[] = [];
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== ORIGIN) return route.abort();
    if (url.pathname === "/ask" && request.method() === "POST") {
      asked.push(request);
      return ask ? ask(route, request) : route.abort();
    }
    const path = resolve(gallery, `.${decodeURIComponent(url.pathname)}`);
    if (!path.startsWith(gallery + sep) || !existsSync(path)) return route.fulfill({ status: 404, body: "" });
    return route.fulfill({ body: readFileSync(path), contentType: TYPES[extname(path)] ?? "application/octet-stream" });
  });
  return asked;
}

const answer =
  (body: string, status = 200, wait = 0): Ask =>
  async (route) => {
    if (wait) await new Promise((done) => setTimeout(done, wait));
    await route.fulfill({ status, body, contentType: "text/html; charset=utf-8" });
  };

for (const [width, height] of [
  [1280, 720],
  [375, 667],
]) {
  test.describe(`at ${width}×${height}`, () => {
    test.use({ viewport: { width, height } });

    test("the unofficial-demo label is visible without scrolling, before a run and after", async ({ page, context }) => {
      await serve(context);
      for (const name of ["sample.html", "no-run--light.html"]) {
        await page.goto(`${ORIGIN}/demo/${name}`);
        const label = page.locator(".cm-topbar-label");
        await expect(label).toHaveText(LABEL);
        await expect(label).toBeInViewport({ ratio: 1 });
      }
    });

    test("nothing is wider than the screen", async ({ page, context }) => {
      await serve(context);
      for (const name of ["sample--light.html", "no-run--light.html"]) {
        await page.goto(`${ORIGIN}/demo/${name}`);
        const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(wide, name).toBe(0);
      }
    });
  });
}

test("the page has no email address or phone number", async ({ page, context }) => {
  await serve(context);
  for (const name of PAGES) {
    await page.goto(`${ORIGIN}/demo/${name}`);
    const text = await page.locator("body").innerText();
    expect(text.match(EMAIL), name).toBeNull();
    expect(text.match(PHONE), name).toBeNull();
    expect((await page.content()).match(EMAIL), name).toBeNull();
  }
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("the ask box is a plain form, sent with its pitch", async ({ page, context }) => {
    const asked = await serve(context, answer("<!doctype html><title>answered</title>"));
    await page.goto(`${ORIGIN}/demo/sample--light.html`);
    await page.getByLabel("Your question").fill("How do I leave a channel?");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page).toHaveTitle("answered");
    const sent = new URLSearchParams(asked[0].postData() ?? "");
    expect(sent.get("question")).toBe("How do I leave a channel?");
    expect(sent.get("v")).toBe("accuracy");
    expect(asked[0].headers()["x-citemark-fragment"]).toBeUndefined();
  });
});

test("with JavaScript, a question is answered in place, searching first", async ({ page, context }) => {
  const asked = await serve(context, answer(ANSWERED, 200, 400));
  await page.goto(`${ORIGIN}/demo/sample.html`);
  const address = page.url();
  await page.getByLabel("Your question").fill("How do I archive a channel?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator("[data-status]")).toHaveText(SEARCHING);
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await expect(page.locator(".cm-asked .cm-turn")).toHaveCount(1);
  await expect(page.locator(".cm-asked .cm-turn")).toBeFocused();
  await expect(page.locator("[data-status]")).toHaveText("");
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();
  await expect(page.getByLabel("Your question")).toHaveValue("");
  expect(page.url()).toBe(address);
  expect(asked[0].headers()["x-citemark-fragment"]).toBe("ask");
  expect(new URLSearchParams(asked[0].postData() ?? "").get("question")).toBe("How do I archive a channel?");
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.map((v) => v.id)).toEqual([]);
});

test("a suggested question sends itself, and its buttons work again after", async ({ page, context }) => {
  const asked = await serve(context, answer(ANSWERED));
  await page.goto(`${ORIGIN}/demo/sample.html`);
  const suggestion = page.locator(".cm-suggestions button").first();
  const question = await suggestion.textContent();
  await suggestion.click();
  await expect(page.locator(".cm-asked .cm-turn")).toHaveCount(1);
  expect(new URLSearchParams(asked[0].postData() ?? "").get("suggestion")).toBe(question);
  await expect(suggestion).toBeEnabled();
});

test("a refused question stays in the box, and the notice is read next", async ({ page, context }) => {
  await serve(context, answer(REFUSED, 429));
  await page.goto(`${ORIGIN}/demo/sample.html`);
  await page.getByLabel("Your question").fill("How do I export my messages?");
  await page.getByRole("button", { name: "Send" }).click();
  const status = page.locator("[data-status]");
  await expect(status).toHaveText("The demo allows 10 questions an hour. You can ask again in 12 minutes.");
  await expect(status).toBeFocused();
  await expect(page.getByLabel("Your question")).toHaveValue("How do I export my messages?");
});

test("when the server can't be reached, the box says so and can be sent again", async ({ page, context }) => {
  await serve(context, async (route) => route.abort());
  await page.goto(`${ORIGIN}/demo/sample.html`);
  await page.getByLabel("Your question").fill("How do I leave a channel?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator("[data-status]")).toHaveText("Something went wrong on our side. Try again.");
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();
  await expect(page.getByLabel("Your question")).toHaveValue("How do I leave a channel?");
});
