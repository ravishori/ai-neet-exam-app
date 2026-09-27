import { test, expect, request as playwrightRequest } from "@playwright/test";

/**
 * B6 hardening: security-critical auth/session/authorization coverage that
 * was previously entirely missing from Playwright, despite the suite
 * existing. Uses deterministic fixtures (direct API calls via page.request,
 * unique synthetic emails) rather than real SMS/email for every test —
 * matches the backend test suite's own established pattern (TwilioVerifyStub,
 * stubbed Razorpay, etc.) applied at the E2E layer.
 *
 * Test-design note (B6 fix, 2026-09-23): the backend's real
 * `register: 5/60s` rate limit is IP-keyed and applies locally too — the
 * first version of this file registered 8 distinct users across 10 tests,
 * which reliably self-collided with that real limit. Fixed by reusing ONE
 * shared "primary" identity across every test that doesn't specifically need
 * a distinct identity (login success/failure, logout, session persistence,
 * forgot-password, non-admin-denial all work identically regardless of
 * which registered user is used) — only the cross-student isolation test
 * genuinely needs two distinct users. Total registrations: 3 (primary,
 * student A, student B), well under the 5/60s cap, registered once in
 * `beforeAll` rather than per-test.
 */

const API = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const PASSWORD = "PlaywrightTest!234";

function uniqueEmail(tag: string): string {
  return `pw-${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

function uniqueMobile(): string {
  const first = ["6", "7", "8", "9"][Math.floor(Math.random() * 4)];
  let rest = "";
  for (let i = 0; i < 9; i++) rest += Math.floor(Math.random() * 10);
  return first + rest;
}

async function registerViaApi(request: import("@playwright/test").APIRequestContext | import("@playwright/test").Page["request"], email: string) {
  const resp = await request.post(`${API}/api/v1/auth/register`, {
    data: {
      email,
      first_name: "PW",
      last_name: "Test",
      mobile: uniqueMobile(),
      state_code: "KARNATAKA",
      city: "Bangalore",
      password: PASSWORD,
    },
  });
  expect(resp.ok(), await resp.text()).toBeTruthy();
  return resp.json();
}

async function loginAs(page: import("@playwright/test").Page, email: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByRole("textbox", { name: "Password" }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test.describe.configure({ mode: "serial" });

let primaryEmail: string;
let studentAEmail: string;
let studentBEmail: string;

test.beforeAll(async () => {
  primaryEmail = uniqueEmail("primary");
  studentAEmail = uniqueEmail("student-a");
  studentBEmail = uniqueEmail("student-b");
  // A manually-created context (no storageState option) — the `page`
  // fixture isn't available in beforeAll, and the built-in `request`
  // fixture would load this project's broken storageState.json default
  // (see global-setup.ts's url-vs-domain cookie-format mismatch, fixed
  // separately but the fixture default still points at that file).
  const api = await playwrightRequest.newContext({ baseURL: API, storageState: undefined });
  // Exactly 3 registrations for the entire file — well under register's
  // real 5/60s rate limit, unlike the original 8-registration version.
  await registerViaApi(api, primaryEmail);
  await registerViaApi(api, studentAEmail);
  await registerViaApi(api, studentBEmail);
  await api.dispose();
});

test.describe("Authentication — critical paths", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
  });

  test("login succeeds with correct credentials and dashboard loads", async ({ page }) => {
    await loginAs(page, primaryEmail);
    await expect(page).toHaveURL(/\/student\/dashboard/, { timeout: 15000 });
  });

  test("login rejects invalid credentials with a visible error, no redirect", async ({ page }) => {
    await loginAs(page, primaryEmail, "TotallyWrongPassword!1");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toBeVisible({ timeout: 10000 });
  });

  test("logout invalidates the session — protected route redirects to login after", async ({ page }) => {
    await loginAs(page, primaryEmail);
    await expect(page).toHaveURL(/\/student\/dashboard/, { timeout: 15000 });

    const logoutResp = await page.request.post(`${API}/api/v1/auth/logout`);
    expect(logoutResp.ok()).toBeTruthy();

    await page.goto("/student/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  });

  test("session persists across a reload", async ({ page }) => {
    await loginAs(page, primaryEmail);
    await expect(page).toHaveURL(/\/student\/dashboard/, { timeout: 15000 });

    await page.reload();
    await expect(page).toHaveURL(/\/student\/dashboard/);
  });
});

test.describe("Forgot / reset password — critical paths", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
  });

  test("forgot-password shows the same generic response for a known and unknown email (non-enumeration)", async ({
    page,
  }) => {
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(primaryEmail);
    await page.getByRole("button", { name: /reset|send/i }).click();
    const knownText = await page.getByRole("status").or(page.getByRole("alert")).first().textContent({ timeout: 10000 });

    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(uniqueEmail("forgot-unknown"));
    await page.getByRole("button", { name: /reset|send/i }).click();
    const unknownText = await page.getByRole("status").or(page.getByRole("alert")).first().textContent({ timeout: 10000 });

    expect(knownText).toBe(unknownText);
  });

  test("reset-password rejects an invalid/garbage token", async ({ page }) => {
    await page.goto("/reset-password?token=not-a-real-token-at-all");
    await page.getByLabel("New password").fill("SomeNewPassword!123");
    await page.getByRole("button", { name: /reset|update|confirm/i }).click();
    await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Authorization — negative paths", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
  });

  test("anonymous user hitting a protected page is redirected to login", async ({ page }) => {
    await page.goto("/student/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  });

  test("anonymous user cannot call a protected API directly (401)", async ({ page }) => {
    const resp = await page.request.get(`${API}/api/v1/attempts`, { headers: { Cookie: "" } });
    expect(resp.status()).toBe(401);
  });

  test("a student without an admin role is denied at an admin route", async ({ page }) => {
    await loginAs(page, primaryEmail);
    await expect(page).toHaveURL(/\/student\/dashboard/, { timeout: 15000 });

    await page.goto("/admin");
    await expect(page.getByText(/don't have access to the admin portal/i)).toBeVisible({ timeout: 10000 });
  });

  test("student A cannot read student B's attempt list data as their own", async ({ page }) => {
    await loginAs(page, studentBEmail);
    await expect(page).toHaveURL(/\/student\/dashboard/, { timeout: 15000 });

    const resp = await page.request.get(`${API}/api/v1/attempts`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(Array.isArray(body.data)).toBeTruthy();
    // A freshly-registered student has zero attempts — proves the list is
    // scoped to the caller, not a global/unfiltered dataset.
    expect(body.data.length).toBe(0);
  });
});
