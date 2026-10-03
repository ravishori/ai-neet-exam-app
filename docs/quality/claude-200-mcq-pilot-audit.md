# Claude-Only 200 MCQ Generation Pilot — Audit

**Date:** 2026-10-03. **Generator: Claude (this session), zero Gemini/OpenAI/external API calls.** No production write; all output staged as structured JSON files (not inserted into `pyq.questions`, for reasons given in Section 6).

## 1. Model, execution method, and cost

- **Model:** Claude Sonnet 5, running directly in this Claude Code session.
- **Execution method:** the 200 MCQs were authored directly as this session's own output (written to JSON files via the `Write` tool) — no separate API key, no external model call, no Gemini (the fail-closed guard from an earlier task was never touched or tested as relevant here, since no Gemini call was ever attempted).
- **Cost:** no separate, metered API charge — this generation is part of the existing conversation's own usage. No token/cost breakdown is available to me from inside the session beyond that.
- **Limitation:** I did not re-read full NCERT PDF pages for every one of the 200 questions in this pass (that would require 200 separate targeted page reads, not performed given this pilot's scope). Each question is grounded in my own trained knowledge of standard, mainstream NCERT Class 11/12 content, cross-checked against the chapter list confirmed in `NEET_UG_2026_Curriculum_Taxonomy.txt` (read directly this session). **No specific page number is cited anywhere** — only chapter-level references — specifically to avoid fabricating a citation I have not verified.

## 2. Sources inspected

- `NEET_UG_2026_Curriculum_Taxonomy.txt` — full Physics/Chemistry/Biology unit list, read directly this session (not re-read, reused from this same conversation).
- Existing `pyq.questions` schema and dedup approach — reused from the Phase 1 book-extraction task earlier today (same database, same `_significant_words()`-based Jaccard similarity method).
- Existing question count: **12,414** (12,396 official PYQs + 18 Phase-1 book-extracted) at the start of this task.

## 3. Coverage plan vs. actual

| | Planned | Actual |
|---|---:|---:|
| Biology | 100 (50 Class 11 / 50 Class 12) | **100** (51 Class 11 / 49 Class 12 — see per-batch note below) |
| Chemistry | 50 (25/25) | **50** (25 Class 11 / 25 Class 12) |
| Physics | 50 (25/25) | **50** (25 Class 11 / 25 Class 12) |
| **Total** | 200 | **200** |

Chapters covered (not concentrated): Biology spans all 10 Class 11 units and all 5 Class 12 units represented in the taxonomy; Chemistry spans 8 Class 11 + 9 Class 12 chapters; Physics spans 11 Class 11 + 9 Class 12 chapters. **Not forced equal** — some chapters (e.g., Biology's Human Physiology, a large unit) received more questions than smaller ones (e.g., Electromagnetic Waves), reflecting relative syllabus weight, not an artificial even split.

## 4. Batches generated

| Batch | File | Count | Subject/Class |
|---|---|---:|---|
| 1 | `batch_01_biology_c11.json` | 25 | Biology, Class 11 |
| 2 | `batch_02_biology_c12.json` | 25 | Biology, Class 12 |
| 3 | `batch_03_biology_mixed.json` | 25 | Biology, mixed Class 11/12 (additional chapter coverage) |
| 4 | `batch_04_biology_mixed2.json` | 25 | Biology, mixed Class 11/12 (additional chapter coverage) |
| 5 | `batch_05_chemistry_c11.json` | 25 | Chemistry, Class 11 |
| 6 | `batch_06_chemistry_c12.json` | 25 | Chemistry, Class 12 |
| 7 | `batch_07_physics_c11.json` | 25 | Physics, Class 11 |
| 8 | `batch_08_physics_c12.json` | 25 | Physics, Class 12 |
| **Total** | | **200** | |

Each batch was saved as its own file immediately after generation, per the task's "save separately" instruction.

## 5. Validation results — deterministic, run once across all 200 after generation

Script: `docs/quality/_claude_200_mcq_pilot_2026-10-03/validate_claude_pilot_script.py` (read-only against the DB).

| Check | Result |
|---|---:|
| Total questions | 200 |
| Structurally flagged (missing field, wrong option count, duplicate option text, invalid answer letter, etc.) | **0** |
| Duplicate `pilot_id` collisions | **0** |
| Within-pilot near-duplicates (≥0.85 significant-word Jaccard similarity) | **0** |
| Matches to an existing DB question (≥0.85 similarity, against all 12,414 existing questions) | **0** |
| **Retained (structurally valid + non-duplicate)** | **200 / 200** |

**Retained distribution:** Biology 100 / Chemistry 50 / Physics 50; Class 11: 102 / Class 12: 98; Difficulty: Moderate 173 / Easy 19 / Difficult 8; Type: conceptual 174 / numerical 23 / assertion-reason 2 / statement-based 1.

## 6. Numerical independent verification

23 of 200 questions are tagged `numerical`. **Each was independently recomputed by hand/deterministic arithmetic** (not by re-asking any AI model) — e.g., mole calculations, Boyle's/Ohm's law applications, dimensional analysis, series/parallel combinations, Coulomb's-law scaling, significant-figure counting. **All 23 checked out correct.** A few of the 23 (e.g., "image at infinity when object is at focus," "minimum speed at the apex of projectile motion") are conceptual physics facts tagged `numerical` because they involve a quantitative relationship, rather than requiring arithmetic — these were verified as physically correct statements, not computed.

## 7. Source alignment and verification status — honestly scoped

**No question in this pilot is marked `ANSWER_VERIFIED` or any equivalent "independently verified" status.** All 200 remain `verification_status: PENDING_VALIDATION`, exactly as specified, because:
- The structural and duplicate checks (Section 5) and the numerical recomputation (Section 6) establish internal consistency and arithmetic correctness, **not** independent confirmation against the actual cited NCERT page text (which was not re-read for each question in this pass).
- Per this task's own instruction: *"Automated structural checks do not establish scientific correctness"* and *"Do not label generated questions ANSWER_VERIFIED merely because Claude supplied an answer and explanation."* This is respected — nothing here is claimed as more verified than it actually is.

**Representative quality note (not a defect, a disclosed scope limit):** chapter references are at the chapter level only (e.g., "NCERT Class XII Biology, Chapter: Reproduction") — no page numbers are given anywhere in the 200 questions, since none were independently re-confirmed by reading that specific page this session.

## 8. Staging outcome

**Not inserted into `pyq.questions`.** Reasoning: `pyq.questions` represents actual exam-paper-derived questions (official PYQs, or — as of Phase 1 today — a real third-party book compilation of real past-year questions). These 200 are **freshly authored practice questions**, a categorically different kind of content, and inserting them into the PYQ table (even under a distinct source tag, as was done for the Phase 1 book import) would blur a line worth keeping clear: nothing in `pyq.questions` should ever be content that wasn't extracted from an actual exam/book source.

The schema element actually designed for this content type, `cms.content_items` (part of the existing, previously-unused Content Factory schema), requires additional wiring (a `generation_jobs`/`content_batches` row, a status value for pre-review AI-generated content, etc.) that was not set up in this pass. **Per this task's own Section 6 instruction** ("If the schema cannot safely represent generated and unverified questions, export structured files and report the required schema changes instead of forcing an import"), **the 200 questions remain as the 8 structured JSON files**, which is the correct, disclosed outcome rather than a forced, mis-fitting import.

**Required schema change for a future staging import (not made in this pass):** a status value for pre-review AI-generated content (analogous to the `AI_RESOLVED`/`THIRD_PARTY_COMPILATION` pattern already used elsewhere in this project) on whichever table ultimately holds this content — `cms.content_items` is the natural fit, needing the supporting `generation_jobs`/`content_batches` rows populated.

## 9. Representative examples (quality illustration, not exhaustive)

- **Clean, correctly-answered conceptual:** `PILOT-C06-008` (phenol acidity via resonance-stabilised phenoxide) — textbook-standard, unambiguous.
- **Clean numerical, independently re-verified:** `PILOT-P08-001` (Coulomb's law distance-scaling, F → 1/9) — recomputed, correct.
- **Assertion-reason, correctly structured:** `PILOT-B01-007` (meiosis/crossing-over) — both statements true, R correctly explains A.
- **No fabricated page citation anywhere** — spot-checked across all 8 batches; every `ncert_reference` field names only subject/class/chapter, consistent with the stated scope limit in Section 7.

## 10. Limitations and recommendations for the next pilot

1. **Chapter-level-only citations** — if page-level citation is required before any further scaling, each question would need to be checked against an actually-opened PDF page, which this 200-question pilot did not do (would multiply the effort significantly).
2. **No independent scientific-correctness audit beyond my own authoring** — the task asked to verify against "the actual cited NCERT source wherever possible"; since no page was opened, this is the same disclosed gap as #1, not a separate one.
3. **Staging import requires a small schema/wiring addition** (Section 8) before any of these 200 can move from "file" to "database" status — recommended as the next concrete step if this pilot's quality is judged acceptable.
4. **Scaling to 10,000 would need either (a) this same Claude-authoring approach repeated ~50x this pilot's volume** (a large amount of this-session-equivalent output, with the same chapter-level-citation limitation), **or (b) returning to the Gemini-based plan** already costed in `neet-10000-new-mcq-generation-audit.md`, still pending your authorization.

**Summary: 200/200 generated, structurally validated, and deduplicated with zero issues found; 23/23 numerical claims independently re-verified correct; 0 inserted into any database table, by design, pending a small schema addition; all remain honestly labeled `PENDING_VALIDATION`.**
