/**
 * Seed V2 — browser logout / login E2E (actual UI Sign out + login form).
 */
const { chromium, request } = require("playwright");
const fs = require("fs");
const path = require("path");

const API = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const ROOT = path.resolve(__dirname, "../../..");
const OUT = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V2_LOGOUT_LOGIN_BROWSER_EVIDENCE_20260904.json");
const EXPECTED_SHA = "a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978";

function write(evidence) {
  fs.writeFileSync(OUT, JSON.stringify(evidence, null, 2));
}

(async () => {
  const evidence = {
    captured_at: new Date().toISOString(),
    kind: "ACTUAL_BROWSER_E2E",
    web: WEB,
    api: API,
    pass: false,
    steps: [],
  };

  const email = `seed-v2-logout-${Date.now()}@example.com`;
  const password = "PracticeTest!234";
  const apiCtx = await request.newContext({ baseURL: API });
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password, first_name: "Logout", last_name: "Login" },
  });
  evidence.student_email = email;
  if (!reg.ok()) {
    evidence.failure = await reg.text();
    write(evidence);
    process.exit(1);
  }
  const jar = await apiCtx.storageState();
  const cookies = [];
  for (const c of jar.cookies) {
    for (const url of [
      "http://127.0.0.1:3000/",
      "http://localhost:3000/",
      "http://127.0.0.1:8000/",
      "http://localhost:8000/",
    ]) {
      cookies.push({
        name: c.name,
        value: c.value,
        url,
        httpOnly: c.httpOnly,
        secure: false,
        sameSite: "Lax",
      });
    }
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await context.addCookies(cookies);
  const page = await context.newPage();

  try {
    const webHost = WEB.includes("127.0.0.1") ? WEB.replace("127.0.0.1", "localhost") : WEB;
    await page.goto(`${webHost}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.getByRole("button", { name: /Practice Seed V2/i }).first().waitFor({ state: "visible", timeout: 60_000 });
    await page.waitForTimeout(2000);

    const practiceNow = page.locator("main").getByRole("button", { name: /Practice now/i }).first();
    const seedV1 = page.locator("main").getByRole("button", { name: /Practice Seed V1/i }).first();
    const seedV2 = page.locator("main").getByRole("button", { name: /Practice Seed V2/i }).first();
    evidence.steps.push({
      step: "cta_visibility",
      practice_now: await practiceNow.isVisible().catch(() => false),
      seed_v1: await seedV1.isVisible().catch(() => false),
      seed_v2: await seedV2.isVisible().catch(() => false),
    });

    await seedV2.scrollIntoViewIfNeeded();
    const practiceRespPromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 90_000 },
    );
    await seedV2.click({ force: true });
    const practiceResp = await practiceRespPromise;
    const practiceJson = await practiceResp.json();
    evidence.steps.push({
      step: "seed_v2_started",
      scope_type: practiceJson?.data?.scope_type,
      sha: practiceJson?.meta?.seed_v2_allowlist_sha256,
      question_count: practiceJson?.data?.question_count,
    });
    if (practiceJson?.data?.scope_type !== "SEED_V2") throw new Error("not SEED_V2");
    if (practiceJson?.meta?.seed_v2_allowlist_sha256 !== EXPECTED_SHA) throw new Error("sha");

    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });
    const attemptUrl = page.url();
    const attemptId = attemptUrl.split("/").pop();
    evidence.attempt_id = attemptId;

    await page.getByRole("button", { name: /^Option A:/i }).first().click();
    evidence.steps.push({ step: "answered_option_a", url: attemptUrl });

    // Logout via UI
    await page.getByRole("button", { name: /Account menu/i }).click();
    await page.getByRole("menuitem", { name: /Sign out/i }).click();
    await page.waitForURL(/\/login/i, { timeout: 30_000 });
    evidence.steps.push({ step: "signed_out", url: page.url() });

    const meAfterLogout = await page.evaluate(async (apiUrl) => {
      const res = await fetch(`${apiUrl}/api/v1/auth/me`, { credentials: "include" });
      return { status: res.status };
    }, "http://localhost:8000");
    evidence.steps.push({ step: "unauth_me", ...meAfterLogout });

    await page.goto(attemptUrl, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const afterAttemptNav = page.url();
    const attemptBlocked =
      /\/login/i.test(afterAttemptNav) ||
      (await page.getByText(/sign in|log in|please log/i).count().catch(() => 0)) > 0 ||
      (await page.getByRole("button", { name: /^Option A:/i }).count()) === 0;
    evidence.steps.push({
      step: "attempt_after_logout",
      url: afterAttemptNav,
      blocked_or_no_options: attemptBlocked,
    });

    // Login again via form (wait for client hydration — unhydrated submit becomes GET)
    await page.goto(`${webHost}/login`, { waitUntil: "networkidle", timeout: 90_000 });
    await page.locator("#email").waitFor({ state: "visible", timeout: 45_000 });
    await page.waitForTimeout(1500);
    await page.locator("#email").fill("");
    await page.locator("#email").fill(email);
    await page.locator("#password").fill("");
    await page.locator("#password").fill(password);
    const loginRespPromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/auth/login") && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    await page.locator("#password").press("Enter");
    let loginResp;
    try {
      loginResp = await loginRespPromise;
    } catch {
      // Fallback: click submit after another hydration beat
      await page.waitForTimeout(1000);
      const retry = page.waitForResponse(
        (r) => r.url().includes("/api/v1/auth/login") && r.request().method() === "POST",
        { timeout: 60_000 },
      );
      await page.getByRole("button", { name: /^Sign in$/i }).click();
      loginResp = await retry;
    }
    evidence.steps.push({
      step: "login_api",
      status: loginResp.status(),
      ok: loginResp.ok(),
      url_after: page.url(),
    });
    if (!loginResp.ok()) throw new Error(`login failed ${loginResp.status()} ${await loginResp.text()}`);
    await page.waitForURL(/\/student/i, { timeout: 45_000 });
    evidence.steps.push({ step: "logged_in_again", url: page.url() });

    await page.goto(`${webHost}/student/dashboard`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    evidence.steps.push({
      step: "dashboard_after_relogin",
      practice_now: await practiceNow.isVisible().catch(() => false),
      seed_v1: await seedV1.isVisible().catch(() => false),
      seed_v2: await seedV2.isVisible().catch(() => false),
    });

    // Resume prior attempt if product allows
    await page.goto(attemptUrl, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const resumeStatus = await page.evaluate(async (apiUrl) => {
      const id = location.pathname.split("/").pop();
      const res = await fetch(`${apiUrl}/api/v1/attempts/${id}`, { credentials: "include" });
      const body = await res.json().catch(() => ({}));
      return {
        http: res.status,
        status: body?.data?.status || null,
        scope: body?.data?.assessment?.scope_type || null,
        qcount: body?.data?.questions?.length || 0,
      };
    }, "http://localhost:8000");
    evidence.steps.push({ step: "resume_attempt", ...resumeStatus });

    // New SEED_V2 session must still be isolated
    await page.goto(`${webHost}/student/dashboard`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const p2 = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    await page.locator("main").getByRole("button", { name: /Practice Seed V2/i }).first().click();
    const p2json = await (await p2).json();
    evidence.steps.push({
      step: "new_seed_v2_after_relogin",
      scope_type: p2json?.data?.scope_type,
      question_count: p2json?.data?.question_count,
      different_assessment: p2json?.data?.id !== practiceJson?.data?.id,
    });

    evidence.observed_session_behavior =
      resumeStatus.http === 200
        ? "prior_attempt_resumable_for_same_user_after_relogin"
        : "prior_attempt_not_accessible_after_logout_relogin";

    evidence.pass =
      meAfterLogout.status === 401 &&
      attemptBlocked &&
      evidence.steps.some((s) => s.step === "cta_visibility" && s.seed_v1 && s.seed_v2) &&
      evidence.steps.some((s) => s.step === "login_api" && s.ok) &&
      p2json?.data?.scope_type === "SEED_V2" &&
      p2json?.data?.question_count === 100 &&
      p2json?.data?.id !== practiceJson?.data?.id;
  } catch (err) {
    evidence.failure = String(err);
    evidence.pass = false;
    evidence.final_url = page.url();
  }

  write(evidence);
  console.log(JSON.stringify({ pass: evidence.pass, out: OUT, failure: evidence.failure || null, steps: evidence.steps }, null, 2));
  await browser.close();
  await apiCtx.dispose();
  process.exit(evidence.pass ? 0 : 1);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
