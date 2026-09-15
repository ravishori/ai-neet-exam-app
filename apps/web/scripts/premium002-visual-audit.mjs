/**
 * FRONTEND-PREMIUM-002 — review-only visual/UX acceptance probe.
 * Authenticates against real backend; does not seed stats.
 */
import { chromium } from "playwright";

const WEB = process.env.PREMIUM_WEB || "http://127.0.0.1:3001";
const API = process.env.PREMIUM_API || "http://127.0.0.1:8000";

const browser = await chromium.launch({ headless: true });
const apiCtx = await browser.newContext();
const email = `premium002-${Date.now()}@example.com`;
const password = "PracticeTest!234";
const reg = await apiCtx.request.post(`${API}/api/v1/auth/register`, {
  data: { email, password, first_name: "Audit", last_name: "Viewer" },
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

async function audit(viewport, colorScheme) {
  const ctx = await browser.newContext({ viewport, colorScheme });
  await ctx.addCookies(cookies);
  const page = await ctx.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  const failedNet = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text().slice(0, 240));
  });
  page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 240)));
  page.on("response", (r) => {
    if (r.status() >= 400 && r.url().includes("/_next/")) {
      failedNet.push(`${r.status()} ${r.url().slice(0, 120)}`);
    }
  });

  await page.goto(`${WEB}/student/dashboard`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(2800);

  const data = await page.evaluate(() => {
    const overflow =
      document.documentElement.scrollWidth - document.documentElement.clientWidth;
    const cta = document.querySelector('[data-testid="practice-now-hero"]');
    const ctaCs = cta ? getComputedStyle(cta) : null;
    const headings = [...document.querySelectorAll("h1,h2,h3")].map((h) => ({
      tag: h.tagName,
      text: (h.textContent || "").trim().slice(0, 80),
    }));
    const progressbars = [...document.querySelectorAll('[role="progressbar"]')].map(
      (el) => ({
        label: el.getAttribute("aria-label"),
        valuemin: el.getAttribute("aria-valuemin"),
        valuemax: el.getAttribute("aria-valuemax"),
        valuenow: el.getAttribute("aria-valuenow"),
      }),
    );
    const subjectChips = document.querySelectorAll(
      '[class*="subject"], [data-subject]',
    ).length;
    const surfaceCards = document.querySelectorAll(
      '[class*="surface"], [data-slot="card"]',
    ).length;
    // Rough card count via SurfaceCard-ish borders
    const borderedCards = [...document.querySelectorAll("section")].length;
    const mobileNav = document.querySelector("[data-mobile-nav]");
    const mobileNavBottom = mobileNav
      ? Math.round(mobileNav.getBoundingClientRect().top)
      : null;
    const lastSection = [...document.querySelectorAll("main section")].at(-1);
    const lastBottom = lastSection
      ? Math.round(lastSection.getBoundingClientRect().bottom)
      : null;
    const bodyPad = mobileNav
      ? getComputedStyle(document.body).paddingBottom ||
        getComputedStyle(document.querySelector("main") || document.body)
          .paddingBottom
      : null;
    const hero = document.querySelector(".page-atmosphere");
    const heroH = hero ? Math.round(hero.getBoundingClientRect().height) : null;
    const viewportH = window.innerHeight;
    const continuePrimary = cta
      ? getComputedStyle(cta).backgroundColor
      : null;
    const outlineBtns = [...document.querySelectorAll("a,button")].filter((el) =>
      /configure scope|practice now|browse subjects/i.test(el.textContent || ""),
    ).length;
    const emptyTitles = [...document.querySelectorAll("h3,p,h2")]
      .map((el) => (el.textContent || "").trim())
      .filter((t) =>
        /nothing due|no submitted|no mastery|no recommendations|not verified/i.test(
          t,
        ),
      );
    const metricLabels = [...document.querySelectorAll(".page-atmosphere span")]
      .map((s) => (s.textContent || "").trim())
      .filter((t) => /accuracy|questions|sessions|readiness/i.test(t));
    const hasHydrationText = /hydrat|did not match/i.test(
      document.body.innerText || "",
    );
    // Sample contrast-ish: muted vs foreground lightness via computed colors
    const sampleMuted = getComputedStyle(
      document.querySelector(".text-muted-foreground") || document.body,
    ).color;
    const sampleFg = getComputedStyle(document.body).color;
    const htmlClass = document.documentElement.className;
    const focusProbe = (() => {
      if (!cta) return null;
      cta.focus();
      const o = getComputedStyle(cta).outlineStyle;
      const ow = getComputedStyle(cta).outlineWidth;
      const ring = getComputedStyle(cta).boxShadow;
      return { outlineStyle: o, outlineWidth: ow, boxShadow: ring.slice(0, 80) };
    })();

    return {
      overflow,
      heroH,
      viewportH,
      heroViewportRatio: heroH && viewportH ? +(heroH / viewportH).toFixed(2) : null,
      ctaText: cta?.textContent?.trim() || null,
      ctaMinHeight: ctaCs ? parseFloat(ctaCs.minHeight || ctaCs.height) : null,
      ctaFontSize: ctaCs ? ctaCs.fontSize : null,
      ctaFontWeight: ctaCs ? ctaCs.fontWeight : null,
      continuePrimary,
      headings,
      progressbars,
      subjectChipHints: subjectChips,
      sectionCount: borderedCards,
      outlineBtnCount: outlineBtns,
      emptyTitles: [...new Set(emptyTitles)].slice(0, 8),
      metricLabels: [...new Set(metricLabels)],
      mobileNav: !!mobileNav,
      mobileNavTop: mobileNavBottom,
      lastSectionBottom: lastBottom,
      bodyPad,
      hasHydrationText,
      htmlClass,
      sampleMuted,
      sampleFg,
      focusProbe,
      brand: !!document.querySelector('[aria-label="Trinetra home"]'),
      commandCenter: /command center/i.test(document.body.innerText || ""),
      priorities: /today.?s priorit/i.test(document.body.innerText || ""),
      subjects: /subject performance/i.test(document.body.innerText || ""),
      moreWays: /more ways to prepare/i.test(document.body.innerText || ""),
      bodyFont: getComputedStyle(document.body).fontFamily,
    };
  });

  // API data presence via page text (honest empty vs populated)
  const bodySnippet = await page.evaluate(() =>
    (document.body.innerText || "").slice(0, 2500),
  );

  await ctx.close();
  return {
    viewport: `${viewport.width}x${viewport.height}`,
    colorScheme,
    consoleErrors: consoleErrors.filter((t) => !/ERR_CONNECTION_REFUSED/.test(t)),
    pageErrors,
    failedNextAssets: failedNet,
    bodyHints: {
      hasRecommended: /recommended practice|not started yet|due for revision/i.test(
        bodySnippet,
      ),
      hasRevisionEmpty: /nothing due right now/i.test(bodySnippet),
      hasZeroActivity: /0\s*\/\s*28|no submitted sessions/i.test(bodySnippet),
      hasSubjectRows: /physics|chemistry|botany|zoology/i.test(bodySnippet),
    },
    ...data,
  };
}

const matrix = [
  [{ width: 390, height: 844 }, "light"],
  [{ width: 390, height: 844 }, "dark"],
  [{ width: 768, height: 1024 }, "light"],
  [{ width: 1280, height: 800 }, "light"],
  [{ width: 1280, height: 800 }, "dark"],
  [{ width: 1440, height: 900 }, "light"],
];

const results = [];
for (const [vp, scheme] of matrix) {
  results.push(await audit(vp, scheme));
}

await browser.close();
console.log(JSON.stringify({ email, results }, null, 2));
