# NCERT Retrieval Relevance Validation & Coverage Optimization

**Date:** 2026-10-01
**Continues:** [`ncert-retrieval-coverage-forensic-audit-2026-10-01.md`](ncert-retrieval-coverage-forensic-audit-2026-10-01.md)
**Scope: read-only.** No database write, no ingestion, no answer resolution/promotion, no Gemini/Claude/OpenAI call, no production access, no source/config change, nothing committed. Confirmed: `git status --short` unchanged in scope (only new/moved files under `docs/quality/`); `ai.ai_requests` row count still 32 (unchanged, all pre-dating this and the prior audit).

## 1. Baseline reproduction

Script: `docs/quality/_retrieval_relevance_2026-10-01/relevance_validation_audit_script.py` (read-only; ends with `session.rollback()`, never `commit()`). Output: `run_output.log`, `baseline_reproduction.json`.

| Metric | Value | Reproduces prior audit? |
|---|---:|---|
| Total pending PYQs | 9,944 | ✓ |
| Knowledge units in index | 1,112 (986 PASSED / 126 FAILED) | ✓ |
| Coverage at strict 0.50 (all units) | **3,868** | ✓ exact match |
| Coverage at strict 0.50 (PASSED-only) | 3,868 (delta = 0) | ✓ exact match |
| Coverage at relaxed 0.25 (PASSED-only) | **8,159** | ✓ exact match |
| **Newly covered at 0.25 but not 0.50** | **4,291** | = 8,159 − 3,868, arithmetic-consistent |

**One discrepancy found and reconciled, not hidden:** this script's zero-overlap count is **155**, not the prior audit's 113. Investigating the breakdown (`zero_overlap_classification.csv`) shows this is not a contradiction — it is a finer split of the same population:

| Reason | Count |
|---|---:|
| Zero shared significant words with any ingested unit (stem has real content) | **113** — exactly reproduces the prior audit's figure |
| Stem has **zero significant words at all** (empty after stopword/length filtering) | **42** — a sub-case the prior script's `continue`-before-counting logic silently folded into the general "uncovered" bucket without labeling it separately |

Both audits' arithmetic is internally consistent; the prior audit's 113 was already a subset of what should have been reported, not wrong — it just didn't surface the 42 degenerate-stem questions as their own category. That is corrected here (Section 6).

## 2. Full-population diagnostic of the 4,291 newly-covered questions

File: `docs/quality/_retrieval_relevance_2026-10-01/newly_covered_full_population.csv` (4,291 rows, full schema per the task's Section 2 spec: question ID, subject, chapter code of best match, overlap score, matched knowledge-unit ID + validation status, source document + page, matched/unmatched significant terms, taxonomy-mismatch warning, stem and passage previews).

Distributions:

| Dimension | Breakdown |
|---|---|
| Subject | `(null)` 2,265 (52.8%), Physics 685, Chemistry 595, Zoology 381, Botany 365 |
| Matched-unit validation status | PASSED 4,247 (99.0%), FAILED 44 (1.0%) — note: "best match is FAILED" does not mean the question has no PASSED candidate; Section 5 addresses exclusive dependence separately |
| Score band | 0.40–0.44: 1,305 · 0.30–0.34: 1,287 · 0.25–0.29: 782 · 0.35–0.39: 732 · 0.45–0.49: 185 |
| Source documents matched | concentrated in a small set of large chapters — top 3: `ncert-books-class-11-chemistry-chapter-4.pdf` (595), `ncert-books-class-11-chemistry-chapter-9.pdf` (244), `ncert-books-class-12-chemistry-chapter-3.pdf` (160) |
| Fully-covered vocabulary (0 unmatched terms) | 0 of 4,291 — every match has at least one stem word not present in the candidate unit's text, consistent with these being partial, not full, overlaps by construction |

**Decisive, directly-measured false-positive-risk signal:** of the 2,026 newly-covered questions that *do* carry a `subject` label (the 2,265 `(null)`-subject rows can't be checked this way), **1,123 (55.4%) have their best-matching knowledge unit's subject code differ from the question's own labeled subject** (`taxonomy_warning` populated). This is a concrete, mechanical red flag — not proof every such match is wrong (word overlap can legitimately cross subject boundaries, e.g. a Biology question referencing a Chemistry concept), but a majority-mismatch rate among labeled questions is strong evidence that a meaningful share of the 4,291 relaxed-threshold matches are not topically relevant. **This one number is the single strongest piece of evidence against lowering the threshold without validation.**

## 3. Stratified human-review sample

File: `docs/quality/_retrieval_relevance_2026-10-01/stratified_review_sample.csv` — **193 rows**, `review_label` column left blank throughout (no label was fabricated).

**Method:** strata defined by (subject × score-band[0.25–0.29/0.30–0.34/0.35–0.39/0.40–0.44/0.45–0.49] × matched-unit validation status), up to 8 questions sampled per non-empty stratum using a fixed seed (`random.Random(20261001)`) for reproducibility. 25 of the possible strata were non-empty; the sample spans Physics (40), Botany (32), Chemistry (32), Zoology (32), and null-subject (57).

**This is not a statistically powered precision estimate** — it is a *review-ready worksheet*, not an executed review. No confidence interval can be honestly reported because **zero rows have been labeled**; the task is explicit that review labels must stay blank until an actual human reviews the evidence, and no human review occurred during this audit. If a full binomial-proportion confidence interval is wanted once labeling happens, the standard approach (Wilson score interval) on n=193 would give roughly ±7 percentage points at 95% confidence around whatever proportion is observed — stated here only as the methodology to apply after review, not as a result.

**Full-population review is not currently feasible** within this audit's deterministic, no-AI, no-write constraints — reviewing all 4,291 would require either manual reading (not performed) or an AI relevance judgment (explicitly prohibited). The 193-row sample is offered as a practical starting point, not a substitute presented as equivalent to full coverage.

Each sampled row carries the exact question text preview, the candidate passage preview, source document, and page — sufficient for an independent human reviewer to judge relevance without this audit pre-judging the outcome.

## 4. False-negative investigation (deterministic diagnostics only)

Directly observed in the matched-term/unmatched-term data (`newly_covered_full_population.csv`):

- **Zero rows have fully-matched vocabulary** (0/4,291 have an empty `unmatched_terms` field) — every accepted match, even at the relaxed threshold, still has stem vocabulary the candidate unit's text doesn't contain. This is consistent with short (`structured_facts`, ≤40-char-minimum sentence) knowledge units being too short to ever fully cover a longer question stem — a chunk-size limitation, not a vocabulary-matching bug.
- **No symbol/formula/equation handling exists anywhere in this matching path** (confirmed from source, Section 8 of the prior audit) — a question using a chemical formula or numeric symbol loses that content entirely at the `[a-zA-Z]+` tokenization step. This is a plausible, code-confirmed mechanism for undercounting matches on numerically/symbolically dense Physics and Chemistry questions, but this audit did not isolate how many of the 5,963 below-0.25 (now more precisely: below-0.25-and-not-zero-overlap would require an additional run) questions this specifically affects — **flagged as `UNVERIFIED`, not quantified**, since doing so would require re-parsing stems for symbol density, which was out of this task's scope.
- **No stemming/lemmatization or synonym table exists** — directly confirmed from `grounding_check.py` source (Section 8 of the prior audit, unchanged). A question using a synonym or inflected form of a source term (e.g., "photosynthetic" vs. "photosynthesis") will not match on that word. This is a known, code-confirmed limitation but, again, not individually quantified against the 9,944 population in this pass — stated as a documented mechanism, not a counted impact.
- **No alternate-chapter-naming normalization issue was found** — the chapter codes observed in the matched-unit data (`PHYSICS-U01`, `CHEMISTRY-U01`, etc.) are consistent and don't show obvious duplication/fragmentation that would indicate a naming-split problem.

**Conclusion for this section:** real, code-confirmed mechanisms for false negatives exist (short chunk length, no symbol/formula handling, no synonym expansion), but this audit did not — and, given the no-AI constraint, largely cannot — quantify their individual contribution to the 5,963-question below-threshold population without either a scoped follow-up diagnostic (e.g., flagging stems containing digits/symbols) or human review.

## 5. FAILED knowledge-unit impact — quantified precisely

File: `docs/quality/_retrieval_relevance_2026-10-01/failed_unit_impact.json`.

| Question | Answer |
|---|---|
| Does each failed unit have a canonical equivalent? | Yes, by construction — every one of the 126 `FAILED` rows' `validation_detail` names the specific PASSED unit it duplicates (sample confirmed: `"duplicate of existing knowledge unit <uuid>"`, each UUID resolves to a real PASSED row). |
| Does the canonical equivalent preserve the same scientific content? | **Not independently re-verified** this round — the duplicate-detection mechanism is summary-text-based (not re-read character-by-character here); flagged `UNVERIFIED`, consistent with the prior audit's identical caveat. |
| Is provenance preserved? | Yes — both the FAILED unit and its canonical PASSED equivalent retain their own `source_section_id` → page/document chain; nothing about the FAILED status erases provenance, it only excludes the row from being user-facing. |
| How many questions match a FAILED unit? | **6,788 question×unit match pairs** at the strict 0.50 threshold reference at least one FAILED unit among their matches. |
| Does excluding FAILED units change the coverage numerator? | **No** — confirmed again this round: `current_covered_strict_0_50_all_units` (3,868) exactly equals `passed_only_covered_strict_0_50` (3,868), delta 0. Every one of those 6,788 match pairs co-occurs with at least one PASSED match on the same question. |
| Do FAILED units alter ranking? | There is no ranking in this system (confirmed, prior audit Section 8) — `_match_units` returns an unordered set, so "ranking" doesn't apply; FAILED units can appear anywhere in that unordered result, including as this audit's own "best by score" pick for 44 of the 4,291 newly-covered questions (Section 2), without affecting whether the question counts as covered. |

**No validation statuses were changed, no records deleted or edited.**

## 6. The 113 (+42) zero/near-zero-overlap questions — reclassified

File: `docs/quality/_retrieval_relevance_2026-10-01/zero_overlap_classification.csv` — **155 rows total**, covering both sub-groups.

Per-question individual review (reading each question against the syllabus) was **not performed** — doing so at this scale without either manual labor or AI assistance exceeds this audit's deterministic tooling. Based on the mechanical evidence available (presence/absence of `subject` metadata, and the stem-text sample), every row is classified `UNRESOLVED` per the task's own instruction ("Use `UNRESOLVED` whenever evidence is insufficient") — **no row was force-classified into a more specific bucket without individual evidence**, consistent with the prior audit's explicit prohibition on concluding "source missing" from zero overlap alone.

| Sub-group | Count | Classification | Why not further resolved |
|---|---:|---|---|
| Zero shared vocabulary with any ingested unit, non-empty stem | 113 | `UNRESOLVED` | Requires reading each question's actual topic against the syllabus/registry — a semantic task, not a mechanical one |
| Zero significant words in the stem at all | 42 | `UNRESOLVED` (distinct mechanism) | These are likely degenerate stems — e.g. very short questions, stems dominated by numbers/symbols/short words, or stems where critical content lives in `raw_options` rather than `raw_stem`. This is a **new, previously-unflagged finding**: these 42 questions cannot structurally be matched by this word-overlap system regardless of threshold, because the matcher only ever looks at `raw_stem` — a stem of e.g. "Which of the following is true?" with all content in the options would score zero overlap by design, independent of whether relevant NCERT content exists. This is the one new, concrete, code-level mechanism this audit surfaces that the prior one did not. |

**No conclusion that source material is missing is drawn for any of the 155.**

## 7. PDF inventory reconciliation (reconfirmed, no new discrepancy)

```
find StudyMaterial -iname "*.pdf" → 93 on disk
discover --dry-run (NEET filename pattern only) → 91
registered (post checksum-dedup)  → 76
```

Confirmed by direct checksum comparison this round (not merely inferred from the prior task): `leph2dd/leph201.pdf` is byte-identical (`sha256=5c9570cc...`) to `leph201.pdf` in the parent folder; `leph2dd/leph2an.pdf` is byte-identical (`sha256=008ef2d5...`) to `leph2an.pdf` in the parent folder. The `leph2dd/` folder (8 files) and the root-level `leph2an.pdf`/`leph2ps.pdf` are exact duplicates of files registered elsewhere, confirming they are correctly excluded from the 76 distinct registered sources — not a data-loss gap. The 2 `Uploads/` files are non-NEET-pattern filenames, out of registry scope by design (not authoritative paths). **No file accounts for a "missing" difference** — the 76-vs-93 gap is fully and exactly explained by (15 checksum duplicates + 2 non-pattern upload files = 17; 93 − 17 = 76). All registered files are authorized project NCERT sources (same conclusion as the prior audit; unchanged, reconfirmed by this round's independent checksum check rather than re-assumed).

## 8. Coverage recommendation

| Measure | Target 1: Retrieval eligibility | Target 2: Validated source relevance | Target 3: Evidence completeness | Target 4: Independent answer verification |
|---|---|---|---|---|
| What it means | Mechanical word-overlap ≥ threshold | A human (or validated process) confirms the matched passage is actually about the question's topic | The matched evidence contains enough content to determine the correct answer, not just a related topic | A `pyq.answer_assertions` row with `VERIFIED` status exists |
| Current measured value | 38.9% (strict) / 82.1% (relaxed, diagnostic) | **Not measured** — 0 rows reviewed (sample prepared, not executed) | Not measured | 19.78% (2,452/12,396, separate from this audit's 9,944 population by definition) |
| This audit's contribution | Reproduced exactly | Built the measurement instrument (193-row sample) but did not execute it | Not addressed | Unchanged, out of scope |

**These four measures are not equivalent and are not conflated here, per the task's explicit instruction.**

**Recommendation: do not change the production threshold (0.50) based on this audit's evidence.** The relaxed-threshold number (82.1%) is a ceiling on mechanical plausibility, not a validated coverage figure — and the 55.4% taxonomy-mismatch rate among labeled newly-covered questions is active evidence *against* adopting it as-is. A middle-ground threshold (e.g., 0.35–0.40) is a **candidate worth testing** once the 193-row sample (or a larger one) is actually reviewed, but **no candidate threshold is approved for student-facing use by this audit** — stated explicitly per the task's requirement.

Subject/chapter-specific differences: the newly-covered population skews heavily toward a handful of large source chapters (Chemistry Ch.4/Ch.9, Biology Ch.9/Ch.10) — any threshold change's risk is not evenly distributed; these chapters would see the largest influx of both true and false positives and are the natural priority for review.

## 9. Limitations

- No human review was performed; all `review_label` values are blank by design.
- Taxonomy-mismatch rate (55.4%) is a proxy for false-positive risk, not a direct relevance measurement — it is possible for a cross-subject match to still be correct, and this audit does not claim otherwise.
- False-negative mechanisms (chunk length, symbol handling, synonym gaps) are code-confirmed but not individually quantified against the full population.
- The 155 zero/near-zero-overlap questions were not individually read; the 42-question "empty significant stem" sub-finding is new and itself needs a follow-up read of `raw_options` content to assess, which was not performed.
- The FAILED-unit "duplicate preserves same scientific content" claim rests on the pipeline's own duplicate-detection logic, not an independent re-read of the 126 pairs.

## 10. Recommended next steps

1. Execute the prepared 193-row review sample (or expand it) with an actual human reviewer; compute a precision estimate and confidence interval only after real labels exist.
2. If precision proves acceptable at some threshold between 0.25 and 0.50, consider re-running this diagnostic at that specific value as a new, separately-scoped, separately-evidenced check — never adopt a threshold from this audit's numbers alone.
3. Investigate the newly-surfaced 42-question "empty significant stem" group — check whether `raw_options` content should be included in the matcher's input, as a distinct, scoped code-review question (not implemented here).
4. If false-negative quantification is wanted, a scoped follow-up diagnostic tagging stems by symbol/digit density would directly measure that mechanism's size — not performed here, flagged as future work only.

## Final confirmations

- All 9,944 pending questions were analyzed mechanically (both at strict and relaxed thresholds) — confirmed by `total_pending: 9944` in `baseline_reproduction.json`, matching the loaded `pending` row count exactly.
- The 193-row human-review subset is clearly distinguished from the full 9,944/4,291 population throughout this report; no sample was presented as a full-population semantic validation.
- **No database record was modified** — the diagnostic script never calls `session.commit()` (confirmed by code), ends with `session.rollback()`.
- **No Gemini, Claude, OpenAI, or other paid AI inference call was made** — `ai.ai_requests` row count unchanged (32, pre-dating this and the prior audit).
- **Production was never accessed.**
- **Nothing was committed, pushed, or deployed.**
- No source file, configuration, migration, or test was changed.

## Evidence

- `docs/quality/_retrieval_relevance_2026-10-01/relevance_validation_audit_script.py` — the exact read-only diagnostic, reproducible against the same database.
- `docs/quality/_retrieval_relevance_2026-10-01/baseline_reproduction.json`
- `docs/quality/_retrieval_relevance_2026-10-01/newly_covered_full_population.csv` (4,291 rows)
- `docs/quality/_retrieval_relevance_2026-10-01/stratified_review_sample.csv` (193 rows, blank review labels)
- `docs/quality/_retrieval_relevance_2026-10-01/zero_overlap_classification.csv` (155 rows)
- `docs/quality/_retrieval_relevance_2026-10-01/failed_unit_impact.json`
- `docs/quality/_retrieval_relevance_2026-10-01/registered_sources.txt`
- `docs/quality/_retrieval_relevance_2026-10-01/run_output.log` (raw script output)
