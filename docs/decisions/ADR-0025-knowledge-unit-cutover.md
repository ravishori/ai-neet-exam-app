# ADR-0025: Knowledge Unit cutover — PR 2 of the frozen AI Content Lifecycle

## Status
Accepted

## Context
ADR-0024 (PR 1) built `KnowledgeUnit` as a real, populated, gate-checked
entity, but deliberately left it disconnected: the four generation workers
(MCQ, Flashcard, Concept Note, Formula/Revision Sheet, all in
`ingestion_pipeline_service.py`) still read `IngestionSection.raw_text`
directly. That ADR named PR 2's scope up front: repoint the workers to
`KnowledgeUnit.structured_facts`, and add traceability columns
(`knowledge_unit_id`, `model_used`, `prompt_version`, `confidence_score`,
`generation_cost_usd`) to `cms.content_versions`. This ADR is that cutover.
The architecture itself is frozen — nothing here revisits what PR 1 already
decided (gate design, schema placement, cost tradeoff). What's new is the
one thing PR 1's own text didn't yet have to resolve: **two of the four
workers aggregate across many Knowledge Units, not one**, and the frozen
column list is singular. Section 3 below is the one real design decision
this PR makes.

## Decision

### 1. Generation reads structured facts, not raw text
Each worker's prompt currently receives a plain string
(`source_text`/`excerpts`) built from `IngestionSection.raw_text`. That
call site changes to build the same shape of string from the matched
section's **PASSED** `KnowledgeUnit` instead — its `summary` plus its
`structured_facts` rendered as a bullet list. The prompt modules
(`ingestion_mcq.py`, `ingestion_flashcards.py`, `ingestion_concept_note.py`,
`ingestion_revision_sheet.py`) keep their existing `build_prompt(...,
source_text: str, ...)` signatures unchanged — they don't need to know
where the string came from. Their `SYSTEM_PROMPT` wording changes from
"grounded in a real NCERT textbook excerpt" to "grounded in verified
structured facts extracted from an NCERT textbook," since the input is now
already-gated atomic claims, not raw prose — an accuracy fix to the prompt
text, not a behavior change.

`KnowledgeUnit.structured_facts` already passed the source-verification
gate (ADR-0024) before generation ever sees it, so this is strictly a
narrower, more trustworthy input than raw text was — the reason PR 1
built the foundation in the first place.

### 2. No knowledge unit, no generation — no silent raw-text fallback
Per matched section, `_run_structuring` already produces at most one
`KnowledgeUnit` (PENDING is never persisted as a final state — PR 1's
`structure_section` returns PASSED, FAILED, or `None` on an AI-call
failure). PR 2 threads the PASSED units it already holds in memory,
straight out of that same job run, into generation:

- `_run_structuring` returns `dict[section_row.id -> KnowledgeUnit]`,
  containing only PASSED units.
- `_run_generation` (MCQ + Flashcard) looks up the section's unit; if
  absent, it skips both assets for that section entirely — no read of
  `raw_text` as a fallback path.
- `_run_concept_notes` and `_run_revision_sheet` filter their matched
  sections down to the PASSED-only subset before building excerpts; if a
  concept (or the whole chapter) has zero PASSED sections, that note/sheet
  is skipped, not generated from whatever raw text exists.

A new `IngestionJob.generation_skipped_no_knowledge_unit` counter records
every one of these skips (section, concept, or chapter level) so a job's
output is auditable without cross-referencing `knowledge_units` by hand —
the same observability precedent as PR 1's `knowledge_units_created` /
`_rejected`. This is a real behavior change from PR 1 (where structuring
failures were invisible to generation): a Knowledge Unit that fails
validation now visibly suppresses the content that would have come from
it, rather than the two pipelines silently staying independent.

### 3. Traceability for a 1:1 worker vs. an N:1 worker (the one open design point)
MCQ and Flashcard generate from exactly one section, hence exactly one
Knowledge Unit — the frozen singular columns
(`knowledge_unit_id`/`knowledge_unit_version`) fit them directly. Concept
Note (per *concept*, every matched section that concept touches) and
Revision Sheet (per *chapter*, every matched section in it) generate from
however many PASSED units happen to apply — per ADR-0023, that's
routinely more than one. A single nullable FK can't honestly represent
"produced from N units" without picking an arbitrary one and silently
dropping the rest — which would make traceability wrong exactly for the
two content types most likely to need it (they synthesize across the most
source material, so a review question like "where did this claim about
Ohm's Law actually come from" matters more for a concept note than for a
single MCQ tied to one section).

**Decision:** add a small join table, `cms.content_version_knowledge_units`
(`content_version_id`, `knowledge_unit_id`, `knowledge_unit_version`) —
one row per contributing unit, for every generated asset, all four
workers. `ContentVersion.knowledge_unit_id`/`knowledge_unit_version` are
additionally populated as a fast-path denormalization **only** when a
version has exactly one contributing unit (true for every MCQ and
Flashcard, and true for a Concept Note/Revision Sheet on the rare occasion
its scope really is one section) — `NULL` when there's more than one,
rather than a misleading first-or-arbitrary pick. The join table is the
one source of truth for "which units"; the column is a convenience index
for the common case. This is the "or a new table" alternative PR 1's own
naming already anticipated, sized to exactly the shape of the actual
many-to-one relationship — no additional fields, no speculative generality
beyond that.

`confidence_score` on a multi-unit version is the **minimum**
`extraction_confidence` across its contributing units, not an average —
traceability should surface the weakest link a reviewer would want to
double-check, not smooth it away. `generation_cost_usd` is the cost of
*this* generation call only (from `AIResponse`, extended with a
`cost_usd` field the gateway already computes internally but didn't
expose), not the upstream structuring calls' cost — those were already
logged as their own `AIRequestLog` rows in PR 1. `prompt_version` is a new
`PROMPT_VERSION` constant added to each of the four generation prompt
modules (starting at `"v1"`), naming *that worker's* prompt, not the
structuring prompt's version.

### Migration
One Alembic migration, following the existing add-columns-to-an-existing-
table pattern (`823b50e0e64f`): adds the five scalar columns to
`cms.content_versions` (all nullable — historical rows predating this PR
have no Knowledge Unit to point to and stay `NULL`, not backfilled), adds
`generation_skipped_no_knowledge_unit` to `ingestion_jobs` (same pattern),
and creates `cms.content_version_knowledge_units` with FKs to
`content_versions` (`CASCADE`) and `knowledge.knowledge_units`
(`RESTRICT` — a unit that's been cited by generated content shouldn't
disappear out from under that citation; PR 1 never deletes units anyway,
only marks them `FAILED`/`superseded_by`, so this is a safety constraint
that should never actually fire).

## Risks
- **Fewer assets generated per run**, by design — any section whose
  Knowledge Unit failed the source-verification or duplicate gate now
  produces zero MCQs/flashcards instead of some, where PR 1 generated from
  raw text regardless. This is the point of the cutover, not a bug, but it
  means a straight before/after count comparison on the pilot chapter is
  expected to show equal-or-fewer items, and quality/groundedness — not
  raw count — is the right comparison.
- **Facts-as-bullets vs. prose excerpt** is a different-shaped input to
  the same prompts; validated by running the real pilot chapter end to end
  and comparing output against ADR-0022/0023's prior manual runs before
  this is considered done (see Tests).

## Tests
- Unit: the facts-to-prompt-text rendering function (deterministic, pure
  — same category as PR 1's `test_grounding_check.py`), and the
  PASSED-only filtering logic for concept-note/revision-sheet section
  selection.
- Integration: existing `test_ingestion_pipeline.py` (job creation, auth,
  path validation) continues unchanged — it doesn't exercise the AI-calling
  interior of the pipeline, per its own docstring.
- Real end-to-end run: the Current Electricity pilot PDF
  (`StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`),
  through the real API with the real Anthropic key already configured,
  comparing generated MCQs/flashcards/notes/sheet against what PR 1's
  structuring stage separately produced for the same sections, and against
  ADR-0022/0023's original raw-text-based output — the bar this ADR sets
  for "done."
- Full backend test suite green, same discipline as every prior ADR in
  this project.

## Consequences
Generation and Knowledge Units are no longer two parallel, independently-
running pipelines — the gap ADR-0024 named as its deliberate, temporary
consequence is closed. Every MCQ, flashcard, concept note, and revision
sheet produced by ingestion from this point forward carries a real,
queryable answer to "which Knowledge Unit(s), which model, which prompt
version, at what confidence, for what cost" — not a comment pointing at a
future PR. `ingestion_sections.raw_text` remains in the schema (still the
input to structuring, and kept for audit/citation per its own docstring)
but is no longer read by any of the four generation workers.
