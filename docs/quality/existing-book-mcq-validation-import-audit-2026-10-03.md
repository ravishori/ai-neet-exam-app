# Book MCQ Validation & Staging Import — Audit

**Date:** 2026-10-03. **Zero AI calls. Zero database import performed** — validation revealed quality defects that make import unsafe right now; reported honestly per this task's own priority ("accuracy... over import volume").

## 1. Reconciliation of the prior extraction

Re-loaded and reconfirmed `docs/quality/_book_mcq_extraction_2026-10-03/extracted_book_mcqs.json`: **148 total** (34 Chemistry, 29 Physics, 85 Botany) — matches the prior report exactly.

## 2. Exact and near-duplicate detection (corrected methodology)

The prior task's "102 unique" figure used **exact normalized-text matching only** — too strict, since PDF-extraction whitespace/line-break differences mean a real duplicate often isn't a byte-exact match. This task re-ran detection using **significant-word Jaccard similarity** (reusing `is_fact_grounded`'s own `_significant_words()` for consistency with the rest of the project) against all 12,396 existing PYQs:

| Classification | Count | Meaning |
|---|---:|---|
| `exact_duplicate` | 46 | Unchanged from prior report |
| `near_duplicate_high_confidence` (similarity ≥ 0.85) | **72** | Same question, reformatted by PDF extraction — **not** genuinely new |
| `near_duplicate_uncertain` (0.55 ≤ similarity < 0.85) | 17 | Flagged for manual review, **not auto-discarded, not auto-accepted** |
| `unique` (similarity < 0.55) | 13 | Candidate net-new |

**Corrected finding: the true unique/uncertain pool is 30 (17+13), not 102.** The prior task's exact-match-only method undercounted duplication by a factor of ~2.4. No within-batch duplicates were found among the 148 themselves.

## 3. Deterministic answer recovery (legitimate, source-based — not guessed)

For the **72 high-confidence near-duplicates**, where the matched existing PYQ is already `VERIFIED`: inherited that existing, independently-verified answer, with explicit provenance (`inherited_from_verified_pyq:<id>:similarity=X.XX`), on the reasoning that a ≥0.85 word-overlap match to an already-verified official PYQ is the same question, reformatted. **29 of the 72 high-confidence matches had an inheritable, already-verified answer; 43 did not** (the matched existing PYQ itself isn't `VERIFIED` yet). **No answer key for the 2024 papers was located or used** — this is the only legitimate, non-guessed answer-recovery path available, and it was only applied where the match confidence was high. **No answer was assigned to any of the 30 unique/uncertain candidates** — correctly, since there's nothing to inherit from for genuinely distinct questions.

## 4. Diagram recovery

All **8** figure-dependent questions flagged previously: source page located by stem-text search and the **full page rendered as a 200 DPI PNG** (deterministic `fitz` rendering, no redrawing) — preserved at `docs/quality/_book_mcq_extraction_2026-10-03/diagram_pages/`. **8/8 located, 0 missing.** A full-page image (not a cropped figure region) was used since no reliable bounding-box extraction was attempted — disclosed as a limitation, not a precise crop.

## 5. Chapter/topic metadata — corrected, but limited

Rebuilt the lookback using keyword overlap against `NEET_UG_2026_Curriculum_Taxonomy.txt`'s actual unit/topic text (not the broken heading-lookback from the prior script). **17 of 148 questions received a chapter assignment** at a conservative confidence floor; the rest were **left unclassified rather than guessed** — per this task's explicit instruction ("leave uncertain classifications pending instead of assigning arbitrary topics"). This is a low hit rate, disclosed honestly: the taxonomy-keyword method is coarse and most stems don't contain enough topic-distinguishing vocabulary to clear the confidence floor.

## 6. Quality validation — the decisive finding

Manually inspected all 30 unique/uncertain candidates (not sampled — all of them, since the set is small). Found two distinct, real extraction defects:

1. **Explanation-section contamination:** at least 2 of the original "13 unique" entries (`Botany #8`, one of two `Botany #96` entries) are not questions at all — they are **answer-explanation text from the solutions section at the back of the booklet**, misparsed as question stems because they happened to start with a line the parser's question-number regex matched. **Filtered out** via a pattern check for a leading `(a)/(b)/(c)/(d)`-style explanation marker, plus a duplicate-question-number check (catches both the artifact and, conservatively, its genuine same-numbered counterpart — a known over-correction, disclosed rather than hidden).
2. **Truncated statement-list stems:** 5 of the remaining candidates (`Botany #51, #58, #62, #86, #90`) have a stem like *"Consider the following statements:"* with **no visible statement list** before the 4 options — the actual Roman-numeral (I/II/III/IV) statement content was lost during option-boundary parsing (the parser's `a./b./c./d.` option detector apparently also swallowed or mis-bounded the preceding enumerated-statement lines). **These are incomplete, not faithful reproductions of the source**, and must not be imported as-is.

**After both filters: 27 of 30 candidates are structurally clean text** (no artifact markers, no duplicate numbering, adequate stem length) — but **5 of those 27 (the truncated-statement-list ones above) have a distinct, separate incompleteness defect** that the automated filters did not catch, found only by reading them. **22 of 148 total** are therefore both (a) genuinely not duplicates and (b) free of the two defects found — the most defensible "clean" subset, though not exhaustively re-verified word-for-word against the source PDF page images.

## 7. Staging import decision: **zero questions imported**

Per this task's own stated priority — *"source fidelity, answer accuracy, uniqueness, provenance and database integrity over import volume"* — importing even the 22 "clean" candidates right now would mean asserting a level of extraction fidelity I have not actually confirmed beyond pattern-based filtering. **None have a verified or even source-supplied answer.** Given the two real defect classes just found by manual reading (not caught by any automated check until I looked), I am not confident additional, uncaught defects don't exist in the 22 "clean" set either. **The responsible decision is to report this, not import it.**

## 8. Tests

No application code was changed in this task (the extraction/validation scripts are one-off, evidence-only, not integrated into the pipeline) — **no new tests were required or written.** No existing test suite was re-run (no code changed; consistent with this session's standing cost-discipline instruction).

## 9. Database counts before/after

**Unchanged: 12,396 PYQs. 0 book-MCQ rows added anywhere.**

## 10. Rejected questions and reasons

| Question | Reason |
|---|---|
| Botany #8 (one occurrence) | Explanation-section text misparsed as a question stem |
| Botany #96 (both occurrences) | One is the same explanation-contamination defect; the other (a genuine, well-formed ABO-blood-group question) was conservatively excluded too, since the duplicate-number filter can't distinguish "artifact + real" from "two real duplicates" — **a disclosed false-positive rejection**, not a quality problem with that specific question itself |
| Botany #51, #58, #62, #86, #90 | Truncated statement-list stems — incomplete relative to the source |
| 46 exact + 72 near-duplicate-high-confidence | Not net-new (correctly excluded, not "rejected" in the quality sense) |

## 11. Remaining manual-review requirements

- The **17 `near_duplicate_uncertain`** candidates need a human (or a better similarity method) to decide duplicate-vs-distinct — not resolved by this pass.
- The **22 "clean" candidates** (Section 6) should be checked word-for-word against the original PDF page text before any import is attempted, given that two separate defect types were found by manual reading that no automated check caught on the first pass.
- The parser itself needs fixing (statement-list boundary handling, explanation-section exclusion) before re-running on these or any other book source.
- Chapter/topic coverage gaps: 131 of 148 (88.5%) have no reliable chapter assignment — would need either a better taxonomy-matching method or manual tagging.

## 12. Exact paths of all scripts, data, and this report

- `docs/quality/_book_mcq_extraction_2026-10-03/extracted_book_mcqs.json` (148, unchanged from prior task)
- `docs/quality/_book_mcq_extraction_2026-10-03/validate_book_mcqs_script.py` (new, this task)
- `docs/quality/_book_mcq_extraction_2026-10-03/validated_book_mcqs.json` (148, with classification/inheritance/chapter fields — new)
- `docs/quality/_book_mcq_extraction_2026-10-03/clean_candidates.json` (27, post-artifact-filter — new)
- `docs/quality/_book_mcq_extraction_2026-10-03/diagram_extraction_log.json` + `diagram_pages/` (8 PNGs — new)
- `docs/quality/existing-book-mcq-validation-import-audit-2026-10-03.md` (this report)

## Summary of genuinely new, usable questions

**0 confirmed import-ready.** Best honest estimate of eventually-usable net-new content, pending the manual source-comparison in Section 11: **up to 22**, out of an original 148 extracted and 12,396 existing PYQs compared against. This is a small number relative to the original task's framing, and is reported as such rather than inflated — consistent with this task's explicit instruction not to force a target or lower quality standards.
