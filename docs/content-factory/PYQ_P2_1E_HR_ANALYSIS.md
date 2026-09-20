# PYQ P2.1E Human Review — Failure Mode Analysis (Baseline R1)

**Reviewed:** `data/staging/pyq/2020-2025/p2_1e_full/` (baseline — not modified)  
**Sample source:** `samples.p2_1e_full.json`, `questions.p2_1e_full.jsonl`, `manifest.p2_1e_full.json`  
**Date:** 2026-09-01

## Executive summary

Of **2,200 PARTIAL** records in baseline R1, failure modes are **systematic and repeatable** — not random OCR noise. The dominant issue is **inline option merge** (~61% of PARTIAL). Parser fix R2 targets this pattern deterministically without relaxing question-boundary rules.

## Failure mode taxonomy (PARTIAL n=2,200)

| Rank | Failure mode | Est. count | Description |
|------|--------------|------------|-------------|
| 1 | **Inline option merge** | ~1,340 | OCR places `(1)…(2)…` on one line; line-start parser captured only first marker → merged text like `Negative (2) Zero` |
| 2 | **Missing some options** | ~561 | Partial `(1)–(4)` sets; often paired with inline merge or OCR dropout |
| 3 | **No options extracted** | ~218 | Question stem found but zero options — often question fragmentation (Q4/Q5 dipole split) |
| 4 | **Options in stem** | ~81 | Option markers embedded in stem OCR (`() 3:1 (2) 1:2`) |
| 5 | **Question-to-question bleed** | (subset) | Block extends to next question when only one validated marker in column (Q15 case — **fixed for options** in R1, stem-only bleed remains) |
| 6 | **OCR fragmentation** | (subset) | Split stems across false Q markers (Q4 continuation of Q5 dipole) |
| 7 | **Diagram-dependent** | 211 total | Correctly classified — not targeted in R2 |
| 8 | **Two-column ordering** | low in R1 | cross_column_flags=0; not primary R2 target |

## Priority cases reviewed

### Q15 inline option merge (HR regression paper, page 3)

**Stem (correct):** "The net magnetic flux through any closed surface is :"  
**R1 options:** `['Negative (2) Zero', '', 'Positive (4) Infinity', '']`  
**Root cause:** Line-start `(1)` / `(3)` detection missed inline `(2)` / `(4)` on same OCR lines.  
**Q20 bleed:** Successfully blocked in R1 — no 223K/669°C tokens.  
**R2 fix:** Split all inline `(1)–(4)` markers via `OPTION_START_RE`; cap option (4) at line boundary; stop at second `(1)` after complete set.

### Q5 (page 2)

**Stem (correct):** Electric dipole question — false `(4) 5 A from A to B through E` rejected.  
**R1 issue:** Options missing (PARTIAL) — stem fragmented across Q4/Q5 OCR markers; **not fixed in R2** (segmentation, not option parsing).

### Q4/Q5 fragmentation (systematic)

OCR emits spurious Q4 marker mid-dipole stem; options attach to Q4 block. Requires marker validation / merge heuristics — **deferred** to avoid overfitting.

## Parser changes for R2

1. **`parse_options_bounded()`** — use global `OPTION_START_RE` (inline-capable) instead of line-start-only matching.
2. **Bounded set** — first contiguous `1→2→3→4` sequence; truncate at second `(1)`.
3. **Line cap on option (4)** — prevent trailing question text from attaching to last option when next `(1)` is distant.
4. **Preserved:** Q15→Q20 boundary protection, Q5 false-marker rejection, idempotent hashing.

## Out of scope for R2

- AI/network calls
- Semantic OCR correction
- Question marker merge for fragmented stems (Q4/Q5)
- Production import / P3/P4/P5

## Expected R2 impact

- **Inline option merge** → large PARTIAL→VALID conversion expected
- **VALID count** should rise; **PARTIAL** should fall
- **Question count** should remain ~stable (no inflation from loosened markers)
- **Q15** should become VALID with clean four options
- **Q5** may remain PARTIAL (fragmentation)
