/**
 * FRONTEND-PREMIUM-004 — practice arena live probe.
 */
import { chromium } from "playwright";

const WEB = "http://127.0.0.1:3001";
const API = "http://127.0.0.1:8000";

const browser = await chromium.launch({ headless: true });
const apiCtx = await browser.newContext();
const email = `premium004-${Date.now()}@example.com`;
const password = "PracticeTest!234";
const reg = await apiCtx.request.post(`${API}/api/v1/auth/register`, {
  data: { email, password, first_name: "Practice", last_name: "Arena" },
});
if (!reg.ok()) throw new Error(`register ${reg.status()} ${await reg.text()}`);
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
  await page.goto(`${WEB}/student/practice`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(2800);
  const data = await page.evaluate(() => {
    const overflow =
      document.documentElement.scrollWidth - document.documentElement.clientWidth;
    const cta = document.querySelector('[data-testid="practice-arena-start"]');
    const practiceNow = [...document.querySelectorAll("button")].filter((b) =>
      /^practice now$/i.test((b.textContent || "").trim()),
    ).length;
    const startPractice = [...document.querySelectorAll("button")].filter((b) =>
      /start practice/i.test((b.textContent || "").trim()),
    ).length;
    return {
      overflow,
      ctaMinHeight: cta ? parseFloat(getComputedStyle(cta).minHeight || "0") : null,
      ctaText: cta?.textContent?.trim() || null,
      practiceNow,
      startPractice,
      hasUntimed: /untimed practice/i.test(document.body.innerText || ""),
      hasMock: /timed mock|open mock tests/i.test(document.body.innerText || ""),
      hasScope: !!document.querySelector("#practice-scope-subject"),
      hasSuggestions: /suggested concepts|no suggestions yet/i.test(
        document.body.innerText || "",
      ),
      commandCenter: /practice command center/i.test(document.body.innerText || ""),
      hydration: /hydrat|did not match/i.test(document.body.innerText || ""),
      htmlClass: document.documentElement.className,
      mobileNav: !!document.querySelector("[data-mobile-nav]"),
      h1: document.querySelector("h1")?.textContent?.trim() || null,
    };
  });
  await ctx.close();
  return {
    viewport: `${viewport.width}x${viewport.height}`,
    colorScheme,
    logs: logs.filter((t) => !/ERR_CONNECTION_REFUSED/.test(t)),
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
console.log(JSON.stringify({ email, results }, null, 2));
