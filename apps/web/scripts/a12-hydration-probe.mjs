import { chromium } from "playwright";

const base = process.env.A12_BASE ?? "http://127.0.0.1:3000";
const colorScheme = process.env.A12_COLOR ?? "light";
const width = Number(process.env.A12_WIDTH ?? "1280");

function extractQlhLinks(html) {
  const links = [];
  const re =
    /<a([^>]*class="[^"]*hover-lift surface-glass[^"]*"[^>]*)>([\s\S]*?)<\/a>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    links.push({
      attrs: m[1].trim(),
      href: (m[1].match(/href="([^"]+)"/) || [])[1] ?? null,
      innerStart: m[2].slice(0, 180),
    });
  }
  return links;
}

function extractBaseUiIds(html) {
  const ids = [...html.matchAll(/id="(base-ui-[^"]+)"/g)].map((x) => x[1]);
  return [...new Set(ids)].sort();
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width, height: 900 },
  colorScheme,
});
await context.addCookies([
  { name: "access_token", value: "a12-preview", url: base },
]);

const ssr = await context.request.get(`${base}/student/dashboard?a12ssr=1`, {
  headers: { Cookie: "access_token=a12-preview" },
});
const ssrHtml = await ssr.text();
const ssrQlh = extractQlhLinks(ssrHtml);
const ssrBaseUi = extractBaseUiIds(ssrHtml);

const page = await context.newPage();
const logs = [];

page.on("console", async (msg) => {
  const text = msg.text();
  const type = msg.type();
  if (
    type === "error" ||
    type === "warning" ||
    /hydrat|did not match|server rendered|client properties|Minified React error #418|#423|#425|base-ui/i.test(
      text,
    )
  ) {
    const args = [];
    for (const a of msg.args()) {
      try {
        args.push(await a.jsonValue());
      } catch {
        try {
          args.push(await a.evaluate((v) => String(v)));
        } catch {
          /* ignore */
        }
      }
    }
    logs.push({ type, text: text.slice(0, 2000), args: args.slice(0, 8) });
  }
});
page.on("pageerror", (err) =>
  logs.push({ type: "pageerror", text: String(err).slice(0, 2000) }),
);

await page.goto(`${base}/student/dashboard?a12client=1`, {
  waitUntil: "domcontentloaded",
  timeout: 60000,
});
// Capture immediately after first paint (hydration window)
await page.waitForTimeout(500);

const early = await page.evaluate(() => {
  const html = document.documentElement.outerHTML;
  const qlh = [...document.querySelectorAll("a.hover-lift.surface-glass")].map(
    (a) => ({
      href: a.getAttribute("href"),
      className: a.className,
      outer: a.outerHTML.slice(0, 280),
    }),
  );
  const baseUi = [
    ...new Set(
      [...html.matchAll(/id="(base-ui-[^"]+)"/g)].map((x) => x[1]),
    ),
  ].sort();
  const bodyText = document.body?.innerText ?? "";
  return {
    qlh,
    baseUi,
    hasHydrationCopy: /hydrat|server rendered HTML|didn.?t match/i.test(
      bodyText,
    ),
    htmlClass: document.documentElement.className,
  };
});

await page.waitForTimeout(2500);

const issueBtn = page.locator("button").filter({ hasText: /issue/i }).first();
if ((await issueBtn.count()) > 0) {
  await issueBtn.click({ timeout: 2000 }).catch(() => {});
  await page.waitForTimeout(600);
}

const overlay = await page.evaluate(() => {
  const text = document.body?.innerText ?? "";
  const idx = text.toLowerCase().indexOf("hydrat");
  return {
    hasHydrationCopy: /hydrat|server rendered HTML|didn.?t match/i.test(text),
    snippet:
      idx >= 0
        ? text.slice(Math.max(0, idx - 120), idx + 900)
        : text.includes("QuickLaunch")
          ? text.slice(
              Math.max(0, text.indexOf("QuickLaunch") - 200),
              text.indexOf("QuickLaunch") + 400,
            )
          : null,
    nextPortal: !!document.querySelector("nextjs-portal"),
  };
});

const hydrationLogs = logs.filter((l) =>
  /hydrat|did not match|server rendered|418|423|425/i.test(l.text),
);

console.log(
  JSON.stringify(
    {
      base,
      colorScheme,
      width,
      ssrStatus: ssr.status(),
      ssrQlhCount: ssrQlh.length,
      ssrQlh,
      ssrBaseUi,
      earlyClientQlh: early.qlh,
      earlyClientBaseUi: early.baseUi,
      htmlClass: early.htmlClass,
      qlhHrefMatch:
        ssrQlh.map((l) => l.href).join("|") ===
        early.qlh.map((l) => l.href).join("|"),
      logs: logs.filter((l) => !/ERR_CONNECTION_REFUSED/.test(l.text)),
      hydrationLogs,
      overlay,
    },
    null,
    2,
  ),
);
await browser.close();
