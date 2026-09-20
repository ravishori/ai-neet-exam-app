const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  const failed = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("response", (r) => {
    if (r.url().includes("/api/v1/auth/login") || r.url().includes("/api/v1/auth/register")) {
      failed.push(`${r.status()} ${r.url()}`);
    }
  });

  await page.goto("http://127.0.0.1:3001/login", { waitUntil: "domcontentloaded", timeout: 60000 });
  const email = `pw-login-${Date.now()}@example.com`;
  const password = "PracticeTest!234";

  // Register via API with same cookie jar so CSRF aligns if needed
  const reg = await context.request.post("http://127.0.0.1:8000/api/v1/auth/register", {
    data: { email, password, first_name: "Pw", last_name: "Login" },
  });
  console.log("register", reg.status());

  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();

  try {
    await page.waitForURL(/\/student\/dashboard/, { timeout: 45000 });
  } catch (e) {
    console.log("url_after_click", page.url());
    console.log("body_snip", (await page.locator("body").innerText()).slice(0, 500));
    console.log("auth_responses", failed);
    console.log("pageErrors", errors.slice(0, 10));
    await browser.close();
    process.exit(1);
  }

  const html = await page.content();
  console.log("url", page.url());
  console.log("has5611Error", html.includes("Cannot find module"));
  console.log("pageErrors", errors.filter((e) => !e.includes("favicon")).slice(0, 8));
  await browser.close();
  if (!page.url().includes("/student/dashboard") || html.includes("Cannot find module")) process.exit(1);
  console.log("LOGIN_BROWSER_OK");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
