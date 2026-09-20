/**
 * Seed V2 — full 100-question browser traversal + visual rendering check.
 * Actual browser E2E (not API-only). Writes audit evidence JSON.
 */
const { chromium, request } = require("playwright");
const fs = require("fs");
const path = require("path");

const API = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const ROOT = path.resolve(__dirname, "../../..");
const AUTH = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json");
const OUT = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V2_FULL100_BROWSER_EVIDENCE_20260904.json");
const EXPECTED_SHA = "a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978";
const VISUAL = {
  "physics-05": "9c51f8a1-bf72-4ca0-bcfd-e0aa5cb8ee53",
  "physics-21": "1633f068-f0df-4ff5-ac0c-57be4417f29e",
  "zoology-12": "ca0e7a05-38bb-4e12-a52d-4fd4c7a26b07",
};

function write(evidence) {
  fs.writeFileSync(OUT, JSON.stringify(evidence, null, 2));
}

(async () => {
  const allowlist = JSON.parse(fs.readFileSync(AUTH, "utf8")).exact_allowlist;
  const allowSet = new Set(allowlist);
  const evidence = {
    captured_at: new Date().toISOString(),
    kind: "ACTUAL_BROWSER_E2E",
    web: WEB,
    api: API,
    pass: false,
    visited_count: 0,
    unique_question_count: 0,
    duplicate_question_count: 0,
    outside_allowlist_count: 0,
    failed_render_count: 0,
    failed_submission_count: 0,
    visual: {},
    steps: [],
    console_errors: [],
  };

  const email = `seed-v2-full100-${Date.now()}@example.com`;
  const password = "PracticeTest!234";
  const apiCtx = await request.newContext({ baseURL: API });
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password, first_name: "Full", last_name: "Hundred" },
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
  page.on("console", (msg) => {
    if (msg.type() === "error") evidence.console_errors.push(msg.text());
  });

  try {
    const webHost = WEB.includes("127.0.0.1") ? WEB.replace("127.0.0.1", "localhost") : WEB;
    await page.goto(`${webHost}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 90_000 });
    await page.waitForTimeout(1500);

    const v2Cta = page.locator("main").getByRole("button", { name: /Practice Seed V2/i }).first();
    await v2Cta.waitFor({ state: "visible", timeout: 45_000 });
    const practiceRespPromise = page.waitForResponse(
      (r) => r.url().includes("/api/v1/assessments/practice") && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    await v2Cta.click();
    const practiceResp = await practiceRespPromise;
    const practiceJson = await practiceResp.json();
    evidence.steps.push({
      step: "practice_create",
      status: practiceResp.status(),
      scope_type: practiceJson?.data?.scope_type,
      question_count: practiceJson?.data?.question_count,
      sha: practiceJson?.meta?.seed_v2_allowlist_sha256,
    });
    if (practiceJson?.data?.scope_type !== "SEED_V2" || practiceJson?.data?.question_count !== 100) {
      throw new Error("SEED_V2 100 not created");
    }
    if (practiceJson?.meta?.seed_v2_allowlist_sha256 !== EXPECTED_SHA) {
      throw new Error("SHA mismatch");
    }

    await page.waitForURL(/\/student\/attempts\/[0-9a-f-]+/i, { timeout: 60_000 });
    const attemptId = page.url().split("/").pop();
    evidence.attempt_id = attemptId;

    const attemptDetail = await page.evaluate(async (apiUrl) => {
      const id = location.pathname.split("/").pop();
      const res = await fetch(`${apiUrl}/api/v1/attempts/${id}`, { credentials: "include" });
      const body = await res.json();
      return {
        status: res.status,
        questions: (body.data?.questions || []).map((q) => ({
          id: q.content_item_id,
          stem: (q.stem || "").slice(0, 80),
          diagram_svg: Boolean(q.diagram_svg && String(q.diagram_svg).includes("<svg")),
          options: (q.options || []).length,
        })),
      };
    }, "http://localhost:8000");
    if (attemptDetail.questions.length !== 100) {
      throw new Error(`expected 100 questions in attempt, got ${attemptDetail.questions.length}`);
    }

    const visited = [];
    let failedRender = 0;
    let failedSubmit = 0;

    for (let i = 0; i < 100; i++) {
      const expected = attemptDetail.questions[i];
      const label = page.getByText(new RegExp(`Q\\s+${i + 1}\\s+/\\s+100`, "i")).first();
      try {
        await label.waitFor({ state: "visible", timeout: 15_000 });
      } catch {
        failedRender += 1;
        evidence.steps.push({ step: "render_fail", index: i + 1, id: expected.id });
        break;
      }

      const outside = !allowSet.has(expected.id);
      if (outside) evidence.outside_allowlist_count += 1;
      visited.push(expected.id);

      const optionA = page.getByRole("button", { name: /^Option A:/i }).first();
      const optCount = await page.getByRole("button", { name: /^Option [A-D]:/i }).count();
      if (optCount < 4) failedRender += 1;
      try {
        await optionA.click({ timeout: 10_000 });
        await optionA.waitFor({ state: "visible", timeout: 5_000 });
      } catch {
        failedSubmit += 1;
      }

      if (i < 99) {
        const next = page.getByRole("button", { name: /Next/i }).locator("visible=true").first();
        await next.click({ force: true, timeout: 15_000 });
      }
    }

    evidence.visited_count = visited.length;
    evidence.unique_question_count = new Set(visited).size;
    evidence.duplicate_question_count = visited.length - new Set(visited).size;
    evidence.failed_render_count = failedRender;
    evidence.failed_submission_count = failedSubmit;
    evidence.outside_allowlist_count =
      evidence.outside_allowlist_count || visited.filter((id) => !allowSet.has(id)).length;

    // Visual checks via palette jump (desktop grid visible at 1366)
    for (const [slot, vid] of Object.entries(VISUAL)) {
      const idx = attemptDetail.questions.findIndex((q) => q.id === vid);
      const payloadHasSvg = attemptDetail.questions[idx]?.diagram_svg === true;
      if (idx < 0) {
        evidence.visual[slot] = { found: false, visible: false };
        continue;
      }
      const cells = page.getByRole("button", { name: new RegExp(`Question ${idx + 1}(,|$)`) });
      const n = await cells.count();
      let clicked = false;
      for (let c = 0; c < n; c++) {
        if (await cells.nth(c).isVisible()) {
          await cells.nth(c).scrollIntoViewIfNeeded().catch(() => null);
          await cells.nth(c).click({ force: true });
          clicked = true;
          break;
        }
      }
      if (!clicked && n > 0) await cells.first().click({ force: true });
      await page.getByText(new RegExp(`Q\\s+${idx + 1}\\s+/\\s+100`, "i")).first().waitFor({
        state: "visible",
        timeout: 15_000,
      });
      const diagram = page.getByTestId("question-diagram-svg");
      await diagram.waitFor({ state: "visible", timeout: 15_000 }).catch(() => null);
      const visible = await diagram.isVisible().catch(() => false);
      let imgOk = false;
      if (visible) {
        await diagram.locator("img").waitFor({ state: "visible", timeout: 10_000 }).catch(() => null);
        imgOk = await diagram
          .locator("img")
          .evaluate(async (el) => {
            const img = el;
            if (!img.complete) {
              await new Promise((resolve) => {
                img.onload = resolve;
                img.onerror = resolve;
                setTimeout(resolve, 3000);
              });
            }
            return Boolean(img.complete && img.naturalWidth > 0);
          })
          .catch(() => false);
      }
      evidence.visual[slot] = {
        id: vid,
        index: idx + 1,
        found: true,
        payload_has_diagram_svg: payloadHasSvg,
        visible,
        img_natural_ok: imgOk,
      };
    }

    // Mobile visual check on physics-05
    await page.setViewportSize({ width: 390, height: 844 });
    const p5 = evidence.visual["physics-05"];
    if (p5?.index) {
      const cell = page.getByRole("button", { name: new RegExp(`Question ${p5.index}\\b`, "i") }).first();
      if (await cell.count()) await cell.click({ force: true }).catch(() => null);
      await page.waitForTimeout(300);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      evidence.visual.mobile_physics_05 = {
        visible: await page.getByTestId("question-diagram-svg").isVisible().catch(() => false),
        overflow_px: overflow,
      };
    }
    await page.setViewportSize({ width: 1366, height: 768 });

    // Complete attempt submit
    const submitBtn = page.locator("div.hidden.sm\\:flex").getByRole("button", { name: /^Submit$/i });
    const submitRespPromise = page.waitForResponse(
      (r) => r.url().includes("/submit") && r.request().method() === "POST",
      { timeout: 180_000 },
    );
    await submitBtn.click({ force: true, timeout: 30_000 });
    const submitResp = await submitRespPromise;
    const submitJson = await submitResp.json().catch(() => ({}));
    evidence.completion = {
      http: submitResp.status(),
      status: submitJson?.data?.status,
      correct: submitJson?.data?.correct_count,
      incorrect: submitJson?.data?.incorrect_count,
      skipped: submitJson?.data?.skipped_count,
      score: submitJson?.data?.score,
    };
    const sum =
      (submitJson?.data?.correct_count || 0) +
      (submitJson?.data?.incorrect_count || 0) +
      (submitJson?.data?.skipped_count || 0);
    evidence.completion.sum_counts = sum;

    const visualsOk = ["physics-05", "physics-21", "zoology-12"].every(
      (s) => evidence.visual[s]?.visible && evidence.visual[s]?.img_natural_ok,
    );
    evidence.pass =
      evidence.visited_count === 100 &&
      evidence.unique_question_count === 100 &&
      evidence.duplicate_question_count === 0 &&
      evidence.outside_allowlist_count === 0 &&
      evidence.failed_render_count === 0 &&
      evidence.failed_submission_count === 0 &&
      submitResp.ok() &&
      sum === 100 &&
      visualsOk &&
      (evidence.visual.mobile_physics_05?.overflow_px ?? 99) <= 1;
  } catch (err) {
    evidence.failure = String(err);
    evidence.pass = false;
    evidence.final_url = page.url();
  }

  write(evidence);
  console.log(
    JSON.stringify(
      {
        pass: evidence.pass,
        visited: evidence.visited_count,
        unique: evidence.unique_question_count,
        outside: evidence.outside_allowlist_count,
        visual: evidence.visual,
        completion: evidence.completion,
        out: OUT,
        failure: evidence.failure || null,
      },
      null,
      2,
    ),
  );
  await browser.close();
  await apiCtx.dispose();
  process.exit(evidence.pass ? 0 : 1);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
