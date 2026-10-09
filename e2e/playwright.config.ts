import { defineConfig, devices } from "@playwright/test";

// The pages are files on disk, built by `citemark gallery` (and later the report build), so no
// server runs. Every check uses Chromium, the browser CI pins.
export default defineConfig({
  testDir: "tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
