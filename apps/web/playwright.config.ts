import { defineConfig } from "@playwright/test";

const WEB_BASE = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3001";
const API_BASE = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

/**
 * Representative viewport matrix (not every size runs the full critical path).
 * Full Practice Now E2E runs on: 390×844, 768×1024, 1366×768, 1920×1080.
 * Overflow-only smoke runs on remaining mobile sizes.
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: WEB_BASE,
    storageState: "./e2e/.auth/student.json",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
    extraHTTPHeaders: {},
  },
  projects: [
    {
      name: "mobile-390",
      use: {
        browserName: "chromium",
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: "mobile-360-smoke",
      testMatch: /viewport-smoke\.spec\.ts/,
      use: { browserName: "chromium", viewport: { width: 360, height: 640 }, isMobile: true, hasTouch: true },
    },
    {
      name: "mobile-430-smoke",
      testMatch: /viewport-smoke\.spec\.ts/,
      use: { browserName: "chromium", viewport: { width: 430, height: 932 }, isMobile: true, hasTouch: true },
    },
    {
      name: "tablet-768",
      use: {
        browserName: "chromium",
        viewport: { width: 768, height: 1024 },
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: "laptop-1366",
      use: { browserName: "chromium", viewport: { width: 1366, height: 768 } },
    },
    {
      name: "desktop-1920",
      use: { browserName: "chromium", viewport: { width: 1920, height: 1080 } },
    },
  ],
  metadata: { apiBase: API_BASE },
});
