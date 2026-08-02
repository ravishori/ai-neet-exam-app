# ADR-0023: Extract once, generate many — which assets, and which don't fit yet

## Status
Accepted

## Context
ADR-0022 proved one pipeline stage (grounded MCQ generation) against one
real chapter. The follow-up ask was explicit: don't stop at MCQs — reuse
the same extracted section text to generate the full spread of NEET
learning assets (MCQs at multiple difficulties, flashcards, short notes,
one-page revision sheets, mind maps, concept maps, NCERT line-by-line
questions, PYQ mappings, mock tests, adaptive quizzes, a doubt-answering
knowledge base, AI tutor content, spaced-revision schedules). Not all
thirteen are the same kind of problem — some are genuinely "one more
prompt against the same extracted text," others need a capability this
pipeline doesn't have, and a few aren't ingestion's job at all because
they already exist elsewhere in the platform.

## Decision

**Built now, all reusing the same extracted section text:**
- **MCQs, explicit difficulty spread** — the existing per-section
  generator now asks for one easy + one hard question instead of leaving
  difficulty to chance.
- **Flashcards** (`FLASHCARD` body: front/back) — 2 per matched section,
  same grounding discipline as MCQs.
- **Short notes** (`CONCEPT_NOTE` body: summary/sections) — one per
  *concept*, not per section, synthesized from every matched section
  that concept touches (e.g. Ohm's Law spans two sections in the pilot
  chapter — one note, not two). Skipped if that concept already has a
  non-archived note, so re-running a job never floods duplicates.
- **One-page revision sheet** (`FORMULA_SHEET` body: formulas list) —
  one per *chapter*, generated last from every matched section's text
  combined. `concept_id` is left null on this item (it spans the whole
  chapter, not one concept) — `ContentItem.concept_id` was already
  nullable for exactly this shape of content.

Bodies are chosen from types the CMS schema (ADR-0009) already defines —
`FLASHCARD`, `CONCEPT_NOTE`, `FORMULA_SHEET` all existed unused. No new
content types needed for this slice.

**Explicitly deferred, with reasons — not silently dropped:**
- **Mind maps / concept maps.** The only content type that fits
  (`DIAGRAM`) requires a real `image_url` — non-optional in the schema.
  This pipeline generates text, not images; wiring an actual
  diagram-rendering step (or an image-generation model) is a distinct
  capability decision, not a prompt-writing one.
- **PYQ mappings.** `QuestionBody.pyq_year` already exists as a field,
  but populating it means attributing a question to a specific real NEET
  paper — which requires an actual dataset of previous-year questions to
  map against. None exists in this project. Inventing plausible-looking
  PYQ years would be fabricating exam history, not extracting it — the
  one thing ADR-0004's "no hallucinated info" quality bar exists to
  prevent. Deferred until real PYQ source data is available to ground it.
- **NCERT line-by-line questions.** A distinct, narrower question style
  (verbatim comprehension checks tied to specific sentences). Lower
  value than the four assets above for a first pass; reconsider once
  those are in real use.

**Not ingestion's job — already exist, and correctly so:**
- **Mock tests / adaptive quizzes.** The assessment engine (ADR-0013)
  already assembles these dynamically from whatever question pool is
  published. Ingestion's job is to grow that pool; it doesn't need its
  own parallel test-assembly logic.
- **AI tutor content / doubt-answering knowledge base.** The AI Tutor
  (ADR-0004, redesigned this session) already grounds its answers in
  published `CONCEPT_NOTE`s for a concept. Generating more concept notes
  *is* the contribution here — a separate "knowledge base" would just be
  the same data through a second door.
- **Spaced-revision schedules.** Already computed automatically
  (ADR-0016) from mastery level once a student answers any question on a
  concept — ingested questions feed this the moment they're published
  and attempted. Nothing new to generate.

## Consequences
`IngestionJob` gains three more counters (`flashcards_generated`,
`notes_generated`, `revision_sheets_generated`) alongside the existing
`questions_generated`/`questions_deduped`, so a job's output mix is
visible without querying `cms.content_items` directly. Every asset still
lands as `DRAFT` through the same `ContentWorkflowService` gate as
before — "extract once, generate many" does not mean "publish many
without review."
