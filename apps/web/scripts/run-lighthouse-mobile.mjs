#!/usr/bin/env node
/**
 * Mobile Lighthouse for public auth surfaces.
 * Authenticated dashboard/practice requires a stored session — documented separately.
 *
 * Usage: node scripts/run-lighthouse-mobile.mjs
 * Env: LIGHTHOUSE_BASE_URL (default http://127.0.0.1:3001)
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const lighthouse = (await import("lighthouse")).default;
const chromeLauncher = require("chrome-launcher");

const WEB = process.env.LIGHTHOUSE_BASE_URL ?? process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3001";
const OUT = join(process.cwd(), "lighthouse-reports");
mkdirSync(OUT, { recursive: true });

const targets = [
  { name: "login", url: `${WEB}/login` },
  { name: "register", url: `${WEB}/register` },
];

const results = [];
const chrome = await chromeLauncher.launch({
  chromeFlags: ["--headless", "--no-sandbox", "--disable-gpu"],
});

try {
  for (const t of targets) {
    try {
      const report = await lighthouse(t.url, {
        port: chrome.port,
        output: ["json", "html"],
        onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
        formFactor: "mobile",
        screenEmulation: { mobile: true, width: 390, height: 844, deviceScaleFactor: 2.625, disabled: false },
        throttlingMethod: "simulate",
      });
      if (!report?.lhr) {
        results.push({ name: t.name, url: t.url, status: "FAIL", error: "No LHR returned" });
        continue;
      }
      const lhr = report.lhr;
      const scores = {
        performance: lhr.categories.performance?.score,
        accessibility: lhr.categories.accessibility?.score,
        bestPractices: lhr.categories["best-practices"]?.score,
        seo: lhr.categories.seo?.score,
      };
      writeFileSync(join(OUT, `${t.name}.report.json`), report.report[0]);
      writeFileSync(join(OUT, `${t.name}.report.html`), report.report[1]);
      results.push({
        name: t.name,
        url: t.url,
        status: "MEASURED",
        scores,
        fetchTime: lhr.fetchTime,
        runtimeError: lhr.runtimeError ?? null,
      });
    } catch (err) {
      results.push({ name: t.name, url: t.url, status: "FAIL", error: String(err).slice(0, 1500) });
    }
  }
} finally {
  try {
    await chrome.kill();
  } catch (err) {
    console.warn("chrome.kill warning:", String(err));
  }
}

writeFileSync(join(OUT, "summary.json"), JSON.stringify(results, null, 2));
console.log(JSON.stringify(results, null, 2));

const budget = {
  notes: [
    "Student mobile budget (targets, not gates): Performance ≥0.70, Accessibility ≥0.90, Best Practices ≥0.90",
    "Dashboard/Practice authenticated Lighthouse: BLOCKED without headless cookie injection in this script",
    "Dev-server measurements are indicative; prefer next start for release gating",
  ],
};
writeFileSync(join(OUT, "budget-notes.json"), JSON.stringify(budget, null, 2));
