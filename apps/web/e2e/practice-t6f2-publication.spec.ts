import { test, expect } from "@playwright/test";

import { bootstrapStudent } from "./helpers";

const API = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

/**
 * T6-F2 DoD remediation: real Practice Now CTA + post-submit explanation.
 * Does NOT use page.evaluate(fetch) to start practice.
 */
test.describe("T6-F2 Practice Now CTA + explanation", () => {
  test("CTA → attempt → answer → submit → score/correctness → explanation", async ({ page }) => {
    const unauth = await page.request.post(`${API}/api/v1/assessments/practice`, {
      data: { scope_type: "FULL", question_count: 5 },
    });
    expect(unauth.status(), "unauthenticated practice must not succeed").toBeGreaterThanOrEqual(401);

    await bootstrapStudent(page);

    // Pre-submit: explanation panel must not be present on dashboard
    await expect(page.getByRole("heading", { name: /^Explanation$/i })).toHaveCount(0);

    const practiceNow = page.getByTestId("practice-now-hero");
    await expect(practiceNow).toBeEnabled();
    await practiceNow.scrollIntoViewIfNeeded();

    const practiceResponsePromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 45_000 },
    );
    await practiceNow.click();

    const practiceResponse = await practiceResponsePromise;
    expect(practiceResponse.ok(), await practiceResponse.text()).toBeTruthy();
    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });

    await expect(page.getByText(/Question\s+1\s+of/i).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /^Explanation$/i })).toHaveCount(0);
    await expect(page.getByText(/Score:/i)).toHaveCount(0);

    const optionA = page.getByRole("button", { name: /^Option A:/i }).first();
    await expect(optionA).toBeVisible();
    await optionA.click();
    await expect(optionA).toHaveAttribute("aria-pressed", "true");

    const next = page.getByRole("button", { name: /Next/i }).first();
    if (await next.isEnabled().catch(() => false)) {
      await next.click();
      await expect(page.getByText(/Question\s+2\s+of/i).first()).toBeVisible({ timeout: 15_000 });
      // Answer Q2 as well so submission is meaningful
      const opt = page.getByRole("button", { name: /^Option A:/i }).first();
      if (await opt.isVisible().catch(() => false)) {
        await opt.click();
      }
    }

    await page.getByRole("button", { name: /^Submit$/i }).first().click();
    await page.getByRole("button", { name: /Confirm submit/i }).click();

    // Correctness / score state (post-submit only)
    await expect(page.getByText(/Score:/i).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/\d+\s+correct/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/\d+\s+incorrect/i).first()).toBeVisible({ timeout: 15_000 });

    // Per-question result badge appears after submit
    await expect(page.getByText(/^(Correct|Incorrect|Skipped)$/i).first()).toBeVisible({ timeout: 15_000 });

    // Explanation heading is rendered only when isSubmitted (question-panel.tsx)
    await expect(page.getByRole("heading", { name: /^Explanation$/i }).first()).toBeVisible({
      timeout: 15_000,
    });

    // Next-question navigation after submit (review mode)
    const nextAfter = page.getByRole("button", { name: /^Next$/i }).first();
    if (await nextAfter.isEnabled().catch(() => false)) {
      await nextAfter.click();
      await expect(page.getByText(/Question\s+\d+\s+of/i).first()).toBeVisible({ timeout: 15_000 });
      // Explanation remains available in review mode for answered items with text
      await expect(page.getByRole("heading", { name: /^Explanation$/i }).first()).toBeVisible({
        timeout: 15_000,
      });
    }
  });
});
