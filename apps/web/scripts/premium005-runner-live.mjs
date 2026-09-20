/**
 * FRONTEND-PREMIUM-005 — practice runner live probe.
 * Starts a real practice session via API, then measures the runner UI.
 */
import { chromium } from "playwright";

const WEB = "http://127.0.0.1:3001";
const API = "http://127.0.0.1:8000";

const browser = await chromium.launch({ headless: true });
const apiCtx = await browser.newContext();
const email = `premium005-${Date.now()}@example.com`;
const password = "PracticeTest!234";
const reg = await apiCtx.request.post(`${API}/api/v1/auth/register`, {
  data: { email, password, first_name: "Runner", last_name: "Audit" },
});
if (!reg.ok()) throw new Error(`register ${reg.status()} ${await reg.text()}`);

const state0 = await apiCtx.storageState();
const csrf =
  state0.cookies.find((c) => c.name === "csrf_token")?.value ??
  state0.cookies.find((c) => c.name === "talos_csrf")?.value ??
  "";
const csrfHeaders = csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {};

const practice = await apiCtx.request.post(`${API}/api/v1/assessments/practice`, {
  data: { scope_type: "FULL", question_count: 5 },
  headers: csrfHeaders,
});
if (!practice.ok()) throw new Error(`practice ${practice.status()} ${await practice.text()}`);
const practiceBody = await practice.json();
const assessmentId = practiceBody?.data?.id;
if (!assessmentId) throw new Error(`no assessment id: ${JSON.stringify(practiceBody).slice(0, 200)}`);

const start = await apiCtx.request.post(`${API}/api/v1/assessments/${assessmentId}/attempts`, {
  headers: csrfHeaders,
});
if (!start.ok()) throw new Error(`start ${start.status()} ${await start.text()}`);
const startBody = await start.json();
const attemptId = startBody?.data?.id;
if (!attemptId) throw new Error(`no attempt id: ${JSON.stringify(startBody).slice(0, 200)}`);

const state = await apiCtx.storageState();
await apiCtx.close();

const cookies = state.cookies.map((c) => ({
  name: c.name,
  value: c.value,
  url: `${WEB}/`,
  httpOnly: c.httpOnly,
  secure: false,
  sameSite: "Lax",
}));

async function probe(viewport, colorScheme) {
  const ctx = await browser.newContext({ viewport, colorScheme });
  await ctx.addCookies(cookies);
  const page = await ctx.newPage();
  const logs = [];
  page.on("console", (m) => {
    if (m.type() === "error") logs.push(m.text().slice(0, 220));
  });
  page.on("pageerror", (e) => logs.push(String(e).slice(0, 220)));
  await page.goto(`${WEB}/student/attempts/${attemptId}`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(3000);
  const data = await page.evaluate(() => {
    const overflow =
      document.documentElement.scrollWidth - document.documentElement.clientWidth;
    const next =
      document.querySelector('[data-testid="practice-runner-next"]') ||
      document.querySelector('[data-testid="practice-runner-next-mobile"]') ||
      document.querySelector('[data-testid="practice-runner-submit"]') ||
      document.querySelector('[data-testid="practice-runner-submit-mobile"]');
    const option = document.querySelector('[data-state]');
    const paletteBtn = document.querySelector('[aria-label^="Question 1"]');
    return {
      overflow,
      hasRunner: !!document.querySelector('[data-testid="practice-runner"]'),
      hasStem: !!document.querySelector('[data-testid="practice-runner-stem"]'),
      hasProgress: !!document.querySelector('[data-testid="practice-runner-progress"]'),
      progressbar: !!document.querySelector('[role="progressbar"]'),
      nextMinHeight: next ? parseFloat(getComputedStyle(next).minHeight || "0") : null,
      optionMinHeight: option ? parseFloat(getComputedStyle(option).minHeight || "0") : null,
      paletteMinHeight: paletteBtn
        ? parseFloat(getComputedStyle(paletteBtn).minHeight || "0")
        : null,
      hydration: /hydrat|did not match/i.test(document.body.innerText || ""),
      htmlClass: document.documentElement.className,
      url: location.href,
    };
  });
  await ctx.close();
  return {
    viewport: `${viewport.width}x${viewport.height}`,
    colorScheme,
    logs: logs.filter((t) => !/ERR_CONNECTION_REFUSED|favicon/i.test(t)),
    ...data,
  };
}

const results = [];
for (const w of [390, 768, 1280, 1440]) {
  results.push(await probe({ width: w, height: w === 390 ? 844 : 900 }, "light"));
}
results.push(await probe({ width: 1280, height: 800 }, "dark"));
results.push(await probe({ width: 390, height: 844 }, "dark"));

await browser.close();
console.log(JSON.stringify({ email, attemptId, results }, null, 2));
