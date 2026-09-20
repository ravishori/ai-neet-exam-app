/**
 * PRODUCTION SEED V1 — Student Experience / Regression Audit (browser + API).
 * Audit-only: does not modify application code or content.
 */
const { chromium, request } = require("playwright");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execSync } = require("child_process");

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const ROOT = path.resolve(__dirname, "../../..");
const AUTH = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json");
const OUT_JSON = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V1_STUDENT_EXPERIENCE_REGRESSION_20260903.json");
const OUT_MD = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V1_STUDENT_EXPERIENCE_REGRESSION_REPORT_20260903.md");
const OUT_BROWSER = path.join(
  ROOT,
  "docs/audits/TALOS_PRODUCTION_SEED_V1_STUDENT_EXPERIENCE_BROWSER_EVIDENCE_20260903.json",
);
const EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1";
const PASSWORD = "PracticeTest!234";

function allowlistSha(ids) {
  return crypto.createHash("sha256").update(ids.join("\n") + "\n", "utf8").digest("hex");
}

function loadAllowlist() {
  const doc = JSON.parse(fs.readFileSync(AUTH, "utf8"));
  const ids = doc.exact_uuid_allowlist;
  const sha = allowlistSha(ids);
  return { ids, sha, set: new Set(ids), embedded: doc.allowlist_sha256 };
}

function csrfFromCookies(cookies) {
  const c = cookies.find((x) => x.name === "csrf_token");
  return c ? decodeURIComponent(c.value) : "";
}

async function registerStudent(apiCtx, tag) {
  const email = `sx-reg-${tag}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}@example.com`;
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD, first_name: "SX", last_name: tag },
  });
  if (!reg.ok()) throw new Error(`register failed ${reg.status()} ${await reg.text()}`);
  return email;
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

async function apiPractice(apiCtx, scope_type, question_count = 30) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const gen = await apiCtx.post("/api/v1/assessments/practice", {
    headers: { "X-CSRF-Token": csrf },
    data: { scope_type, question_count },
  });
  const body = await gen.json().catch(() => ({}));
  return { status: gen.status(), ok: gen.ok(), body };
}

async function apiStartAttempt(apiCtx, assessmentId) {
  const state = await apiCtx.storageState();
  const csrf = csrfFromCookies(state.cookies);
  const r = await apiCtx.post(`/api/v1/assessments/${assessmentId}/attempts`, {
    headers: { "X-CSRF-Token": csrf },
  });
  const body = await r.json().catch(() => ({}));
  return { status: r.status(), ok: r.ok(), body };
}

async function apiGetAttempt(apiCtx, attemptId) {
  const r = await apiCtx.get(`/api/v1/attempts/${attemptId}`);
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

async function clickSaveAndNext(page) {
  const btn = page.getByRole("button", { name: /Save\s*&\s*Next/i }).first();
  if (await btn.isVisible().catch(() => false)) {
    await btn.click();
    return "Save & Next";
  }
  const next = page.getByRole("button", { name: /^Next$/i }).first();
  if (await next.isVisible().catch(() => false)) {
    await next.click();
    return "Next";
  }
  throw new Error("No Save & Next / Next control visible");
}
  const btn = page.locator("main").getByRole("button", { name: buttonNameRegex }).first();
  await btn.waitFor({ state: "visible", timeout: 45_000 });
  const practiceRespPromise = page.waitForResponse(
    (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
    { timeout: 60_000 },
  );
  const attemptRespPromise = page.waitForResponse(
    (r) =>
      /\/api\/v1\/assessments\/[^/]+\/attempts$/.test(new URL(r.url()).pathname) &&
      r.request().method() === "POST",
    { timeout: 60_000 },
  );
  await btn.click();
  const [practiceResp, attemptResp] = await Promise.all([practiceRespPromise, attemptRespPromise]);
  const practiceJson = await practiceResp.json().catch(() => null);
  const attemptJson = await attemptResp.json().catch(() => null);
  await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });
  return {
    practice_ok: practiceResp.ok(),
    practice_status: practiceResp.status(),
    attempt_ok: attemptResp.ok(),
    attempt_status: attemptResp.status(),
    scope_type: practiceJson?.data?.scope_type,
    title: practiceJson?.data?.title,
    question_count: practiceJson?.data?.question_count,
    meta: practiceJson?.meta,
    assessment_id: practiceJson?.data?.id,
    attempt_id: attemptJson?.data?.id,
    url: page.url(),
    expected_scope_ok: practiceJson?.data?.scope_type === expectedScope,
  };
}

(async () => {
  const allow = loadAllowlist();
  const failures = [];
  const limitations = [];
  const console_errors = [];
  const page_errors = [];
  const http_errors = [];

  let gitCommit = null;
  let gitStatus = null;
  try {
    gitCommit = execSync("git rev-parse --short HEAD", { cwd: ROOT }).toString().trim();
    gitStatus = execSync("git status -sb", { cwd: ROOT }).toString().trim().split("\n")[0];
  } catch {
    /* ignore */
  }

  const report = {
    audit: "Production Seed V1 Student Experience / Regression Audit",
    date: "2026-09-03",
    captured_at: new Date().toISOString(),
    environment: {
      frontend: WEB,
      backend: API,
      browser: "chromium (playwright headless)",
      commit: gitCommit,
      working_tree: gitStatus,
      student_fixture: "ephemeral register — email retained without password",
    },
    seed_allowlist_hash: allow.sha,
    expected_allowlist_hash: EXPECTED_SHA,
    allowlist_hash_match: allow.sha === EXPECTED_SHA && allow.embedded === EXPECTED_SHA,
    dashboard: {},
    full_practice_regression: {},
    seed_entry_point: {},
    seed_firewall: {},
    answer_submission: {},
    explanation: {},
    next_question: {},
    refresh: {},
    back_forward_navigation: {},
    duplicate_submission: {},
    session_restart: {},
    logout_login: {},
    concurrent_sessions: {},
    route_security: {},
    responsive: {},
    accessibility_smoke: {},
    runtime: {},
    database_consistency: {},
    publication_firewall: {},
    exact30_integrity: {},
    failures: [],
    limitations: [],
    verdict: "RED",
  };

  const browserEvidence = {
    captured_at: report.captured_at,
    steps: [],
    console_errors,
    page_errors,
    http_errors,
  };

  if (!report.allowlist_hash_match) {
    failures.push({ gate: "allowlist_hash", actual: allow.sha, expected: EXPECTED_SHA });
  }

  const apiCtx = await request.newContext({ baseURL: API });
  const email = await registerStudent(apiCtx, "primary");
  report.environment.student_email = email;
  const jar = await apiCtx.storageState();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await context.addCookies(cookiesForOrigins(jar));
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") console_errors.push({ where: "desktop", text: msg.text() });
  });
  page.on("pageerror", (err) => page_errors.push({ where: "desktop", text: String(err) }));
  page.on("response", (res) => {
    const url = res.url();
    if (!url.includes("/api/v1/")) return;
    if (res.status() >= 400) {
      http_errors.push({ url, method: res.request().method(), status: res.status() });
    }
  });

  try {
    // -------- 4. Dashboard --------
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.waitForTimeout(1500);
    const fullBtn = page.locator("main").getByRole("button", { name: "Practice now with any published question" });
    const seedBtn = page.locator("main").getByRole("button", { name: /Practice Seed V1/i });
    const dash = {
      url: page.url(),
      full_visible: await fullBtn.isVisible().catch(() => false),
      full_enabled: await fullBtn.isEnabled().catch(() => false),
      seed_visible: await seedBtn.isVisible().catch(() => false),
      seed_enabled: await seedBtn.isEnabled().catch(() => false),
      full_label: await fullBtn.getAttribute("aria-label").catch(() => null),
      seed_label: await seedBtn.getAttribute("aria-label").catch(() => null),
      seed_text: await seedBtn.innerText().catch(() => null),
      console_errors_on_load: console_errors.length,
      failed_api_on_load: http_errors.filter((e) => e.status >= 500).length,
    };
    dash.pass =
      dash.full_visible &&
      dash.full_enabled &&
      dash.seed_visible &&
      dash.seed_enabled &&
      /any published/i.test(dash.full_label || "") &&
      /Seed V1/i.test(dash.seed_label || dash.seed_text || "");
    report.dashboard = dash;
    browserEvidence.steps.push({ step: "dashboard", ...dash });
    if (!dash.pass) failures.push({ gate: "dashboard", detail: dash });

    // -------- 17. Accessibility smoke (desktop) --------
    await seedBtn.focus();
    const seedFocused = await page.evaluate(() => {
      const el = document.activeElement;
      return el && /Seed V1/i.test(el.getAttribute("aria-label") || el.textContent || "");
    });
    await page.keyboard.press("Tab");
    const a11y = {
      seed_cta_keyboard_focusable: seedFocused,
      seed_aria_label: dash.seed_label,
      full_aria_label: dash.full_label,
      note: "Smoke only — not WCAG certification",
    };
    a11y.pass = Boolean(a11y.seed_cta_keyboard_focusable && a11y.seed_aria_label && a11y.full_aria_label);
    report.accessibility_smoke = a11y;
    if (!a11y.pass) failures.push({ gate: "accessibility_smoke", detail: a11y });

    // -------- 5. FULL practice regression --------
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1000);
    const fullStart = await startViaUi(page, /Practice now with any published question/i, "FULL");
    await page.getByText(/Question\s+1\s+of/i).first().waitFor({ timeout: 60_000 });
    const fullAttempt = await apiGetAttempt(apiCtx, fullStart.attempt_id);
    const fullQs = fullAttempt.body?.data?.questions || [];
    const fullIds = fullQs.map((q) => q.content_item_id);
    const fullOutside = fullIds.filter((id) => !allow.set.has(id));
    const fullExplBefore = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    await page.getByRole("button", { name: /^Option A:/i }).first().click();
    const nextFull = page.getByRole("button", { name: /Save\s*&\s*Next|^Next$/i }).first();
    if (await nextFull.isEnabled().catch(() => false)) {
      await nextFull.click();
      await page.getByText(/Question\s+2\s+of/i).first().waitFor({ timeout: 15_000 });
      const opt = page.getByRole("button", { name: /^Option A:/i }).first();
      if (await opt.isVisible().catch(() => false)) await opt.click();
    }
    await page.getByRole("button", { name: /^Submit$/i }).first().click();
    await page.getByText(/Score:/i).first().waitFor({ timeout: 60_000 });
    const fullExplAfter = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    const full = {
      ...fullStart,
      available_count: fullStart.meta?.available_count,
      broader_than_seed: (fullStart.meta?.available_count || 0) > 30,
      presented_count: fullIds.length,
      outside_seed_count: fullOutside.length,
      observed_non_seed_uuid: fullOutside[0] || null,
      explanation_before_submit: fullExplBefore,
      explanation_after_submit: fullExplAfter,
      score_visible: true,
    };
    full.pass =
      full.practice_ok &&
      full.attempt_ok &&
      full.expected_scope_ok &&
      full.broader_than_seed &&
      fullExplBefore === 0 &&
      fullExplAfter > 0;
    report.full_practice_regression = full;
    browserEvidence.steps.push({ step: "full_practice", ...full });
    if (!full.pass) failures.push({ gate: "full_practice_regression", detail: full });

    // -------- 6–8 Seed entry + firewall + answer/explain/next --------
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1000);
    const seedStart = await startViaUi(page, /Practice Seed V1/i, "SEED_V1");
    await page.getByText(/Question\s+1\s+of/i).first().waitFor({ timeout: 60_000 });
    const seedAttemptDetail = await apiGetAttempt(apiCtx, seedStart.attempt_id);
    const seedQs = seedAttemptDetail.body?.data?.questions || [];
    const seedIds = seedQs.map((q) => q.content_item_id);
    const seedOutside = seedIds.filter((id) => !allow.set.has(id));
    const seedMissing = allow.ids.filter((id) => !seedIds.includes(id));
    const subjects = [...new Set(seedQs.map((q) => (q.subject && (q.subject.name || q.subject)) || "unknown"))];

    report.seed_entry_point = {
      ...seedStart,
      meta_hash: seedStart.meta?.seed_v1_allowlist_sha256,
      meta_hash_ok: seedStart.meta?.seed_v1_allowlist_sha256 === EXPECTED_SHA,
      pass:
        seedStart.practice_ok &&
        seedStart.attempt_ok &&
        seedStart.expected_scope_ok &&
        seedStart.meta?.seed_v1_allowlist_sha256 === EXPECTED_SHA,
    };
    if (!report.seed_entry_point.pass) failures.push({ gate: "seed_entry_point", detail: report.seed_entry_point });

    report.seed_firewall = {
      presented_count: seedIds.length,
      unique_count: new Set(seedIds).size,
      outside_count: seedOutside.length,
      outside_sample: seedOutside.slice(0, 5),
      missing_count: seedMissing.length,
      subjects_observed: subjects,
      exact_match_30: seedIds.length === 30 && seedOutside.length === 0 && new Set(seedIds).size === 30,
      question_log: seedQs.slice(0, 8).map((q, i) => ({
        n: i + 1,
        uuid: q.content_item_id,
        subject: q.subject?.name || q.subject || null,
        in_allowlist: allow.set.has(q.content_item_id),
      })),
    };
    report.seed_firewall.pass = report.seed_firewall.exact_match_30;
    if (!report.seed_firewall.pass) failures.push({ gate: "seed_firewall", detail: report.seed_firewall });

    // Answer UX: select A on Q1, next, select A on Q2, then submit attempt
    const explBefore = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    const scoreBefore = await page.getByText(/Score:/i).count();
    await page.getByRole("button", { name: /^Option A:/i }).first().click();
    const q1Selected = await page.getByRole("button", { name: /^Option A:/i }).first().getAttribute("aria-pressed");
    await page.getByRole("button", { name: /^Next$/i }).first().click();
    await page.getByText(/Question\s+2\s+of/i).first().waitFor({ timeout: 15_000 });
    // Leak check: Q2 should not show explanation yet
    const explOnQ2 = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    await page.getByRole("button", { name: /^Option B:/i }).first().click().catch(async () => {
      await page.getByRole("button", { name: /^Option A:/i }).first().click();
    });
    // Progress label
    const progressText = await page.getByText(/Q\s+2\s*\/\s*30|Question\s+2\s+of\s+30/i).first().textContent().catch(() => null);

    // Continue answering a few more quickly via API for completion path, then UI submit
    // Answer remaining via API for scoring completeness while keeping UI for submit/explain
    for (let i = 0; i < seedQs.length; i++) {
      const q = seedQs[i];
      const label = i % 2 === 0 ? "A" : "B";
      await apiAnswer(apiCtx, seedStart.attempt_id, q.content_item_id, label);
    }

    await page.getByRole("button", { name: /^Submit$/i }).first().click();
    await page.getByText(/Score:/i).first().waitFor({ timeout: 60_000 });
    const explAfter = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    const scoreText = await page.getByText(/Score:/i).first().textContent();
    const correctText = await page.getByText(/\d+\s+correct/i).first().textContent().catch(() => null);
    const incorrectText = await page.getByText(/\d+\s+incorrect/i).first().textContent().catch(() => null);

    // Next after submit (review mode)
    const nextAfter = page.getByRole("button", { name: /Save\s*&\s*Next|^Next$/i }).first();
    let nextAfterOk = false;
    if (await nextAfter.isEnabled().catch(() => false)) {
      await nextAfter.click();
      await page.getByText(/Question\s+\d+\s+of/i).first().waitFor({ timeout: 15_000 });
      nextAfterOk = true;
    }

    const submittedAttempt = await apiGetAttempt(apiCtx, seedStart.attempt_id);
    const submittedData = submittedAttempt.body?.data || {};

    report.answer_submission = {
      q1_option_pressed: q1Selected,
      answers_persisted: (submittedData.questions || []).filter((q) => q.selected_option).length,
      pass: q1Selected === "true" && submittedData.status === "SUBMITTED",
    };
    report.explanation = {
      before_submit_heading_count: explBefore,
      before_submit_score_count: scoreBefore,
      on_q2_before_attempt_submit: explOnQ2,
      after_submit_heading_count: explAfter,
      pass: explBefore === 0 && scoreBefore === 0 && explOnQ2 === 0 && explAfter > 0,
      contract: "explanation/correctness exposed after attempt SUBMITTED (not per-option immediate)",
    };
    report.next_question = {
      progressed_to_q2_before_submit: Boolean(progressText),
      review_next_after_submit: nextAfterOk,
      pass: Boolean(progressText) && nextAfterOk,
    };
    report.progress = {
      progress_text_q2: progressText,
      pass: Boolean(progressText),
    };
    report.scoring = {
      scoreText,
      correctText,
      incorrectText,
      status: submittedData.status,
      correct_count: submittedData.correct_count,
      incorrect_count: submittedData.incorrect_count,
      pass:
        submittedData.status === "SUBMITTED" &&
        submittedData.score != null &&
        (submittedData.correct_count || 0) + (submittedData.incorrect_count || 0) + (submittedData.skipped_count || 0) ===
          30,
    };
    report.completion = {
      status: submittedData.status,
      pass: submittedData.status === "SUBMITTED",
    };
    for (const g of ["answer_submission", "explanation", "next_question", "progress", "scoring", "completion"]) {
      if (!report[g].pass) failures.push({ gate: g, detail: report[g] });
    }
    browserEvidence.steps.push({
      step: "seed_session_core",
      entry: report.seed_entry_point,
      firewall: report.seed_firewall,
      explanation: report.explanation,
      scoring: report.scoring,
    });

    // -------- 9. Refresh / reload --------
    // Start a fresh Seed session for refresh test
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(800);
    const refreshStart = await startViaUi(page, /Practice Seed V1/i, "SEED_V1");
    await page.getByText(/Question\s+1\s+of/i).first().waitFor({ timeout: 60_000 });
    await page.getByRole("button", { name: /^Option A:/i }).first().click();
    await clickSaveAndNext(page);
    await page.getByText(/Question\s+2\s+of/i).first().waitFor({ timeout: 15_000 });
    const urlBeforeRefresh = page.url();
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const urlAfterRefresh = page.url();
    const stillOnAttempt = /\/student\/attempts\//i.test(urlAfterRefresh);
    const qLabelAfter = await page.getByText(/Question\s+\d+\s+of/i).first().textContent().catch(() => null);
    const afterRefreshAttempt = await apiGetAttempt(apiCtx, refreshStart.attempt_id);
    const answeredAfter = (afterRefreshAttempt.body?.data?.questions || []).filter((q) => q.selected_option).length;
    // Product: attemptId in URL persists; currentIndex is client state → typically resets to Q1
    report.refresh = {
      url_before: urlBeforeRefresh,
      url_after: urlAfterRefresh,
      still_same_attempt_route: stillOnAttempt && urlAfterRefresh.includes(refreshStart.attempt_id),
      question_label_after_reload: qLabelAfter,
      answered_persisted_server: answeredAfter >= 1,
      observed_contract:
        "Attempt ID resume via URL is supported; local question index resets to first question on remount (client state).",
      pass: stillOnAttempt && urlAfterRefresh.includes(refreshStart.attempt_id) && answeredAfter >= 1,
      no_corruption: afterRefreshAttempt.body?.data?.status === "IN_PROGRESS",
    };
    if (!report.refresh.pass) failures.push({ gate: "refresh", detail: report.refresh });
    limitations.push(
      "Refresh resumes the same attempt by URL but resets local question index to Question 1; server-saved answers persist.",
    );

    // -------- 10. Back/forward --------
    const backUrlBefore = page.url();
    await page.goBack({ waitUntil: "domcontentloaded" }).catch(() => null);
    await page.waitForTimeout(1000);
    const afterBack = page.url();
    await page.goForward({ waitUntil: "domcontentloaded" }).catch(() => null);
    await page.waitForTimeout(1000);
    const afterForward = page.url();
    const attemptAfterNav = await apiGetAttempt(apiCtx, refreshStart.attempt_id);
    report.back_forward_navigation = {
      after_back: afterBack,
      after_forward: afterForward,
      attempt_status: attemptAfterNav.body?.data?.status,
      pass: attemptAfterNav.body?.data?.status === "IN_PROGRESS" && !attemptAfterNav.body?.data?.status?.includes("corrupt"),
      note: "Browser history may leave attempt page; attempt record remains IN_PROGRESS without duplicate creation from back alone.",
    };
    // Verify no accidental second practice create from back — check network wasn't forced
    if (!report.back_forward_navigation.pass) failures.push({ gate: "back_forward", detail: report.back_forward_navigation });

    // -------- 11. Duplicate submission --------
    // Answer all + submit twice via API on a dedicated attempt
    const dupGen = await apiPractice(apiCtx, "SEED_V1", 30);
    const dupAtt = await apiStartAttempt(apiCtx, dupGen.body.data.id);
    const dupId = dupAtt.body.data.id;
    const dupQs = (await apiGetAttempt(apiCtx, dupId)).body.data.questions;
    for (const q of dupQs) {
      await apiAnswer(apiCtx, dupId, q.content_item_id, "A");
    }
    const sub1 = await apiSubmit(apiCtx, dupId);
    const sub2 = await apiSubmit(apiCtx, dupId);
    const afterDup = await apiGetAttempt(apiCtx, dupId);
    report.duplicate_submission = {
      first_submit_ok: sub1.ok,
      second_submit_status: sub2.status,
      second_submit_rejected: !sub2.ok || sub2.status >= 400,
      final_status: afterDup.body?.data?.status,
      correct_count: afterDup.body?.data?.correct_count,
      pass: sub1.ok && afterDup.body?.data?.status === "SUBMITTED" && (!sub2.ok || sub2.status >= 400),
    };
    if (!report.duplicate_submission.pass) failures.push({ gate: "duplicate_submission", detail: report.duplicate_submission });

    // -------- 12. Session restart --------
    const restart1 = await apiPractice(apiCtx, "SEED_V1", 30);
    const restartAtt1 = await apiStartAttempt(apiCtx, restart1.body.data.id);
    const restart2 = await apiPractice(apiCtx, "SEED_V1", 30);
    const restartAtt2 = await apiStartAttempt(apiCtx, restart2.body.data.id);
    report.session_restart = {
      attempt_1: restartAtt1.body?.data?.id,
      attempt_2: restartAtt2.body?.data?.id,
      distinct: restartAtt1.body?.data?.id !== restartAtt2.body?.data?.id,
      scope_1: restart1.body?.data?.scope_type,
      scope_2: restart2.body?.data?.scope_type,
      pass:
        restartAtt1.ok &&
        restartAtt2.ok &&
        restartAtt1.body?.data?.id !== restartAtt2.body?.data?.id &&
        restart1.body?.data?.scope_type === "SEED_V1" &&
        restart2.body?.data?.scope_type === "SEED_V1",
    };
    if (!report.session_restart.pass) failures.push({ gate: "session_restart", detail: report.session_restart });

    // -------- 13. Logout / login --------
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    // Clear cookies = logout analogue for this fixture, then login via API cookies for second user
    await context.clearCookies();
    const meUnauth = await page.evaluate(async (api) => {
      const res = await fetch(`${api}/api/v1/auth/me`, { credentials: "include" });
      return res.status;
    }, API);
    const apiCtx2 = await request.newContext({ baseURL: API });
    const email2 = await registerStudent(apiCtx2, "second");
    const jar2 = await apiCtx2.storageState();
    await context.addCookies(cookiesForOrigins(jar2));
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1000);
    const me2 = await page.evaluate(async (api) => {
      const res = await fetch(`${api}/api/v1/auth/me`, { credentials: "include" });
      const j = await res.json().catch(() => ({}));
      return { status: res.status, email: j?.data?.email };
    }, API);
    // Second user cannot access first user's attempt
    const cross = await apiCtx2.get(`/api/v1/attempts/${seedStart.attempt_id}`);
    report.logout_login = {
      unauth_me_status: meUnauth,
      second_user_email: email2,
      second_user_me_ok: me2.status === 200,
      cross_attempt_status: cross.status(),
      cross_attempt_denied: cross.status() === 404 || cross.status() === 403 || cross.status() >= 400,
      pass: meUnauth === 401 && me2.status === 200 && (cross.status() === 404 || cross.status() === 403 || cross.status() >= 400),
    };
    if (!report.logout_login.pass) failures.push({ gate: "logout_login", detail: report.logout_login });

    // -------- 14. Concurrent sessions --------
    const concSeed = await apiPractice(apiCtx, "SEED_V1", 30);
    const concFull = await apiPractice(apiCtx, "FULL", 30);
    const concSeedAtt = await apiStartAttempt(apiCtx, concSeed.body.data.id);
    const concFullAtt = await apiStartAttempt(apiCtx, concFull.body.data.id);
    const concSeedQs = (await apiGetAttempt(apiCtx, concSeedAtt.body.data.id)).body.data.questions.map((q) => q.content_item_id);
    const concFullQs = (await apiGetAttempt(apiCtx, concFullAtt.body.data.id)).body.data.questions.map((q) => q.content_item_id);
    const concSeedOutside = concSeedQs.filter((id) => !allow.set.has(id));
    report.concurrent_sessions = {
      supported: true,
      seed_attempt: concSeedAtt.body?.data?.id,
      full_attempt: concFullAtt.body?.data?.id,
      distinct: concSeedAtt.body?.data?.id !== concFullAtt.body?.data?.id,
      seed_scope: concSeed.body?.data?.scope_type,
      full_scope: concFull.body?.data?.scope_type,
      seed_outside: concSeedOutside.length,
      full_available: concFull.body?.meta?.available_count,
      pass:
        concSeed.body?.data?.scope_type === "SEED_V1" &&
        concFull.body?.data?.scope_type === "FULL" &&
        concSeedAtt.body?.data?.id !== concFullAtt.body?.data?.id &&
        concSeedOutside.length === 0 &&
        (concFull.body?.meta?.available_count || 0) > 30,
    };
    if (!report.concurrent_sessions.pass) failures.push({ gate: "concurrent_sessions", detail: report.concurrent_sessions });

    // -------- 15. Route / security --------
    const badScope = await apiPractice(apiCtx, "NOT_A_REAL_SCOPE", 5);
    const injectish = await apiCtx.post("/api/v1/assessments/practice", {
      headers: { "X-CSRF-Token": csrfFromCookies((await apiCtx.storageState()).cookies) },
      data: {
        scope_type: "SEED_V1",
        question_count: 30,
        content_item_ids: ["00000000-0000-0000-0000-000000000001"],
      },
    });
    const injectBody = await injectish.json().catch(() => ({}));
    // Direct attempt URL still requires auth ownership — already tested
    report.route_security = {
      unknown_scope_status: badScope.status,
      unknown_scope_rejected: badScope.status === 400,
      inject_extra_field_ignored_or_ok: injectish.ok() && injectBody?.data?.scope_type === "SEED_V1",
      inject_did_not_change_membership:
        injectish.ok() &&
        injectBody?.meta?.available_count === 30 &&
        injectBody?.meta?.seed_v1_allowlist_sha256 === EXPECTED_SHA,
      pass:
        badScope.status === 400 &&
        injectish.ok() &&
        injectBody?.data?.scope_type === "SEED_V1" &&
        injectBody?.meta?.seed_v1_allowlist_sha256 === EXPECTED_SHA,
    };
    if (!report.route_security.pass) failures.push({ gate: "route_security", detail: report.route_security });

    // -------- 16. Responsive --------
    await context.clearCookies();
    await context.addCookies(cookiesForOrigins(jar2));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1200);
    const mobileSeed = page.locator("main").getByRole("button", { name: /Practice Seed V1/i });
    const mobileFull = page.locator("main").getByRole("button", { name: "Practice now with any published question" });
    const mobile = {
      viewport: { width: 390, height: 844 },
      seed_visible: await mobileSeed.isVisible().catch(() => false),
      full_visible: await mobileFull.isVisible().catch(() => false),
    };
    if (mobile.seed_visible) {
      const mStart = await startViaUi(page, /Practice Seed V1/i, "SEED_V1");
      await page.getByText(/Question\s+1\s+of/i).first().waitFor({ timeout: 60_000 });
      const optVisible = await page.getByRole("button", { name: /^Option A:/i }).first().isVisible();
      await page.getByRole("button", { name: /^Option A:/i }).first().click();
      const submitVisible = await page.getByRole("button", { name: /^Submit$/i }).first().isVisible();
      mobile.session = {
        scope_type: mStart.scope_type,
        option_visible: optVisible,
        submit_visible: submitVisible,
        practice_ok: mStart.practice_ok,
      };
      mobile.pass =
        mobile.seed_visible &&
        mobile.full_visible &&
        mStart.expected_scope_ok &&
        optVisible &&
        submitVisible;
    } else {
      mobile.pass = false;
    }
    report.responsive = mobile;
    if (!report.responsive.pass) failures.push({ gate: "responsive", detail: report.responsive });

    // Restore desktop cookies for cleanup not needed
  } catch (err) {
    failures.push({ gate: "runtime_exception", detail: String(err) });
    report.runtime_exception = String(err);
  }

  // -------- DB / publication integrity via dedicated read-only script --------
  let integrity = {};
  try {
    const pyPath = path.join(ROOT, "apps/backend/scripts/seed_v1_student_experience_integrity_snapshot.py");
    const pyExe = path.join(ROOT, "apps/backend/.venv/Scripts/python.exe");
    const out = execSync(`"${pyExe}" "${pyPath}"`, {
      encoding: "utf8",
      cwd: path.join(ROOT, "apps/backend"),
    });
    integrity = JSON.parse(out.trim().split("\n").filter(Boolean).pop());
  } catch (e) {
    integrity = { error: String(e) };
    failures.push({ gate: "integrity_script", detail: String(e).slice(0, 500) });
  }

  report.exact30_integrity = {
    allowlist_sha256: integrity.sha || allow.sha,
    match: (integrity.sha || allow.sha) === EXPECTED_SHA,
    status: integrity.status,
    fingerprint_mismatches: integrity.mismatches || [],
    pass:
      (integrity.sha || allow.sha) === EXPECTED_SHA &&
      (integrity.status || {}).PUBLISHED === 30 &&
      !(integrity.mismatches || []).length,
  };
  report.publication_firewall = {
    published: (integrity.status || {}).PUBLISHED,
    approved: (integrity.status || {}).APPROVED || 0,
    draft: (integrity.status || {}).DRAFT || 0,
    ecaep: integrity.ecaep,
    unintended_publications: 0,
    pass:
      (integrity.status || {}).PUBLISHED === 30 &&
      ((integrity.status || {}).APPROVED || 0) === 0 &&
      ((integrity.status || {}).DRAFT || 0) === 0 &&
      integrity.ecaep === 0,
  };
  report.database_consistency = {
    recent_seed_submitted_attempts: integrity.recent_seed_submitted,
    protected_unchanged: integrity.unchanged,
    content_fingerprint_mismatches: (integrity.mismatches || []).length,
    pass:
      report.exact30_integrity.pass &&
      integrity.unchanged?.t6d &&
      integrity.unchanged?.t6f2 &&
      integrity.unchanged?.legacy,
  };
  if (!report.exact30_integrity.pass) failures.push({ gate: "exact30_integrity", detail: report.exact30_integrity });
  if (!report.publication_firewall.pass) failures.push({ gate: "publication_firewall", detail: report.publication_firewall });
  if (!report.database_consistency.pass) failures.push({ gate: "database_consistency", detail: report.database_consistency });

  const blockerHttp = http_errors.filter((e) => e.status >= 500);
  // 4xx from intentional negative tests are expected
  report.runtime = {
    console_errors: console_errors.slice(0, 20),
    page_errors: page_errors.slice(0, 20),
    http_errors_sample: http_errors.slice(0, 30),
    blocker_5xx: blockerHttp.length,
    classification: blockerHttp.length ? "BLOCKER" : console_errors.length || page_errors.length ? "MEDIUM" : "NONE",
    pass: blockerHttp.length === 0 && page_errors.length === 0,
  };
  if (!report.runtime.pass) failures.push({ gate: "runtime", detail: report.runtime });

  report.failures = failures;
  report.limitations = [
    ...new Set([
      ...limitations,
      "Accessibility check is a smoke test only (not WCAG certification).",
      "Responsive check covers 1366×768 and 390×844 only.",
      "Logout simulated via cookie clear + second registered student (established E2E pattern).",
    ]),
  ];

  const requiredPass = [
    report.dashboard?.pass,
    report.full_practice_regression?.pass,
    report.seed_entry_point?.pass,
    report.seed_firewall?.pass,
    report.answer_submission?.pass,
    report.explanation?.pass,
    report.next_question?.pass,
    report.progress?.pass,
    report.scoring?.pass,
    report.completion?.pass,
    report.refresh?.pass,
    report.back_forward_navigation?.pass,
    report.duplicate_submission?.pass,
    report.session_restart?.pass,
    report.logout_login?.pass,
    report.concurrent_sessions?.pass,
    report.route_security?.pass,
    report.responsive?.pass,
    report.accessibility_smoke?.pass,
    report.runtime?.pass,
    report.database_consistency?.pass,
    report.exact30_integrity?.pass,
    report.publication_firewall?.pass,
  ];

  const criticalFail = failures.some((f) =>
    [
      "seed_entry_point",
      "seed_firewall",
      "full_practice_regression",
      "answer_submission",
      "explanation",
      "scoring",
      "completion",
      "route_security",
      "exact30_integrity",
      "publication_firewall",
      "runtime",
    ].includes(f.gate),
  );

  if (requiredPass.every(Boolean) && !criticalFail) {
    report.verdict = "GREEN";
  } else if (!criticalFail && requiredPass.filter(Boolean).length >= requiredPass.length - 2) {
    report.verdict = "AMBER";
  } else {
    report.verdict = "RED";
  }

  report.gate_summary = {
    dashboard: report.dashboard?.pass ? "PASS" : "FAIL",
    full_practice: report.full_practice_regression?.pass ? "PASS" : "FAIL",
    seed_entry: report.seed_entry_point?.pass ? "PASS" : "FAIL",
    seed_firewall: report.seed_firewall?.pass ? "PASS" : "FAIL",
    answer_submission: report.answer_submission?.pass ? "PASS" : "FAIL",
    explanation: report.explanation?.pass ? "PASS" : "FAIL",
    next_question: report.next_question?.pass ? "PASS" : "FAIL",
    progress: report.progress?.pass ? "PASS" : "FAIL",
    scoring: report.scoring?.pass ? "PASS" : "FAIL",
    completion: report.completion?.pass ? "PASS" : "FAIL",
    refresh: report.refresh?.pass ? "PASS" : "FAIL",
    back_forward: report.back_forward_navigation?.pass ? "PASS" : "FAIL",
    duplicate_submission: report.duplicate_submission?.pass ? "PASS" : "FAIL",
    session_restart: report.session_restart?.pass ? "PASS" : "FAIL",
    logout_login: report.logout_login?.pass ? "PASS" : "FAIL",
    concurrent_sessions: report.concurrent_sessions?.pass ? "PASS" : "FAIL",
    route_security: report.route_security?.pass ? "PASS" : "FAIL",
    responsive: report.responsive?.pass ? "PASS" : "FAIL",
    accessibility_smoke: report.accessibility_smoke?.pass ? "PASS" : "FAIL",
    runtime: report.runtime?.pass ? "PASS" : "FAIL",
    database_consistency: report.database_consistency?.pass ? "PASS" : "FAIL",
    content_integrity: report.exact30_integrity?.pass ? "PASS" : "FAIL",
    t6d: integrity.unchanged?.t6d ? "UNCHANGED" : "CHANGED",
    t6f2: integrity.unchanged?.t6f2 ? "UNCHANGED" : "CHANGED",
    ecaep: integrity.ecaep,
  };

  browserEvidence.pass = report.verdict !== "RED";
  fs.writeFileSync(OUT_BROWSER, JSON.stringify(browserEvidence, null, 2));
  fs.writeFileSync(OUT_JSON, JSON.stringify(report, null, 2));

  const md = `# PRODUCTION SEED V1 — STUDENT EXPERIENCE / REGRESSION AUDIT REPORT

**Date:** 2026-09-03  
**Verdict:** ${report.verdict}  
**Allowlist hash:** \`${report.seed_allowlist_hash}\`

## Environment

- Frontend: ${WEB}
- Backend: ${API}
- Browser: Chromium (Playwright headless)
- Commit: ${gitCommit || "n/a"} (${gitStatus || "n/a"})
- Student fixtures: ephemeral registrations (emails in JSON; passwords omitted)

## Gate summary

\`\`\`json
${JSON.stringify(report.gate_summary, null, 2)}
\`\`\`

## Failures

\`\`\`json
${JSON.stringify(report.failures, null, 2)}
\`\`\`

## Limitations

\`\`\`json
${JSON.stringify(report.limitations, null, 2)}
\`\`\`

## Key evidence

### Dashboard
\`\`\`json
${JSON.stringify(report.dashboard, null, 2)}
\`\`\`

### FULL regression
\`\`\`json
${JSON.stringify(report.full_practice_regression, null, 2)}
\`\`\`

### Seed entry + firewall
\`\`\`json
${JSON.stringify({ entry: report.seed_entry_point, firewall: report.seed_firewall }, null, 2)}
\`\`\`

### Refresh / duplicate / concurrency / security
\`\`\`json
${JSON.stringify(
  {
    refresh: report.refresh,
    duplicate_submission: report.duplicate_submission,
    concurrent_sessions: report.concurrent_sessions,
    route_security: report.route_security,
  },
  null,
  2,
)}
\`\`\`

### Integrity
\`\`\`json
${JSON.stringify(
  {
    exact30: report.exact30_integrity,
    publication: report.publication_firewall,
    database: report.database_consistency,
  },
  null,
  2,
)}
\`\`\`

## Final verdict

**${report.verdict}**
`;
  fs.writeFileSync(OUT_MD, md);

  console.log(
    JSON.stringify(
      {
        verdict: report.verdict,
        gate_summary: report.gate_summary,
        failure_count: failures.length,
        artifacts: [OUT_JSON, OUT_MD, OUT_BROWSER],
      },
      null,
      2,
    ),
  );

  await browser.close();
  await apiCtx.dispose();
  process.exit(report.verdict === "RED" ? 1 : 0);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
