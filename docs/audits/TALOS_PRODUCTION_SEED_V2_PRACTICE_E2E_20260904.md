# TALOS Production Seed V2 — Student Practice E2E

**Date:** 2026-09-04  
**Commit:** `916c157e0c5ff9a064d9050ac6c71e7520dbcc22` (`main`)  
**Verdict:** **AMBER**

V2 Publication Authorization and SEED_V2 implementation verification remain **CLOSED**. This gate is student E2E only. V1 practice was not modified.

This is **not** a claim of full 100-click browser completion.

## Environment

| Item | Value |
| --- | --- |
| Backend | `http://127.0.0.1:8000` `/health` 200 (restarted so `question_count` 100 is live) |
| Frontend | `http://127.0.0.1:3000` 200 |
| DB | `trinetra_db` (read-only on content/publication) |
| Hero Practice now | `/student/dashboard` → `FULL` / 30 |
| Practice Seed V1 | `/student/dashboard` → `SEED_V1` / 30 |
| Practice Seed V2 | `/student/dashboard` → `SEED_V2` / 100 |
| Attempt | `/student/attempts/:id` |

Unrelated dirty files were not committed as part of this gate.

## Exact V2 cohort (DATABASE VERIFICATION)

SHA-256: `a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978`  
Found 100 / missing 0 / extra 0 / deleted 0 / superseded 0  
Physics 35 / Chemistry 35 / Botany 15 / Zoology 15 — all `PUBLISHED`  
Post-E2E cohort body fingerprint unchanged. V1 published still 30. No Gemini. No content/NCERT/publication mutation.

## Session (API)

- Assessment `b05d514b-3ef0-4599-8331-7f75e54dab77`
- Attempt `79be727f-a857-44d7-9503-d512a54d9fc9`
- Scope `SEED_V2`, requested 100, returned 100, available 100
- Outside allowlist: 0
- Score after controlled completion: **99 correct / 1 incorrect / 0 skipped** (marks 99)

Browser session (sampled): assessment `d51fe46d-df96-4130-b1ee-f7c643490560`, attempt `b89ec30a-5f14-4b94-bb58-f0a181ffef3c`.

## Evidence classes

| Kind | Result |
| --- | --- |
| DATABASE VERIFICATION | PASS (pre + post) |
| API student flow (full 100) | PASS |
| ACTUAL BROWSER E2E (CJS sample) | PASS (`seed-v2-live-practice-browser-audit.cjs`) |
| AUTOMATED Playwright | 2 passed (`seed-v2-practice.spec.ts` mobile-390 + laptop-1366) |
| AUTOMATED pytest isolation | 11 passed |

## Student flow

| Step | Result |
| --- | --- |
| Entry Practice Seed V2 | PASS (separate CTA; Hero still FULL) |
| Display stem + A–D | PASS |
| Answer leak before attempt submit | PASS (API + UI Explanation heading 0) |
| Correct / incorrect | PASS (API; browser sample submit) |
| Explanation after submit | PASS |
| Next / progress Q 1/100 → 2/100 | PASS (browser) |
| Scoring | PASS (API 99/1/0) |
| Completion | PASS **API 100/100**; browser sample only |
| Refresh | PASS (same attempt URL) |
| Back/forward | PASS after submit (CJS) |
| Restart | PASS (API new attempt, same allowlist, no explanation leak) |
| Duplicate attempt submit | PASS HTTP 409; no double score |
| Logout/login UI | **NOT BROWSER-TESTED**; other user GET attempt **404** |
| Concurrent | PASS (API second SEED_V2 100) |

## Firewall (session of 100)

V1 / T6-D / T6-F2 / legacy / historical / DRAFT / APPROVED / arbitrary / outside = **0**  
Forged allowlist/SHA ignored. FULL `question_count=100` → **422**. Forged scope `SEED_V2 ` → **422**.

## Visual

Stored `diagram_svg` on physics-05 / physics-21 / zoology-12. All three in SEED_V2 session; answers 200.  
**Student UI does not render `diagram_svg`** (attempt `images` length 0; QuestionPanel only shows KU visual-assets). Layout did not break. SVG is **not** claimed as NCERT evidence.

## Numerical

physics-10/11/20/34 all in session; stored keys used; answers 200.

## V1 regression

Hero Practice now still FULL / 30. Practice Seed V1 still SEED_V1, SHA `c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1`, 30 IDs, **0 V2 IDs**. Code for V1 was not changed in this gate.

## Mobile / accessibility

CJS mobile overflow 0. Playwright mobile-390 + laptop-1366 passed including axe critical/serious empty.

## AMBER reasons (bounded)

1. Diagram SVG stored on three visual slots is not shown in the student attempt UI.
2. Full 100-question browser click-through was not performed (API completed 100).
3. Browser logout/login path not exercised (API isolation 404).

Isolation, scoring, duplicate-submit, V1 integrity, and publication integrity are intact.

## Tests added

- `apps/backend/scripts/run_seed_v2_live_practice_e2e.py`
- `apps/web/e2e/seed-v2-live-practice-browser-audit.cjs`
- `apps/web/e2e/seed-v2-practice.spec.ts`

## Artifacts

- `docs/audits/TALOS_PRODUCTION_SEED_V2_PRACTICE_E2E_20260904.json`
- `docs/audits/TALOS_PRODUCTION_SEED_V2_PRACTICE_E2E_20260904.md`
- `docs/audits/TALOS_PRODUCTION_SEED_V2_LIVE_PRACTICE_BROWSER_EVIDENCE_20260904.json`

**Final gate:** V2 Practice Isolation + Exact Published 100 E2E Verification = **AMBER** (not CLOSED/GREEN).

STOP. Do not start 1,000-question generation.
