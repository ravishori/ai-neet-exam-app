# ADR-0013: Assessment Engine — generated on demand, not authored content

## Status
Accepted

## Context
The BRD's Assessment Domain lists nine test types (Full NEET, Chapter,
Unit, Subject, Custom, Adaptive, Previous Year Paper, Weekly, Daily Quiz)
with an authoring lifecycle (Create → Publish → Assign → Attempt →
Submit → Evaluate). Building a separate CRUD/authoring surface for test
*definitions* — on top of the ECAEP pipeline that already governs the
*questions* inside them — would duplicate editorial machinery for content
that doesn't need review: an assessment is just a selection of already-
published questions, not new content.

## Decision
Two assessment types for v1: **PRACTICE** and **MOCK**. Neither is
authored ahead of time — both are generated on request from currently
`PUBLISHED` questions matching a scope (concept, chapter, subject, or
full-syllabus):
- `POST /api/v1/assessments/practice` — untimed, no negative marking,
  scoped to a concept/chapter/subject
- `POST /api/v1/assessments/mock` — timed, NEET marking (+4 / −1),
  scoped the same way or full-syllabus

Every question drawn into an assessment must already be `PUBLISHED` via
ECAEP — the assessment layer never bypasses that pipeline.

**Deferred:** Adaptive tests (needs the Sprint 6 mastery model to pick
difficulty), Previous Year Papers as a distinct type (a PYQ is just a
`QUESTION` content item tagged accordingly — no separate entity), Weekly/
Daily scheduled tests (needs the Sprint 7 revision engine to decide
*when*), pause/resume (client re-fetches attempt state on reload, which
covers the common case), server-side time-limit enforcement (the client
auto-submits on timer expiry; the server trusts `submitted_at` for v1 —
revisit if this is ever exploitable in a graded/competitive context).

## Why
This keeps the question bank as the single source of editorial truth and
avoids a second content-authoring surface. It also means the assessment
pool grows automatically as ECAEP content is published — no separate
"add this question to a mock test" step.

## Consequences
Mock test size is whatever's currently published for the requested scope,
not a fixed 45/180-question NEET pattern — with ~8 seeded questions across
4 subjects, an early "full mock" is intentionally small. This is correct
behavior, not a bug: it's real signal that more content needs to move
through ECAEP, visible directly in the coverage grid (ADR-0009).
