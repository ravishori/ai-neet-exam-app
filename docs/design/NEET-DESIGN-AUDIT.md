# NEET Design Audit — Phase 0 (read-only)

**Date**: 2026-09-16 · **Branch**: phase2-question-bank · **Scope**: `apps/web`

Prerequisite reading (already in repo): [`docs/design/mobile-first-design-system.md`](./mobile-first-design-system.md).

This audit is intentionally short. It records what already exists, where the gaps really are, and what the safest migration order looks like. **No code was modified.**

---

## 1. Current architecture

- **App**: Next.js 15 (App Router) + React 19 + TypeScript 5. Route groups: `(auth)` / `(public)` / `admin` / `student` / `api`.
- **Styling**: Tailwind CSS **v4** via `@tailwindcss/postcss` — no `tailwind.config.*` file; the token layer lives inside `src/app/globals.css` (`@theme inline { … }`, 560 lines).
- **Component libraries**: shadcn v4 CLI (`shadcn@^4.16.1`), Base UI (`@base-ui/react@^1.6.0`), Lucide icons, `next-themes`, `tw-animate-css`.
- **Forms/data**: `react-hook-form`, `zod@^4`, `@tanstack/react-query@^5.101`, KaTeX + `rehype-katex`, `rehype-highlight`.
- **Testing**: Vitest (35 files / 125 tests), Playwright with `@axe-core/playwright`, Lighthouse Mobile runner script.
- **Missing tooling**: **no Storybook** (no `.storybook/`, no `stories/`, no `storybook` script). **No Penpot spec** doc.

## 2. Current design system (stronger than the brief presumed)

`src/app/globals.css` already codifies:

| Layer | Where it lives | Notes |
|-------|---------------|-------|
| Semantic colors | `:root { --background … --success/--warning/--destructive/--ring }` in OKLCH; `.dark { … }` override | Full role coverage. |
| Subject identities | `--subject-physics/-chemistry/-biology` + `-from/-to/-muted/-border`; `.subject-gradient-*` utilities | Physics = indigo, Chemistry = amethyst, Biology = emerald. Botany + Zoology fold into biology via `src/components/ds/subject-theme.ts`. |
| AI accents | `--ai-from` (cyan) → `--ai-to` (violet); `.ai-gradient` | Used by Study Coach chrome + readiness. |
| Surface levels | `.page-atmosphere/.surface-l0` · `.surface-l1` · `.surface-glass/.surface-l2` · `.surface-l3` | L0 wash, L1 work, L2 elevated chrome, L3 inset. |
| Elevation | `--elevation-xs … xl` (5 steps) | Dark-mode variant present. |
| Radius | `--radius-sm/md/lg/xl/2xl/3xl/4xl` derived from `--radius: 0.75rem` | Explicit guidance: controls md/lg, cards xl/2xl, pills full. |
| Motion | `--motion-fast/normal/slow`, `--motion-ease-out`, `.hover-lift`, `.animate-fade-*`, `.exam-mode` toggle | Every motion utility is gated by `prefers-reduced-motion` **and** by `--exam-motion` (exam mode kills lift/blur). |
| Typography | `.text-display/h1/h2/h3/body/small/caption/meta/question`; heading font `--font-plus-jakarta`; mono `--font-geist-mono` | `text-question` enforces `--prose-measure: 42rem`. |
| Layout tokens | `--content-max: 72rem`, `--touch-target-min: 2.75rem`, `--practice-sticky-offset`, `--prose-measure` | A11y-first touch minimums. |

**Custom DS layer** — `src/components/ds/`:
`SurfaceCard`, `StatCard`, `MetricPill`, `SubjectChip`, `PageHeader`, `SectionHeader`, `ReadinessGauge`, `StreakHeatmap`, `QuickLaunchHub`, `StudentBottomNav`, `StudentPage`, `AnswerOption`, `SkipToMain`, `ThemeToggle`, plus `student-more-nav.ts` (single-source IA for the More menu).

**shadcn primitives present** — `src/components/ui/`:
Accordion · Alert · Badge · Breadcrumb · Button · Card · Dialog · DropdownMenu · EmptyState · FieldSelect · Input · Label · Pagination · Popover · Separator · Skeleton · Table · Tabs · Textarea · Tooltip.

## 3. Screen inventory (student surfaces)

| Screen | Path | Lines | Primitive uses | Notes |
|--------|------|------:|---------------:|-------|
| Dashboard | `src/app/student/dashboard/page.tsx` | 739 | 65 (`SurfaceCard/StatCard/PageHeader/SubjectChip/…`) | Long single component; three regression tests already in place. |
| Practice config | `src/app/student/practice/page.tsx` | 388 | 23 | Sticky sidebar pattern; a few ad-hoc arbitrary Tailwind values (see §5). |
| Question Runner | `src/app/student/attempts/[attemptId]/page.tsx` | 666 | uses `QuestionPanel` + `AnswerOption` | Correctness signalled by icon + colour + `aria-pressed`/`aria-invalid` (not colour-only). |
| Mock tests | `src/app/student/mock-tests/page.tsx` | 118 | list only | Small — full CBT experience lives in the attempt route. |
| Flashcards | `src/app/student/flashcards/page.tsx` | 235 | `FlipCard`, `SurfaceCard` | |
| Study Coach | `src/components/ds/ai-study-coach-shell.tsx` (+ launcher) | — | dialog-based | Existing a11y test suite present. |
| Analytics | `src/app/student/analytics/…` | — | uses `TopicPerformanceBreakdown`, `ScoreTrendChart` | Existing regression tests. |

## 4. What actually needs work

### 4.1 Native `<select>` still used where `FieldSelect` exists
`src/app/student/settings/page.tsx:62` and 8 admin pages (`ai-review`, `content/new`, `content`, `factory-review`, `ingestion`, `knowledge-units`, `users`, `visual-assets`) still use bare `<select>` while a canonical `FieldSelect` (native under the hood, but style-normalised, aria-invalid support) exists at `src/components/ui/field-select.tsx`. Registration already migrated to it in Phase 1. **Action: mechanical replacement — no visual re-design.**

### 4.2 Duplicated / abandoned files
- `src/components/ds/theme-toggle.tsx`, `theme-toggle.committed.tsx`, `theme-toggle.fixed.tsx` — three variants of the same component. `theme-toggle.test.tsx` has an order-dependent flake (passes in isolation both with and without recent auth-diff, fails in the full run). Deduplicate before writing stories.
- `dashboard/` has three `*.test.tsx` files (`dashboard-errors`, `hero-clarity`, `practice-now-hero`) targeting a 739-line page. Split candidates surface naturally.

### 4.3 Ad-hoc arbitrary values inside student surfaces
Scan hits in dashboard/practice:
```
dashboard/page.tsx:132   max-w-[9rem] text-[0.7rem]
dashboard/page.tsx:282   text-[0.7rem]
dashboard/page.tsx:429   max-w-[12rem] text-xs
dashboard/page.tsx:521   text-[0.65rem] tracking-[0.12em]
dashboard/page.tsx:709   min-h-[10rem]
practice/page.tsx:89     max-w-[9rem] text-[0.7rem]
```
All are near-duplicates of `text-caption`/`text-meta` and existing spacing tokens. **Action: replace with the utility classes already defined in `globals.css` — pure token adoption, no design change.**

### 4.4 Primitives the brief expects but repo lacks
Not present today; each is a small addition, not a redesign:

| Primitive | Why | Nearest existing |
|-----------|-----|------------------|
| `Toast` | Success/error announcements in flows (register, change-password) | none — flows use inline `Alert` today |
| `Combobox` / `Command` | Concept picker + scope search | ad-hoc combobox in `concept-picker.tsx`, `scope-picker.tsx` |
| `Drawer` | Study coach launcher is a `Dialog` — a real bottom-drawer at mobile would fit better | `Dialog` |
| `DataTable` | Admin tables use `<Table>` directly with per-page pagination logic | `Table` |
| `Avatar` | Not currently rendered anywhere user-facing | none |
| `IconButton` | Currently everyone uses `Button size="icon"` variants | `Button` |
| `ErrorState` | Fetch failures render inline `Alert`; no shared shell | `EmptyState`, `Alert` |
| `Breadcrumb` a11y wrapper for admin | `Breadcrumb` exists, admin pages don't use it | `Breadcrumb` |

### 4.5 Component sprawl / long files
- Dashboard page: 739 lines in one client component. Splittable into `TodayObjectiveCard`, `SubjectProgressCard`, `MockReadinessCard`, `WeakAreasCard`, `RecommendedNextCard`, `StreakCard` — no visual redesign required for the split, just isolation for testing and Storybook stories.
- Question Runner: 666 lines. Boundary: keep `QuestionPanel`, `AnswerOption`, `QuestionPalette` outside; extract `AttemptToolbar` + `AttemptSummaryDrawer` as siblings.

### 4.6 A11y / responsive spot-checks (from source)
- `AnswerOption` (`components/ds/answer-option.tsx`): `touch-target`, `min-h-12`, `aria-pressed`, `aria-invalid`, focus-visible ring — solid baseline.
- `--touch-target-min: 2.75rem` (~44px) is applied via `.touch-target` utility.
- `Question` stems capped at `--prose-measure: 42rem` — protect this in any redesign.
- Motion utilities gated by `prefers-reduced-motion` and `--exam-motion`. Do not bypass.
- Header uses `.surface-glass` + `.backdrop-blur-md` — exam-mode CSS already flattens the blur.

### 4.7 Missing infra vs brief
- **No Storybook** — needs a fresh `storybook@8` setup for Next.js + Tailwind v4. Nontrivial (Tailwind v4 + tw-animate-css + shadcn tokens must load into the preview).
- **No Penpot spec doc** — the token catalogue lives only in CSS today. A Penpot handoff file requires exporting current tokens + component states in a spec-friendly form.

## 5. Recommended migration plan (safe, incremental)

| Phase | Change | Blast radius | Reversibility |
|-------|--------|--------------|---------------|
| **P0 (this doc)** | Audit only | none | — |
| **P1 — token consolidation** | Replace ad-hoc `text-[…]` / `max-w-[…]` in dashboard + practice with existing utilities. Delete `theme-toggle.committed.tsx` + `theme-toggle.fixed.tsx` once the flake is nailed. | Visual byte-identical | High |
| **P2 — missing primitives** | Add `Toast`, `Combobox` (Base UI), `Drawer` (Base UI), `IconButton` (thin wrapper), `ErrorState`, `Avatar`. No screen migrations yet. | New files only | High |
| **P3 — Storybook** | Install `@storybook/nextjs@8`, register Tailwind v4 preview, add stories for **Button, Card, Input, FieldSelect, Badge, Alert, Skeleton, EmptyState, Dialog, Tabs, Progress (new), AnswerOption, SubjectChip, StatCard, MetricPill, ReadinessGauge, AI Study Coach shell, Question stem**. | New dep + preview app | High |
| **P4 — Dashboard split** | Extract 6 dashboard sub-cards into `src/app/student/dashboard/_sections/`. No visual change; passes existing 3 tests. | Contained to dashboard | Medium |
| **P5 — Practice + Runner polish** | Adopt tokens; add Playwright screenshot baselines at 375/768/1280. No stem re-layout unless tests confirm. | Contained | Medium |
| **P6 — Mock Test / CBT** | Timer + palette hardening (existing `question-palette` component already tested). Adopt drawer for mobile palette. | Contained | Medium |
| **P7 — Flashcards** | Front/back hierarchy uses `SurfaceCard` variant; reveal uses reduced-motion-gated animation. | Contained | Medium |
| **P8 — Study Coach** | Confirm existing `role="dialog"` / `aria-modal` / focus containment tests still pass; add subject-aware header strip. | Contained | High |
| **P9 — Penpot spec** | New file `docs/design/PENPOT-DESIGN-SPEC.md` mirroring current tokens/components. | Doc only | High |
| **P10 — QA gate** | typecheck + lint + vitest + Playwright + a11y + responsive at 375/390/768/1024/1280. | — | — |

## 6. Risk areas (do not treat as free work)

1. **Tailwind v4 config-in-CSS**. Any new design token must extend `@theme inline` inside `globals.css`, not a `tailwind.config.js` — the file does not exist by design. A parallel config would silently duplicate the token system.
2. **Question Runner regression surface**. `attempts/[attemptId]/page.tsx` has autosave-debounce and answer-commit paths under test. Refactoring order must land AnswerOption/QuestionPanel changes with the runner in one PR, not split.
3. **Exam mode**. The `.exam-mode` class flattens motion/blur/gradients. Any new animation MUST be gated by `--exam-motion` and `prefers-reduced-motion` — this is a correctness requirement, not a preference.
4. **`text-question` measure**. `--prose-measure: 42rem` must not be weakened. Stems will over-run on wide screens if the containing card ignores it.
5. **Test-order flake in `theme-toggle.test.tsx`**. Passes in isolation. Fixing must precede any theme-toggle refactor otherwise the flake will mask real regressions.
6. **Storybook + Tailwind v4**. Not every Storybook Next.js preset ships with a working Tailwind v4 pipeline as of this writing; expect ~1 day of setup + a documented reproduction if the preview host can't resolve `@tailwindcss/postcss`.
7. **Live workloads competing for attention**: (a) 5,000-MCQ production generation background job `b0svod7jj` is running against OpenAI; do not merge design changes that touch backend routes or CI without confirming with that owner. (b) Uncommitted password-policy diff + Alembic migration `a1b2c3d4e5f7` exists on the working tree — commit before opening a design branch.
8. **Bundle size / performance**. Base UI + shadcn + KaTeX + highlight.js + react-markdown is already a heavy client bundle. Any new primitive should be tree-shakeable; avoid full-icon-set imports (`lucide-react/*` per-icon is fine).
9. **Two long-lived screens** (Dashboard 739 lines, Runner 666 lines) — plan the split before the visual redesign; otherwise regressions get harder to isolate.
10. **`must_change_password=false` regression risk**. New auth path just changed. Do not roll in a "welcome first login" banner into the redesign that assumes the old auto-issued-password flow.

## 7. What this audit does NOT recommend

- Rewriting the token system. It's already comprehensive and OKLCH-native.
- Replacing shadcn or Base UI. Both are current versions and working.
- Introducing a new state manager or CSS-in-JS solution.
- Redesigning admin surfaces in this pass — student surfaces are the ROI target.
- A parallel `tailwind.config.js`. Any new token belongs in `globals.css @theme inline`.

## 8. Next step

Proceed only when the user confirms. Recommended P1 (token consolidation) is <200 LOC of edits with zero visual regression and no new dependencies. It also produces the cleanest baseline for the Storybook install in P3.

— END P0 —
