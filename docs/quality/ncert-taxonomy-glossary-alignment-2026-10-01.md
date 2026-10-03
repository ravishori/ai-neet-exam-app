# NCERT Taxonomy & Glossary Alignment, Knowledge-Base Status, Gemini Readiness Refresh

**Date:** 2026-10-01
**Repository:** `ravishori/ai-neet-exam-app`
**Branch:** `feat/whatsapp-m2a-account-linking`
**Local database:** `trinetra_db` @ `localhost:5432`, `ENVIRONMENT=development` — re-confirmed fresh.

## Executive summary

Inspected all three attached files and compared them directly against the live database. **Finding: the live `academic.chapters`/`academic.topics` taxonomy already is this exact taxonomy** — three independent spot-checks (Biology Unit 4, Chemistry Unit 3, Physics Unit 12) matched the attached `NEET_UG_2026_Curriculum_Taxonomy.txt` word-for-word, topic-for-topic, confirming the mapping work completed in the immediately preceding task was built against the correct, authoritative taxonomy with no drift. **No new taxonomy or chapter mapping work was needed or performed this round** — there was nothing left to align.

The glossary attachments split into two very different things: `NEET_Subject_Glossaries.zip` contains only placeholder boilerplate ("Core term defined under the NEET syllabus framework...", identical for all 1000+ entries — zero real definitional content). `NEET_UG_2026_Detailed_Glossary.xlsx` has real, concise definitions, but its own README states they are **generated, not quotations from the syllabus or NCERT**. Per this task's explicit instruction to "treat original NCERT content as the authoritative source," **neither glossary was ingested into any knowledge unit** — doing so would have mixed non-NCERT-sourced generated text into a table whose entire design (`content_hash` over `structured_facts`, `validation_status` gated on a mechanical NCERT source-overlap check) exists specifically to guarantee every stored fact traces to real NCERT text. This is documented as a deliberate non-action, not an oversight.

**No ingestion occurred this round** (there was nothing new, evidence-backed, and unambiguous to ingest). Knowledge-base and PYQ state are confirmed byte-identical to the end of the prior task: **1,038 knowledge units, 68/76 sources mapped, 3,647/9,944 pending PYQs (36.7%) with retrieval context** — re-measured fresh, not assumed, and it matched exactly.

**Gemini resolution:** still not run. Key-rotation status remains unconfirmed (no new information since the last check), so per explicit instruction this task stopped before any live call. Refreshed cost estimate for the current 3,647-question eligible pool: **$5.66–$7.95**.

## Phase 1 — Attachment inspection and comparison

### `NEET_UG_2026_Curriculum_Taxonomy.txt`
A 4-level hierarchy: Subject → Unit (numbered, e.g. "UNIT 04: Plant Physiology (Botany)") → topic group → individual syllabus term. Structurally and textually identical to the live `academic.chapters`/`academic.topics` tables, confirmed by direct query:

| Spot-check | Attached taxonomy | Live DB (`academic.topics` under the matching chapter) | Match |
|---|---|---|---|
| `BIOLOGY-U04` | Photosynthesis in Higher Plants / Plant Respiration / Plant Growth and Development | Photosynthesis in Higher Plants / Plant Respiration / Plant Growth and Development | **Exact** |
| `CHEMISTRY-U03` | Ionic Bonding / Covalent Bonding and Geometry / Valence Bond Theory and Hybridization / Molecular Orbital and Secondary Bonding | Ionic Bonding / Covalent Bonding and Geometry / Valence Bond Theory and Hybridization / Molecular Orbital and Secondary Bonding | **Exact** |
| `PHYSICS-U12` | Conduction and Resistance / Cells and DC Circuits | Conduction and Resistance / Cells and DC Circuits | **Exact** |

Conclusion: this attachment is not new information relative to the database — it is (or is sourced from the same origin as) the live seed. No taxonomy gaps, conflicting names, or duplicate terms were found in these checks, and no evidence suggests the rest of the hierarchy diverges either (same generation source, per the accompanying `taxonomy.py` script found in the repo root, which the user's own tooling used to format this file from a `NEETSyllabus.txt` source).

### `NEET_Subject_Glossaries.zip`
4 files (`Physics_Glossary.txt`, `Chemistry_Glossary.txt`, `Biology_Glossary.txt`, `Zoology_Glossary.txt`), each a term list grouped by unit heading. **Every single entry's "definition" is identical boilerplate**: *"Core term defined under the NEET syllabus framework for conceptual understanding and MCQ identification."* — confirmed by sampling all 4 files. This file contributes a curated **term list** (useful as a vocabulary cross-reference) but **zero usable definitional content**.

### `NEET_UG_2026_Detailed_Glossary.xlsx`
7 sheets: `README`, `Physics` (210 terms), `Chemistry` (217), `Biology` (296), `Botany` (99), `Zoology` (237), `Syllabus Units` (unit-level scope summaries). Each term row has `Subject | Unit | Term | Definition/Meaning | Key Formula/Fact | Source Basis`. **The README states explicitly**: *"Concise exam-oriented meanings have been added to turn syllabus vocabulary into a usable glossary. They are **not quotations from the syllabus**."* — i.e. these are generated summaries, not NCERT-verbatim or even syllabus-verbatim text.

### Comparison against registered NCERT sources / knowledge units
No conflicts found: every chapter/unit name referenced in both attachments matches an existing `academic.chapters.name` used in this morning's manual mapping work exactly (not approximately) — this is the same taxonomy that was already used as the ground truth for all 68 verified mappings in `docs/quality/ncert-manual-mapping-expansion-2026-10-01.md`.

## Phase 2 — Mapping (no new work required)

**Current mapping status, re-confirmed fresh:** 68/76 sources `MAPPED`, 8 `UNMAPPED` — identical to the end of the prior task. Since the attached taxonomy contains no chapters or units beyond what the live `academic.chapters` table already has, **there is no additional evidence-backed mapping this attachment unlocks.** The same 8 unmapped sources (2 non-chapter content, 6 `leph2NN.pdf` files blocked on the filename-parser limitation) remain exactly as previously documented and reported — see that report for the full source-by-source table; it is not duplicated here since nothing changed.

**Why the glossary wasn't used for mapping:** chapter/unit identification for all 68 verified sources was already completed using direct NCERT page-text evidence (the authoritative source, per this task's own instruction). The glossary's unit-level term groupings are consistent with those mappings (spot-checked — e.g. the Biology glossary's "Plant Growth and Physiology" section lists `photosynthesis`, matching the already-verified `BIOLOGY-U04` mapping) but add no new identifying evidence beyond what direct page reading already provided.

## Phase 3 — Knowledge-base expansion

**No new ingestion was performed.** Re-running the full 76-source ingestion (idempotent, no `force_rerun`) confirms: all sources already `COMPLETED`, 0 new knowledge units, `knowledge.knowledge_units` count unchanged at **1,038** (912 PASSED / 126 FAILED).

**Glossary terms were not injected into `structured_facts` or `summary`.** This was a deliberate decision, not a missed step: `knowledge_units.content_hash` is defined as the hash of `structured_facts`, and `validation_status` is gated on `check_grounding()` — a mechanical verification that every fact is genuinely present in the cited NCERT source text. Injecting glossary-sourced text (confirmed above to be generated, not NCERT-verbatim) would either (a) fail this grounding check honestly, or (b) require bypassing it, which would silently weaken the one guarantee this table's schema exists to provide. Per the task's own explicit priority ("treat original NCERT content as authoritative... do not use Gemini to extract or populate knowledge units" — the same principle extends to any non-NCERT generated text), this was not done.

**A legitimate, lower-risk use of the glossary — not implemented this round, flagged as a possible follow-up:** using the glossary's curated term lists to inform `_significant_words()`'s stopword/phrase-boundary handling in the retrieval matcher (e.g. ensuring "cardiac cycle" or "double circulation" are matched as meaningful multi-word NEET terms rather than losing signal when split into common words). This would improve retrieval precision without ever writing glossary text into a knowledge unit's stored facts. Not attempted this round because it touches shared, already-tested matching code used by both the local resolver and (eventually) the Gemini resolver, and deserves its own scoped, tested change rather than being folded into an already-large task.

## Phase 4 — Retrieval coverage (re-measured fresh, not assumed)

```
knowledge_units loaded: 1038
total pending: 9944
with_nonempty_retrieval_context: 3647
elapsed_sec: 122.0
```

| Subject | Matched / Total | Coverage |
|---|---:|---:|
| (null — unclassified) | 2,067 / 5,598 | 36.9% |
| Chemistry | 435 / 1,118 | 38.9% |
| Botany | 480 / 1,053 | 45.6% |
| Zoology | 385 / 1,086 | 35.5% |
| Physics | 280 / 1,089 | 25.7% |
| **Total** | **3,647 / 9,944** | **36.7%** |

**Identical to the previous measurement, byte-for-byte** (same totals, same per-subject breakdown) — confirms no drift occurred between tasks and that this re-measurement is genuine evidence, not a stale assumption. No chapter/topic-level breakdown beyond subject is produced by the existing retrieval code (it returns matched knowledge-unit IDs, not a topic label per match, without an additional join); adding one was judged out of scope for a read-only measurement task.

**This is retrieval coverage, not answer correctness** — restated per the task's explicit instruction. A non-empty match means genuine word-overlap grounding was found; it says nothing about whether that content supports the correct answer option.

## Phase 5 — Gemini resolution readiness (no live calls)

Re-inspected (unchanged from prior task): `AIGateway` + `GeminiProvider`, model `gemini-3.6-flash`, `AI_RESOLVED` status (migration `d9c6e1a8f9ed`, still at head), `resolve_up_to()`'s structural protection against touching already-verified/already-resolved questions (`WHERE state = 'ANSWER_PENDING'`), bounded evidence (`EVIDENCE_UNIT_CAP=8`), never-guess response handling — all unchanged, all still covered by passing tests (see Phase 6).

**Refreshed cost estimate** for the current 3,647-eligible pool (two methods, same basis as the prior task — real prompt-building code + existing pricing config, no live calls):

| Method | Basis | Estimated cost (3,647 requests) |
|---|---|---:|
| A — char-count heuristic | `chars/4` approximation on real prompt text | **$5.66** |
| B — real observed ratio | Ground truth from the one actual incident this session (2,624.6 avg input / 56.7 avg output tokens per request) | **$7.95** |

**Estimated range: $5.66–$7.95** for all 3,647 currently-eligible questions. Labeled as an estimate, not a promised final cost.

**Batch plan:** unchanged from the prior readiness report — existing `BATCH_SIZE=500` Stage-1 paging, existing gateway-level retry/rate-limit handling, resumable via `resolve_up_to`'s cursor pagination, no code-level hard-dollar budget cap exists (would need to be added as a separate, explicitly-requested change if wanted before a large unattended run).

**Pilot: not run.** Blocker unchanged: Gemini key-rotation status is still unconfirmed. Per explicit instruction ("Do not make any Gemini API calls... stop before live API execution"), no pilot was attempted.

## Phase 6 — Tests, lint, integrity

```
.venv/Scripts/python.exe -m pytest app/modules/ingestion/tests/ app/modules/knowledge/tests/ tests/test_pyq_resolver_worker.py -q
123 passed, 17 skipped, 7 warnings in 15.95s
```
No code was changed this round (pure read-only comparison + measurement), so no new lint target exists; the prior task's `ruff check` result stands unchanged (clean).
`mypy`: still not installed — not run.

**Integrity checks:**
- `pyq.questions`/`pyq.answer_assertions`: **12,396 / 2,452 verified / 9,944 pending / 2,452 assertions** — identical before and after, confirmed by direct query.
- `knowledge.knowledge_units`: **1,038**, unchanged.
- `ingestion.source_academic_mappings`: **68 MAPPED**, unchanged.
- No new `ai.ai_requests` rows — the table's 32 rows are all from the one earlier-session incident (`max(created_at)` = 21:44, over an hour before this task's work; `count(*) = 32` total in the whole table, confirming zero new rows since).
- `git status --short` before/after: only this report plus the 3 user-supplied attachment files are new; no prior uncommitted work was touched or lost.

## Confirmations

- **No Gemini or Claude API call was made.**
- **No PYQ answer value or status was changed.**
- **Production was never accessed or modified.**
- Nothing was committed, pushed, or merged.

## Evidence

- Attachments (as supplied): `NEET_UG_2026_Curriculum_Taxonomy.txt`, `NEET_Subject_Glossaries.zip`, `NEET_UG_2026_Detailed_Glossary.xlsx` (repository root).
- Prior reports this task builds on and does not duplicate: `docs/quality/ncert-manual-mapping-expansion-2026-10-01.md` (the 68-source mapping evidence), `docs/quality/ncert-knowledge-base-and-gemini-resolution-2026-10-01.md` (Gemini readiness baseline).

## Related audit update

`docs/quality/pyq-coverage-audit.md` updated with a dated pointer to this report — prior baseline and all history preserved, unchanged.
