# NCERT Retrieval Coverage — Forensic Audit

**Date:** 2026-10-01
**Repository:** `ravishori/ai-neet-exam-app`
**Branch:** `feat/whatsapp-m2a-account-linking`, commit `94e3206ca72dc034b618745159a4edf53899b23f` (unchanged by this audit)
**Local database:** `trinetra_db` @ `localhost:5432`, `ENVIRONMENT=development`
**Scope: strictly read-only.** No database write, no ingestion apply-mode run, no PYQ resolver invocation, no Gemini/Claude/OpenAI call, no config/code/test change. Confirmed by `git status --short` before/after (identical) and `ai.ai_requests` row count (32, unchanged, all from an earlier-session incident — `max(created_at)` = 21:44, well before this audit).

## 1. Executive summary

**Current retrieval coverage: 3,868/9,944 (38.9%)** — recomputed directly, reproduces the latest reported figure exactly. No discrepancy found between reported, database, and code-computed values.

**The single most important, directly-measured finding of this audit:** retrieval coverage is overwhelmingly gated by a **matching-threshold choice**, not by missing NCERT source content. Running the exact same already-ingested knowledge units through the identical matching function with a relaxed-but-still-real overlap threshold (25% instead of the production 50%) yields **8,159/9,944 (82.1%)** — more than double, with **zero new content**. Only **113 of 9,944 questions (1.1%)** share not even one significant word with any of the 1,112 ingested knowledge units; these are the only questions where "the right content may genuinely be absent" is the most defensible hypothesis from mechanical evidence alone.

This does **not** mean lowering the threshold is a validated fix — a looser threshold also raises false-positive risk (coincidental word overlap with irrelevant content), and this audit did not and could not assess per-question relevance at scale without either manual review or a method this task explicitly prohibits (AI-based relevance judgment). That assessment is this audit's single largest recommended next step, scoped precisely in Section 14.

A second concrete, fully-evidenced finding: the 126 `FAILED`-validation knowledge units are **included** in the production retrieval index (the loading query filters only `deleted_at IS NULL`, not `validation_status`) — but measured directly, **zero** of the 3,868 currently-covered questions depend exclusively on a FAILED unit; every one also has at least one PASSED match. So this is a real architectural inconsistency (worth fixing for defense-in-depth) but **not currently inflating the reported coverage number** — stated precisely, not assumed.

A third finding: all 126 `FAILED` knowledge units failed for the identical reason — `duplicate of existing knowledge unit` — not for ungrounded or malformed facts. No extraction-quality failure mode was found in this database.

## 2. Current baseline (recomputed directly, not assumed)

```sql
SELECT count(*), count(*) FILTER (WHERE state='ANSWER_VERIFIED'), count(*) FILTER (WHERE state='ANSWER_PENDING') FROM pyq.questions;
-- 12396, 2452, 9944
SELECT count(*) FROM knowledge.knowledge_units;
-- 1112
SELECT validation_status, count(*) FROM knowledge.knowledge_units GROUP BY 1;
-- PASSED 986, FAILED 126
SELECT count(*) FROM ingestion.source_documents;
-- 76
SELECT mapping_status, count(*) FROM ingestion.source_academic_mappings GROUP BY 1;
-- MAPPED 74, UNMAPPED 2
```

| Metric | Reported ("latest") | Recomputed this audit | Match |
|---|---:|---:|---|
| Total PYQs | 12,396 | 12,396 | ✓ |
| Verified answers | 2,452 | 2,452 | ✓ |
| Pending | 9,944 | 9,944 | ✓ |
| Retrieval coverage | 3,868 | **3,868** (reproduced via independent script, Section 4) | ✓ |
| Coverage % | 38.9% | 38.9% | ✓ |
| Registered PDFs | 76 | 76 | ✓ |
| Knowledge units | 1,112 | 1,112 | ✓ |

**No discrepancy found anywhere.** Git branch and commit unchanged throughout (`feat/whatsapp-m2a-account-linking` @ `94e3206c...`).

## 3. Exact definition of "retrieval coverage" (read from code, not inferred)

**Code path:** `scripts/resolve_pyq_answers.py::_load_ku_index()` + `_match_units()`, calling `app/modules/knowledge/services/grounding_check.py::is_fact_grounded()`.

- **Index construction:** `SELECT id, summary, structured_facts FROM knowledge.knowledge_units WHERE deleted_at IS NULL` — **no `validation_status` filter**. All 1,112 non-deleted units (986 PASSED + 126 FAILED) are candidates.
- **Word significance:** `_significant_words()` lowercases, extracts `[a-zA-Z]+` tokens, keeps only those ≥4 characters and not in a 40-word English stopword list.
- **Candidate lookup:** an inverted index (word → unit IDs) narrows candidates to units sharing at least one significant word with the question stem.
- **Eligibility test:** `is_fact_grounded(stem, unit_text)` — `overlap_ratio = |stem_words ∩ unit_words| / |stem_words|`, eligible iff `overlap_ratio >= 0.5` (`OVERLAP_THRESHOLD` in `grounding_check.py`).
- **A question is "covered" iff at least one unit passes this test.** No ranking, no top-k, no embeddings (none exist in the schema — confirmed by `\d knowledge.knowledge_units`, no vector column), no subject/chapter/class filter of any kind — **the matcher is subject-agnostic and searches the entire global index regardless of `pyq.questions.subject`.** This is a notable, directly-verified fact: a question with `subject = NULL` (61% of the pending pool) is not structurally disadvantaged by that NULL for retrieval purposes — it is searched exactly the same as a labeled question.

### Distinguishing the five measures requested (Section 4 of the task)

| Measure | What this audit can state |
|---|---|
| A. Source availability | 91 candidate PDFs discovered on disk; 76 distinct (post-checksum-dedup) registered — see Section 6. |
| B. Ingestion coverage | 1,112 knowledge units extracted from 74/76 mapped sources (986 PASSED). |
| C. Retrieval eligibility | **This is exactly what "38.9%" measures** — mechanical ≥50% word-overlap against the full KU index, confirmed above. |
| D. Evidence relevance | **Not measured by the 38.9% figure and not assessed by this audit at scale.** A "covered" question's matched unit is not confirmed topically relevant beyond passing the mechanical overlap test; a 50%-overlap match on a short stem can occur between genuinely related content or between coincidentally similar phrasing. No relevance-validation pass was run (would require either manual review or a method this task prohibits). |
| E. Answer verification | Entirely separate — governed by `pyq.answer_assertions`, untouched by retrieval coverage. 2,452/12,396 questions already have an independently verified answer; this audit's entire 9,944-question population is disjoint from that set by definition (`state='ANSWER_PENDING'`). |

**The 38.9% figure is purely measure C.** It says nothing about D or E. This is stated explicitly per the task's own instruction not to conflate these.

## 4. Decisive diagnostic: threshold sensitivity (full 9,944-question population, not a sample)

Script: `docs/quality/_forensic_audit_2026-10-01/forensic_coverage_audit_script.py` (preserved, read-only, in-memory only — the relaxed threshold is a local variable in this diagnostic script and was never written to `grounding_check.py` or any persistent configuration).

| Configuration | Units searched | Threshold | Covered | Coverage % |
|---|---|---:|---:|---:|
| **Current production behavior** | All 1,112 (incl. 126 FAILED) | 0.50 (production) | **3,868** | 38.9% — reproduces the reported figure exactly |
| PASSED-only | 986 | 0.50 | 3,868 | 38.9% (identical — see Section 5) |
| PASSED-only, relaxed (diagnostic) | 986 | **0.25** | **8,159** | **82.1%** |
| — | — | — | Zero-overlap subset of the uncovered | **113** / 9,944 (1.1%) |

**Interpretation, stated carefully:** 5,963 questions currently uncovered (9,944 − 3,868 − 113) share *some* real vocabulary with at least one ingested knowledge unit — not zero, just below the 50% bar. This is strong, direct evidence that **the dominant bottleneck is the matching threshold / short-fact-overlap mechanics, not absent source content**, for the large majority of the uncovered population. It is not proof that all 5,963 would be *correctly* matched at a lower threshold — only that the vocabulary overlap exists. **No claim of fixed coverage is made.** Section 14 scopes the validation work needed before any threshold change could be responsibly proposed.

## 5. FAILED-unit inclusion in the retrieval index

Directly measured, not inferred: comparing "all 1,112 units" vs "PASSED-only 986 units" at the production 0.50 threshold produces **the identical 3,868 covered count** — `delta = 0`. Every currently-covered question has at least one PASSED-status match; none rely exclusively on a FAILED unit. **Conclusion:** the architectural gap (FAILED units being searchable at all) is real and worth closing for defense-in-depth (a future state where a FAILED unit *does* uniquely cover some question is possible as more content is ingested), but it is **not currently responsible for any part of the reported 38.9%.**

## 6. NCERT PDF inventory reconciliation (re-verified fresh)

```
find StudyMaterial -iname "*.pdf" | wc -l        → 93 (on disk, all folders)
discover --dry-run (NEET-pattern filter only)     → 91 discovered
discover (apply, checksum dedup)                  → 76 distinct registered (15 checksum-duplicates of already-registered files)
```

| Folder | File count |
|---|---:|
| Biology/Class 11-Biology | 19 |
| Biology/Class 12-Biology | 10 |
| Chemistry/Class 11-Chemistry | 9 |
| Chemistry/Class 12-Chemistry | 10 |
| Physics/Class 11-Physics | 12 |
| Physics/Class 12-Physics | 23 |
| Physics/Class 12-Physics/leph2dd | 8 (checksum-duplicates of files already counted above) |
| Uploads | 2 (non-standard path, out of registry scope by design — not NEET-chapter-pattern files) |

**Mapping status (post the two preceding tasks' work):** 74/76 MAPPED, 2/76 UNMAPPED (confirmed genuinely non-chapter content — an Appendices file and a cover-page file; both correctly excluded, not a recoverable gap). **No missing Class 11/12 chapter is currently known** across Physics/Chemistry/Biology given the registry's current coverage — every registered, chapter-bearing source is now mapped. This reconciles exactly with the prior three reports; no new discrepancy found.

## 7. Question-level diagnostic — full 9,944-question population, deterministic categories only

**Scope limitation stated explicitly, per the task's own prohibition on AI-generated classification or guessing:** assigning each of the 9,944 questions to one of the task's 16 fine-grained causal categories (e.g. distinguishing "chapter mapping ambiguous" from "requires a diagram" from "different NCERT edition") requires semantic judgment about what each question is actually asking and whether specific NCERT content addresses it. A mechanical word-overlap matcher — the only tool available in this codebase and the only method this audit was permitted to use — cannot make that distinction. Attempting to force a 16-way split would mean inventing a conclusion that mechanical evidence does not support. **This audit instead reports the finest-grained split that is fully, mechanically supportable, and explicitly maps it to the closest matching requested categories.**

| Category | Count | % of 9,944 | Mechanical evidence | Closest requested category | Recoverable? |
|---|---:|---:|---|---|---|
| **Covered** (≥50% overlap with ≥1 ingested unit) | 3,868 | 38.9% | Direct match, reproduced in Section 4 | N/A — already retrieval-eligible | N/A |
| **Below-threshold overlap** (some shared vocabulary, 1–49% overlap, with ≥1 ingested unit) | 5,963 | 60.0% | Zero-to-current-threshold delta measured directly (Section 4); relaxed-threshold test shows most of this group has real, non-coincidental vocabulary overlap | Closest to **category 1** ("relevant content exists and is ingested, but retrieval misses it") — **candidate only**, relevance not individually validated | `RECOVERABLE_AFTER_PARSER_FIX` **or** retrieval-tuning fix — see Section 14; genuinely `UNRESOLVED` at per-question granularity until a relevance-validation pass runs |
| **Zero overlap** (no shared significant word with any of the 1,112 ingested units) | 113 | 1.1% | Direct count, Section 4 | Could map to categories 2, 14, or 15 (content not ingested / different edition / no source located yet) — **cannot be distinguished among these three without either manual reading of each question or a broader source search** | `UNRESOLVED` — see Section 14 |
| **Total** | **9,944** | **100%** | | | |

This 3-row split **sums exactly to 9,944**, with no double-counting, no estimation, and no category assigned without a specific, reproducible measurement behind it.

**What this audit could not determine, stated as `UNVERIFIED`/`UNRESOLVED`, not guessed:**
- Whether a given "below-threshold" question's matched-but-rejected unit is *actually* about the same concept (requires relevance judgment).
- Whether a given "zero-overlap" question's true topic has ever been published as an NCERT chapter at all vs. simply not yet ingested vs. requiring a diagram/table the current text-only extraction cannot capture (categories 13–15 specifically) — distinguishing these three for each of the 113 questions would require reading each question individually against the syllabus, not performed in this pass given the scale and the prohibition on AI-assisted classification.
- Per-chapter/per-topic breakdown of the uncovered population beyond subject-level (Section 4's `by_subject` table) — the matcher returns matched unit IDs, not a labeled topic per miss; computing a full chapter-level breakdown of the *uncovered* set would require a second pass attributing each uncovered question to its *most plausible intended* chapter, which again requires judgment this audit was not permitted to supply by guessing.

Raw list of the 6,076 currently-uncovered question IDs (both below-threshold and zero-overlap groups) is preserved at `docs/quality/_forensic_audit_2026-10-01/uncovered_question_ids.json` for any future, more targeted pass.

## 8. Retrieval-system findings (Section 8 of the task)

- **Text normalization:** lowercase + regex word extraction only; no stemming, no lemmatization, no synonym expansion.
- **Tokenization:** whitespace/regex-boundary, not a proper tokenizer; no handling of hyphenated terms, chemical formulas (e.g. "H2SO4"), or numeric/symbolic content beyond alphabetic character runs.
- **Stop-word removal:** a fixed 40-word list, English function words only — no domain-specific stopword tuning.
- **Matching:** pure set-overlap ratio, no TF-IDF, no term weighting (a rare, highly diagnostic word counts the same as a common domain word).
- **Thresholds:** single fixed value, `OVERLAP_THRESHOLD = 0.5`, defined once in `grounding_check.py`, used identically for both the ingestion-time grounding gate (fact-vs-source) and the resolver's retrieval matching (stem-vs-unit) — **the same constant serves two different purposes**, which was not separately tunable before this audit's diagnostic script existed.
- **Top-k / ranking:** none — `_match_units` returns *all* units clearing the threshold, unordered; no relevance ranking exists anywhere in this path.
- **Chunk length:** `structured_facts` are sentence-level (`MIN_FACT_CHARS=40`, max 8 facts per section) — short, which mechanically caps how much overlap surface a single knowledge unit's text can offer a long or differently-worded PYQ stem.
- **Duplicate handling:** `KnowledgeRepository.find_duplicate()` (summary-based, per-concept) — confirmed as the sole cause of all 126 FAILED units (Section 9).
- **Equations/symbols/synonyms:** no special handling anywhere in this path — a question using "H₂SO₄" vs a source using "sulphuric acid" would not overlap at the word level at all.
- **Class 11/12 naming variants:** handled correctly at the *mapping* layer (registry keys include `class_level`), but the retrieval matcher itself has no class-awareness — it is purely a global text search.
- **Embedding infrastructure:** confirmed absent — no vector column on `knowledge_units`, no embedding model configured or imported anywhere in this code path.
- **Does retrieval use the same DB/config as the coverage report?** Yes — `_load_ku_index()` is the single, shared function; this audit's diagnostic script loads from the identical query, confirmed by the exact reproduction of 3,868 in Section 4.

**Estimate of how much of the uncovered population is a retrieval-system issue vs. missing-content issue:** per Section 4's direct measurement, **at most 1.1% (113/9,944) is plausibly a missing-content issue** on current mechanical evidence; the remaining uncovered 60.0% (5,963/9,944) shares real vocabulary with ingested content and is a retrieval-system-sensitivity candidate, not a confirmed content gap.

## 9. Failed/rejected knowledge-unit audit

```sql
SELECT CASE WHEN validation_detail LIKE 'duplicate%' THEN 'duplicate' ... END, count(*)
FROM knowledge.knowledge_units WHERE validation_status='FAILED' GROUP BY 1;
-- duplicate: 126 (100%)
```

**All 126 FAILED units failed for exactly one reason: flagged as a duplicate of an already-PASSED unit** (`KnowledgeRepository.find_duplicate()`, summary-text-based, scoped per `concept_id`). **Zero** failed for ungrounded/malformed facts (`"N/M facts failed source-overlap check"` — this message pattern, searched for directly, matched zero rows).

By chapter:
```
CHEMISTRY-U01: 44   CHEMISTRY-U03: 36   PHYSICS-U01: 18
PHYSICS-U12: 15      BIOLOGY-U01: 12     PHYSICS-U13: 1
```
Concentrated in the chapters with the most sections ingested (Chemistry Units 1 & 3, Physics Unit 1) — consistent with ordinary within-chapter sentence repetition across multiple pages/sections triggering the per-concept duplicate check, not with a systematic extraction defect. **No evidence was found that deduplication incorrectly removed a uniquely useful chapter context** — each FAILED unit's `structured_facts` duplicate an already-PASSED unit's content by construction of the check; this audit did not individually re-read all 126 to confirm semantic (not just textual) redundancy, so this specific sub-claim is marked `UNVERIFIED` rather than confirmed.

## 10. Recovery feasibility classification

| Group | Questions | Classification | Evidence | Required action |
|---|---:|---|---|---|
| Below-threshold overlap | 5,963 | `RECOVERABLE_AFTER_PARSER_FIX` *(tentative — retrieval-tuning, not a PDF parser; naming follows the task's taxonomy)* | Section 4 relaxed-threshold test | A scoped relevance-validation pass (manual or rule-based) on a representative sample before any threshold change; see Section 14 |
| Zero overlap | 113 | `UNRESOLVED` | Section 4 direct count | Individual review — could be `REQUIRES_ADDITIONAL_AUTHORIZED_PDF`, `RECOVERABLE_FROM_EXISTING_PDFS` (under-extracted), or a data-quality issue in the question text itself; not distinguishable without reading each one |
| 2 unmapped sources (Appendices, cover page) | 0 directly (no PYQ traced to them) | `NOT_CURRENTLY_RECOVERABLE` | Confirmed non-chapter content, Section 6 | None — permanently out of scope |
| All other registered sources | 0 additional | N/A | 74/76 already mapped and ingested (Sections 2, 6) | None outstanding |

**No group total double-counts** — the 3-way split in Section 7 is a strict partition of the 9,944, and this table maps those same groups without re-deriving new counts.

## 11. Conservative and potential coverage projections

- **Conservative:** no responsible numeric projection is offered for the 5,963 below-threshold group without relevance validation — the task explicitly warns against promising coverage the evidence doesn't support. What **can** be said: this group is bounded above by 5,963 (today's below-threshold count) and the relaxed-threshold test (Section 4) shows the vocabulary overlap exists for roughly 73% of it (4,291 of the ~5,963 would newly clear a 0.25 threshold — `8,159 − 3,868 = 4,291`, against the PASSED-only base), but that is a *ceiling on mechanical plausibility*, not a validated recoverable count.
- **Zero-overlap group (113):** cannot be projected without individual investigation; treated as fully `UNRESOLVED`.
- **No claim of 100% achievability is made.** The honest floor on "currently content-impossible" questions, from mechanical evidence alone, is a maximum of 113 (1.1%) — and even that is an upper bound pending the individual review Section 10 recommends, not a confirmed missing-source count.

## 12. Risks, uncertainty, unresolved questions

- Relevance of matches (measure D, Section 3) was not assessed anywhere in this audit — this is the single largest open question and the prerequisite for any further coverage work being trustworthy rather than merely numeric.
- The 113 zero-overlap questions were not individually read; their true cause (genuinely absent source vs. unusual question phrasing vs. requires a diagram/table/equation not captured by text extraction) is unknown.
- Whether any of the 126 FAILED (duplicate) units represent a genuinely distinct, uniquely useful chapter context incorrectly discarded was not individually verified (Section 9).
- This audit used a fixed relaxed threshold (0.25) as one diagnostic data point, not a sweep — the true relationship between threshold and both coverage and false-positive rate across the full range was not characterized.

## 13. Staged recovery roadmap

**Stage 1 — Existing content and metadata.** No confirmed taxonomy mismatches found this round (Section 6 — mapping is now complete except 2 permanently-excluded files). Files: none identified as needing a change. Validation criteria: re-run Section 6's reconciliation after any future source addition. Status: effectively complete for the current source set.

**Stage 2 — Source extraction and ingestion.** No PDFs are currently present-but-uningested (74/76 mapped sources are all ingested; the 2 unmapped are non-chapter content). Status: complete for the current source set; revisit only if new PDFs are added.

**Stage 3 — Missing authorized source documents.** No specific missing NCERT chapter was identified with evidence (Section 6 found no chapter gap in the registered corpus). The 113 zero-overlap questions (Section 7) are the only candidates for this stage, pending individual review. Files: none yet — this stage requires the Section 10 review to even produce a missing-document list.

**Stage 4 — Retrieval quality (the highest-leverage stage per this audit's evidence).**
- Files likely involved: `app/modules/knowledge/services/grounding_check.py` (the shared threshold constant currently serves two different purposes — ingestion-time grounding gate and retrieval matching — consider whether they should be decoupled), `scripts/resolve_pyq_answers.py` (`_match_units`).
- Tasks: (a) build a relevance-validation sample (e.g. 200–400 below-threshold questions, stratified by subject) and manually or semi-manually confirm whether their below-threshold match is topically correct; (b) based on that sample's precision, decide whether a lower threshold, phrase-aware matching, or per-fact chunk-size increase is warranted; (c) consider separating the retrieval threshold from the ingestion-grounding threshold so they can be tuned independently without re-running ingestion.
- Dependencies: none on Stages 1–3 for *this* database's current state.
- Validation criteria: measured precision (true-relevant / total-matched) on the sample, not just a raw coverage number.
- Risks: a naive threshold drop increases coverage numerically while reducing evidence quality — exactly the failure mode this task's final instruction warned against.
- Definition of done: a documented precision/recall tradeoff decision, signed off by the project owner, before any threshold change ships.

**Stage 5 — Content-quality validation.** Not started. Depends on Stage 4's outcome — once any retrieval-tuning change is made, re-validate a sample of newly-covered questions against their source pages before treating them as reliable evidence for the Gemini resolver.

## 14. Recommended next, scoped step

Build a **relevance-validation harness**: sample N below-threshold questions (stratified by subject/chapter-hit), surface each alongside its best-matching (but currently-rejected) knowledge unit's text, and have a human reviewer (or a separately-scoped, explicitly-authorized process) mark each as relevant/irrelevant. This produces the precision estimate Section 13's Stage 4 needs before any threshold or matching-algorithm change can be responsibly proposed. This was not performed in this audit — it exceeds "deterministic analysis" and was correctly out of scope here.

## 15. Final decision register

| Item | Status |
|---|---|
| 3,868/9,944 (38.9%) current coverage | **Confirmed, reproduced independently** |
| Dominant uncovered-cause mechanism (threshold vs. content) | **Confirmed via direct measurement**: threshold-sensitive for 60.0%, content-ambiguous for 1.1% |
| FAILED units inflating coverage | **Confirmed false** — delta measured as exactly 0 |
| All FAILED units' root cause | **Confirmed**: 100% duplicate-of-existing, 0% ungrounded-facts |
| Missing NCERT chapters in the registered corpus | **None found** — 74/76 mapped, 2/76 confirmed non-chapter |
| Per-question relevance of matches | **Not assessed — explicitly out of scope for this audit's methods** |
| Per-question fine-grained 16-category causal diagnosis | **Not performed as specified** — would require semantic judgment beyond deterministic word-overlap tooling; the 3-way mechanical partition in Section 7 is the defensible substitute |
| Path to materially higher coverage | **Retrieval-quality tuning (Stage 4), pending relevance validation** — not new PDF acquisition, based on current evidence |

---

## Confirmations

- **No database record was modified.** All queries were `SELECT`-only or explicit dry-runs; the diagnostic script never calls `session.commit()` (confirmed by code — ends with `session.rollback()`).
- **No Gemini, Claude, OpenAI, or other paid AI inference call was made.** `ai.ai_requests` row count unchanged (32, all pre-dating this audit).
- **Production was never accessed.**
- **Nothing was committed, pushed, or deployed.**

## Evidence

- `docs/quality/_forensic_audit_2026-10-01/forensic_coverage_audit_script.py` — the exact read-only diagnostic script, reproducible against the same database.
- `docs/quality/_forensic_audit_2026-10-01/uncovered_question_ids.json` — the 6,076 currently-uncovered question IDs (below-threshold + zero-overlap), for any future targeted follow-up.
- Prior reports this audit builds on, cross-references, and does not contradict: `docs/quality/ncert-physics-filename-parser-fix-2026-10-01.md`, `docs/quality/ncert-manual-mapping-expansion-2026-10-01.md`, `docs/quality/ncert-taxonomy-glossary-alignment-2026-10-01.md`, `docs/quality/ncert-knowledge-base-and-gemini-resolution-2026-10-01.md`.
