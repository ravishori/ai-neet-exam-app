/**
 * FRONTEND-PREMIUM-003 live acceptance probe (presentation polish).
 */
import { chromium } from "playwright";

const WEB = "http://127.0.0.1:3001";
const API = "http://127.0.0.1:8000";

const browser = await chromium.launch({ headless: true });
const apiCtx = await browser.newContext();
const email = `premium003-${Date.now()}@example.com`;
const password = "PracticeTest!234";
const reg = await apiCtx.request.post(`${API}/api/v1/auth/register`, {
  data: { email, password, first_name: "Polish", last_name: "Dash" },
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
  await page.goto(`${WEB}/student/dashboard`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(2800);
  const data = await page.evaluate(() => {
    const overflow =
      document.documentElement.scrollWidth - document.documentElement.clientWidth;
    const cta = document.querySelector('[data-testid="practice-now-hero"]');
    const hero = document.querySelector("section.page-atmosphere");
    const scope = [...document.querySelectorAll("a")].find((a) =>
      /configure scope/i.test(a.textContent || ""),
    );
    const practiceNowButtons = [...document.querySelectorAll("button")].filter((b) =>
      /^practice now$/i.test((b.textContent || "").trim()),
    );
    const quietPractice = [...document.querySelectorAll("button")].filter((b) =>
      /^practice$/i.test((b.textContent || "").trim()),
    );
    const emailInHero = (() => {
      if (!hero) return false;
      return /email not verified/i.test(hero.textContent || "");
    })();
    const emailOutside = [...document.querySelectorAll('[role="status"]')].some((el) =>
      /email not verified/i.test(el.textContent || ""),
    );
    const notStarted = /not started yet/i.test(document.body.innerText || "");
    const openLinks = [...document.querySelectorAll("a")].filter((a) =>
      /^open$/i.test((a.textContent || "").trim()),
    ).length;
    return {
      overflow,
      heroH: hero ? Math.round(hero.getBoundingClientRect().height) : null,
      ctaMinHeight: cta ? parseFloat(getComputedStyle(cta).minHeight || "0") : null,
      ctaText: cta?.textContent?.trim() || null,
      practiceNowCount: practiceNowButtons.length,
      quietPracticeCount: quietPractice.length,
      scopeClass: scope?.className?.slice(0, 160) || null,
      scopeColor: scope ? getComputedStyle(scope).color : null,
      scopeBg: scope ? getComputedStyle(scope).backgroundColor : null,
      emailInHero,
      emailOutside,
      notStarted,
      openLinks,
      hydration: /hydrat|did not match/i.test(document.body.innerText || ""),
      htmlClass: document.documentElement.className,
      mobileNav: !!document.querySelector("[data-mobile-nav]"),
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
