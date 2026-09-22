import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * B9 hardening: automated accessibility checks on critical routes, using
 * the axe-core dependency that was already installed but never wired into
 * any test. Does not claim full WCAG compliance from automated tooling
 * alone (axe-core itself only catches a subset of WCAG violations
 * reliably — this is explicit, not an overclaim).
 */

async function scanPage(page: import("@playwright/test").Page) {
  return new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
}

test.describe("Accessibility — critical routes (automated, axe-core)", () => {
  test("landing page has no critical/serious violations", async ({ page }) => {
    await page.goto("/");
    const results = await scanPage(page);
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });

  test("login page has no critical/serious violations", async ({ page }) => {
    await page.goto("/login");
    const results = await scanPage(page);
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });

  test("register page has no critical/serious violations", async ({ page }) => {
    await page.goto("/register");
    const results = await scanPage(page);
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });

  test("student dashboard has no critical/serious violations", async ({ page }) => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const statePath = path.join(__dirname, ".auth", "student.json");
    test.skip(!fs.existsSync(statePath), "requires authenticated storageState from globalSetup");
    await page.goto("/student/dashboard");
    const results = await scanPage(page);
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });

  test("practice page has no critical/serious violations", async ({ page }) => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const statePath = path.join(__dirname, ".auth", "student.json");
    test.skip(!fs.existsSync(statePath), "requires authenticated storageState from globalSetup");
    await page.goto("/student/practice");
    const results = await scanPage(page);
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });
});
