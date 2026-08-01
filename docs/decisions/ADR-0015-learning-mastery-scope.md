# ADR-0015: Learning/Mastery scope — 2-level, derived from real attempts

## Status
Accepted

## Context
The roadmap (SP6) calls for "Learning/Mastery, simplified — Concept →
mastery score, 2-level." The BRD's full vision (Knowledge Graph,
Micro-Competency layer, Digital Twin, decay curves, spaced-repetition
scheduling) is backlog per ADR-0007. This ADR fixes what "2-level,
simplified" means concretely, now that Assessment (SP4) produces real
`assessment.attempt_answers` to compute from.

## Decision

**Two levels, one of them stored:**
- **Concept-level mastery is persisted** in a new `learning.concept_mastery`
  table — one row per `(user_id, concept_id)`, updated in place.
- **Topic-level mastery is computed on read**, by averaging the stored
  concept rows under that topic. No separate table — averaging live
  numbers is cheap and keeps a single source of truth. Any rollup above
  topic (chapter/subject) shown on the dashboard is the same computation
  carried one level further for display purposes; it is not a third
  stored entity.

**New `learning` schema.** ADR-0001's original schema list did not
reserve one (it reserved `analytics` and `commerce` for later sprints
but missed this one) — migration `0001` schemas are being extended here.

**Scoring is arithmetic, not an AI Gateway agent.** `mastery_score` is
`round(100 * correct_count / attempts_count)`; `mastery_level` is a pure
function of `(attempts_count, correct_count)`:
- `attempts_count == 0` → `NOT_STARTED`
- `attempts_count < 3` → `LEARNING`
- `score >= 80` → `MASTERED`
- else → `PRACTICING`

The 3-attempt floor exists so one lucky or unlucky guess can't flip a
concept straight to `MASTERED` or leave it stuck at a low score with no
context. This is deliberately simple — no recency weighting, no decay
over time, no spaced-repetition interval. Those are explicitly BRD scope
still on the backlog list (ADR-0007), not silently dropped.

**Recomputed synchronously on attempt submission**, not on a schedule.
`AssessmentService.submit_attempt()` already loads every answered
question's `is_correct` and `content_item_id` in that method; after
scoring the attempt, it now also groups those content items by
`concept_id` and calls `MasteryService.recompute_for_concepts(user_id,
concept_ids)` in the same request. There is no background job
scheduler in this project (Coolify/Hetzner + modular monolith per
ADR-0001/ADR-0002) — recompute-on-submit is the simplest thing that
keeps mastery always current, at the cost of a few extra queries on the
submit path, which is already not latency-sensitive (one attempt
submission, not a hot loop).

**Source of truth stays `attempt_answers`.** Recompute is a full
re-aggregation (`COUNT(*)`, `COUNT(*) FILTER (is_correct)`) over that
concept's answers for that user, not an incremental counter update — so
`concept_mastery` can always be rebuilt from `attempt_answers` if it
ever drifts, and re-running recompute is idempotent.

**API surface** (`/api/v1/learning/mastery/...`, `dependencies=[get_current_user]`):
- `GET /concepts/{concept_id}` — one concept's mastery for the caller.
- `GET /topics/{topic_id}` — topic average + per-concept breakdown (also
  used to render the concept list under a topic in one call).
- `GET /overview` — per-subject rollup for the student dashboard
  (concepts_total / concepts_attempted / mastered_count / average_score).

No admin/teacher view of other students' mastery in this sprint — that
belongs with Analytics (SP8) or a future cohort-reporting feature, not
here.

## Consequences
Mastery is only as good as the questions answered — a concept with one
seed question behaves noisily until more content exists, which is
expected at this stage of content authoring (ECAEP, SP3) and improves as
the question bank grows. Recompute-on-submit means mastery is always
consistent with the latest attempt with no eventual-consistency window,
at the cost of doing the aggregation query synchronously inside
`submit_attempt` for however many distinct concepts that attempt
touched (bounded by the assessment's question count, already small).
