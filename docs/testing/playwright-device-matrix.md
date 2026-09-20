# Playwright device matrix

**Config:** `apps/web/playwright.config.ts`  
**Specs:** `apps/web/e2e/practice-now.spec.ts`, `apps/web/e2e/viewport-smoke.spec.ts`  
**Auth:** `apps/web/e2e/global-setup.ts` registers once → `e2e/.auth/student.json` (avoids `/auth/register` 5/min rate limit).

## Commands

```bash
cd apps/web
npx playwright install chromium
# Prefer IPv4 when uvicorn binds 127.0.0.1 only:
set PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001
set PLAYWRIGHT_API_URL=http://127.0.0.1:8000
npm run test:e2e
npm run test:e2e:practice
npm run test:e2e:smoke
```

## Coverage rationale

| Project | Viewport | Specs | Why |
|---------|----------|-------|-----|
| mobile-390 | 390×844 | practice-now + smoke | Primary phone target |
| mobile-360-smoke | 360×640 | smoke only | Small Android |
| mobile-430-smoke | 430×932 | smoke only | Large phone |
| tablet-768 | 768×1024 | practice-now + smoke | Tablet portrait |
| laptop-1366 | 1366×768 | practice-now + smoke | Common laptop |
| desktop-1920 | 1920×1080 | practice-now + smoke | Desktop |

Full critical path is expensive; smaller phones get overflow/smoke + landscape swap.

All projects use **Chromium** (real Safari = real-device procedure).

## Latest evidence (2026-09-02 Phase 2)

**10 passed / 0 failed** on production `next start` (`127.0.0.1:3001`) with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` baked at build time — cookie host must match the browser API origin.

Critical path asserts: CTA POST `/assessments/practice`, attempt UI, option `aria-pressed`, Submit → Score, no horizontal overflow, axe critical/serious empty.

## Known lab caveats

- Stale `next start` without valid `.next` chunks leaves dashboard stuck on “Loading…” (SSR without hydration) — tests now fail fast if `/_next/static` HEAD fails.
- Prefer `127.0.0.1` over `localhost` on Windows when the API is IPv4-only.
