# P2.1F Root-Cause Analysis (Read-Only)

**Status:** COMPLETE
**Timestamp:** 2026-09-01T16:18:23.795177+00:00

## Executive summary

Confirmed cross-column contamination: **25** cases audited.
Primary failure modes are **question boundary** and **option boundary** failures in two-column LEFT streams,
not column-order swaps. Q15/Q20 inline fix remains PASS.

## Step 1 — Confirmed case population

| Expected | Observed |
|----------|----------|
| 25 | 25 |

HR Q3 p2 (00d8cababe821fcf) cross-flagged; see Step 5.

## Step 3 — Root cause frequency

| ROOT CAUSE | COUNT | % OF 25 | EXAMPLES |
|------------|------:|--------:|----------|
| OPTION BOUNDARY FAILURE (C) | 20 | 80.0% | 00d8cababe821fcf:p8:q3, 10030e374de702ab:p9:q3 |
| OCR SOURCE CORRUPTION (I) | 3 | 12.0% | 00d8cababe821fcf:p11:q73, 8633a3811ea07447:p13:q82 |
| QUESTION BOUNDARY FAILURE (B) | 1 | 4.0% | 8633a3811ea07447:p5:q4 |
| QUESTION MARKER DETECTION FAILURE (F) | 1 | 4.0% | 1d7ffd36a442fa95:p2:q3 |

## Step 5 — 2023 Q3/Q5 case (detailed reconstruction)

### Important paper distinction

The **canonical dipole-in-option_c defect** appears on paper `1d7ffd36a442fa95` (Paper-20231108005054), record `1d7ffd36a442fa95:p2:q3`:
- **option_c** contains full Q5 dipole stem text embedded after option markers
- **quality:** DIAGRAM_DEPENDENT (cross-flagged, Class-E adjacent)
- **primary root cause:** F (QUESTION MARKER DETECTION) + C (OPTION BOUNDARY)

On the **HR regression paper** `00d8cababe821fcf` (Paper-20231108005448), R2 parsed Q3 p2 options are **clean** (no dipole in options, no cross_column flag). The related defect manifests as **Q4/Q5 fragmentation** on the same page (see Step 9).

### Extraction path (1d7ffd36 Q3 p2 — canonical case)

| Stage | What happened |
|-------|---------------|
| SOURCE/PDF | Two-column page 2; rectifier Q3 LEFT column above dipole Q5 |
| OCR WORDS | Column text preserves `(3) transformer` then `4) p-n diodes` then `4 An electric dipole...` |
| GEOMETRY | TWO_COLUMN; LEFT column reading order top→bottom |
| READING ORDER | Q5 stem follows Q3 option markers without validated `5` line-start marker |
| **QUESTION SEGMENTATION** | **FIRST FAILURE:** Q3 block extends from Q3 marker to next validated marker; includes dipole lines |
| **QUESTION MARKER DETECTION** | **Contributing:** `4 An electric dipole` parsed as option `(4)` not question 5 |
| **OPTION SEGMENTATION** | **Visible failure:** option_c absorbs text from `(3)` through false `(4)` including dipole stem |
| CLASSIFICATION | DIAGRAM_DEPENDENT + foreign-marker flag; not downgraded from VALID |

## Step 6 — Six VALID contaminations

Count: **6**

- `00d8cababe821fcf:p8:q3` — VALID must require zero geometry_quality_flags and no foreign question stem tokens in options
- `8633a3811ea07447:p20:q133` — VALID must require zero geometry_quality_flags and no foreign question stem tokens in options
- `a1c3361678271d6e:p24:q162` — VALID must require zero geometry_quality_flags and no foreign question stem tokens in options
- `a43894b5fbc8cd28:p9:q3` — VALID must require zero geometry_quality_flags and no foreign question stem tokens in options
- `d11cf53d4d8ef5b0:p30:q195` — VALID must require zero geometry_quality_flags and no foreign question stem tokens in options
- `f5378eb6785774c3:p21:q145` — VALID must require zero geometry_quality_flags and no foreign question stem tokens in options

## Step 8 — Other 19 cross-column flags

Classifications: {'OCR_ARTIFACT': 19} — predominantly OCR page-number artifacts; not release blockers.

## Step 10 — Generalized remediation (no code)

### Question block must end before foreign validated question ma…
- **Covers:** 2 cases
- **Type:** DETERMINISTIC_FIX

### Option text must not extend past line-cap OR next question-n…
- **Covers:** 8 cases
- **Type:** DETERMINISTIC_FIX

### VALID quality forbidden when geometry_quality_flags non-empt…
- **Covers:** 6 cases
- **Type:** DETERMINISTIC_FIX

### Reject option fields containing foreign question stem token …
- **Covers:** 6 cases
- **Type:** DETERMINISTIC_FIX

### Merge/heal spurious mid-stem question markers (Q4 fragment o…
- **Covers:** 2 cases
- **Type:** DETERMINISTIC_FIX

## Step 9 — Q5 root cause (HR paper 00d8cababe821fcf p2)

| Finding | Evidence |
|---------|----------|
| Q5 quality | PARTIAL — stem correct, zero options |
| Q4 quality | PARTIAL — stem is dipole fragment; options contain 2/4/6/4 mC |
| Q3 quality | VALID — parsed options clean post-R2 inline fix |
| Root cause | **B+F** (same family as 1d7ffd36 Q3, distinct manifestation) |
| Option parser fault | **No** — options absent because segmentation assigned them to Q4 |
| Related to cross-column 25 | **Yes** — same column stream; HR Q3 not in confirmed 25 but Q4 p5 (8633a381) is |
| Disposition | **REMAIN_PARTIAL** |

## Step 7 — VALID vs other 19

**COMMON_ROOT_CAUSE = TRUE** — all 6 VALID contaminations share option-boundary / foreign-marker mechanism with the other 19 confirmed cases; difference is classification layer (G) failed to reject flagged VALID records.

## Step 11 — AI requirement

| Failure type | Classification |
|--------------|----------------|
| Option boundary / question boundary | **DETERMINISTIC_FIX** |
| VALID+flag classification gap | **DETERMINISTIC_FIX** |
| OCR garbled chemistry strings | **HUMAN_REVIEW** |
| Diagram-dependent pages | **HUMAN_REVIEW** |
| Q5 stem fragmentation | **DETERMINISTIC_FIX** (marker merge) — not AI |

**AI_RECOVERY: not required** for the 25 confirmed contamination cases.
