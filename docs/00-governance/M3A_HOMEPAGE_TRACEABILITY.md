# M3A Homepage Traceability

**Feature**: Public homepage hero v2.1 — six-capability product-led hero.
**Route**: `/` — `apps/web/src/app/(public)/page.tsx`.
**Owner**: Frontend product.
**Status**: Placeholders shipped. Awaiting Indian-aspirant photography.

This document is the source of truth for what the M3A hero claims,
which existing pages it routes to, and which product surfaces are
intentionally stated as placeholders rather than finished features.

---

## 1. Capabilities and CTA destinations

| # | Capability          | Copy                                                    | Destination (verified route)         | Verification                              |
| - | ------------------- | ------------------------------------------------------- | ------------------------------------ | ----------------------------------------- |
| 1 | Custom Practice     | "Practice exactly what you need."                       | `/student/practice`                  | `apps/web/src/app/student/practice/page.tsx` |
| 2 | Weekly Assessment   | "Know where you stand every week."                      | `/student/weekly-assessments`        | `apps/web/src/app/student/weekly-assessments/page.tsx` |
| 3 | Weak Topic Focus    | "See where your preparation needs attention."           | `/student/analytics`                 | `apps/web/src/app/student/analytics/…` — chapter/topic mastery panels already ship there |
| 4 | Revision            | "Keep important concepts in rotation."                  | `/student/dashboard`                 | `apps/web/src/app/student/dashboard/page.tsx` — surfaces recent chapters + weekly-revision card |
| 5 | NEET Mock           | "Prepare for the exam, not just the questions."         | `/student/mock-tests`                | `apps/web/src/app/student/mock-tests/page.tsx` |
| 6 | Study Coach         | "Get help when you're stuck."                           | `/login` (opens dialog after sign-in) | `apps/web/src/components/ds/ai-study-coach-shell.tsx` — mounted in student layout only |

### Route decisions that deliberately do NOT invent new pages

- No `/student/weak-topics`. Weak-topic surfacing is a lens over existing analytics; the tile routes to `/student/analytics` which already renders topic/chapter mastery breakdowns.
- No `/student/revision`. There is no dedicated revision page; the tile routes to `/student/dashboard`, which shows recent chapters and the weekly-revision recommendation card. A future dedicated revision surface is a separate scope.
- No `/student/bookmarks`. Bookmarks exist as `learning.question_bookmarks` records but there is no dedicated library page — the hero does not claim one.
- No `/student/coach`. `AiStudyCoachShell` is a dialog inside the authenticated student shell. The tile routes public visitors to `/login`; once signed in they can open the Coach launcher on any student page.

---

## 2. Component inventory

All files live under `apps/web/src/app/(public)/_hero/`:

| File                                    | Kind             | Notes |
| --------------------------------------- | ---------------- | ----- |
| `data.ts`                               | shared           | `HERO_CAPABILITIES` — the single source of truth for tile title/copy/href/theme/preview. |
| `HeroCarousel.tsx`                      | client component | Orchestrates state + touch swipe. No auto-advance (see §5). |
| `HeroCapabilityNav.tsx`                 | client component | Tablist. Keyboard: ArrowLeft/Right, Home, End. `role="tab"` + `aria-selected` + `aria-controls`. Every tab uses the `touch-target` utility (>=48 px min height). |
| `HeroCopy.tsx`                          | server component | H1 + subcopy + trust line. Static markup. |
| `HeroVisual.tsx`                        | client component | Thin `<div role="tabpanel">` swapper for the active preview. |
| `previews/preview-shell.tsx`            | server component | Fixed-aspect (`aspect-[4/3]`) subject-themed frame. All previews use the same shell → no layout shift when swapping. |
| `previews/custom-practice-preview.tsx`  | server component | Subject chips + chapter tags + question count. |
| `previews/weekly-assessment-preview.tsx`| server component | Week card + 15/15/30 blueprint + duration/marks. |
| `previews/weak-topic-focus-preview.tsx` | server component | Chapter-level mastery bars sourced from example data. |
| `previews/revision-preview.tsx`         | server component | Subject-themed topic list + "3 today" counter. |
| `previews/mock-exam-preview.tsx`        | server component | 180Q blueprint + palette grid. |
| `previews/study-coach-preview.tsx`      | server component | Question/answer bubbles with `.ai-gradient` accent. |

No new external dependencies. No new animation library. Motion utilities used are those already declared in `apps/web/src/app/globals.css` (`.hover-lift`, `.animate-fade-*`, `.motion-safe/motion-reduce`).

---

## 3. Missing assets and placeholder strategy

Expected future asset paths (see §6 for content policy):

- `public/images/neet/hero/neet-hero-custom-practice.webp`
- `public/images/neet/hero/neet-hero-weekly-assessment.webp`
- `public/images/neet/hero/neet-hero-weak-topic-focus.webp`
- `public/images/neet/hero/neet-hero-revision-queue.webp`
- `public/images/neet/hero/neet-hero-mock-exam.webp`
- `public/images/neet/hero/neet-hero-study-coach.webp`

**None of these files exist today.** The hero renders CSS + SVG UI previews only — no `<img>` tags, no `next/image`, no stock/copyrighted imagery downloaded from anywhere. Every preview container carries `data-preview-placeholder="true"` so a future swap-in can be verified programmatically.

Preview shells use:
- `aspect-[4/3]` on a shared container so eventual `next/image` art can drop into the same box with **zero layout shift**.
- Subject-theme tokens (`--subject-physics/-chemistry/-biology`, `.ai-gradient`) so the placeholder chrome will visually harmonise with the final photography.

The `futureAssetPath` field on each `HeroCapability` records the intended file so the swap-in PR only needs to add the WebP files and flip a single import.

---

## 4. Interaction and accessibility

- Exactly one `<h1>` on the page (verified by the hero test suite).
- Tab-strip is a `role="tablist"` with `role="tab"` children carrying `aria-selected` and `aria-controls`. Panels are `role="tabpanel"` with `aria-labelledby`.
- **Keyboard**: `ArrowRight`, `ArrowLeft`, `Home`, `End`. `Tab` gives one stop into the tablist (roving `tabIndex`) — matches WAI-ARIA authoring practice for tabs.
- **Touch**: swipe left/right on the visual pane changes tabs (40 px threshold). Buttons themselves are `touch-target` + `min-h-12`.
- **Focus visibility**: `focus-visible:ring-2 focus-visible:ring-ring/50` on every interactive control.
- **Reduced motion**: transitions are `motion-safe:` and `motion-reduce:transition-none`. No animation is gated on user motion beyond the pre-existing `.animate-fade-*` utilities the DS already respects.
- **Overflow**: page uses `overflow-hidden` on `<main>` and horizontal padding on all child containers. Tablist scrolls internally with `overflow-x-auto` + `scroll-thin` → no page-level 375 px overflow.

---

## 5. Motion + auto-advance

**Auto-advance is intentionally off.** The task brief allowed a gentle auto-advance; a11y research and hero-carousel telemetry (repeated finding across public studies) consistently show autoplay depresses click-through and disorients keyboard/screen-reader users. Manual selection only. If auto-advance is later re-added, the following rules from the brief must hold:

- pause on hover, focus, and any pointer / touch interaction
- honour `prefers-reduced-motion: reduce`
- interval ≥ 6 seconds
- announce the new active panel via `aria-live="polite"` on the tabpanel container

---

## 6. Truth guard — claims we do NOT make

The hero copy is deliberately narrow. It does **not** claim:

- automatic percentage-weighted exam generation (the assessment engine ships subject-quota allocation and a Weekly Revision recommender; percentage-weighted quiz generation is not part of the current runtime — Task B allocator is a pure module, not yet wired into a generation route)
- spaced-repetition / SRS revision (there is no SRS scheduler; the Revision tile shows "keep in rotation" without any temporal promise)
- a bookmark library (bookmarks are stored but have no dedicated page)
- a dedicated revision page (`/student/revision` does not exist and is not created here)
- a dedicated Study Coach route (`/student/coach` does not exist and is not created here)
- fully automated deep weak-topic analytics (analytics render chapter-level mastery from existing attempts; no additional model is claimed)

---

## 7. Analytics status

No client-side event-tracking abstraction exists in `apps/web` at the time of writing (`grep -rE "trackEvent|analytics|logEvent"` returns only admin/student **analytics dashboard** pages, not an event bus). The four event names from the task brief (`home_hero_view`, `home_hero_capability_select`, `home_hero_cta_click`, `home_hero_swipe`) are **not** wired — the task explicitly permits omitting them until an abstraction lands.

When such an abstraction lands, the natural mount points inside this component tree are:
- `home_hero_view` — top of `HeroCarousel` on first render (client `useEffect`).
- `home_hero_capability_select` — inside `HeroCapabilityNav`'s `onSelect`.
- `home_hero_cta_click` — the primary CTA `Link` inside `HeroCarousel`.
- `home_hero_swipe` — the `onTouchEnd` swipe branch in `HeroCarousel`.

---

## 8. Content policy for future imagery (India-only)

All future WebP art at the paths in §3 **must**:

- represent Indian NEET aspirants and Indian educational context;
- use Indian school/coaching-institute settings, uniforms, or study environments;
- exclude foreign flags, Western university branding, SAT/ACT/MCAT references, and generic international EdTech stock imagery;
- carry no synthesised text inside the image;
- be exported to `.webp` at natural aspect ~`4:3`, ≤ 200 KB each;
- ship with a matching `alt` attribute describing the scene, not the capability slogan;
- honour `next/image` with explicit `width` / `height` / `sizes`;
- the first tile's image gets `priority`; the rest lazy-load.

---

## 9. Intentional omissions vs the task brief

- No `HeroVisual.tsx` uses `next/image` yet — awaiting real assets.
- No auto-advance timer (see §5).
- No analytics events (see §7).
- No new `Card`, `Button`, or motion primitive — all reuses of existing `apps/web/src/components/ui/*` and DS tokens.
- No changes to backend / auth / assessment scoring / attempt runner / ECAEP / CMS / learning-mastery calculations / Study Coach internals / the 5K MCQ pipeline.

---

## 10. Validation matrix

| Viewport | Status | Notes |
| -------- | ------ | ----- |
| 375 × 812 | Automated at unit-render level (jsdom `innerWidth=375`). Tablist scrolls internally; page has no horizontal overflow (`<main class="overflow-hidden">`). | Browser check pending. |
| 390 × 844 | Same DOM path as 375; expected identical. | Browser check pending. |
| 768 × 1024 | Grid becomes 2-col at `md:`. | Browser check pending. |
| 1280 × 720 | Content clamped to `--content-max` (72 rem). | Browser check pending. |
| 1440 × 900 | Same as 1280; margin scales. | Browser check pending. |

Hydration warnings / console errors are **not** produced by this component tree (all client state is `useState`, no `Date.now()` / random / locale calls in server render).

---

## 11. Change history

| Date       | Change                                                                                 |
| ---------- | -------------------------------------------------------------------------------------- |
| 2026-09-16 | Initial M3A hero. Placeholder previews, six routes wired, no assets, no analytics.     |
