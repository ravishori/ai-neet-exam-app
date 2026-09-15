# FRONTEND-A12 — Hydration and runtime hard gate

**Verdict: GREEN** (2026-09-14)

## Exact root cause

`QuickLaunchHub` is **not** the hydration source. Live SSR HTML and client DOM match for all seven `hover-lift surface-glass` links (href + className). The hub has no theme hooks, browser APIs, or generated ids.

Historical Next.js overlays that named `quick-launch-hub.tsx` were **misattribution**. The premium UI audit already recorded the real class of bug: Base UI `DropdownMenuTrigger` `id` values (`base-ui-_R_*`) when menus SSR. That lives in the shell (`AppHeader` / `ThemeToggle` / `StudentBottomNav`).

A6–A9 already defer those menus with `useMounted` so SSR emits **zero** `base-ui-*` ids. A12 locked that baseline with probes + regression tests.

## Measured baseline

| Check | Result |
|---|---|
| SSR `base-ui-*` ids on dashboard | `[]` |
| QLH SSR↔client href match | true |
| Hydration console / overlay | none (390/768/1280/1440, light/dark) |
| Vitest focused | 19 passed |
| ESLint (changed files) | pass |
| TypeScript | pre-existing `ecaep-queue-filters.ts` TS2345 only |

## Files changed

- `apps/web/src/components/ds/quick-launch-hub.tsx`
- `apps/web/src/hooks/use-mounted.ts`
- `apps/web/src/components/ds/quick-launch-hub.test.tsx`
- `apps/web/src/components/app-header.hydration.test.tsx`
- `apps/web/src/hooks/use-mounted.test.tsx`
- `apps/web/scripts/a12-hydration-probe.mjs`
- `docs/audits/frontend_a12_hydration_20260914.json` (+ this md)

## Not done (out of scope)

- No commit
- No dashboard redesign / A10–A13
- No unrelated dirty-tree cleanup
- No `next build` / production-start fix for admin named export
