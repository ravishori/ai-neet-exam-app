# FRONTEND-PREMIUM-004 — Practice Launch Experience

**Verdict: GREEN** (2026-09-14)

Presentation-only upgrade of `/student/practice` into a NEET practice command center.

## UX

1. Hero with dominant **Start practice** (FULL×30 or current scope; same `useStartPractice`).
2. Mode clarity: untimed practice vs timed mock (quiet link to `/student/mock-tests`).
3. Resume strip when `IN_PROGRESS` attempt exists (link only).
4. Scope configure card — existing `ScopePicker`; ghost “Start with this scope”.
5. Suggested concepts from `learningApi.recommendations` — quiet Practice →; honest empty.

## Files

- `apps/web/src/app/student/practice/page.tsx`
- `apps/web/src/app/student/practice/practice-page.test.tsx`
- `apps/web/src/features/assessment/use-start-practice.ts` (`PRACTICE_ARENA_START_TEST_ID` only)
- `apps/web/scripts/premium004-practice-live.mjs`
- `docs/audits/frontend_premium_004_20260914.{md,json}`

## APIs

Unchanged: `useStartPractice` / `generatePractice`+`startAttempt`, `ScopePicker`→`academicApi`, `learningApi.recommendations`, `assessmentApi.listAttempts`.

## Verification

| Check | Result |
|---|---|
| Practice + message tests | 12/12 (7 PREMIUM-004 + 5 message) |
| A12 | 19/19 |
| ESLint | 0 |
| tsc | 0 |
| build | GREEN |
| Live | :3001 + :8000 |

No commit/push.
