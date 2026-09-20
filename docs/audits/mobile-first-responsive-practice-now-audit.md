# Mobile-first responsive Practice Now audit

**Date:** 2026-09-02 (Phase 1 + Phase 2)  
**Scope:** Student Practice Now flow + mobile-first responsive shell + Phase-2 hardening  
**Product:** Trinetra AI Learning OS (TALOS)

# Executive Verdict

**YELLOW — PARTIALLY VERIFIED**

| Dimension | Verdict |
|-----------|---------|
| Functionality (Practice Now) | **PASS** — Playwright critical path + API scoring |
| Gate B — 30 legitimate published questions | **BLOCKED** — Phase-D pilot remains DRAFT (0 PUBLISHED); live pool = 11 |
| Responsiveness (Chromium viewports) | **PASS** — Playwright matrix 10/10 |
| Real devices (Android/iPhone/iPad) | **NOT TESTED** |
| Accessibility | **PARTIAL** — axe critical/serious cleared on result UI; full SR pass NOT TESTED |
| Performance (Lighthouse) | See Phase-2 section — measured or documented |
| Build | See Phase-2 Gate F |

Practice Now works. **Cannot declare GREEN** while Gate B (30/30 published + traversed) and real-device verification remain open.

---

## Phase 2 addendum (2026-09-02)

### Gate B — why 11 not 30

Trace: `POST /assessments/practice` → CMS **PUBLISHED** `QUESTION` pool only → request `question_count=30` → shrinks to available published (`meta.shrunk`).

| Source | Count / status |
|--------|----------------|
| All PUBLISHED questions | **11** |
| Pilot `phase-d-30-mcq-authorized-20260825` | **35 DRAFT**, **0 PUBLISHED** |
| ECAEP | DRAFT → IN_REVIEW → APPROVED → PUBLISH (`content.publish`) — auto-publish forbidden |

**30/30 = BLOCKED.** Content integrity preserved; no silent publish.

Evidence: `apps/backend/scripts/verify_practice_scoring.py` → `GATE_B_30.status=BLOCKED`, scoring independent recompute **match=true** for delivered 11.

### Playwright

- Harness under `apps/web/e2e/` with global auth setup
- **10 passed** across mobile 360/390/430, tablet 768, laptop 1366, desktop 1920
- Docs: `docs/testing/playwright-device-matrix.md`

### Accessibility fixes (Phase 2)

- Progressbar `aria-label` on the `role="progressbar"` node
- Account menu trigger `aria-label="Account menu"` (icon-only on small screens)
- Student + attempt error boundaries

### Performance (Lighthouse — production `next start` :3001)

Measured 2026-09-02 via `npm run lighthouse:mobile` (mobile form factor):

| Page | Performance | Accessibility | Best Practices | SEO | Status |
|------|-------------|---------------|----------------|-----|--------|
| `/login` | **0.97** | **1.00** | **1.00** | **1.00** | MEASURED |
| `/register` | **0.85** | **1.00** | **1.00** | **1.00** | MEASURED |

Authenticated Dashboard/Practice Lighthouse: **BLOCKED** (script has no cookie injection for headless Chrome).  
Artifacts: `apps/web/lighthouse-reports/*.report.json` (gitignored).

### Build (Gate F)

`cd apps/web && npm run build` — **PASS** when `.next` is clean and no concurrent `next dev/start` shares the folder.  
Concurrent build while `next` is running can produce `Cannot find module './NNNN.js'` prerender flakes — environmental, not Phase-2 type regressions. Prior `asChild` type errors fixed in Phase 2.

---

## 1. Repository Architecture

```
apps/web (Next.js 15 + React 19 + Tailwind 4 + shadcn/base-ui + TanStack Query)
  → /student/dashboard  Practice Now CTA
  → /student/practice   Scope + start
  → /student/attempts/[id]  Runner + results
  → apiClient (cookies + CSRF) → http://localhost:8000

apps/backend (FastAPI + SQLAlchemy async + PostgreSQL)
  → POST /api/v1/assessments/practice
  → POST /api/v1/assessments/{id}/attempts
  → GET  /api/v1/attempts/{id}
  → POST /api/v1/attempts/{id}/answers
  → POST /api/v1/attempts/{id}/submit

cms.content_items (status=PUBLISHED only) → assessment pool
```

One codebase. No separate mobile/tablet apps.

## 2. Practice Now Root Cause

Observed failure mode for “button does nothing”:

1. **Primary UX gap:** Dashboard hero had **no** primary Practice Now CTA. The only “Practice now” labels were small concept-row buttons; Quick Launch “Practice” only navigated to a configure page.
2. **Loading feedback too weak:** While the mutation ran, feedback was easy to miss (`Starting…` on a small outline button). On slower first requests this looked like a dead click.
3. **Inventory constraint (data, not UI):** Live DB had **11 PUBLISHED** questions; Phase-D **30-question pilot remains DRAFT** → cannot deliver a true 30-question validation session from production pool.
4. **Blank attempt error path:** `if (!attempt || !question) return null` produced an empty screen on load/error.

**Not root causes (verified):** missing click handler; wrong route; API stubs; overlay permanently blocking buttons; Base UI `onClick` broken.

Live reproduction (2026-09-02):

- Concept “Practice now” → attempt runner (4 Q Ohm’s Law) — **TESTED**
- Hero “Practice now” → attempt with progress bar (11 Q FULL, requested 30, shrunk) — **TESTED**
- API e2e generate → answer all → submit → score — **TESTED** (`scripts/verify_practice_now_e2e.py`)

## 3. Practice Now Fix

| Change | File |
|--------|------|
| Shared `useStartPractice` (generate → start → navigate) with clear messages | `apps/web/src/features/assessment/use-start-practice.ts` |
| Hero **Practice now** CTA + retry + aria-live loading | `apps/web/src/app/student/dashboard/page.tsx` |
| Practice arena uses same starter; requests up to 30 (shrinks honestly) | `apps/web/src/app/student/practice/page.tsx` |
| Attempt loading / error / empty states; progress bar; sticky mobile controls | `apps/web/src/app/student/attempts/[attemptId]/page.tsx` |
| Larger option hit targets + `aria-pressed` / `aria-label` | `apps/web/src/components/question-panel.tsx` |
| API verification script | `apps/backend/scripts/verify_practice_now_e2e.py` |

## 4. Responsive Architecture

- Tailwind breakpoints (`sm`/`lg`) retained — no competing system.
- Mobile bottom nav (`StudentBottomNav`) for primary student routes.
- Safe-area padding on sticky chrome.
- Study Coach FAB raised on small screens so it does not cover sticky practice controls.
- Design tokens extended in `globals.css` (`--touch-target-min`, etc.).

## 5. Mobile Implementation

IMPLEMENTED:

- Bottom navigation
- Sticky Prev/Next/Submit on attempt runner
- Larger Practice Now / option touch targets
- Progress indicator on practice header
- `pb-24` on dashboard/practice to clear bottom nav

TESTED: browser automation against live app (layout evidence captured).  
Real Android Chrome / iOS Safari: **NOT TESTED**.

## 6. Tablet Implementation

IMPLEMENTED via existing `lg` two-column attempt layout + bottom nav hidden at `lg`.  
Real iPad / Android tablet: **NOT TESTED**.

## 7. Laptop/Desktop Implementation

IMPLEMENTED: header link row, sticky question palette sidebar, hero CTA.  
TESTED in desktop browser automation.

## 8. Accessibility

IMPLEMENTED: loading `aria-busy` / `aria-live`, option `aria-pressed` + labels, progressbar named semantics, account menu label, focus rings retained.  
Phase 2: axe-core on Practice result UI (Chromium matrix) — **critical/serious = 0**.  
Full keyboard + screen-reader lab pass: **NOT TESTED**.

## 9. Performance

Lighthouse script: `npm run lighthouse:mobile` → `apps/web/lighthouse-reports/`.  
Authenticated dashboard/practice Lighthouse without cookie injection: **BLOCKED** in script (public login/register measured when server healthy).  
Budget notes written beside reports — green score is not the sole quality metric.

## 10. Automated Tests

| Suite | Result |
|-------|--------|
| `npm test -- src/features/assessment/use-start-practice.test.ts` | PASS (Phase 1) |
| `python scripts/verify_practice_now_e2e.py` | PASS (Phase 1) |
| `python scripts/verify_practice_scoring.py` | PASS (score match; Gate B BLOCKED) |
| Playwright matrix (`npm run test:e2e`) | **10 passed** (Phase 2) |

## 11. Device Test Matrix

See `docs/testing/device-compatibility-matrix.md` and `docs/testing/playwright-device-matrix.md`.  
Chromium viewports: **PASS**. Physical devices: **NOT TESTED**.

## 12. Known Failures

None observed for the critical path when backend + DB are up and PUBLISHED inventory &gt; 0.

## 13. Known Limitations

- Phase-D 30 MCQ pilot still **DRAFT** → cannot verify true 30/30 without ECAEP publish.
- Practice defaults request 30; pool shrinks to available published count (meta.shrunk).
- Physical device lab unavailable in this environment.
- Host `:3000` process can serve stale `.next` (SSR without JS) — use a healthy `next dev`/`next start` on a free port.

## 14. Files Changed

### Phase 1 (preserved)
- `apps/web/src/features/assessment/use-start-practice.ts` (+ tests)
- Dashboard / practice / attempt runner / question panel / bottom nav / globals

### Phase 2
- `apps/web/e2e/**`, `apps/web/playwright.config.ts`
- `apps/web/scripts/run-lighthouse-mobile.mjs`
- `apps/web/src/app/student/error.tsx`, `attempts/[attemptId]/error.tsx`
- `apps/web/src/components/app-header.tsx` (account menu a11y)
- `apps/web/src/app/student/attempts/[attemptId]/page.tsx` (progressbar name)
- Admin `asChild` / Suspense build fixes (login + content pages)
- `apps/backend/scripts/verify_practice_scoring.py`
- Docs under `docs/audits/`, `docs/testing/`, `docs/design/`

## 15. Database Changes

**None.** No migrations. No production MCQ content mutations. No Phase-D publish.

## 16. API Changes

**None.** Existing assessment endpoints reused.

## 17. Verification Commands

```bash
# Frontend unit
cd apps/web && npm test -- src/features/assessment/use-start-practice.test.ts

# Scoring + Gate B evidence
cd apps/backend && .venv/Scripts/python.exe scripts/verify_practice_scoring.py

# Playwright (IPv4 recommended on Windows)
cd apps/web
set PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001
set PLAYWRIGHT_API_URL=http://127.0.0.1:8000
npm run test:e2e

# Lighthouse (public pages)
set LIGHTHOUSE_BASE_URL=http://127.0.0.1:3001
npm run lighthouse:mobile
```

## 18. Evidence

- API scoring: delivered **11/30** (shrunk), independent score **match**, Gate B **BLOCKED**
- Playwright: **10/10** including axe on result UI
- Published inventory: **11 PUBLISHED**; Phase-D pilot **DRAFT**

## 19. Remaining Work (before GREEN)

1. Publish validated Phase-D set via ECAEP — then traverse true 30/30.
2. Real-device lab: Android Chrome, iOS Safari, iPad (procedure ready).
3. Authenticated mobile Lighthouse on dashboard + practice.
4. Manual keyboard/SR audit of practice runner.
5. Stable production `next build` + `next start` on release host (document any residual prerender flakes).
