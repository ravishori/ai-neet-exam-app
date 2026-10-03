# Fresh MCQ Generation — Inspection, Source Inventory, and Blocker Report

**Date:** 2026-10-03. **No MCQs were generated or imported in this task.** Inspection-only, as the findings below make clear why proceeding to bulk generation would violate this task's own quality and no-unauthorized-AI-cost rules.

## 1. Source inventory

| Source | Status | Notes |
|---|---|---|
| `StudyMaterial/` (76 registered NCERT PDFs, custom filenames) | Ingested | 1,112 knowledge units (local dev), 381 (production) — from this session's earlier audits |
| `NCERT Books/Class {11,12}/{Biology,Chemistry 1&2,Physics}.zip` (newly provided) | **Not ingested** | Official NCERT short-filename convention (`kebo1*`, `keph1*`); not checksummed against `StudyMaterial/` for overlap in this pass (flagged previously, still not done) |
| `NEET_Subject_Glossaries.zip` | Accessible, already audited | Prior session's finding stands: **placeholder boilerplate, no real definitions** — unusable as a generation source |
| `NEET_Subject_Glossaries(1).zip` (requested by this task) | **Not found / inaccessible** | Only the un-suffixed `NEET_Subject_Glossaries.zip` exists on disk; the "(1)" variant does not exist — reported, not assumed accessible |
| `NEET_UG_2026_Detailed_Glossary.xlsx`, `NEET_UG_2026_Curriculum_Taxonomy.txt`, `NEETSyllabus.txt` | Accessible | Classification/taxonomy references only, per this task's own rule 2 ("not as standalone proof of scientific answers") |
| `PYExamPapers/2024/NEET 2024 Paper - {Chemistry,Physics,Botany}.pdf` (newly provided) | Accessible, not yet parsed into the PYQ pipeline | Real NEET 2024 question papers |
| `PYExamPapers/NEET-2025-Answer-Key.pdf` (newly provided) | **Accessible — a genuine official answer key** | This directly answers an open question from the prior zero-cost-pilot audit ("no answer-key source located") — one now exists. Not yet parsed or linked to any question set in this task (out of this task's own scope — it's about *resolving* existing PYQs, not generating new ones; flagged for a separate task) |
| `PYExamPapers/NEET-2026-WITH-WATER-MARK-COMP04.05.2026.pdf`, `RE-NEET-QUESTIONS-COMPRESSED.pdf` (newly provided) | Accessible, not parsed | Likely further question papers; content not inspected in this pass |

## 2. Existing database state (local dev, read-only)

```
cms.content_items: 0
cms.question_fingerprints: 0
```
**The Content Factory's entire MCQ output tables are empty** — this pipeline has never actually produced a single stored question in this database, despite substantial existing schema/code for it.

## 3. Existing MCQ-generation infrastructure — inspected

Found: `app/modules/cms/mcq/p2_3/` (generation, validation, dedup, human-gold-review scaffolding) plus a full schema (`content_items`, `generation_jobs`, `generation_candidates`, `qa_results`, `question_fingerprints` for dedup, `question_blueprints`, `review_sessions`, etc.) — **substantial, real, reusable infrastructure.**

**Critical finding:** every generation path in this pipeline routes through `app/modules/cms/mcq/p2_3/provider_routing.py`, which selects an AI provider (Gemini or OpenAI) to actually author question text. **There is no deterministic, non-AI MCQ-authoring path in this codebase.** The retrieval/grounding machinery used elsewhere in this project (`is_fact_grounded`, knowledge-unit retrieval) is built to *validate* a claim against a source, not to *compose* a new, well-formed four-option question with a defensible explanation from raw text — that composition step is inherently generative and was always designed to be done by an AI model.

**"Sol/Terra" role architecture:** searched the codebase for this naming — **not found anywhere**. No service, model, or module uses "Sol" or "Terra" as a role name. **Reporting this limitation directly, as instructed, rather than pretending to have used it.**

## 4. Hard blocker

**10,000 genuinely new, quality-verified MCQs cannot be generated with zero paid-API cost using this codebase's existing infrastructure.** This is not a capacity or time limitation — it is architectural: the only question-authoring code path that exists requires an AI provider call, and this task explicitly prohibits invoking one (and the fail-closed guard implemented in the immediately-prior task would correctly block it even if attempted).

**What a non-AI pipeline *could* mechanically produce** — and why it would not meet this task's own quality bar:
- A cloze/fill-in-the-blank question auto-generated from a single `structured_facts` sentence (mask one term, use 3 other facts' terms as distractors). This is mechanically possible with existing data, but produces exactly the kind of "trivial rewording" and "excessive recall-only" question this task's Section 3 explicitly says to avoid, and the distractors would not be independently checked for "accidental correctness" the way a real MCQ requires. **I did not build or run this**, since it would not satisfy "NEET-appropriate... avoid trivial rewording" and would misrepresent template output as a verified MCQ.

**I am not proposing a pilot of fabricated or template-generated questions**, per this task's own instruction: *"Do not force the target by lowering validation standards."* Generating anything at volume right now would only be possible by lowering the explicitly-stated quality bar.

## 5. What this task's own instructions direct me to do here

Per Section 7: *"If the task cannot reach adequate quality with currently authorized resources, report the blocker and propose a bounded pilot rather than silently changing provider settings."* **Done — this report is that disclosure.** No provider setting was changed, no guard was bypassed, no paid call was made.

**Proposed bounded pilot, for your explicit authorization, not yet run:** once you decide how to proceed, two real options exist:
1. **Authorize a small, cost-estimated Gemini batch** (e.g., 100 questions) through the *existing* Content Factory pipeline (reusing `generation_jobs`/`generation_candidates`/the human-gold review gate already in the schema) — this is real, already-built infrastructure, not something I would need to invent. I can give you an exact cost estimate before running it, once you confirm Gemini re-enablement for this specific, bounded purpose (distinct from PYQ resolution).
2. **A genuinely deterministic cloze-style generator**, explicitly labeled as low-quality/recall-only and routed to `PENDING_REVIEW` (never auto-verified), if you want a zero-cost experiment despite the quality tradeoff disclosed above.

Neither has been started. Both require your decision before any further work.

## 6. Preservation confirmation

- No existing PYQ was touched.
- No schema, migration, or production configuration was changed.
- No Gemini or other paid API call was made.
- `cms.content_items`/`question_fingerprints`: unchanged (0 → 0).

## 7. Required report fields — answered honestly

| Field | Value |
|---|---|
| Starting question count | 12,396 PYQs (unchanged); 0 Content-Factory-generated MCQs |
| Generated / validated / verified / rejected / duplicate / imported | **0 / 0 / 0 / 0 / 0 / 0** — nothing was generated |
| Subject/class/chapter distribution | N/A — no generation occurred |
| Final net-new count vs. 10,000 target | **0 of 10,000.** Gap: 10,000, blocked by the architectural dependency in Section 3–4 |
| Cost incurred | **$0** |
| Tests run | None new (no code was changed in this task) |
| Outstanding blocker | No non-AI MCQ-authoring path exists in this codebase; generating real, quality-bar-meeting questions requires either an authorized, cost-estimated AI call or accepting a disclosed, lower-quality deterministic alternative |

**I am not claiming any progress toward 10,000 that didn't happen.** This report's purpose is the inspection and blocker disclosure the task itself calls for when adequate-quality generation isn't reachable with currently authorized resources.
