# ADR-0024: Knowledge Unit foundation — PR 1 of the frozen AI Content Lifecycle

## Status
Accepted

## Context
The AI Content Lifecycle Specification (frozen architecture) requires that no
student-facing asset ever be generated directly from raw source text — every
asset must be a function of a versioned, gate-checked **Knowledge Unit**, not
a side effect of one ingestion run. The current shipped pipeline (ADR-0022,
ADR-0023) doesn't yet honor this: `ingestion_sections.raw_text` is read
directly by four generation workers (MCQ, Flashcard, Concept Note, Formula
Sheet), with no durable, independently-versioned, gate-checked knowledge
representation between extraction and generation.

This ADR is the first implementation slice of that specification's own
Migration Plan, Step 1: *"`ingestion_sections` (raw text, side effect of one
job) → formal `knowledge_unit` table, versioned, independently addressable."*

## Decision

**Scope is deliberately split into two PRs**, per the spec's own migration
discipline of shipping one step at a time rather than a cutover:

**This PR (PR 1):** introduce `KnowledgeUnit` as a real, populated,
version-tracked, gate-checked entity, fed by a new structuring stage inserted
after concept-matching. **The four existing generation workers are
unchanged** — they continue reading `IngestionSection.raw_text` directly,
exactly as they do today. Knowledge Units are created and validated
alongside the existing pipeline, proven correct, before anything is made to
depend on them.

**PR 2 (tracked separately, not built here):** cut the four generation
workers over to consume `KnowledgeUnit.structured_facts` instead of raw
section text, and add the full traceability columns
(`knowledge_unit_id`, `model_used`, `prompt_version`, `confidence_score`,
`generation_cost_usd`) to `cms.content_versions`.

**New `knowledge` schema** — matches the existing schema-per-domain
convention (`learning`, `ingestion` were each created the same way, in their
own first migration, per `38e32c83fa42` and `b7d07ac8deec`).

**`KnowledgeUnit` fields, and what's deliberately absent:** `id`, `version`,
`content_hash` (SHA-256 of `structured_facts`, the cheap idempotency check
specified for version-bumping), `structured_facts` (JSONB array of atomic
claims), `summary`, `source_section_id` → `concept_id`, `extraction_confidence`,
`validation_status`, `superseded_by` (self-FK, nullable). **No `embedding`
column in this PR** — a nullable placeholder column with no real type
(pgvector's `vector` type requires `CREATE EXTENSION vector`, not run here)
would itself be exactly the kind of placeholder the frozen architecture
bans. Activating pgvector is a distinct capability decision (Target
Architecture doc, M3); the column is added in the same future work that
turns it on, not speculatively ahead of it.

**Quality gates, honestly scoped:** the Lifecycle Spec's Section 7 describes
nine gates, several requiring infrastructure this PR doesn't include (a
human-expert medical-review queue, a Bloom-taxonomy calibration set). This
PR implements exactly two, both real and mechanically enforced, not model
self-assertion:

1. **Source verification** — keyword/span overlap between each claimed fact
   in `structured_facts` and the section's raw source text. This directly
   applies the Lifecycle Spec's own Version-2 self-correction ("Source
   Verification... needs a more mechanical check... before it can be
   trusted as a hard gate," found in that document's self-review). A claim
   that doesn't overlap the source text fails before any model judgment is
   involved.
2. **Duplicate detection** — Postgres trigram similarity against existing
   Knowledge Units for the *same concept only*, mirroring the exact pattern
   already proven for question-stem dedup in `ingestion_repository.py`.

A Knowledge Unit that fails either gate gets `validation_status=FAILED` and
is not counted toward `knowledge_units_created` — it is not deleted, and not
retried automatically within this PR (that's a `Continuous Improvement`
concern the Lifecycle Spec assigns to a later stage, not this one).

**Cost tradeoff, stated plainly:** this adds a fifth AI call per matched
section (on top of the two MCQs and two flashcards already generated per
section), a real ~25–40% increase in per-run AI spend for this phase. This
is the correct architectural tradeoff — Knowledge Units must be
model-agnostic and durable, independent of any one generation call — not a
hidden cost.

## Consequences
Until PR 2 lands, Knowledge Units exist and are provably correct but nothing
consumes them — a deliberate, temporary gap between "the foundation exists"
and "the foundation is used," accepted in exchange for a smaller, safer,
independently-reviewable change. PR 2 is tracked as a real follow-up task,
not a code comment, per the frozen architecture's explicit ban on
placeholder TODOs.
