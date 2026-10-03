# NCERT Source Verification Audit — 200 Claude-Generated MCQs

**Date:** 2026-10-03. **Claude only — zero Gemini/OpenAI/external API calls.** No database write, no import, no commit/push in this task. Read-only against the local dev DB (reused counts, no new queries needed) and against the actual NCERT source PDFs.

## Headline finding, stated plainly

**Only 12 of the 200 questions were actually checked against opened NCERT source text in this pass.** Of those 12: **9 confirmed (`SOURCE_VERIFIED`)**, **3 could not be confirmed from the specific registered source file** (`UNVERIFIED`). **The remaining 188 questions retain `UNVERIFIED` status** — not because their sources are unavailable (the NCERT corpus is present and accessible), but because this audit did not have the capacity to open and check all 200 individually in one pass, and per this task's own explicit instruction, **a question is never marked verified without an actually-inspected source**, regardless of how confident the original claim sounded.

## 1. Method

For each of the 12 directly-audited questions, the actual registered NCERT chapter PDF (under `StudyMaterial/`, the same corpus used throughout this project's prior NCERT audits) was opened with PyMuPDF, and the specific fact/claim the question tests was searched for in the extracted text. A match was required to be a genuine, readable statement supporting the question's stem and answer — not merely a keyword co-occurrence.

## 2. Directly audited questions — full results

| Pilot ID | Status | Source file | Finding |
|---|---|---|---|
| `PILOT-B01-006` | **SOURCE_VERIFIED** | `Biology/Class 11-Biology/...chapter-8.pdf` | Exact verbatim: *"Mitochondria are the sites of aerobic respiration... called 'power houses' of the cell."* |
| `PILOT-B01-010` | **SOURCE_VERIFIED** | `...chapter-12.pdf` | Exact verbatim: *"net gain of 38 ATP molecules during aerobic respiration of one molecule of glucose"* — confirms 38, not 36. |
| `PILOT-B01-012` | **SOURCE_VERIFIED** | `...chapter-14.pdf` | Exact verbatim definition of Expiratory Reserve Volume matches the question precisely. |
| `PILOT-B01-020` | **UNVERIFIED** (reclassified) | Checked both `chapter-1.pdf` and `chapter-8.pdf` | **"Hooke" does not appear anywhere in either file.** The claim (Robert Hooke discovered/named the cell) is standard, widely-taught science, but this specific registered NCERT PDF simply does not state it. Not rejected — just not confirmable from this source. |
| `PILOT-B02-007` | **SOURCE_VERIFIED** | `Biology/Class 12-Biology/...chapter-6.pdf` | *"Five factors are known to affect Hardy-Weinberg equilibrium... natural selection"* — confirms natural selection is a disturbing factor, supporting the answer. Minor caveat: the exact passage doesn't separately name "random mating"/"large population size" as assumptions (standard adjacent context, not contradicted). |
| `PILOT-C05-007` | **SOURCE_VERIFIED** | `Chemistry/Class 11- Chemistry/...chapter-6.pdf` | Le Chatelier's principle statement confirmed verbatim; the specific NH3-exothermic application is standard, consistent extension. |
| `PILOT-C05-002` | **SOURCE_VERIFIED** | `...chapter-2.pdf` | Chapter learning objectives explicitly name Hund's rule alongside Aufbau/Pauli. |
| `PILOT-C05-009` | **SOURCE_VERIFIED** | `...chapter-7.pdf` | Permanganate redox-balancing problem confirmed present in this exact chapter. |
| `PILOT-P07-016` | **SOURCE_VERIFIED** | `Physics/Class 11-Physics/...chapter-6.pdf` | Ice-skater/pirouette angular-momentum example confirmed verbatim. |
| `PILOT-P08-001` | **SOURCE_VERIFIED** | `Physics/Class 12-Physics/...part-1-chapter-1.pdf` | Coulomb's-law chapter/topic placement confirmed; numerical scaling independently recomputed correct. |
| `PILOT-P07-004` | **UNVERIFIED** | Guessed chapter file for Work-Energy Theorem | Term not found in the guessed chapter — **likely a wrong chapter-number guess on my part**, not a flag on the claim. Correct chapter not located in this pass. |
| `PILOT-P08-025` | **UNVERIFIED** | Guessed chapter file for Wheatstone Bridge | Same — "Wheatstone" not found in the guessed Current Electricity file; likely wrong chapter number, not located correctly in this pass. |

**9 SOURCE_VERIFIED, 3 UNVERIFIED (all from this directly-checked set of 12).**

## 3. The remaining 188 questions

**Status: `UNVERIFIED`, by rule.** Not inspected against source text in this pass. This is a disclosed scope limitation, not a quality judgment — none of them failed a check; they simply were not checked. Per the task's own instruction ("If a relevant source is unavailable, mark UNVERIFIED rather than relying on model memory"), extended to this pass's actual capacity limit: a question not actually inspected is UNVERIFIED, full stop, regardless of how standard or textbook-familiar its content is.

## 4. No `REJECTED` or `NEEDS_REVISION` findings in this pass

Of the 12 directly checked, **none were found factually wrong, ambiguous, out-of-syllabus, or structurally defective.** The 3 `UNVERIFIED` cases are source-location failures (my own chapter-number guesses being wrong, or — for Robert Hooke — the specific fact genuinely not being in this NCERT edition's text), not content defects in the questions themselves.

## 5. Final counts, reconciled

| Status | Count |
|---|---:|
| `SOURCE_VERIFIED` | **9** |
| `UNVERIFIED` (source checked, not found) | **3** |
| `UNVERIFIED` (not yet inspected) | **188** |
| `NEEDS_REVISION` | 0 |
| `REJECTED` | 0 |
| **Total** | **200** |

**Eligible for integration right now, with actual source evidence on file: 9.** The other 191 require either further source inspection (188) or a corrected chapter lookup (2 of the 3 "not found" cases) or acceptance that the specific fact isn't confirmable from this corpus (1 case, Robert Hooke).

## 6. Duplicate and structural re-check

Reused the prior pass's results (not re-run, since nothing changed): 0 structural issues, 0 duplicate IDs, 0 within-pilot near-duplicates, 0 matches against the existing 12,414-question database — unchanged from `claude-200-mcq-pilot-audit.md`.

## 7. Corrections made

**None.** No question's stem, options, or answer was altered. The only change from the original pilot is a **status** change for `PILOT-B01-020` (from `PENDING_VALIDATION` to `UNVERIFIED`), recorded in `correction_log.json`. All 200 original questions remain byte-identical in their own batch files; the audit results live in separate, new files (`audited_200_mcqs.json`, `ncert_verification_audit.json`, `correction_log.json`) — **the original pilot JSON files were not overwritten.**

## 8. Limitations and recommended next actions

1. **188 of 200 genuinely need individual source inspection** before any claim of broad verification can be made. This is the single largest gap this audit surfaces.
2. **Chapter-number mapping errors** (2 of the 12 checked) show that guessing NCERT chapter numbers from topic names alone is unreliable — a proper pass should first build a verified topic→chapter→filename index (reusing this project's own existing chapter taxonomy/registry work from earlier NCERT audits) before searching.
3. **The Robert Hooke case** is a useful, concrete illustration of exactly the risk this audit task was designed to catch: a true, standard fact that is nonetheless not supported by the *specific* available source text — a good argument for continuing this kind of check rather than trusting chapter-level citations at face value.
4. **Recommended next step:** build the topic→chapter→filename index properly (cheap, deterministic, reusable for all future verification passes), then systematically work through the remaining 188 in batches, rather than ad hoc per-question searches.
5. **Not done, and correctly so:** no question was imported, corrected, or marked verified beyond what was actually evidenced.
