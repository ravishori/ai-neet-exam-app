/**
 * FRONTEND-RUNTIME-004 — production smoke probe (read-only; no app source changes).
 * Target: http://127.0.0.1:3001
 */
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.A14_BASE ?? "http://127.0.0.1:3001";
const API = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const AUTH_STATE = path.join(
  process.cwd(),
  "e2e",
  ".auth",
  "student.json",
);

const ROUTES = [
  "/register",
  "/login",
  "/student/dashboard",
  "/student/practice",
  "/student/subjects",
  "/student/analytics",
  "/student/questions",
  "/student/flashcards",
  "/student/mock-tests",
  "/student/attempts",
];

const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
];

function extractCssHrefs(html) {
  return [...html.matchAll(/href="(\/_next\/static\/css\/[^"]+)"/g)].map(
    (m) => m[1],
  );
}

function extractJsSrcs(html) {
  return [...html.matchAll(/src="(\/_next\/static\/[^"]+\.js[^"]*)"/g)].map(
    (m) => m[1],
  );
}

async function headOk(context, urlPath) {
  const res = await context.request.get(`${BASE}${urlPath}`, {
    maxRedirects: 0,
  });
  return { status: res.status(), ok: res.ok(), url: urlPath };
}

async function checkAssets(context, html) {
  const css = extractCssHrefs(html);
  const js = extractJsSrcs(html);
  const cssResults = [];
  for (const href of css) {
    const r = await context.request.get(`${BASE}${href}`);
    cssResults.push({
      href,
      status: r.status(),
      isDevLayoutPath: href.includes("/css/app/layout.css"),
    });
  }
  const jsResults = [];
  for (const src of [...new Set(js)].slice(0, 12)) {
    const r = await context.request.get(`${BASE}${src}`);
    jsResults.push({ src, status: r.status() });
  }
  return { cssResults, jsResults };
}

async function probeRoute(browser, route, cookies, viewport, colorScheme) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    colorScheme,
    baseURL: BASE,
  });
  if (cookies?.length) await context.addCookies(cookies);

  const logs = [];
  const failed = [];
  const page = await context.newPage();
  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning") {
      logs.push({ type: msg.type(), text: msg.text().slice(0, 500) });
    }
  });
  page.on("pageerror", (err) =>
    logs.push({ type: "pageerror", text: String(err).slice(0, 500) }),
  );
  page.on("requestfailed", (req) => {
    failed.push({
      url: req.url(),
      error: req.failure()?.errorText ?? "failed",
    });
  });

  const nav = await page.goto(`${BASE}${route}`, {
    waitUntil: "domcontentloaded",
    timeout: 45000,
  });
  await page.waitForTimeout(1800);

  const finalUrl = page.url();
  const html = await page.content();
  const assets = await checkAssets(context, html);

  const metrics = await page.evaluate(() => {
    const btn = document.querySelector("[data-slot=button], button");
    const bs = btn ? getComputedStyle(btn) : null;
    return {
      title: document.title,
      bodyFont: getComputedStyle(document.body).fontFamily,
      htmlClass: document.documentElement.className,
      hasHydrationCopy: /hydrat|server rendered HTML|didn.?t match/i.test(
        document.body?.innerText || "",
      ),
      btnRadius: bs?.borderRadius ?? null,
      shellBrand: !!document.querySelector('[aria-label="Trinetra home"]'),
      themeBtn: !!document.querySelector('[aria-label^="Theme"]'),
      accountBtn: !!document.querySelector('[aria-label="Account menu"]'),
      mobileNav: !!document.querySelector("[data-mobile-nav]"),
      desktopNav: !!document.querySelector("[data-desktop-nav]"),
    };
  });

  const hydra = logs.filter((l) =>
    /hydrat|did not match|server rendered|418|423|425/i.test(l.text),
  );
  const apiFails = failed.filter(
    (f) =>
      f.url.includes(":8000") ||
      f.url.includes("/api/") ||
      /ERR_CONNECTION_REFUSED/.test(f.error),
  );
  const staticFails = failed.filter((f) => f.url.includes("/_next/static/"));

  const redirectedToLogin =
    route.startsWith("/student") && /\/login/.test(finalUrl);

  await context.close();

  return {
    route,
    viewport: `${viewport.width}x${viewport.height}`,
    colorScheme,
    httpStatus: nav?.status() ?? null,
    finalUrl,
    redirectedToLogin,
    blockedAuth: redirectedToLogin,
    css: assets.cssResults,
    jsSample: assets.jsResults,
    cssAll200: assets.cssResults.every((c) => c.status === 200),
    jsAll200: assets.jsResults.every((j) => j.status === 200),
    hasDevCssPath: assets.cssResults.some((c) => c.isDevLayoutPath),
    metrics,
    hydrationLogs: hydra,
    consoleErrors: logs.filter(
      (l) =>
        l.type === "error" ||
        l.type === "pageerror" ||
        (l.type === "warning" && /hydrat/i.test(l.text)),
    ),
    staticNetworkFails: staticFails,
    apiNetworkFails: apiFails.slice(0, 8),
    apiFailCount: apiFails.length,
  };
}

async function tryAuthCookies(browser) {
  // Prefer existing Playwright storage if present
  if (fs.existsSync(AUTH_STATE)) {
    try {
      const stored = JSON.parse(fs.readFileSync(AUTH_STATE, "utf8"));
      const cookies = [];
      for (const c of stored.cookies || []) {
        cookies.push({
          name: c.name,
          value: c.value,
          url: `${BASE}/`,
          httpOnly: c.httpOnly ?? false,
          secure: false,
          sameSite: "Lax",
        });
      }
      // Validate cookie still accepted by middleware (page loads dashboard not login)
      const ctx = await browser.newContext({ baseURL: BASE });
      await ctx.addCookies(cookies);
      const page = await ctx.newPage();
      await page.goto(`${BASE}/student/dashboard`, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });
      await page.waitForTimeout(800);
      const ok = !/\/login/.test(page.url());
      await ctx.close();
      if (ok) return { cookies, source: "e2e/.auth/student.json", ok: true };
    } catch {
      /* fall through */
    }
  }

  // Try live register/login against API
  const health = await fetch(`${API}/health`).catch(() => null);
  if (!health || !health.ok) {
    return {
      cookies: [],
      source: null,
      ok: false,
      reason: "backend_unavailable",
    };
  }

  const email = `runtime004-${Date.now()}@example.com`;
  const password = "PracticeTest!234";
  const reg = await fetch(`${API}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      first_name: "Runtime",
      last_name: "Four",
    }),
  });
  if (!reg.ok) {
    return {
      cookies: [],
      source: null,
      ok: false,
      reason: `register_failed_${reg.status}`,
    };
  }
  // Extract Set-Cookie from register if any — use playwright request instead
  const context = await browser.newContext({ baseURL: API });
  const apiPage = await context.newPage();
  const loginRes = await context.request.post(`${API}/api/v1/auth/login`, {
    data: { email, password },
  });
  if (!loginRes.ok()) {
    await context.close();
    return {
      cookies: [],
      source: null,
      ok: false,
      reason: `login_failed_${loginRes.status()}`,
    };
  }
  const state = await context.storageState();
  const cookies = [];
  for (const c of state.cookies) {
    cookies.push({
      name: c.name,
      value: c.value,
      url: `${BASE}/`,
      httpOnly: c.httpOnly,
      secure: false,
      sameSite: "Lax",
    });
  }
  await context.close();
  return { cookies, source: "live_api_register", ok: cookies.length > 0 };
}

const browser = await chromium.launch({ headless: true });
const auth = await tryAuthCookies(browser);

const matrix = [];
// Primary pass: 1280 light for all routes
for (const route of ROUTES) {
  const needsAuth = route.startsWith("/student");
  const cookies = needsAuth && auth.ok ? auth.cookies : [];
  const row = await probeRoute(
    browser,
    route,
    cookies,
    { width: 1280, height: 800 },
    "light",
  );
  if (needsAuth && !auth.ok) {
    row.blockedAuth = true;
    row.blockReason = auth.reason ?? "no_auth";
  }
  matrix.push(row);
}

// Responsive + theme on dashboard (or login if blocked)
const focusRoute =
  auth.ok ? "/student/dashboard" : "/register";
const responsive = [];
for (const vp of VIEWPORTS) {
  responsive.push(
    await probeRoute(
      browser,
      focusRoute,
      auth.ok ? auth.cookies : [],
      vp,
      "light",
    ),
  );
}
const dark = await probeRoute(
  browser,
  focusRoute,
  auth.ok ? auth.cookies : [],
  { width: 1280, height: 800 },
  "dark",
);

// Nav smoke: register -> login link works
const navCtx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  baseURL: BASE,
});
const navPage = await navCtx.newPage();
await navPage.goto(`${BASE}/register`, { waitUntil: "domcontentloaded" });
await navPage.getByRole("link", { name: /Sign in/i }).click();
await navPage.waitForTimeout(1000);
const navToLogin = /\/login/.test(navPage.url());
await navCtx.close();

await browser.close();

const publicRows = matrix.filter((r) => !r.route.startsWith("/student"));
const studentRows = matrix.filter((r) => r.route.startsWith("/student"));

const cssOk =
  matrix.every((r) => !r.hasDevCssPath) &&
  matrix
    .filter((r) => !r.blockedAuth || r.finalUrl.includes(r.route))
    .every((r) => r.cssAll200 !== false);

const report = {
  task: "FRONTEND-RUNTIME-004",
  base: BASE,
  auth,
  matrix,
  responsive,
  dark,
  navRegisterToLogin: navToLogin,
  summary: {
    publicRoutesOk: publicRows.every(
      (r) =>
        r.httpStatus === 200 &&
        r.cssAll200 &&
        r.jsAll200 &&
        !r.hasDevCssPath &&
        r.hydrationLogs.length === 0 &&
        r.staticNetworkFails.length === 0,
    ),
    studentAuthBlocked: !auth.ok,
    studentAccessible: auth.ok
      ? studentRows.every((r) => !r.redirectedToLogin && r.httpStatus === 200)
      : false,
    anyDevCssPath: matrix.some((r) => r.hasDevCssPath),
    anyStatic404: matrix.some(
      (r) =>
        !r.cssAll200 ||
        !r.jsAll200 ||
        r.staticNetworkFails.length > 0,
    ),
    anyHydration: matrix.some((r) => r.hydrationLogs.length > 0 || r.metrics.hasHydrationCopy),
  },
};

const outPath = path.join(
  process.cwd(),
  "..",
  "..",
  "docs",
  "audits",
  "frontend_runtime_004_smoke_20260914.json",
);
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
