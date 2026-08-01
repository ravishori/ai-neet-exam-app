# ADR-0012: Academic Engine — 5-level hierarchy, not 7+

## Status
Accepted

## Context
The BRD's Sprint 2 spec models the curriculum as
`Exam → Subject → Unit → Chapter → Topic → Subtopic → Concept`, plus
separate tables for subject aliases/translations, chapter versions,
concept aliases/metadata/tags/relationships, and curriculum versioning.
Consistent with ADR-0007 and ADR-0011, this is scoped down for v1 using
the same reasoning: build what the first real content pass needs, not
what a mature, multi-exam, multi-language platform would eventually want.

## Decision
**Built now:** `academic.exams → academic.subjects → academic.chapters →
academic.topics → academic.concepts` — five levels, dropping the separate
`Unit` layer (chapters are grouped directly under subject; `Unit` was
purely organizational and nothing downstream reads it yet) and `Subtopic`
(Topic → Concept is granular enough for the MVP question/content volume).

Each `Concept` carries a single free-text `ncert_reference` field
(book/chapter/section, however the content author wants to describe it)
instead of the BRD's structured NCERT mapping table with book/edition/
chapter/section/figure/table/page-range columns.

**Deferred:** subject aliases/translations (no i18n yet — ADR-0007),
chapter/curriculum versioning (single current syllabus, no version
history needed until the syllabus actually changes), concept aliases/
metadata/tags/relationships and the Knowledge Graph (ADR-0007 already
defers this explicitly).

## Why
Every one of the deferred items is real infrastructure for a mature
platform, and none of them are load-bearing for getting NCERT-aligned
content, questions, and the AI Tutor working end to end on real chapters.

## Consequences
Adding `Unit` or `Subtopic` back later is an additive migration (a new
table + a nullable FK), not a redesign — `Chapter` and `Topic` already
have stable, versioned primary keys that a `Unit`/`Subtopic` table could
attach to without touching existing rows.
