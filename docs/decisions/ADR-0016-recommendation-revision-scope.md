# ADR-0016: Recommendation + spaced-repetition revision — rule-based, dashboard-only

## Status
Accepted

## Context
Roadmap SP7 is "Recommendation + spaced-repetition revision." The BRD's
full vision (per-item ease factors, real SM-2/SM-18 scheduling, ML-driven
recommendation, push/email/SMS reminders) is backlog per ADR-0007. This
ADR fixes what ships now, building directly on SP6's `learning.concept_mastery`
(ADR-0015).

## Decision

**Spaced repetition is a fixed interval keyed on `mastery_level`, not
SM-2.** No ease factor, no per-item history of past intervals — just a
lookup:
- `LEARNING` → review again in 1 day
- `PRACTICING` → review again in 3 days
- `MASTERED` → review again in 7 days
- `NOT_STARTED` → no schedule (nothing to revise yet)

`concept_mastery` gets one new column, `next_review_at`, set every time
`MasteryService._recompute_one()` runs (i.e., on every attempt
submission touching that concept) — the schedule always reflects the
concept's *current* level, not a decaying curve building on the
previous interval. This is deliberately simpler than real spaced
repetition; it still produces the behavior that matters for an MVP
(weak concepts resurface sooner than mastered ones) without a second
scheduling algorithm to get wrong.

**Recommendation is rule-based ranking, not ML.** `get_recommendations()`
fills a fixed-size list (default 5) in strict priority order, each item
tagged with why it's there:
1. **`due_for_revision`** — `next_review_at <= now()`, most overdue first.
2. **`weak_concept`** — `mastery_level = PRACTICING`, lowest score first
   (concepts a student attempted but hasn't mastered).
3. **`new_concept`** — concepts with no `concept_mastery` row at all, in
   curriculum order (subject → chapter → topic → concept
   `display_order`) — so the recommendation naturally follows the NEET
   syllabus sequence for a student who hasn't started yet.

No collaborative filtering, no difficulty-adaptive selection, no
cross-student signal — every recommendation is derived solely from the
requesting student's own `concept_mastery` rows plus the academic
hierarchy's existing ordering.

**Dashboard widgets only — no dedicated revision page.** Both endpoints
back two cards on the student dashboard (each item has a "Practice now"
button that generates a `CONCEPT`-scoped practice assessment and starts
the attempt immediately, reusing the SP4 practice flow exactly as the
existing `/student/practice` page does). A standalone `/student/revision`
browsing page is not needed yet — everything actionable fits in a
dashboard card at this scope, and adding a second surface for the same
data would be premature.

**No reminders.** No email/SMS/push nudges when something becomes due —
this project has no outbound notification channel wired up yet (auth is
still dev-mode OTP-less), and building one is its own scope, not a
side effect of a revision queue.

## API surface
- `GET /api/v1/learning/revision/due` — concepts with `next_review_at <=
  now()`, most overdue first, capped at 10.
- `GET /api/v1/learning/recommendations` — up to 5 ranked items per the
  priority order above.

Both are per-student reads under the existing `get_current_user`
dependency — no new permissions.

## Consequences
Because the schedule resets to a flat interval on every recompute
rather than accumulating history, a concept a student keeps re-answering
correctly every day will still show up again in exactly `MASTERED`'s
7-day window, not further out — there's no long-term "graduated" state.
That's an acceptable simplification for now; moving to real spaced
repetition later is additive (a new `ease_factor` column and a real
SM-2 update rule), not a breaking change to this schema.
