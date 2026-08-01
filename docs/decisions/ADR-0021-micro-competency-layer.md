# ADR-0021: Micro-competency layer — one level, not three, not 21,000 rows

## Status
Accepted

## Context
ADR-0007 deferred the BRD's "4-layer competency model" — Concept → Learning
Objective → Competency → Micro-Competency, with the BRD itself estimating
roughly 21,000 micro-competencies across the NEET syllabus. ADR-0012 froze
the academic hierarchy at five levels ending in `Concept`, explicitly
noting that a finer layer underneath could be added later as "a new table
+ a nullable FK, not a redesign." This is that addition — the second
Phase 2 backlog item taken up, by direct user request.

## Decision

**One new layer, not three.** The BRD's `Learning Objective → Competency →
Micro-Competency` chain collapses into a single `academic.micro_competencies`
table, one level under `Concept`. The value here is "finer-grained than a
whole concept," not the specific number of intermediate naming tiers —
three additional hierarchy levels for a v1 slice would repeat exactly the
over-scoping ADR-0012 already cut once.

**A handful per concept, not ~21,000 total.** `academic.micro_competencies`
(`id`, `concept_id` FK, `code`, `name`, `display_order`) — a concept like
"Ohm's Law" gets 2–4 rows ("Apply V=IR to calculate current", "Explain how
resistance depends on material/geometry", "Distinguish ohmic from
non-ohmic conductors"), not hundreds. The BRD's ~21,000 figure is
enterprise-scale content-authoring output over years, not something to
fabricate as placeholder rows — this ADR seeds real micro-competencies for
the one concept (Ohm's Law) already fully seeded through ECAEP, matching
the "seed one thing completely" precedent from ADR-0009/ADR-0019.

**`cms.content_items` gets a nullable `micro_competency_id`.** A `QUESTION`
can optionally be tagged with the one micro-competency it tests. Nullable
and optional, not required — every existing question stays valid untagged,
and only new/updated authoring decides to tag finer. One micro-competency
per question for v1 (not a many-to-many), matching how a single NEET MCQ
usually targets one specific skill.

**Concept-level mastery becomes a rollup with a fallback, not a
replacement.** `learning.micro_competency_mastery` mirrors
`concept_mastery`'s exact shape (attempts_count, correct_count,
mastery_score, mastery_level) and is recomputed the same way — on attempt
submission, from `attempt_answers` joined through `content_items.micro_competency_id`.
Concept-level mastery then averages its micro-competencies' scores *only
for concepts that have any* — a concept with zero tagged micro-competencies
keeps computing exactly as it did in ADR-0015 (direct aggregate over the
concept's own `attempt_answers`). This is the same graceful-degradation
shape as ADR-0019's language fallback: partial adoption doesn't break
untagged content, it just doesn't benefit from the finer granularity yet.

**Authoring**: the admin content form gets an optional micro-competency
dropdown when creating a `QUESTION` against a concept that has any defined;
a small new endpoint lets an author create micro-competencies under a
concept (`content.create`-gated, same permission as authoring content
itself — this is content-adjacent curriculum data, not full academic-admin
territory).

**Student-facing**: the concept detail page shows a per-micro-competency
mastery breakdown underneath the existing overall concept mastery card,
for concepts that have any tagged data — otherwise unchanged from ADR-0015.

## Consequences
A concept's overall mastery score can shift slightly once micro-
competencies are added and a question gets tagged, because the
computation path changes from "average of raw attempt_answers" to
"average of micro-competency averages" — mathematically different from a
straight aggregate whenever attempt counts are uneven across
micro-competencies. This is expected and desired: it's the whole point of
the finer layer (a concept with one heavily-drilled micro-competency and
one never-attempted one now surfaces that imbalance, instead of a single
blended number hiding it). Concepts with no micro-competencies tagged see
no change at all.
