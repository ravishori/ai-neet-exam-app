# Existing Book MCQ Extraction & Import — Final Audit (Phase 1, Completed)

**Date:** 2026-10-03. **Local dev database only — no production write.** Zero AI calls. This report supersedes the two prior same-day reports on this topic (`existing-book-mcq-extraction-import-audit-2026-10-03.md`'s earlier draft and `existing-book-mcq-validation-import-audit-2026-10-03.md`) by fixing the parser bug those reports had already identified but not yet fixed, and completing the staging import those reports deliberately withheld pending that fix.

## 1. The parser bug — found earlier, fixed in this pass

Prior reports found 2 "unique" candidates were actually explanation-section text, and 5 more had truncated statement-list stems. Direct source inspection (Botany Q51) found the exact cause: **statement lists use uppercase `A./B./C./D.`, while the real answer options always use lowercase `a./b./c./d.`** The original regex was case-insensitive and stopped stem-collection at the first uppercase statement line, truncating both the stem and the real options. **Fixed**: the option-detection regex is now lowercase-only. Verified directly — Botany Q51 now extracts its full statement list and its real options (`C only`/`D only`/`B only`/`A only`) correctly, where before it had wrongly captured the uppercase statements themselves as if they were the options.

## 2. Re-extraction results

| | Before fix | After fix |
|---|---:|---:|
| Total extracted | 148 | **158** |
| Chemistry | 34 | 38 |
| Physics | 29 | 31 |
| Botany | 85 | 89 |

## 3. Deduplication — re-run against the corrected extraction

Method unchanged from the prior validation pass (significant-word Jaccard similarity against all 12,396 existing PYQs, reusing `_significant_words()` from `grounding_check.py`):

| Classification | Count |
|---|---:|
| `exact_duplicate` | 53 |
| `near_duplicate_high_confidence` (≥0.85) | 86 |
| `near_duplicate_uncertain` (0.55–0.85) | 17 |
| `unique` (<0.55) | 2 |
| **Total duplicate/overlap** | **139 (88.0%)** |
| **Total candidate pool** | **19 (12.0%)** |

**The fix itself improved duplicate-detection accuracy**, not just extraction completeness: previously-truncated stems had artificially low word-overlap with their true matches, undercounting duplicates. Confirms these compilations are, as suspected, overwhelmingly a reorganization of already-known PYQs.

## 4. Answer recovery

**38 of the 86 high-confidence near-duplicates** had an already-`VERIFIED` matched existing PYQ — inherited that answer with explicit provenance (`inherited_from_verified_pyq:<id>:similarity=X.XX`). No answer key for these specific 2024 compilations was located; no answer was guessed or assigned to any of the 19 candidates.

## 5. Manual quality check of all 19 candidates (not sampled)

All 19 read as **structurally complete and clean** post-fix — no further explanation-artifact or truncation defects found, **except one**: `Chemistry #40` still has a corrupted stem (`"For the given reaction C = CH 'P' (major product) H KMnO4/H+ 'P' is a. CH CH OH OH..."`) — an organic-chemistry reaction-scheme question whose structural diagram/notation was lost in extraction, a different defect (diagram-dependent, not caught by the lowercase-option fix). **Excluded from import.**

## 6. Diagrams

8/8 previously figure-dependent questions: source page located, rendered at 200 DPI, saved to `docs/quality/_book_mcq_extraction_2026-10-03/diagram_pages/`. Unchanged from the prior pass (the regex fix didn't affect these).

## 7. Chapter/topic metadata

19/158 (12%) received a taxonomy-keyword-based chapter assignment at a conservative confidence floor; the remainder were **left unclassified rather than guessed**, per instruction. Still a low hit rate — the coarse keyword-overlap method remains a real limitation, not fixed in this pass.

## 8. Staging import — completed, local dev database only

**18 of 19 candidates imported** (all except the still-corrupted `Chemistry #40`), using the existing `pyq.questions`/`pyq.source_files`/`pyq.import_batches`/`pyq.sources` schema, with a **new, distinct `pyq.sources` row** (`source_key='NEET_2024_BOOK_COMPILATION_CHAPTERWISE'`, `authority_type='THIRD_PARTY_COMPILATION'`) so these are never confused with `NEET_PYQ_OFFICIAL` rows.

```sql
-- Idempotency key used (the schema's real constraint, confirmed by inspection,
-- not assumed): UNIQUE (source_file_id, question_number, extraction_version)
```

| Check | Result |
|---|---|
| `pyq.questions` total before | 12,396 |
| `pyq.questions` total after | **12,414** (+18, exactly matching the import count) |
| By source | `NEET_PYQ_OFFICIAL`: 12,396 (unchanged) · `NEET_2024_BOOK_COMPILATION_CHAPTERWISE`: 18 (new) |
| State assigned | `ANSWER_PENDING` for all 18 (no answer source available — schema's existing pending status used, no new status invented) |
| Idempotency re-test | Re-ran the identical insert once more — **0 new rows created**, confirmed by direct count |
| Existing PYQs modified | **0** |
| **Database target** | **Local dev `trinetra_db` only. Not production.** |

## 9. Tests

No application code was changed (extraction/validation/import scripts are evidence-only, not integrated into the pipeline) — no new automated tests were required. The import itself was verified by direct post-insert query (Section 8), not by a formal test suite run.

## 10. Final reconciled counts

| Stage | Count |
|---|---:|
| Found in source (text-native files only; 3 scanned files still pending OCR, not counted here) | 158 |
| Successfully extracted | 158 |
| Structurally validated (stem + 4 options present) | 158 |
| Exact + near-duplicate (excluded as not net-new) | 139 |
| Candidate pool | 19 |
| Rejected for residual corruption | 1 (`Chemistry #40`) |
| **Imported** | **18** |
| Independently verified | **0** — none have a confirmed-correct answer; all are `ANSWER_PENDING` |
| Answer-supported via legitimate inheritance (within the 139 duplicates, not the 18 imported) | 38 |
| Production-deployed | **0 — not authorized, not attempted** |

## 11. Remaining accessible materials still requiring extraction

Unchanged from the prior report: `NEET-2025-Answer-Key.pdf` (actually the 2025 question booklet, scanned), `NEET-2026-WITH-WATER-MARK...pdf` and `RE-NEET-QUESTIONS-COMPRESSED.pdf` (third-party, scanned) — all need full OCR, not performed in this pass.

## Exact paths

- `docs/quality/_book_mcq_extraction_2026-10-03/extract_book_mcqs_script.py` (fixed)
- `docs/quality/_book_mcq_extraction_2026-10-03/extracted_book_mcqs.json` (158, corrected)
- `docs/quality/_book_mcq_extraction_2026-10-03/validate_book_mcqs_script.py`
- `docs/quality/_book_mcq_extraction_2026-10-03/validated_book_mcqs.json` (158, corrected)
- `docs/quality/_book_mcq_extraction_2026-10-03/diagram_pages/` (8 PNGs)
- This report (final, Phase 1 complete)

**Phase 1 is complete.** 18 net-new, deduplicated, structurally-validated questions staged in the local dev database with distinct, traceable provenance and `ANSWER_PENDING` status. Proceeding to Phase 2 planning (gap analysis + generation-cost gate) in a separate report, per the task's required sequencing.
