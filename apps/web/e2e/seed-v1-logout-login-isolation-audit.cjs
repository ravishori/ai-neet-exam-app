/**
 * Seed V1 logout/login isolation:
 * - unauth GET /api/v1/auth/me -> expected 401
 * - second user cannot GET attempt belonging to first user
 * Audit-only.
 */
const { request } = require("playwright");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../../..");

const AUTH = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json");
const EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1";
const PASSWORD = "PracticeTest!234";

const OUT_PATH = path.join(ROOT, "docs/audits/_seed_v1_logout_login_isolation_tmp.json");

function csrfFromCookies(cookies) {
  const c = cookies.find((x) => x.name === "csrf_token");
  return c ? decodeURIComponent(c.value) : "";
}

async function registerStudent(apiCtx, tag) {
  const email = `sx-reg-logout-${tag}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}@example.com`;
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD, first_name: "SX", last_name: tag },
  });
  if (!reg.ok()) throw new Error(`register failed ${reg.status()} ${await reg.text()}`);
  return email;
}

async function apiPractice(apiCtx, scope_type, question_count = 30) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post("/api/v1/assessments/practice", {
    headers: { "X-CSRF-Token": csrf },
    data: { scope_type, question_count },
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

(async () => {
  const results = {
    audit: "Seed V1 logout/login isolation (tmp)",
    date: "2026-09-03",
    unauth_me_status: null,
    cross_attempt_status: null,
    pass: false,
  };

  const apiUnauth = await request.newContext({ baseURL: API });
  try {
    const res = await apiUnauth.get("/api/v1/auth/me");
    results.unauth_me_status = res.status();
  } catch (e) {
    results.unauth_me_status = e?.response?.status ?? null;
  }
  await apiUnauth.dispose();

  const apiCtx1 = await request.newContext({ baseURL: API });
  const email1 = await registerStudent(apiCtx1, "one");

  const apiCtx2 = await request.newContext({ baseURL: API });
  const email2 = await registerStudent(apiCtx2, "two");

  const gen = await apiPractice(apiCtx1, "SEED_V1", 30);
  const att = await apiStartAttempt(apiCtx1, gen.body.data.id);
  const attemptId = att.body.data.id;

  const cross = await apiGetAttempt(apiCtx2, attemptId);
  results.cross_attempt_status = cross.status;
  results.cross_denied = cross.status === 404 || cross.status === 403 || cross.status >= 400;

  results.pass = results.unauth_me_status === 401 && results.cross_denied;
  results.email1 = email1;
  results.email2 = email2;
  results.attempt_id = attemptId;

  fs.writeFileSync(OUT_PATH, JSON.stringify(results, null, 2), "utf8");
  console.log(JSON.stringify({ out: OUT_PATH, pass: results.pass }, null, 2));

  await apiCtx1.dispose();
  await apiCtx2.dispose();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

