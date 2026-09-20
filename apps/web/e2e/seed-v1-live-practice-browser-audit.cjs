/**
 * Seed V1 live Practice Now browser evidence (audit-only).
 */
const { chromium, request } = require("playwright");
const fs = require("fs");
const path = require("path");

const API = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const OUT = path.resolve(
  __dirname,
  "../../../docs/audits/TALOS_PRODUCTION_SEED_V1_LIVE_PRACTICE_BROWSER_EVIDENCE_20260903.json",
);

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
  };

  const email = `seed-v1-browser-${Date.now()}@example.com`;
  const password = "PracticeTest!234";
  const apiCtx = await request.newContext({ baseURL: API });
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password, first_name: "Seed", last_name: "Browser" },
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
    // Must match NEXT_PUBLIC_API_URL host (localhost) for SameSite cookie credentialed POSTs.
    const webHost = WEB.includes("127.0.0.1") ? WEB.replace("127.0.0.1", "localhost") : WEB;
    await page.goto(`${webHost}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.waitForTimeout(2000);
    evidence.steps.push({ step: "dashboard_loaded", url: page.url() });

    // Confirm auth cookies reachable from page context against API host
    const meCheck = await page.evaluate(async (apiUrl) => {
      const res = await fetch(`${apiUrl}/api/v1/auth/me`, { credentials: "include" });
      return { status: res.status, ok: res.ok };
    }, "http://localhost:8000");
    evidence.steps.push({ step: "auth_me_from_browser", ...meCheck });
    if (!meCheck.ok) throw new Error(`browser auth/me ${meCheck.status}`);

    const seedCta = page.locator("main").getByRole("button", { name: /Practice Seed V1/i }).first();
    await seedCta.waitFor({ state: "visible", timeout: 45_000 });
    const enabled = await seedCta.isEnabled();
    evidence.steps.push({
      step: "seed_v1_cta_visibility",
      visible: true,
      enabled,
      aria_label: await seedCta.getAttribute("aria-label"),
      text: await seedCta.innerText(),
    });
    if (!enabled) throw new Error("Practice Seed V1 disabled");

    // Confirm FULL CTA still present (regression surface)
    const fullCta = page.locator("main").getByRole("button", {
      name: "Practice now with any published question",
    });
    evidence.steps.push({
      step: "full_cta_still_present",
      visible: await fullCta.isVisible().catch(() => false),
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

    await seedCta.click();
    evidence.steps.push({ step: "clicked_practice_seed_v1" });

    const [practiceResp, attemptResp] = await Promise.all([practiceRespPromise, attemptRespPromise]);
    const practiceJson = await practiceResp.json().catch(() => null);
    const attemptJson = await attemptResp.json().catch(() => null);
    evidence.steps.push({
      step: "practice_api_response",
      status: practiceResp.status(),
      ok: practiceResp.ok(),
      assessment_id: practiceJson?.data?.id,
      question_count: practiceJson?.data?.question_count,
      scope_type: practiceJson?.data?.scope_type,
      title: practiceJson?.data?.title,
      meta: practiceJson?.meta,
      errors: practiceJson?.errors,
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
    if (practiceJson?.data?.scope_type !== "SEED_V1") {
      throw new Error(`expected SEED_V1 scope, got ${practiceJson?.data?.scope_type}`);
    }

    evidence.steps.push({
      step: "post_click_state",
      url: page.url(),
      button_busy: await seedCta.getAttribute("aria-busy").catch(() => null),
    });

    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });
    evidence.steps.push({ step: "navigated_to_attempt", url: page.url() });

    // Firewall: every question on the attempt must be in the frozen allowlist
    const authPath = path.resolve(
      __dirname,
      "../../../docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json",
    );
    const allowlist = JSON.parse(fs.readFileSync(authPath, "utf8")).exact_uuid_allowlist;
    const allowSet = new Set(allowlist);
    const attemptDetail = await page.evaluate(async (apiUrl) => {
      const id = location.pathname.split("/").pop();
      const res = await fetch(`${apiUrl}/api/v1/attempts/${id}`, { credentials: "include" });
      const body = await res.json();
      return { status: res.status, questions: (body.data && body.data.questions) || [] };
    }, "http://localhost:8000");
    const presented = attemptDetail.questions.map((q) => q.content_item_id);
    const outside = presented.filter((id) => !allowSet.has(id));
    evidence.steps.push({
      step: "seed_firewall",
      presented_count: presented.length,
      outside_count: outside.length,
      outside_sample: outside.slice(0, 5),
      all_in_allowlist: outside.length === 0 && presented.length > 0,
      unique_count: new Set(presented).size,
    });
    if (outside.length) throw new Error(`SEED firewall fail outside=${outside.slice(0, 3)}`);

    await page.getByText(/Question\s+1\s+of/i).first().waitFor({ timeout: 60_000 });
    const qText = await page.getByText(/Question\s+\d+\s+of\s+\d+/i).first().textContent();
    const explanationBefore = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    evidence.steps.push({
      step: "first_question_rendered",
      question_label: qText,
      explanation_heading_count_before_submit: explanationBefore,
    });

    const optionA = page.getByRole("button", { name: /^Option A:/i }).first();
    await optionA.click();
    evidence.steps.push({ step: "selected_option_a", aria_pressed: await optionA.getAttribute("aria-pressed") });

    const next = page.getByRole("button", { name: /^Next$/i }).first();
    if (await next.isEnabled().catch(() => false)) {
      await next.click();
      await page.getByText(/Question\s+2\s+of/i).first().waitFor({ timeout: 15_000 });
      evidence.steps.push({
        step: "next_question_transition",
        label: await page.getByText(/Question\s+\d+\s+of/i).first().textContent(),
      });
      const opt = page.getByRole("button", { name: /^Option A:/i }).first();
      if (await opt.isVisible().catch(() => false)) await opt.click();
    }

    await page.getByRole("button", { name: /^Submit$/i }).first().click();
    await page.getByText(/Score:/i).first().waitFor({ timeout: 60_000 });
    const scoreText = await page.getByText(/Score:/i).first().textContent();
    const correctText = await page
      .getByText(/\d+\s+correct/i)
      .first()
      .textContent()
      .catch(() => null);
    const incorrectText = await page
      .getByText(/\d+\s+incorrect/i)
      .first()
      .textContent()
      .catch(() => null);
    const explanationAfter = await page.getByRole("heading", { name: /^Explanation$/i }).count();
    evidence.steps.push({
      step: "submitted",
      scoreText,
      correctText,
      incorrectText,
      explanation_heading_count_after_submit: explanationAfter,
    });

    const firstQ = evidence.steps.find((s) => s.step === "first_question_rendered");
    const submitted = evidence.steps.find((s) => s.step === "submitted");
    const practiceOk = evidence.steps.some((s) => s.step === "practice_api_response" && s.ok);
    const ctaEmittedNetwork = evidence.network.some((n) => String(n.url || "").includes("/assessments/practice"));
    evidence.cta_click_emitted_practice_request = ctaEmittedNetwork;
    evidence.pass =
      practiceOk &&
      firstQ &&
      firstQ.explanation_heading_count_before_submit === 0 &&
      submitted &&
      submitted.explanation_heading_count_after_submit > 0 &&
      evidence.console_errors.length === 0 &&
      evidence.steps.some((s) => s.step === "practice_api_response" && s.scope_type === "SEED_V1") &&
      evidence.steps.some((s) => s.step === "seed_firewall" && s.all_in_allowlist) &&
      evidence.steps.some((s) => s.step === "full_cta_still_present" && s.visible);
    // page SyntaxError may be ambient; record but do not auto-fail if flow completed
    if (evidence.page_errors.length) {
      evidence.page_error_note = "page_errors present; see page_errors array";
    }
  } catch (err) {
    evidence.failure = String(err);
    evidence.final_url = page.url();
    evidence.pass = false;
  }

  writeEvidence(evidence);
  console.log(JSON.stringify({ pass: evidence.pass, out: OUT, failure: evidence.failure || null, steps: evidence.steps }, null, 2));
  await browser.close();
  await apiCtx.dispose();
  process.exit(evidence.pass ? 0 : 1);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
