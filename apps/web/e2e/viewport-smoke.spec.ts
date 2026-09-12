import { test, expect } from "@playwright/test";

import { assertNoHorizontalOverflow, bootstrapStudent } from "./helpers";

/**
 * Lightweight viewport smoke: dashboard + practice start visibility + overflow.
 * Full critical path lives in practice-now.spec.ts for representative sizes.
 */
test.describe("viewport smoke", () => {
  test("Practice Now visible without horizontal overflow", async ({ page }) => {
    await bootstrapStudent(page);
    await page.goto("/student/dashboard");
    await expect(page.getByTestId("practice-now-hero")).toBeVisible();
    await assertNoHorizontalOverflow(page);

    // Landscape check for mobile-sized projects
    const vp = page.viewportSize();
    if (vp && vp.width <= 430) {
      await page.setViewportSize({ width: vp.height, height: vp.width });
      await page.reload();
      await expect(page.getByTestId("practice-now-hero")).toBeVisible();
      await assertNoHorizontalOverflow(page);
    }
  });
});
