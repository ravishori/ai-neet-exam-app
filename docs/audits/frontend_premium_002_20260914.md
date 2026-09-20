# FRONTEND-PREMIUM-002 — Student Dashboard Visual Acceptance Audit

**Verdict: YELLOW** (2026-09-14)  
**Visual score: 7.5 / 10**

Review-only. No product code changes. Live URLs: `http://127.0.0.1:3001/student/dashboard` + `:8000`.

## Method

- Implementation review of `apps/web/src/app/student/dashboard/page.tsx`
- Playwright matrix: 390/768/1280/1440 × light (+ dark @390 & 1280) via `apps/web/scripts/premium002-visual-audit.mjs`
- Cursor browser screenshots: mobile first fold, desktop hero, priorities, subject rows, dark hero
- Real auth + real learning/assessment APIs (new register user; existing session “Premium”)

## First impression

**Strong.** Eyebrow “NEET command center”, personalized welcome, next-focus concept from recommendations, and primary **Continue practice** appear in the first viewport at 390 and 1280. Reads as intentional preparation HQ, not a decorative splash.

## Hero / CTA

- Primary CTA: solid brand fill, `min-h-12` (48px), play icon, `aria-label` — immediately obvious.
- Secondary “Configure scope” correctly outline.
- Desktop hero ~457px with two-column grid (copy+CTA | readiness gauge).
- Mobile hero tall (~835px including metric strip) — CTA still first-fold; gauge+metrics consume most of the remaining fold.
- **Dilution:** five outline **Practice now** buttons in Recommended practice compete once the user scrolls.

## Progress

- Readiness gauge + metric strip (Accuracy —, Questions 0, Sessions 0, Readiness 0%) are honest for unused accounts.
- Progressbars expose `aria-valuemin/max/now` + labeled mastery.
- Zero fill (`width: 0`) means subject accent colors are invisible on bars until progress > 0 — chips/dots carry distinction.
- Readiness appears twice (gauge + pill) — mild redundancy.

## Subjects

- Physics (blue), Chemistry (violet), Botany/Zoology (shared green biology token) via `resolveSubjectTheme` / `SubjectChip`.
- Labels + chips prevent color-only encoding; Botany vs Zoology same accent is taxonomy/token reality.
- Zero-state comparison is readable but flat (identical empty tracks).

## Empty states

- Revision: “Nothing due right now” + Browse subjects — intentional.
- Activity: 0/28 + “No submitted sessions yet” — intentional.
- Accuracy “—” when no scored answers — honest.
- Recommendations populated from real API — no fabricated metrics.

## Responsive

| Viewport | Overflow | CTA height | Notes |
|---|---|---|---|
| 390 | 0 | 48 | CTA first-fold; bottom nav present (~791 top); no cramped cards |
| 768 | 0 | 48 | Balanced stack |
| 1280 / 1440 | 0 | 48 | Content ~1152px; hierarchy clear; not a sparse void |

## Light / dark

- Semantic OKLCH surfaces; dark fg `oklch(0.97…)` on `oklch(0.16…)` body.
- Dark hero readable; primary CTA remains blue.
- Dark “Configure scope” becomes very light — slightly loud next to primary (polish item).

## Accessibility

- Heading chain H1 → H2 → H3 intact.
- Progressbar semantics present.
- Touch targets ≥44px on primary/outline touch buttons.
- Buttons use `focus-visible` rings (DS convention).
- Not color-only for subjects (chip + name + numeric coverage).

## Runtime

- Playwright: no page errors, no failed `/_next/` assets, no hydration text across matrix.
- Browser: hashed CSS/JS loaded; no Next overlay.
- Backend healthy; API emptiness ≠ frontend failure.

## Concrete defects (none blocking RED)

1. **CTA competition** — multiple “Practice now” vs single “Continue practice”.
2. **Mobile hero density** — readiness + 4 metrics inflate first scroll unit.
3. **Zero-state subject bars** — accent fills invisible at 0%.
4. **Dark secondary CTA** — high-luminance outline rivals primary slightly.
5. **Hero email-unverified badge** — useful but interrupts premium narrative.

## Highest-value improvements (do not auto-implement)

1. Demote recommendation actions (link/chevron or single “Next concept”) so hero stays the only loud practice CTA.
2. Tighten mobile hero: shrink gauge or move metric strip below fold / into a quieter strip.
3. Zero-state subject storytelling: show coverage track or muted subject wash even at 0% mastery.
4. Soften dark-mode outline secondary; keep unverified email out of hero (banner/account).

## Safety

- No Practice/Mock/ECAEP/AuthZ/DB/API/taxonomy/NCERT/syllabus/A6–A12 changes.
- No frozen DRAFT mutations.
- No commit/push.
- Product code unchanged in this audit (probe script only).

## Prior GREEN gates (assumed still true; not re-run build)

- PREMIUM-001 tests 4/4, A12 19/19, build GREEN — unchanged by this review-only pass.
