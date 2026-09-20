# TALOS Production Seed V2 — Practice E2E Remediation

**Date:** 2026-09-04  
**Base commit (pre-remediation):** `96a4628`  
**Verdict:** **GREEN** (three AMBER gaps closed)

V2 Publication Authorization remains CLOSED. Published cohort was not modified. V1 practice was not modified. No Gemini / generation / 1k work.

## Original AMBER findings

1. Stored `diagram_svg` / `visual_spec` not rendered in student UI  
2. Browser did not traverse all 100 questions  
3. Logout/login was API-only, not browser UI

## Gap 1 — Visual rendering root cause

V2 visual questions store SVG on `cms.content_versions.body.diagram_svg`.  
Attempt API `_question_meta` only populated `images` from knowledge-unit `visual_assets`.  
Frontend `QuestionPanel` only rendered `question.images`.

**Fix (presentation plumbing only):**

- Backend: expose `diagram_svg` on in-progress and submitted attempt question payloads (`assessment_router.py`)  
- Frontend: render `diagram_svg` as a data-URI `<img>` with `data-testid="question-diagram-svg"` (`question-panel.tsx` + `api.ts` type)

No stem/options/answer/explanation/visual_spec/NCERT/publication changes.

### Visual verification (actual browser)

| Slot | ID | Visible | img natural |
| --- | --- | --- | --- |
| physics-05 | `9c51f8a1-…ee53` | YES | YES |
| physics-21 | `1633f068-…f29e` | YES | YES |
| zoology-12 | `ca0e7a05-…6b07` | YES | YES |

Mobile 390×844: physics-05 visible, overflow_px = 0.  
SVG is **not** claimed as NCERT evidence.

## Gap 2 — Full 100 browser traversal

Script: `apps/web/e2e/seed-v2-full100-browser-audit.cjs`  
Evidence: `docs/audits/TALOS_PRODUCTION_SEED_V2_FULL100_BROWSER_EVIDENCE_20260904.json`

| Metric | Result |
| --- | --- |
| visited_count | 100 |
| unique_question_count | 100 |
| duplicate_question_count | 0 |
| outside_allowlist_count | 0 |
| failed_render_count | 0 |
| failed_submission_count | 0 |
| completion | SUBMITTED; correct+incorrect+skipped = 100 |

## Gap 3 — Browser logout / login

Script: `apps/web/e2e/seed-v2-logout-login-browser-audit.cjs`  
Evidence: `docs/audits/TALOS_PRODUCTION_SEED_V2_LOGOUT_LOGIN_BROWSER_EVIDENCE_20260904.json`

Observed product behavior:

- UI **Sign out** → `/login`; `/auth/me` → 401  
- Prior attempt URL redirects to login (`?next=…`) while unauthenticated  
- Browser login form succeeds; same user can resume IN_PROGRESS SEED_V2 attempt (100 Q)  
- New Practice Seed V2 creates a **different** assessment (no contamination)  
- Hero Practice now + Practice Seed V1 CTAs remain visible

## V1 regression

- Pytest: `test_seed_v1_practice_isolation` + `test_seed_v2_practice_isolation` → **12 passed** (includes new `diagram_svg` surface test)  
- Playwright `seed-v2-practice.spec.ts` mobile-390 + laptop-1366 → **2 passed**  
- Hero Practice now / SEED_V1 / 30-ID allowlist unchanged in code paths exercised

## Database integrity (post-remediation)

- V2 published = 100; subjects 35/35/15/15  
- SHA `a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978`  
- deleted = 0; superseded = 0  
- V1 published = 30  
- Visual SVG lengths retained on the three slots  
- No publication/content/NCERT mutation; Gemini calls = 0

## Tests

| Suite | Result |
| --- | --- |
| pytest V1+V2 isolation | 12 passed |
| Playwright seed-v2-practice | 2 passed |
| Full-100 browser audit | pass: true |
| Logout/login browser audit | pass: true |

## Limitations

- Full-100 answers used deterministic Option A for every item (valid per product save-answer contract); score 29/71 reflects that, not content quality.  
- Overall “V2 Practice gate CLOSED” is a separate product decision; this remediation only closes the three E2E AMBER gaps.

## Artifacts

- `docs/audits/TALOS_PRODUCTION_SEED_V2_PRACTICE_E2E_REMEDIATION_20260904.md`  
- `docs/audits/TALOS_PRODUCTION_SEED_V2_PRACTICE_E2E_REMEDIATION_20260904.json`  
- `docs/audits/TALOS_PRODUCTION_SEED_V2_FULL100_BROWSER_EVIDENCE_20260904.json`  
- `docs/audits/TALOS_PRODUCTION_SEED_V2_LOGOUT_LOGIN_BROWSER_EVIDENCE_20260904.json`

STOP. Do not start 1,000-question generation.
