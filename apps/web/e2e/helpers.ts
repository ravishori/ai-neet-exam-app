import { Page, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const API = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3001";
const STATE = path.join(__dirname, ".auth", "student.json");

/** Ensure cookies from global setup are present (covers WEB + API origins). */
export async function bootstrapStudent(page: Page) {
  if (!fs.existsSync(STATE)) {
    throw new Error(`Missing ${STATE} — run Playwright globalSetup first`);
  }
  const stored = JSON.parse(fs.readFileSync(STATE, "utf8")) as {
    cookies: Array<{
      name: string;
      value: string;
      url?: string;
      domain?: string;
      path?: string;
      httpOnly?: boolean;
      secure?: boolean;
      sameSite?: "Strict" | "Lax" | "None";
    }>;
  };

  // Re-apply for both origins in case storageState only captured one.
  const cookies = [];
  for (const c of stored.cookies) {
    for (const url of [`${WEB}/`, `${API}/`]) {
      cookies.push({
        name: c.name,
        value: c.value,
        url,
        httpOnly: c.httpOnly ?? false,
        secure: false,
        sameSite: (c.sameSite as "Lax") ?? "Lax",
      });
    }
  }
  await page.context().addCookies(cookies);

  const me = await page.request.get(`${API}/api/v1/auth/me`);
  expect(me.ok(), await me.text()).toBeTruthy();

  await page.goto("/student/dashboard");
  await expect(page).toHaveURL(/\/student\/dashboard/);

  const chunkOk = await page.evaluate(async () => {
    const scripts = [...document.querySelectorAll("script[src]")] as HTMLScriptElement[];
    const chunk = scripts.find((s) => s.src.includes("/_next/static/"));
    if (!chunk) return false;
    const res = await fetch(chunk.src, { method: "HEAD" });
    return res.ok;
  });
  expect(chunkOk, `Next static chunks unavailable on ${WEB}`).toBeTruthy();

  await expect(page.getByRole("button", { name: /^Practice now$/i }).first()).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/Loading/i, { timeout: 30_000 });
}

export async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, `horizontal overflow ${overflow}px`).toBeLessThanOrEqual(1);
}

/** Start practice via same-origin browser fetch (exercises CSRF + cookies). */
export async function startPracticeViaBrowserFetch(page: Page) {
  const result = await page.evaluate(async (apiBase) => {
    const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1] ?? "";
    const gen = await fetch(`${apiBase}/api/v1/assessments/practice`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf) },
      body: JSON.stringify({ scope_type: "FULL", question_count: 30 }),
    });
    const gj = await gen.json();
    if (!gen.ok || !gj.success) return { ok: false, stage: "generate", status: gen.status, body: gj };
    const start = await fetch(`${apiBase}/api/v1/assessments/${gj.data.id}/attempts`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(csrf) },
    });
    const sj = await start.json();
    if (!start.ok || !sj.success) return { ok: false, stage: "start", status: start.status, body: sj };
    return { ok: true, attemptId: sj.data.id as string, questionCount: gj.data.question_count as number };
  }, API);
  expect(result.ok, JSON.stringify(result)).toBeTruthy();
  return result as { ok: true; attemptId: string; questionCount: number };
}
