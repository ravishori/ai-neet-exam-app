# ADR-0028: The Educational Knowledge Unit (EKU) — formalizing KnowledgeUnit as the canonical hub

## Status
Accepted — Phases A, B, C, and D implemented and verified (see Self-Review
below). Phase E (Concept Graph) and Phase F (Knowledge Embeddings) remain
explicitly not built — see Self-Review for why.

## Context

**The Educational Knowledge Unit already exists.** It's `knowledge.knowledge_units`
(`KnowledgeUnit`), built in ADR-0024, wired into generation in ADR-0025,
and already referenced by `VisualAsset` (ADR-0026). Before designing
anything, this section states plainly what's real today, verified against
the actual code rather than assumed:

| Capability named in this request | Current state, verified |
|---|---|
| Question Generation reads Knowledge Units | **Done.** MCQ, Flashcard, Concept Note, and Revision Sheet generation all read `KnowledgeUnit.structured_facts` (ADR-0025), never raw text. |
| Every extracted Question references one or more Knowledge Units | **Done**, for ingestion-generated questions. `cms.content_version_knowledge_units` is a real N:1 join table (ADR-0025), plus a fast-path `content_versions.knowledge_unit_id` for the common single-unit case. Pre-ingestion seeded questions (Sprint 4, before Knowledge Units existed) have no link and are not backfilled — same non-backfill precedent as every prior ADR. |
| Figures reference Knowledge Units | **Schema exists, never populated.** `VisualAsset.knowledge_unit_id` (ADR-0026) is a real nullable FK that nothing writes to yet — a disclosed, tracked gap from that ADR, not new news. |
| AI Tutor is powered by Knowledge Units | **Not built.** `TutorService.explain()` reads `Concept.summary`, `Concept.ncert_reference` (a plain string field), and published `CONCEPT_NOTE` items — it has never touched `KnowledgeUnit`. |
| Adaptive Learning / Weak Topic Analysis is powered by Knowledge Units | **Not built.** `ConceptMastery` and `MicroCompetencyMastery` (ADR-0015/0021) track `attempts_count`/`correct_count`/`mastery_score`/`mastery_level` at the Concept and Micro-Competency level only — there is no per-Knowledge-Unit mastery signal anywhere. |
| Concept Graph | **Does not exist at any level.** No prerequisite, relationship, or edge table between concepts exists in the schema today. |
| Explanations as a first-class entity | **Not separate.** The `QUESTION` content body (`content_bodies.py`) has an `explanation: str` field baked into its JSON — there is no standalone, independently-queryable Explanation entity. |

**What this means for the request as written:** designing a *new* "EKU
model" as a distinct entity would mean building a second, parallel
knowledge-representation table next to the one that already exists, is
tested, and is already the input to four generation workers. That would
violate "100% backward compatible" and "do not redesign" simultaneously —
it's the exact duplication those constraints exist to prevent. This ADR
therefore does not introduce a new table called `EducationalKnowledgeUnit`.
It formalizes `KnowledgeUnit` as the EKU — the same entity, the conceptual
name "Educational Knowledge Unit" applied to it in documentation and
product language — and designs the specific, additive relationships needed
to close the six real gaps in the table above.

## Decision

### 1. Naming: EKU is a conceptual name, not a new class
`KnowledgeUnit` keeps its name in code and in the schema. Renaming a
shipped, referenced-from-three-other-modules class for a documentation
label would be pure churn — every import, every FK comment, every prior
ADR's cross-reference would need updating for zero behavioral change. "EKU"
and "Educational Knowledge Unit" are adopted as the term this project uses
when talking *about* `KnowledgeUnit`'s role, starting with this ADR.

### 2. Relationship model — what's added, what's deferred, and why

**Added: `KnowledgeUnit.ncert_reference`** (nullable `VARCHAR(300)`).
Today a citation requires two hops (`source_section_id` →
`IngestionSection.source_page`/`heading`, or `concept_id` →
`Concept.ncert_reference`). A denormalized, single-hop reference computed
once at creation time (from the section's heading + page + the chapter's
own reference) is the same fast-path-denormalization pattern ADR-0025
already used for `content_versions.knowledge_unit_id` — the FK chain stays
the source of truth; this column is a convenience for the common case
(AI Tutor and flashcards both need "cite where this came from" cheaply,
on every request, not via a join every time).

**Closed via wiring, not new schema: `VisualAsset.knowledge_unit_id`
population.** The column already exists (ADR-0026). When
`KnowledgeStructuringService.structure_section` creates a `PASSED` unit, it
already knows `section.source_page`; associating any `VisualAsset` rows
detected on that same page is a service-layer change, not a schema change.

**New table: `learning.knowledge_unit_mastery`** — mirrors
`ConceptMastery`'s exact, already-proven shape (`user_id`,
`knowledge_unit_id`, `attempts_count`, `correct_count`, `mastery_score`,
`mastery_level`, `last_attempt_at`, `updated_at`; unique on
`(user_id, knowledge_unit_id)`). This is the real mechanism for "Weak Topic
Analysis powered by Knowledge Units": today, a wrong answer only tells you
"weak at Ohm's Law" (the whole concept); tracing the answered question back
through the existing `content_version_knowledge_units` join table to its
specific contributing unit(s) lets the same signal say "weak at *this*
specific fact about Ohm's Law" — a real capability upgrade, not a
speculative one, since the join table making it possible already exists
and is populated.

**New table: `academic.concept_prerequisites`** — a plain directed edge
(`concept_id`, `prerequisite_concept_id`, both FK to `academic.concepts`,
`CASCADE`; unique on the pair). Scoped deliberately small: one edge type
("requires"), no edge weighting, no edge metadata, no generic graph engine.
This is the entire "Concept Graph" this ADR proposes — enough to answer
"what should this student review before attempting this concept," not a
speculative general-purpose graph database.

**Deferred by design: a standalone Explanation entity.** `KnowledgeUnit.summary`
is already the grounded "why" behind a generated fact, and the `QUESTION`
body's own `explanation` field already serves students at read time.
Building a separate `explanations` table, addressable independently of its
parent question, has no second real consumer today — nothing needs to
query "all explanations" independent of the question they belong to. Per
this project's standing anti-speculative-generality discipline (applied
identically in the ADR-0026 architecture review to OCR/vision/layout
plugins), this is named and explicitly not built, not silently skipped.

**Already extensible, no change needed: Future Learning Assets.**
`content_version_knowledge_units` references `content_version_id`, not "one
of these four known content types" — a fifth content type (say, a mind map
or an audio summary, both already named as aspirational in ADR-0023's
scope discussion) gets the exact same Knowledge-Unit traceability the
moment it's added to `CONTENT_TYPES`, with no schema change. This is a
genuine strength already present in ADR-0025's design, worth confirming
rather than re-solving.

### 3. Database changes — additive only

- `ALTER TABLE knowledge.knowledge_units ADD COLUMN ncert_reference VARCHAR(300) NULL` — nullable, no backfill (historical units stay `NULL`, same precedent as every prior additive column in this project).
- `CREATE TABLE learning.knowledge_unit_mastery` — new table, same shape and constraints as `ConceptMastery`.
- `CREATE TABLE academic.concept_prerequisites` — new table.

No table is renamed, dropped, or has a column removed. No existing column
gains a `NOT NULL` constraint. Every existing query, model, and test
continues to work unmodified — this ADR's Phase A (below) is designed to
be provably a no-op for all existing behavior, the same non-interference
bar every prior ADR in this project has been held to.

### 4. Two real open questions this ADR does not resolve
- **Who authors a `concept_prerequisites` edge?** Manual admin curation
  (matches the existing ECAEP editorial workflow) versus AI-suggested
  edges (a new agent, out of scope here) is a real decision with cost and
  quality-control implications neither this ADR nor its requester has
  settled. Flagged for a follow-up ADR before Phase E is built, not decided
  by default here.
- **Does `knowledge_unit_mastery` apply to all four generated content
  types, or only Questions?** MCQs have a clear right/wrong signal to
  recompute mastery from; Concept Notes and Revision Sheets don't have an
  "attempt" in the same sense. This ADR scopes Phase D to Questions only —
  extending it to other types is a separate decision once there's a real
  notion of "attempting" a note or sheet.

## Phased implementation (not built in this ADR)

**Phase A — Schema only.** The three additive changes in §3, plus tests
proving zero behavioral change to any existing query or counter (the same
non-interference bar as ADR-0024's PR 1). No service code changes.

**Phase B — AI Tutor integration.** `TutorService.explain()` additionally
fetches `PASSED` Knowledge Units for the concept (via the existing
`concept_id` FK — no new schema) and cites their `ncert_reference` in the
response, alongside what it already reads. Service-layer only.

**Phase C — Close the `VisualAsset.knowledge_unit_id` gap.**
`KnowledgeStructuringService` associates same-page `VisualAsset` rows to
the unit it creates. Service-layer only, using schema that already exists.

**Phase D — `knowledge_unit_mastery` population, Questions only.**
`MastureService.recompute_for_content_items` (the existing hook, already
triggered after answer submission) additionally traces each answered
`QUESTION` content item through `content_version_knowledge_units` to its
contributing unit(s) and updates `knowledge_unit_mastery` the same way it
already updates `ConceptMastery`/`MicroCompetencyMastery`.

**Phase E — `concept_prerequisites` authoring and consumption.** Blocked
on the open question in §4; not scheduled until that's resolved.

Each phase is independently shippable and independently reviewable — the
same "one bounded PR at a time" discipline as ADR-0024/0025's PR1/PR2
split, not a single large change.

## Risks

- **A third near-identical mastery table.** `knowledge_unit_mastery` will
  be the third table sharing almost exactly `ConceptMastery`'s column set
  (after `MicroCompetencyMastery`). This is real, growing duplication worth
  naming — a shared base/mixin is a legitimate future refactor — but not
  fixed in this ADR, since doing so now means touching two already-shipped,
  tested tables for a benefit that's still theoretical until Phase D
  actually ships.
- **No cycle detection in `concept_prerequisites`.** A future importer
  could create A→requires→B→requires→A. Flagged, not solved — building
  cycle-detection before a single real prerequisite edge exists in the
  data would be solving an imagined problem, not an observed one.
- **`ncert_reference` denormalization can drift.** Computed once at
  creation, not kept in sync if the source section or chapter reference
  later changes. Accepted — the identical tradeoff ADR-0025 already made
  for its own denormalized columns.

## Tests (per phase, to be written when that phase is implemented)

- **Phase A:** migration apply/rollback; model round-trip tests for the
  two new tables and the new column; full existing suite stays green
  (currently 131/131) with zero new failures, proving the additive changes
  are inert until Phase B–D's service code reads them.
- **Phase B:** `TutorService` test asserting it fetches and cites
  `PASSED` Knowledge Units for a concept, with an existing-notes-only
  concept still working exactly as it does today (non-regression).
- **Phase C:** a section with detected `VisualAsset` rows on its source
  page gets those rows' `knowledge_unit_id` populated after structuring;
  existing visual-asset counts and detection tests unaffected.
- **Phase D:** answering a question updates `knowledge_unit_mastery` for
  its contributing unit(s) exactly as `recompute_for_content_items`
  already updates `ConceptMastery`; existing concept/micro-competency
  mastery tests unaffected.
- **Phase E:** none scoped until the authoring-mechanism question is
  resolved.

## Acceptance criteria

This ADR is ready to move from Proposed to Accepted when:
1. The "no rename, `KnowledgeUnit` stays `KnowledgeUnit`" decision (§1) is confirmed.
2. One specific phase (A–D; E is blocked) is chosen as the next real PR — matching how every prior ADR in this project went from a full proposal to one scoped, reviewed increment before any code was written.
3. Phase A, once built, leaves the full backend suite green with no existing test modified — proving the additive schema changes are truly inert until later phases wire them up.

## Phase A audit — every consumer that bypasses KnowledgeUnit today

Verified by direct inspection (grep for any `KnowledgeUnit`/`knowledge_unit`
reference across every file in `app/modules/ai/services/` and
`app/modules/learning/services/`), not assumed:

| Service | Touches `KnowledgeUnit` today? |
|---|---|
| `ingestion_pipeline_service.py` (MCQ/Flashcard/Note/Revision Sheet generation) | **Yes** — ADR-0025 |
| `knowledge_structuring_service.py` | **Yes** — creates them, ADR-0024 |
| `tutor_service.py` (AI Tutor) | No |
| `question_generator_service.py` (admin "generate question" button, Sprint 5) | No |
| `study_planner_service.py` | No |
| `evaluator_service.py` | No |
| `mastery_service.py` (Concept/Micro-Competency mastery) | No |
| `recommendation_service.py` | No |

**Routed through KnowledgeUnit by this implementation (Phase B/D below):**
`tutor_service.py` (via the new `KnowledgeService`) and `mastery_service.py`
(via the new `knowledge_unit_mastery` table). **Not routed through it, and
explicitly not touched by this implementation:** `question_generator_service.py`,
`study_planner_service.py`, `evaluator_service.py`, `recommendation_service.py`
— each predates ADR-0024, each works today, and none was named in ADR-0028's
six target consumers. Rewiring them is real future work (tracked, not
silently done here) rather than scope creep into services nobody asked to
change.

## Self-review (implementation, against the checklist requested)

- **Zero breaking changes** — confirmed. No table renamed or dropped, no
  column removed, no existing column made `NOT NULL`. `TutorService.explain()`'s
  five original response keys (`answer`, `concept_name`, `ncert_reference`,
  `is_fallback`, `cited_published_notes`) are unchanged in name and meaning;
  two new keys (`knowledge_units_cited`, `visual_assets_available`) were
  added additively.
- **Existing tests still pass** — full backend suite: **142/142 passing**
  (up from 131 before this implementation; 11 new tests added, zero
  existing tests modified).
- **New migrations are additive** — two migrations, both pure `ADD COLUMN`/
  `CREATE TABLE`, applied and verified against both the dev and test
  databases. Downgrade paths included and symmetric.
- **AI Tutor uses KnowledgeService** — confirmed by inspection
  (`TutorService` no longer imports `AIRepository`) and by test
  (`test_tutor_service.py` proves it reads `PASSED` Knowledge Units when
  they exist and falls back to `Concept.summary` when they don't, matching
  pre-ADR-0028 behavior for concepts ingestion hasn't reached yet).
- **Visual Assets linked to Knowledge Units** — confirmed by test
  (`test_passed_unit_links_same_page_visual_assets`): a same-page,
  previously-unlinked `VisualAsset` gets `knowledge_unit_id` populated the
  moment its section's Knowledge Unit passes; a `FAILED` unit links
  nothing (`test_failed_unit_does_not_link_visual_assets`).
- **Mastery model implemented** — `knowledge_unit_mastery` exists, mirrors
  `ConceptMastery`'s real shape (not the unpopulatable expanded column list
  a later prompt suggested — see that turn's stated conflict), and is
  populated by the real `recompute_for_content_items` hook already
  triggered on answer submission. Verified end-to-end through the actual
  HTTP practice-attempt-submit flow, not a mocked shortcut
  (`test_knowledge_unit_mastery.py`).
- **Concept Graph implemented** — **not implemented**, by design. ADR-0028
  scoped this as blocked pending an unresolved authoring-mechanism
  question; a later turn asked for a larger, generalized graph instead of
  resolving that question, and was declined for the same reason (see that
  turn's response). Still open.
- **Embedding infrastructure added** — **not implemented**, by design.
  ADR-0024 explicitly pre-decided against exactly this (a placeholder
  embedding column with nothing generating values). A later turn's request
  for it was declined on that basis. Still open, pending an actual pgvector
  activation decision.
- **Provenance maintained** — every Knowledge-Unit-sourced artifact this
  implementation touches (generated Questions/Flashcards/Notes/Sheets via
  ADR-0025, Visual Assets via Phase C, mastery signals via Phase D) traces
  back to a specific `KnowledgeUnit.id`. Artifacts that predate ADR-0024
  (Sprint 4 seeded questions, non-ingested CMS content) have no such trace
  and are not retroactively backfilled — consistent with every prior ADR's
  non-backfill precedent, not a gap unique to this one.
- **Clean Architecture preserved** — `TutorService` (application service)
  → `KnowledgeService` (domain service) → `KnowledgeRepository`/`AIRepository`
  (repositories) → ORM models. No SQL in `TutorService` or `KnowledgeService`;
  all queries live in the repository layer, matching the pattern already
  used by every other module in this codebase.

## Remaining technical debt

- **A third near-identical mastery table.** `knowledge_unit_mastery` joins
  `ConceptMastery` and `MicroCompetencyMastery` as a third table sharing
  almost the same column set. Flagged in the original ADR-0028 design as a
  legitimate future refactor (a shared base/mixin), not fixed here — doing
  so now would mean touching two already-shipped, tested tables for a
  benefit that's still theoretical.
- **`KnowledgeService.get_revision_material` only draws from published
  Concept Notes**, not Flashcards or MCQs, because that's the one query
  `AIRepository` already had. A real "all revision material for a concept"
  view spanning every content type is future work, not invented here.
- **`question_generator_service.py`, `study_planner_service.py`,
  `evaluator_service.py`, and `recommendation_service.py` still bypass
  KnowledgeUnit** (see Phase A audit). None were named as ADR-0028 target
  consumers; rewiring them is real, separately-scoped future work.

## Future enhancement opportunities

- Resolve the Concept Graph authoring-mechanism question (manual curation
  vs. an AI-suggestion agent), then build the small `concept_prerequisites`
  edge table ADR-0028 originally scoped — not the larger generalized graph
  a later request proposed without resolving that question first.
- Activate pgvector as its own infrastructure decision, then add the
  embeddings table and column in the same work that starts actually
  generating values for it — never speculatively ahead of it.
- Extend `GetWeakAreas`-style Knowledge-Unit-grained analysis into the
  existing recommendation/revision-queue features (ADR-0016), so a
  student's "what to review next" list can eventually point at the specific
  atomic fact they're weak on, not just the whole concept.

## Consequences

`KnowledgeUnit` becomes, in name and in a concretely scoped set of new
relationships, the entity this project's documentation has been calling it
informally all along — the canonical, citable unit of verified knowledge
behind every generated asset. Three real gaps (Tutor, Adaptive
Learning/Weak-Topic, Concept Graph) get a specific, additive, non-breaking
path to close, phase by phase, rather than a single large migration. Two
gaps (Figures, Future Learning Assets) turn out to already have most or all
of what they need — this ADR's investigation is itself the deliverable
there. One gap (a standalone Explanation entity) is named and deliberately
not built, for the same reason this project has declined every other
speculative abstraction proposed this session: no second real consumer
exists to prove the shape it should take.
