/**
 * Seed V1 accessibility smoke: keyboard focus on Seed CTA, no obvious traps.
 * Audit-only.
 */
const { chromium, request } = require("playwright");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const API = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

const ROOT = path.resolve(__dirname, "../../..");
const AUTH = path.join(ROOT, "docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json");
const EXPECTED_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1";
const PASSWORD = "PracticeTest!234";

const OUT_PATH = path.join(ROOT, "docs/audits/_seed_v1_accessibility_smoke_tmp.json");

function allowlistSha(ids) {
  return crypto.createHash("sha256").update(ids.join("\n") + "\n", "utf8").digest("hex");
}

function loadAllowlist() {
  const doc = JSON.parse(fs.readFileSync(AUTH, "utf8"));
  const ids = doc.exact_uuid_allowlist;
  return { ids, set: new Set(ids), sha: allowlistSha(ids), embedded: doc.allowlist_sha256 };
}

function csrfFromCookies(cookies) {
  const c = cookies.find((x) => x.name === "csrf_token");
  return c ? decodeURIComponent(c.value) : "";
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

async function registerStudent(apiCtx, tag) {
  const email = `sx-reg-a11y-${tag}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}@example.com`;
  const reg = await apiCtx.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD, first_name: "SX", last_name: tag },
  });
  if (!reg.ok()) throw new Error(`register failed ${reg.status()} ${await reg.text()}`);
  return email;
}

(async () => {
  const allow = loadAllowlist();
  const results = { audit: "Seed V1 accessibility smoke (tmp)", date: "2026-09-03", allow_sha: allow.sha, pass: false, errors: [] };

  const apiCtx = await request.newContext({ baseURL: API });
  const email = await registerStudent(apiCtx, "a11y");
  const jar = await apiCtx.storageState();
  results.student_email = email;

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx.addCookies(cookiesForOrigins(jar));
  const page = await ctx.newPage();

  const console_errors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") console_errors.push(msg.text());
  });

  try {
    await page.goto(`${WEB}/student/dashboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1200);
    const seedBtn = page.locator("main").getByRole("button", { name: /Practice Seed V1/i }).first();
    const seedAria = await seedBtn.getAttribute("aria-label").catch(() => null);
    // Smoke: keyboard Tab traversal should eventually reach the Seed CTA.
    // We do not assert exact tab order; we just require it is keyboard reachable.
    let active = null;
    let focusedSeed = false;
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press("Tab").catch(() => null);
      await page.waitForTimeout(120);
      active = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el) return null;
        return {
          tag: el.tagName,
          aria: el.getAttribute("aria-label"),
          text: el.textContent?.slice(0, 120) || null,
        };
      });
      focusedSeed =
        Boolean(active?.aria && /Seed V1/i.test(active.aria)) ||
        Boolean(active?.text && /Seed V1/i.test(active.text));
      if (focusedSeed) break;
    }

    results.accessibility_smoke = {
      seed_aria_label: seedAria,
      active_after_tab: active,
      pass: focusedSeed && console_errors.length === 0,
    };
    results.pass = results.accessibility_smoke.pass;
    results.console_errors_on_dashboard = console_errors;
  } catch (e) {
    results.errors.push(String(e));
  }

  fs.writeFileSync(OUT_PATH, JSON.stringify(results, null, 2), "utf8");
  console.log(JSON.stringify({ out: OUT_PATH, pass: results.pass, errors: results.errors }, null, 2));
  await browser.close();
  await apiCtx.dispose();
  process.exit(results.pass ? 0 : 1);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

