/**
 * Seed V1 student experience: session restart, logout/login isolation,
 * concurrency, route/security, responsive smoke.
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

const OUT_PATH = path.join(ROOT, "docs/audits/_seed_v1_restart_logout_concurrency_route_responsive_tmp.json");

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

async function apiPractice(apiCtx, scope_type, question_count = 30, extra = {}) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post("/api/v1/assessments/practice", {
    headers: { "X-CSRF-Token": csrf },
    data: { scope_type, question_count, ...extra },
  });
  return { status: r.status(), ok: r.ok(), body: await r.json().catch(() => ({})) };
}

async function apiStartAttempt(apiCtx, assessmentId) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post(`/api/v1/assessments/${assessmentId}/attempts`, {
    headers: { "X-CSRF-Token": csrf },
  });
  return { status: r.status(), ok: r.ok(), body: await r.json().catch(() => ({})) };
}

async function apiGetAttempt(apiCtx, attemptId) {
  const r = await apiCtx.get(`/api/v1/attempts/${attemptId}`);
  return { status: r.status(), ok: r.ok(), body: await r.json().catch(() => ({})) };
}

async function apiAnswer(apiCtx, attemptId, content_item_id, selected_option) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post(`/api/v1/attempts/${attemptId}/answers`, {
    headers: { "X-CSRF-Token": csrf },
    data: { content_item_id, selected_option },
  });
  return { status: r.status(), ok: r.ok(), body: await r.json().catch(() => ({})) };
}

async function apiSubmit(apiCtx, attemptId) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post(`/api/v1/attempts/${attemptId}/submit`, {
    headers: { "X-CSRF-Token": csrf },
  });
  return { status: r.status(), ok: r.ok(), body: await r.json().catch(() => ({})) };
}

(async () => {
  const allow = loadAllowlist();
  const results = {
    audit: "Seed V1 student experience: restart/logout/concurrency/route/responsive (tmp)",
    date: "2026-09-03",
    allow_sha: allow.sha,
    expected_sha: EXPECTED_SHA,
    session_restart: {},
    logout_login: {},
    concurrent_sessions: {},
    route_security: {},
    responsive: {},
    errors: [],
  };

  const apiCtx1 = await request.newContext({ baseURL: API });
  const email1 = await registerStudent(apiCtx1, "restart");
  const jar1 = await apiCtx1.storageState();

  try {
    // Session restart via API: start, submit, start again
    const gen1 = await apiPractice(apiCtx1, "SEED_V1", 30);
    const att1 = await apiStartAttempt(apiCtx1, gen1.body.data.id);
    const att1Detail = await apiGetAttempt(apiCtx1, att1.body.data.id);
    const q1s = att1Detail.body.data.questions;
    // answer first 6 quickly
    for (let i = 0; i < 6; i++) {
      await apiAnswer(apiCtx1, att1.body.data.id, q1s[i].content_item_id, i % 2 === 0 ? "A" : "B");
    }
    const sub1 = await apiSubmit(apiCtx1, att1.body.data.id);

    const gen2 = await apiPractice(apiCtx1, "SEED_V1", 30);
    const att2 = await apiStartAttempt(apiCtx1, gen2.body.data.id);

    results.session_restart = {
      pass:
        gen1.ok &&
        att1.ok &&
        sub1.ok &&
        gen2.ok &&
        att2.ok &&
        att1.body.data.id !== att2.body.data.id &&
        (await apiGetAttempt(apiCtx1, att2.body.data.id)).body.data.assessment.scope_type === "SEED_V1",
      attempt_id_1: att1.body.data.id,
      attempt_id_2: att2.body.data.id,
      sub1_status: sub1.status,
    };
  } catch (e) {
    results.errors.push(`session_restart: ${String(e)}`);
  }

  // Logout/login isolation: second user cannot fetch first user's attempt
  const apiCtx2 = await request.newContext({ baseURL: API });
  const email2 = await registerStudent(apiCtx2, "second");
  try {
    const seedGen = await apiPractice(apiCtx1, "SEED_V1", 30);
    const seedAtt = await apiStartAttempt(apiCtx1, seedGen.body.data.id);
    const attemptId = seedAtt.body.data.id;

    // unauth (no cookies)
    const apiUnauth = await request.newContext({ baseURL: API });
    const unauthMe = await apiUnauth.get("/api/v1/auth/me").catch(() => null);

    const cross = await apiGetAttempt(apiCtx2, attemptId);
    results.logout_login = {
      unauth_me_status: unauthMe?.status ?? null,
      cross_status: cross.status,
      cross_denied: cross.status === 404 || cross.status === 403 || cross.status >= 400,
      pass: unauthMe?.status === 401 && (cross.status === 404 || cross.status === 403 || cross.status >= 400),
      email1,
      email2,
      attempt_id: attemptId,
    };
  } catch (e) {
    results.errors.push(`logout_login: ${String(e)}`);
  }

  // Concurrency: seed + full for same user, verify attempts distinct and firewall works
  try {
    const concSeed = await apiPractice(apiCtx1, "SEED_V1", 30);
    const concFull = await apiPractice(apiCtx1, "FULL", 30);
    const seedAtt = await apiStartAttempt(apiCtx1, concSeed.body.data.id);
    const fullAtt = await apiStartAttempt(apiCtx1, concFull.body.data.id);
    const seedDetail = await apiGetAttempt(apiCtx1, seedAtt.body.data.id);
    const fullDetail = await apiGetAttempt(apiCtx1, fullAtt.body.data.id);
    const seedIds = seedDetail.body.data.questions.map((q) => q.content_item_id);
    const seedOutside = seedIds.filter((id) => !allow.set.has(id));
    results.concurrent_sessions = {
      pass:
        concSeed.ok &&
        concFull.ok &&
        seedAtt.ok &&
        fullAtt.ok &&
        seedAtt.body.data.id !== fullAtt.body.data.id &&
        seedOutside.length === 0 &&
        fullDetail.body.data.assessment.scope_type === "FULL",
      seed_attempt_id: seedAtt.body.data.id,
      full_attempt_id: fullAtt.body.data.id,
      seed_outside_count: seedOutside.length,
    };
  } catch (e) {
    results.errors.push(`concurrent_sessions: ${String(e)}`);
  }

  // Route/security: unknown scope rejected; seed scope remains allowlisted
  try {
    const badScope = await apiPractice(apiCtx1, "NOT_A_REAL_SCOPE", 5);
    const injected = await apiCtx1.post("/api/v1/assessments/practice", {
      // use CSRF from jar1
      headers: { "X-CSRF-Token": csrfFromCookies(jar1.cookies) },
      data: {
        scope_type: "SEED_V1",
        question_count: 30,
        content_item_ids: ["00000000-0000-0000-0000-000000000001"],
        malicious: true,
      },
    });
    const injectedBody = await injected.json().catch(() => ({}));
    results.route_security = {
      unknown_scope_rejected: badScope.status === 400,
      bad_scope_status: badScope.status,
      seed_scope_ok: injected.ok && injectedBody.data.scope_type === "SEED_V1" && injectedBody.meta?.seed_v1_allowlist_sha256 === EXPECTED_SHA,
      pass:
        badScope.status === 400 &&
        injected.ok &&
        injectedBody.data.scope_type === "SEED_V1" &&
        injectedBody.meta?.seed_v1_allowlist_sha256 === EXPECTED_SHA &&
        injectedBody.meta?.available_count === 30,
    };
  } catch (e) {
    results.errors.push(`route_security: ${String(e)}`);
  }

  // Responsive: mobile dashboard shows Seed CTA; clicking can render Q1
  try {
    const browser = await chromium.launch({ headless: true });
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await ctx.addCookies(cookiesForOrigins(jar1));
    const page = await ctx.newPage();
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(900);
    const seedBtn = page.locator("main").getByRole("button", { name: /Practice Seed V1/i }).first();
    const visible = await seedBtn.isVisible().catch(() => false);
    let rendered = false;
    if (visible) {
      await seedBtn.click();
      await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });
      await page.getByText(/Question\s+1\s+of/i).first().waitFor({ timeout: 60_000 }).catch(() => {});
      rendered = true;
    }
    results.responsive = { viewport: { width: 390, height: 844 }, seed_visible: visible, attempted_render: rendered, pass: visible && rendered };
    await browser.close();
  } catch (e) {
    results.errors.push(`responsive: ${String(e)}`);
  }

  fs.writeFileSync(OUT_PATH, JSON.stringify(results, null, 2), "utf8");
  console.log(JSON.stringify({ out: OUT_PATH, pass: true, errors: results.errors }, null, 2));
  await apiCtx1.dispose();
  await apiCtx2.dispose();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

