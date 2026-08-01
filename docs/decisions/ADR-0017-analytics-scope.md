# ADR-0017: Analytics dashboard — live aggregation, no new schema, admin-only

## Status
Accepted

## Context
Roadmap SP8 is "Analytics dashboard." ADR-0001 reserved an `analytics`
schema back in Sprint 0, anticipating dedicated tables for this. Six
sprints later there's now real data worth surfacing that has never had
a UI: `assessment.attempts`/`attempt_answers` (since SP4) and
`ai.ai_requests` — every AI Gateway call's cost/latency/success, logged
since SP5 but never displayed anywhere.

## Decision

**No new tables.** The reserved `analytics` schema stays empty. At
current data volumes, aggregating live over `assessment.attempts` and
`ai.ai_requests` with `GROUP BY`/`COUNT`/`AVG` is cheap — the same
reasoning ADR-0015 used for topic-level mastery (computed on read
instead of stored). If this ever needs materialized rollups for
performance at real scale, that's the point to actually use the
reserved schema — not before.

**New `app/modules/analytics/` module** with no models of its own —
its whole job is read-only aggregation across other modules' existing
tables (`assessment`, `ai`, `academic`), which doesn't fit inside any
one of those modules without creating an awkward cross-module
dependency in the wrong direction (e.g. `assessment` importing from
`ai`). A thin module whose only job is joining across others is a
better fit than distorting module boundaries elsewhere.

**Two areas, both platform-wide (not per-student):**

1. **Assessment analytics** — total submitted attempts, a breakdown by
   `assessment_type` (PRACTICE vs MOCK), overall average score
   percentage, a 14-day daily attempt-count trend, and the 10
   lowest-accuracy concepts platform-wide (aggregated across every
   student's `attempt_answers`, not one student's — the per-student
   version of "weak concepts" already exists as `[[project_talos]]`
   SP7's recommendation feed). This tells an admin or content author
   where the question bank or explanations need work, which student-
   scoped mastery data can't show.

2. **AI usage analytics** — total requests, total estimated cost,
   overall fallback rate, and a per-`agent_type` breakdown (request
   count, total cost, average latency, success rate). Pure aggregation
   over `ai.ai_requests`, unchanged since ADR-0014.

**Gated by the existing `analytics.view` permission** — seeded back in
Sprint 0/1 to `ADMIN` and `SUPER_ADMIN` only, never previously used by
any endpoint. `TEACHER`'s separate `reports.view` permission (intended
for per-student progress reports, a teacher-facing feature) stays
unused — that is a distinct feature from admin-facing operational
analytics and is not addressed in this sprint.

**No export, no custom date ranges.** One overview page, fixed
lookback windows (14 days for the trend). CSV export and configurable
reporting windows are real BI-tool territory — BRD backlog per
ADR-0007, not a side effect of building the first version of this
page.

## Consequences
Every query here re-scans `attempts`/`attempt_answers`/`ai_requests`
on each page load rather than reading a precomputed summary — fine at
this data volume, and it means the dashboard is never stale. The
weakest-concepts query has the same shape as SP7's per-student weak-
concept query but grouped across all users instead of filtered to one,
so extending it later (e.g., per-cohort filtering for Teacher reports)
is additive, not a rewrite.
