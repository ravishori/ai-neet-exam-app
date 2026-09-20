import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

import { assertNoHorizontalOverflow, bootstrapStudent } from "./helpers";

test.describe("Practice Now critical path", () => {
  test("CTA request + attempt interact + a11y at representative viewport", async ({ page }) => {
    page.on("console", (msg) => {
      if (msg.type() === "error") console.log("BROWSER_CONSOLE_ERROR", msg.text());
    });

    await bootstrapStudent(page);

    // Target the hero CTA only — concept-row buttons share the visible label
    // "Practice now" and must not steal the click when the hero aria-label
    // previously diverged from /^Practice now$/.
    const practiceNow = page.getByTestId("practice-now-hero");
    await expect(practiceNow).toBeEnabled();
    await practiceNow.scrollIntoViewIfNeeded();

    const practiceRequests: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/api/v1/assessments/practice")) {
        practiceRequests.push(req.url());
      }
    });

    const practiceResponsePromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 45_000 },
    );

    await practiceNow.click();

    const practiceResponse = await practiceResponsePromise;
    expect(practiceResponse.ok(), await practiceResponse.text()).toBeTruthy();
    expect(practiceRequests.length, "exactly one practice-start POST from CTA").toBe(1);
    expect(practiceResponse.request().postDataJSON()).toMatchObject({
      scope_type: "FULL",
      question_count: 30,
    });

    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });

    await expect(page.getByText(/Question\s+1\s+of/i).first()).toBeVisible({ timeout: 30_000 });
    await assertNoHorizontalOverflow(page);

    const optionA = page.getByRole("button", { name: /^Option A:/i }).first();
    await expect(optionA).toBeVisible();
    await optionA.click();
    await expect(optionA).toHaveAttribute("aria-pressed", "true");

    const next = page.getByRole("button", { name: /Next/i }).first();
    if (await next.isEnabled().catch(() => false)) {
      await next.click();
      await expect(page.getByText(/Question\s+2\s+of/i).first()).toBeVisible({ timeout: 15_000 });
    }

    await page.getByRole("button", { name: /^Submit$/i }).first().click();
    await page.getByRole("button", { name: /Confirm submit/i }).click();
    await expect(page.getByText(/Score:/i).first()).toBeVisible({ timeout: 30_000 });

    await assertNoHorizontalOverflow(page);
    const accessibility = await new AxeBuilder({ page }).analyze();
    const critical = accessibility.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
  });
});
