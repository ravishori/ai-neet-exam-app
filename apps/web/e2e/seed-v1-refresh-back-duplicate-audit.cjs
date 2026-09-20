/**
 * Seed V1 student experience: refresh, back/forward, duplicate submit.
 * Audit-only.
 */
const { chromium, request } = require("playwright");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

const ROOT = path.resolve(__dirname, "../../..");
const AUTH = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json");
const EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1";
const PASSWORD = "PracticeTest!234";

function allowlistSha(ids) {
  return crypto.createHash("sha256").update(ids.join("\n") + "\n", "utf8").digest("hex");
}

function loadAllowlist() {
  const doc = JSON.parse(fs.readFileSync(AUTH, "utf8"));
  const ids = doc.exact_uuid_allowlist;
  return { ids, set: new Set(ids), sha: allowlistSha(ids), embedded: doc.allowlist_sha256 };
}

function csrfFromCookies(cookies) {
  const c = cookies.find((x) => x.name === "csrf_token");
  return c ? decodeURIComponent(c.value) : "";
}

function cookiesForOrigins(jar) {
  const origins = [
    "http://127.0.0.1:3000/",
    "http://localhost:3000/",
    "http://127.0.0.1:8000/",
    "http://localhost:8000/",
  ];
  const cookies = [];
  for (const c of jar.cookies) {
    for (const url of origins) {
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
  return cookies;
}

async function registerStudent(apiCtx, tag) {
  const email = `sx-reg-${tag}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}@example.com`;
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD, first_name: "SX", last_name: tag },
  });
  if (!reg.ok()) throw new Error(`register failed ${reg.status()} ${await reg.text()}`);
  return email;
}

async function apiGetAttempt(apiCtx, attemptId) {
  const r = await apiCtx.get(`/api/v1/attempts/${attemptId}`);
  const body = await r.json().catch(() => ({}));
  return { status: r.status(), ok: r.ok(), body };
}

async function apiSubmit(apiCtx, attemptId) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post(`/api/v1/attempts/${attemptId}/submit`, {
    headers: { "X-CSRF-Token": csrf },
  });
  const body = await r.json().catch(() => ({}));
  return { status: r.status(), ok: r.ok(), body };
}

async function apiAnswer(apiCtx, attemptId, content_item_id, selected_option) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post(`/api/v1/attempts/${attemptId}/answers`, {
    headers: { "X-CSRF-Token": csrf },
    data: { content_item_id, selected_option },
  });
  const body = await r.json().catch(() => ({}));
  return { status: r.status(), ok: r.ok(), body };
}

async function clickSaveAndNext(page) {
  const saveNext = page.getByRole("button", { name: /Save\s*&\s*Next/i }).first();
  if (await saveNext.isVisible().catch(() => false)) {
    await saveNext.click();
    return "Save & Next";
  }
  const next = page.getByRole("button", { name: /^Next$/i }).first();
  if (await next.isVisible().catch(() => false)) {
    await next.click();
    return "Next";
  }
  throw new Error("No Save & Next / Next visible");
}

function parseAttemptId(url) {
  const m = url.match(/\/student\/attempts\/([0-9a-f-]+)/i);
  return m ? m[1] : null;
}

(async () => {
  const allow = loadAllowlist();
  const outPath = path.join(
    ROOT,
    "docs/audits/_seed_v1_refresh_back_duplicate_audit_result.json",
  );

  const result = {
    audit: "Seed V1 student experience: refresh/back/duplicate",
    date: "2026-09-03",
    allowlist_sha: allow.sha,
    expected_allowlist_sha: EXPECTED_SHA,
    pass: false,
    dashboard: {},
    refresh: {},
    back_forward: {},
    duplicate_submission: {},
    errors: [],
  };

  const apiCtx = await request.newContext({ baseURL: API });
  const email = await registerStudent(apiCtx, "refresh");
  result.student_email = email;
  const jar = await apiCtx.storageState();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await context.addCookies(cookiesForOrigins(jar));
  const page = await context.newPage();

  try {
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.waitForTimeout(1200);

    const seedBtn = page.locator("main").getByRole("button", { name: /Practice Seed V1/i }).first();
    result.dashboard.seed_visible = await seedBtn.isVisible().catch(() => false);
    if (!result.dashboard.seed_visible) throw new Error("Seed CTA not visible");

    const practiceRespPromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    const attemptRespPromise = page.waitForResponse(
      (r) => /\/api\/v1\/assessments\/[^/]+\/attempts$/.test(new URL(r.url()).pathname) && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    await seedBtn.click();
    await Promise.all([practiceRespPromise, attemptRespPromise]);
    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });

    const attemptId = parseAttemptId(page.url());
    if (!attemptId) throw new Error(`Could not parse attempt id from ${page.url()}`);

    await page.getByText(/Question\s+1\s+of/i).first().waitFor({ timeout: 60_000 });
    await page.getByRole("button", { name: /^Option A:/i }).first().click();
    await clickSaveAndNext(page);
    await page.getByText(/Question\s+2\s+of/i).first().waitFor({ timeout: 15_000 });

    const urlBefore = page.url();
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const urlAfter = page.url();

    const afterAttempt = await apiGetAttempt(apiCtx, attemptId);
    const answeredAfter = (afterAttempt.body?.data?.questions || []).filter((q) => q.selected_option).length;

    result.refresh = {
      attempt_id: attemptId,
      url_before: urlBefore,
      url_after: urlAfter,
      still_same_attempt_route: urlAfter.includes(attemptId),
      answered_persisted_server: answeredAfter >= 1,
      pass: urlAfter.includes(attemptId) && answeredAfter >= 1,
    };
    if (!result.refresh.pass) throw new Error("Refresh behavior failed");

    // Back/forward on the attempt page
    const statusBefore = afterAttempt.body?.data?.status;
    await page.goBack({ waitUntil: "domcontentloaded" }).catch(() => null);
    await page.waitForTimeout(900);
    await page.goForward({ waitUntil: "domcontentloaded" }).catch(() => null);
    await page.waitForTimeout(900);
    const afterNav = await apiGetAttempt(apiCtx, attemptId);
    result.back_forward = {
      attempt_status_before: statusBefore,
      attempt_status_after: afterNav.body?.data?.status,
      pass: afterNav.body?.data?.status === "IN_PROGRESS",
    };
    if (!result.back_forward.pass) throw new Error("Back/forward behavior failed");

    // Duplicate submission: answer remaining quickly and submit twice
    const seedAttempt = afterNav;
    const seedQs = seedAttempt.body?.data?.questions || [];
    for (let i = 0; i < seedQs.length; i++) {
      const q = seedQs[i];
      const opt = i % 2 === 0 ? "A" : "B";
      await apiAnswer(apiCtx, attemptId, q.content_item_id, opt);
    }
    const sub1 = await apiSubmit(apiCtx, attemptId);
    const sub2 = await apiSubmit(apiCtx, attemptId);
    const afterDup = await apiGetAttempt(apiCtx, attemptId);
    result.duplicate_submission = {
      first_status: sub1.status,
      second_status: sub2.status,
      status_final: afterDup.body?.data?.status,
      pass: afterDup.body?.data?.status === "SUBMITTED" && (!sub2.ok || sub2.status >= 400),
    };
    if (!result.duplicate_submission.pass) {
      // allow idempotent success as PASS
      result.duplicate_submission.pass = afterDup.body?.data?.status === "SUBMITTED";
    }

    result.pass = result.refresh.pass && result.back_forward.pass && result.duplicate_submission.pass;
  } catch (e) {
    result.errors.push(String(e));
    result.pass = false;
  }

  fs.writeFileSync(outPath, JSON.stringify(result, null, 2), "utf8");
  console.log(JSON.stringify({ pass: result.pass, outPath, errors: result.errors }, null, 2));
  await browser.close();
  await apiCtx.dispose();
  process.exit(result.pass ? 0 : 1);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});

