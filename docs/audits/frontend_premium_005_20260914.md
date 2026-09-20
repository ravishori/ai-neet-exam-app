# FRONTEND-PREMIUM-005 — Practice Runner Premium Pass

**Verdict: GREEN** (2026-09-14)

Presentation-only upgrade of the Practice/Mock attempt runner. Assessment semantics unchanged.

## Before (findings)

- Runner: `attempts/[attemptId]/page.tsx` + `QuestionPanel` + `AnswerOption` + `QuestionPalette`
- Hierarchy: session title competed with stem; options adequate but selected state restrained
- Nav: Submit often louder than Next mid-session
- Palette buttons `size-9` (36px) under 44px target
- Timer: Badge-only when timed; absent for untimed practice (correct)
- Tests: only `answer-option.test.tsx` (4); no runner page tests

## After (UX)

1. Stronger session progress (Q current/total + answered %)
2. Stem dominant; quieter metadata via SubjectChip
3. Options: min-h-12, clearer selected letter badge
4. Next primary mid-session; Submit ghost until last question
5. Palette ≥44px; current filled primary
6. Timed remaining timer card (semantics unchanged); no timer invented for practice
7. Loading skeleton polish

## Files

- `apps/web/src/app/student/attempts/[attemptId]/page.tsx`
- `apps/web/src/app/student/attempts/[attemptId]/practice-runner.test.tsx`
- `apps/web/src/components/question-panel.tsx`
- `apps/web/src/components/question-palette.tsx`
- `apps/web/src/components/question-palette.test.tsx`
- `apps/web/src/components/ds/answer-option.tsx`
- `apps/web/scripts/premium005-runner-live.mjs`
- `docs/audits/frontend_premium_005_20260914.{md,json}`

## Verification

| Gate | Result |
|---|---|
| Existing AnswerOption | 4/4 |
| PREMIUM-005 runner + palette | 7/7 |
| Focused total | 11/11 |
| A12 | 19/19 |
| ESLint | 0 errors (pre-existing img warnings) |
| tsc | 0 |
| build | GREEN |
| Live :3001/:8000 | overflow 0; CTA/options 48; palette 44; no hydration |

No commit/push. Protected assessment systems untouched.
