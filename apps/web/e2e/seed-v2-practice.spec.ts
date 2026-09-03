import { test, expect, request as pwRequest } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

import { assertNoHorizontalOverflow } from "./helpers";

const AUTH = path.resolve(
  __dirname,
  "../../../docs/audits/TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json",
);
const V1_AUTH = path.resolve(
  __dirname,
  "../../../docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json",
);
const EXPECTED_SHA = "a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978";
const API = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";

function loadAllow(p: string, key: "exact_allowlist" | "exact_uuid_allowlist") {
  return new Set(JSON.parse(fs.readFileSync(p, "utf8"))[key] as string[]);
}

async function loginFreshStudent(page: import("@playwright/test").Page) {
  const api = await pwRequest.newContext({ baseURL: API });
  const email = `pw-v2-${Date.now()}@example.com`;
  const password = "PracticeTest!234";
  const reg = await api.post("/api/v1/auth/register", {
    data: { email, password, first_name: "Pw", last_name: "V2" },
  });
  expect(reg.ok(), await reg.text()).toBeTruthy();
  const jar = await api.storageState();
  const cookies = [];
  for (const c of jar.cookies) {
    for (const url of [`${WEB}/`, `${API}/`, "http://localhost:3000/", "http://localhost:8000/"]) {
      cookies.push({
        name: c.name,
        value: c.value,
        url,
        httpOnly: c.httpOnly,
        secure: false,
        sameSite: "Lax" as const,
      });
    }
  }
  await page.context().addCookies(cookies);
  await api.dispose();
  const webHost = WEB.includes("127.0.0.1") ? WEB.replace("127.0.0.1", "localhost") : WEB;
  await page.goto(`${webHost}/student/dashboard`, { waitUntil: "domcontentloaded" });
}

test.describe("Practice Seed V2 critical path", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("CTA + exact 100 allowlist + sample submit + V1 CTAs remain", async ({ page }) => {
    const allow = loadAllow(AUTH, "exact_allowlist");
    const v1 = loadAllow(V1_AUTH, "exact_uuid_allowlist");
    await loginFreshStudent(page);

    const practiceNow = page.locator("main").getByRole("button", { name: /^Practice now$/i }).first();
    const seedV1 = page.locator("main").getByRole("button", { name: /Practice Seed V1/i }).first();
    const seedV2 = page.locator("main").getByRole("button", { name: /Practice Seed V2/i }).first();
    await expect(practiceNow).toBeVisible();
    await expect(seedV1).toBeVisible();
    await expect(seedV2).toBeEnabled();

    const practiceResponsePromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 45_000 },
    );
    await seedV2.click();
    const practiceResponse = await practiceResponsePromise;
    expect(practiceResponse.ok(), await practiceResponse.text()).toBeTruthy();
    const practiceJson = await practiceResponse.json();
    const req = practiceResponse.request().postDataJSON() as { scope_type?: string; question_count?: number };
    expect(req.scope_type).toBe("SEED_V2");
    expect(req.question_count).toBe(100);
    expect(practiceJson.data.scope_type).toBe("SEED_V2");
    expect(practiceJson.data.question_count).toBe(100);
    expect(practiceJson.meta.seed_v2_allowlist_sha256).toBe(EXPECTED_SHA);

    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });
    const attemptId = page.url().split("/").pop() as string;
    const detail = await page.request.get(`${API}/api/v1/attempts/${attemptId}`);
    expect(detail.ok()).toBeTruthy();
    const body = await detail.json();
    const questions = body.data.questions as Array<{
      content_item_id: string;
      explanation?: string | null;
      correct_option?: string | null;
    }>;
    expect(questions).toHaveLength(100);
    const ids = questions.map((q) => q.content_item_id);
    expect(new Set(ids).size).toBe(100);
    expect(ids.every((id) => allow.has(id))).toBeTruthy();
    expect(ids.some((id) => v1.has(id))).toBeFalsy();
    expect(questions.every((q) => !q.explanation && !q.correct_option)).toBeTruthy();

    await expect(page.getByText(/Q\s+1\s+\/\s+100/i).first()).toBeVisible({ timeout: 30_000 });
    await assertNoHorizontalOverflow(page);
    const optionA = page.getByRole("button", { name: /^Option A:/i }).first();
    await expect(optionA).toBeVisible();
    await optionA.click();
    await expect(optionA).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: /Next/i }).first().click();
    await expect(page.getByText(/Q\s+2\s+\/\s+100/i).first()).toBeVisible({ timeout: 15_000 });

    await page.reload();
    await expect(page.getByRole("button", { name: /^Option [A-D]:/i }).first()).toBeVisible({ timeout: 30_000 });

    const submitVisible = page.getByRole("button", { name: /^Submit$/i }).locator("visible=true");
    const submitRespPromise = page.waitForResponse(
      (r) => r.url().includes("/submit") && r.request().method() === "POST",
      { timeout: 180_000 },
    );
    await submitVisible.click({ force: true, timeout: 60_000 });
    const submitResp = await submitRespPromise;
    expect(submitResp.ok(), await submitResp.text()).toBeTruthy();
    await expect(page.getByText(/Score:/i).first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { name: /^Explanation$/i }).first()).toBeVisible();

    const dup = await page.evaluate(async (apiUrl) => {
      const id = location.pathname.split("/").pop();
      const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1] ?? "";
      const res = await fetch(`${apiUrl}/api/v1/attempts/${id}/submit`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": decodeURIComponent(csrf) },
      });
      return res.status;
    }, "http://localhost:8000");
    expect(dup).toBe(409);

    const accessibility = await new AxeBuilder({ page }).analyze();
    const critical = accessibility.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
  });
});
