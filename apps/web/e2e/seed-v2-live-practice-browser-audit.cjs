/**
 * Seed V2 live Practice Seed V2 browser evidence (audit-only).
 * Completes a sampled student UI path — not a 100-click completion.
 */
const { chromium, request } = require("playwright");
const fs = require("fs");
const path = require("path");

const API = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const OUT = path.resolve(
  __dirname,
  "../../../docs/audits/TALOS_PRODUCTION_SEED_V2_LIVE_PRACTICE_BROWSER_EVIDENCE_20260904.json",
);
const AUTH = path.resolve(
  __dirname,
  "../../../docs/audits/TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json",
);
const EXPECTED_SHA = "a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978";
const VISUAL = {
  "physics-05": "9c51f8a1-bf72-4ca0-bcfd-e0aa5cb8ee53",
  "physics-21": "1633f068-f0df-4ff5-ac0c-57be4417f29e",
  "zoology-12": "ca0e7a05-38bb-4e12-a52d-4fd4c7a26b07",
};

function writeEvidence(evidence) {
  fs.writeFileSync(OUT, JSON.stringify(evidence, null, 2));
}

(async () => {
  const evidence = {
    captured_at: new Date().toISOString(),
    web: WEB,
    api: API,
    steps: [],
    console_errors: [],
    page_errors: [],
    network: [],
    pass: false,
    full_100_browser_completion: false,
  };

  const email = `seed-v2-browser-${Date.now()}@example.com`;
  const password = "PracticeTest!234";
  const apiCtx = await request.newContext({ baseURL: API });
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password, first_name: "Seed", last_name: "V2Browser" },
  });
  evidence.student_email = email;
  evidence.steps.push({ step: "register", status: reg.status(), ok: reg.ok() });
  if (!reg.ok()) {
    evidence.failure = await reg.text();
    writeEvidence(evidence);
    process.exit(1);
  }

  const jar = await apiCtx.storageState();
  const cookies = [];
  const origins = [
    "http://127.0.0.1:3000/",
    "http://localhost:3000/",
    "http://127.0.0.1:8000/",
    "http://localhost:8000/",
  ];
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

  const allowlist = JSON.parse(fs.readFileSync(AUTH, "utf8")).exact_allowlist;
  const allowSet = new Set(allowlist);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await context.addCookies(cookies);
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") evidence.console_errors.push(msg.text());
  });
  page.on("pageerror", (err) => evidence.page_errors.push(String(err)));
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/v1/assessments") || url.includes("/api/v1/attempts")) {
      evidence.network.push({
        url,
        method: res.request().method(),
        status: res.status(),
        ok: res.ok(),
      });
    }
  });

  try {
    const webHost = WEB.includes("127.0.0.1") ? WEB.replace("127.0.0.1", "localhost") : WEB;
    await page.goto(`${webHost}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.waitForTimeout(2000);
    evidence.steps.push({ step: "dashboard_loaded", url: page.url() });

    const meCheck = await page.evaluate(async (apiUrl) => {
      const res = await fetch(`${apiUrl}/api/v1/auth/me`, { credentials: "include" });
      return { status: res.status, ok: res.ok };
    }, "http://localhost:8000");
    evidence.steps.push({ step: "auth_me_from_browser", ...meCheck });
    if (!meCheck.ok) throw new Error(`browser auth/me ${meCheck.status}`);

    const fullCta = page.locator("main").getByRole("button", { name: /^Practice now$/i }).first();
    const v1Cta = page.locator("main").getByRole("button", { name: /Practice Seed V1/i }).first();
    const v2Cta = page.locator("main").getByRole("button", { name: /Practice Seed V2/i }).first();
    await v2Cta.waitFor({ state: "visible", timeout: 45_000 });
    evidence.steps.push({
      step: "cta_visibility",
      practice_now: await fullCta.isVisible(),
      seed_v1: await v1Cta.isVisible(),
      seed_v2: true,
      seed_v2_enabled: await v2Cta.isEnabled(),
      seed_v2_aria: await v2Cta.getAttribute("aria-label"),
    });

    const practiceRespPromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 45_000 },
    );
    const attemptRespPromise = page.waitForResponse(
      (r) =>
        /\/api\/v1\/assessments\/[^/]+\/attempts$/.test(new URL(r.url()).pathname) &&
        r.request().method() === "POST",
      { timeout: 45_000 },
    );
    await v2Cta.click();
    const [practiceResp, attemptResp] = await Promise.all([practiceRespPromise, attemptRespPromise]);
    const practiceJson = await practiceResp.json().catch(() => null);
    const attemptJson = await attemptResp.json().catch(() => null);
    const reqBody = practiceResp.request().postDataJSON();
    evidence.steps.push({
      step: "practice_api_response",
      status: practiceResp.status(),
      ok: practiceResp.ok(),
      client_body: reqBody,
      assessment_id: practiceJson?.data?.id,
      question_count: practiceJson?.data?.question_count,
      scope_type: practiceJson?.data?.scope_type,
      title: practiceJson?.data?.title,
      meta: practiceJson?.meta,
    });
    evidence.steps.push({
      step: "attempt_api_response",
      status: attemptResp.status(),
      ok: attemptResp.ok(),
      attempt_id: attemptJson?.data?.id,
    });
    if (!practiceResp.ok() || !attemptResp.ok()) {
      throw new Error(`practice/attempt failed ${practiceResp.status()}/${attemptResp.status()}`);
    }
    if (practiceJson?.data?.scope_type !== "SEED_V2") {
      throw new Error(`expected SEED_V2, got ${practiceJson?.data?.scope_type}`);
    }
    if (practiceJson?.data?.question_count !== 100) {
      throw new Error(`expected 100 questions, got ${practiceJson?.data?.question_count}`);
    }
    if (practiceJson?.meta?.seed_v2_allowlist_sha256 !== EXPECTED_SHA) {
      throw new Error("allowlist sha mismatch in meta");
    }

    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });
    evidence.steps.push({ step: "navigated_to_attempt", url: page.url() });

    const attemptDetail = await page.evaluate(async (apiUrl) => {
      const id = location.pathname.split("/").pop();
      const res = await fetch(`${apiUrl}/api/v1/attempts/${id}`, { credentials: "include" });
      const body = await res.json();
      const qs = (body.data && body.data.questions) || [];
      return {
        status: res.status,
        attemptStatus: body.data && body.data.status,
        questions: qs.map((q) => ({
          id: q.content_item_id,
          stem: q.stem,
          options: (q.options || []).map((o) => o.label),
          explanation: q.explanation || null,
          correct_option: q.correct_option || null,
          subject: q.subject && (q.subject.name || q.subject.title),
          images: (q.images || []).length,
        })),
      };
    }, "http://localhost:8000");
    const presented = attemptDetail.questions.map((q) => q.id);
    const outside = presented.filter((id) => !allowSet.has(id));
    evidence.steps.push({
      step: "seed_v2_firewall",
      presented_count: presented.length,
      outside_count: outside.length,
      all_in_allowlist: outside.length === 0 && presented.length === 100,
      unique_count: new Set(presented).size,
      leak_before_submit: attemptDetail.questions.filter((q) => q.explanation || q.correct_option).length,
    });
    if (outside.length || presented.length !== 100) {
      throw new Error(`firewall fail outside=${outside.slice(0, 3)} n=${presented.length}`);
    }

    await page.getByText(/Q\s+1\s+\/\s+100|Question\s+1\s+of\s+100/i).first().waitFor({ timeout: 60_000 });
    const qLabel = await page.getByText(/Q\s+\d+\s+\/\s+\d+|Question\s+\d+\s+of\s+\d+/i).first().textContent();
    const explanationBefore = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    const optionA = page.getByRole("button", { name: /^Option A:/i }).first();
    await optionA.click();
    evidence.steps.push({
      step: "first_question_rendered",
      question_label: qLabel,
      explanation_heading_count_before_submit: explanationBefore,
      option_a_pressed: await optionA.getAttribute("aria-pressed"),
      four_options: await page.getByRole("button", { name: /^Option [A-D]:/i }).count(),
    });

    const next = page.getByRole("button", { name: /Next/i }).first();
    await next.click();
    await page.waitForTimeout(500);
    evidence.steps.push({
      step: "next_question",
      label: await page.getByText(/Q\s+\d+\s+\/\s+\d+|Question\s+\d+\s+of\s+\d+/i).first().textContent(),
    });
    await page.getByRole("button", { name: /^Option B:/i }).first().click();

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /^Option [A-D]:/i }).first().waitFor({ timeout: 30_000 });
    evidence.steps.push({ step: "refresh", url: page.url(), still_attempt: /\/student\/attempts\//.test(page.url()) });

    const submitBtn = page.locator("div.hidden.sm\\:flex").getByRole("button", { name: /^Submit$/i });
    const submitRespPromise = page.waitForResponse(
      (r) => r.url().includes("/submit") && r.request().method() === "POST",
      { timeout: 180_000 },
    );
    await submitBtn.click({ force: true, timeout: 60_000 });
    const submitResp = await submitRespPromise;
    evidence.steps.push({ step: "submit_http", status: submitResp.status(), ok: submitResp.ok() });
    if (!submitResp.ok()) throw new Error(`submit failed ${submitResp.status()}`);
    await page.getByText(/\d+\s+correct/i).first().waitFor({ timeout: 60_000 });
    const explanationAfter = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    const scoreCount = await page.getByText(/Score:/i).count();
    evidence.steps.push({
      step: "submitted_sample",
      scoreVisible: scoreCount > 0,
      correctText: await page.getByText(/\d+\s+correct/i).first().textContent(),
      explanation_heading_count_after_submit: explanationAfter,
    });

    const visIndex = presented.findIndex((id) => id === VISUAL["physics-05"]);
    if (visIndex >= 0) {
      const cell = page.getByRole("button", { name: new RegExp(`Question ${visIndex + 1}\\b`, "i") }).first();
      if (await cell.count()) await cell.click().catch(() => null);
      await page.waitForTimeout(400);
      evidence.steps.push({
        step: "visual_physics_05_after_submit",
        index: visIndex + 1,
        img_count: await page.locator("img").count(),
        svg_count: await page.locator("svg").count(),
      });
    }

    await page.goBack({ waitUntil: "domcontentloaded" }).catch(() => null);
    await page.goForward({ waitUntil: "domcontentloaded" }).catch(() => null);
    evidence.steps.push({ step: "back_forward", url: page.url() });

    const dupSubmit = await page.evaluate(async (apiUrl) => {
      const id = location.pathname.split("/").pop();
      const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1] ?? "";
      const res = await fetch(`${apiUrl}/api/v1/attempts/${id}/submit`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": decodeURIComponent(csrf) },
      });
      return { status: res.status };
    }, "http://localhost:8000");
    evidence.steps.push({ step: "duplicate_submit", ...dupSubmit });

    // Mobile viewport on same session result page
    await page.setViewportSize({ width: 390, height: 844 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    evidence.steps.push({ step: "mobile_overflow_px", overflow });

    const firewall = evidence.steps.find((s) => s.step === "seed_v2_firewall");
    const first = evidence.steps.find((s) => s.step === "first_question_rendered");
    const submitted = evidence.steps.find((s) => s.step === "submitted_sample");
    evidence.pass =
      practiceJson?.data?.scope_type === "SEED_V2" &&
      practiceJson?.data?.question_count === 100 &&
      firewall?.all_in_allowlist &&
      first?.explanation_heading_count_before_submit === 0 &&
      submitted?.explanation_heading_count_after_submit > 0 &&
      dupSubmit.status === 409 &&
      evidence.steps.some((s) => s.step === "cta_visibility" && s.practice_now && s.seed_v1);
  } catch (err) {
    evidence.failure = String(err);
    evidence.final_url = page.url();
    evidence.pass = false;
  }

  writeEvidence(evidence);
  console.log(JSON.stringify({ pass: evidence.pass, out: OUT, failure: evidence.failure || null }, null, 2));
  await browser.close();
  await apiCtx.dispose();
  process.exit(evidence.pass ? 0 : 1);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
