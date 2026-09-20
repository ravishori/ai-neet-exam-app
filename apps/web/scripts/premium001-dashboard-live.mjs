import { chromium } from "playwright";

const WEB = "http://127.0.0.1:3001";
const API = "http://127.0.0.1:8000";

const browser = await chromium.launch({ headless: true });
const apiCtx = await browser.newContext();
const email = `premium001-${Date.now()}@example.com`;
const password = "PracticeTest!234";
const reg = await apiCtx.request.post(`${API}/api/v1/auth/register`, {
  data: { email, password, first_name: "Premium", last_name: "Dash" },
});
if (!reg.ok()) throw new Error(`register ${reg.status()} ${await reg.text()}`);
const state = await apiCtx.storageState();
await apiCtx.close();

const cookies = [];
for (const c of state.cookies) {
  cookies.push({
    name: c.name,
    value: c.value,
    url: `${WEB}/`,
    httpOnly: c.httpOnly,
    secure: false,
    sameSite: "Lax",
  });
}

async function probe(viewport, colorScheme) {
  const ctx = await browser.newContext({ viewport, colorScheme });
  await ctx.addCookies(cookies);
  const page = await ctx.newPage();
  const logs = [];
  page.on("console", (m) => {
    if (m.type() === "error") logs.push(m.text().slice(0, 300));
  });
  page.on("pageerror", (e) => logs.push(String(e).slice(0, 300)));
  await page.goto(`${WEB}/student/dashboard`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(2500);
  const data = await page.evaluate(() => {
    const overflow =
      document.documentElement.scrollWidth - document.documentElement.clientWidth;
    const cta = document.querySelector('[data-testid="practice-now-hero"]');
    const cs = cta ? getComputedStyle(cta) : null;
    return {
      url: location.href,
      title: document.title,
      overflow,
      htmlClass: document.documentElement.className,
      bodyFont: getComputedStyle(document.body).fontFamily,
      hasContinue: !!cta,
      ctaMinHeight: cs ? parseFloat(cs.minHeight || cs.height) : null,
      hasHydration: /hydrat|did not match/i.test(document.body.innerText || ""),
      heroEyebrow: !!Array.from(document.querySelectorAll("p")).find((p) =>
        /command center/i.test(p.textContent || ""),
      ),
      priorities: !!Array.from(document.querySelectorAll("h2")).find((h) =>
        /priorit/i.test(h.textContent || ""),
      ),
      subjects: !!Array.from(document.querySelectorAll("h2")).find((h) =>
        /subject performance/i.test(h.textContent || ""),
      ),
      mobileNav: !!document.querySelector("[data-mobile-nav]"),
      brand: !!document.querySelector('[aria-label="Trinetra home"]'),
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
  results.push(await probe({ width: w, height: 900 }, "light"));
}
results.push(await probe({ width: 1280, height: 800 }, "dark"));

console.log(JSON.stringify({ email, results }, null, 2));
await browser.close();
