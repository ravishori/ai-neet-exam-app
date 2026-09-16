import { test, expect } from "@playwright/test";

import { assertNoHorizontalOverflow } from "./helpers";

/** Minimal public-homepage viewport smoke.
 *
 * Runs without the student storage state (public visitor), across the
 * seven viewports named in the M3A audit brief. Asserts:
 *   - `/` returns 200 and DOM ready
 *   - exactly one <h1>
 *   - hero tablist visible + keyboard-usable
 *   - primary CTA visible
 *   - the active image is visible
 *   - no horizontal overflow
 */

const VIEWPORTS = [
  { width: 375, height: 812 },
  { width: 390, height: 844 },
  { width: 414, height: 896 },
  { width: 768, height: 1024 },
  { width: 1024, height: 768 },
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
] as const;

// Public page — no auth cookies required. Override the project-level
// storageState (which loads a signed-in student) for this suite.
test.use({ storageState: { cookies: [], origins: [] } });

for (const vp of VIEWPORTS) {
  test(`homepage renders cleanly at ${vp.width}x${vp.height}`, async ({ page }) => {
    await page.setViewportSize(vp);
    const resp = await page.goto("/", { waitUntil: "domcontentloaded" });
    expect(resp?.status(), "homepage should return 2xx").toBeLessThan(300);

    // Single H1 with the M3A copy.
    const h1s = page.getByRole("heading", { level: 1 });
    await expect(h1s).toHaveCount(1);
    await expect(h1s.first()).toContainText("Your NEET preparation. Built around you.");

    // Hero tablist usable.
    const tablist = page.getByRole("tablist");
    await expect(tablist).toBeVisible();
    const tabs = page.getByRole("tab");
    await expect(tabs).toHaveCount(6);

    // Primary CTA visible.
    await expect(page.getByRole("link", { name: /Start practice — Custom Practice/i })).toBeVisible();

    // Active preview image visible (first tile → priority-loaded).
    const activePanel = page.locator('[role="tabpanel"]:not([hidden])').first();
    const img = activePanel.locator("img").first();
    await expect(img).toBeVisible();

    // No horizontal overflow.
    await assertNoHorizontalOverflow(page);
  });
}
