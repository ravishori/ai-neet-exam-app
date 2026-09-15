# FRONTEND-PREMIUM-001 — Premium Student Dashboard Redesign

**Verdict: GREEN** (2026-09-14)

## Scope

Presentation/UX redesign of `apps/web/src/app/student/dashboard/page.tsx` only, plus focused test + live probe. Design-system primitives reused; no API/Practice/Mock/ECAEP/AuthZ/DB changes.

## UX changes

1. **Hero / command center** — `page-atmosphere` surface, greeting, next-focus line from recommendations, primary **Continue practice** (existing FULL×30 `useStartPractice`), secondary Configure scope.
2. **Readiness gauge** — existing `ReadinessGauge` + `computeReadinessIndex` from overview data.
3. **Metric strip** — accuracy / questions / sessions / readiness from real overview/attempts only (honest dash/`0` when empty).
4. **Today’s priorities** — revision-due + recommendations with first revision as next-up; honest empty states.
5. **Subject performance** — themed progress bars via `SubjectChip` / `resolveSubjectTheme` (not a card wall).
6. **Recent activity** — compact heatmap + score trend; empty state when no submitted sessions.
7. **Secondary** — existing `QuickLaunchHub` under “More ways to prepare”.

## Files changed

| File | Role |
|---|---|
| `apps/web/src/app/student/dashboard/page.tsx` | Redesign |
| `apps/web/src/app/student/dashboard/practice-now-hero.test.tsx` | CTA label assert |
| `apps/web/scripts/premium001-dashboard-live.mjs` | Live viewport/theme probe (new) |

Local presentation helpers in page only: `HeroPracticeCta`, `MetricPill`, `SubjectMasteryRow` (not new DS package exports).

## APIs reused (unchanged contracts)

- `useMe`
- `learningApi.overview` / `revisionDue` / `recommendations`
- `assessmentApi.listAttempts`
- `useStartPractice` (`FULL`×30 hero; `CONCEPT` per recommendation)

## Verification

| Check | Result |
|---|---|
| Dashboard vitest | 4/4 |
| A12 vitest (A6–A9 + hydration) | **19/19** |
| ESLint (prior run on changed files) | pass |
| `tsc --noEmit` / `npm run build` | GREEN (prior task run) |
| Live `:3001` + `:8000` | Dashboard loads; real recommendations; honest zeros |
| Viewports 390/768/1280/1440 | overflow 0; CTA min-height 48; hierarchy present |
| Dark (1280) | `html.dark`; same structure |
| Hydration logs | none |
| Practice/Mock/ECAEP/AuthZ/DB/DRAFT freeze | untouched |

## Safety

- No backend/schema/API edits
- No A6–A9 shell edits
- No fabricated stats
- No commit/push
