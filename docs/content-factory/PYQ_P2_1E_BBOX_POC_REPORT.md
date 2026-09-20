# PYQ P2.1E Bbox OCR Proof-of-Concept Report

**Generated:** 2026-09-01T13:49:28.040834+00:00
**Verdict:** **YELLOW**
**Mode:** Targeted re-OCR with persisted Tesseract word geometry (POC only)
**Output:** `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025\p2_1e`

## 1. Executive verdict

**YELLOW — material fidelity improvement demonstrated; not production-ready.**

P2.1E proves that **persisted Tesseract word bounding boxes + x-coordinate column clustering** materially improves source fidelity on targeted NEET pages versus P2.1B/P2.1C text-only geometry.

| Result | Value |
|--------|-------|
| Target pages OCR'd | 24 (not full 1,008) |
| Bbox geometry valid | 24/24 |
| Fidelity rate (A+B) | **64.0%** (baseline 1.8%) |
| HR Q5 regression | **PASS** — dipole stem recovered |
| HR Q15 regression | **PASS** (forbidden tokens); options still imperfect |
| Idempotent | **TRUE** |
| Tests | **76 passed**, 0 failed |

**Not GREEN:** Q15 options still bleed from adjacent questions; Q5 options empty; full corpus not OCR'd.

## 2. Target page selection

| SHA (prefix) | Page | Category | Reason |
|--------------|-----:|----------|--------|
| `00d8cababe82…` | 2 | A_Q5_regression | Q5 stem bleed / false marker |
| `00d8cababe82…` | 3 | B_Q15_regression | Q15/Q11 option contamination |
| `00d8cababe82…` | 1 | F_instruction_bilingual | Instruction cover — must not yield questions |
| `00d8cababe82…` | 6 | D_one_column | Physics Section B single-column layout |
| `00d8cababe82…` | 7 | E_diagram | Diagram-dependent Q43/Q44 circuit pages |
| `00d8cababe82…` | 4 | C_two_column_contamination | TWO_COLUMN physics continuation |
| `00d8cababe82…` | 31 | D_one_column | Rough-work blank page |
| `00d8cababe82…` | 8 | G_page_boundary | Chemistry section start / page boundary |
| `00d8cababe82…` | 11 | C_two_column_contamination | Low pipe ratio TWO_COLUMN page |
| `1d7ffd36a442…` | 2 | C_cross_column | cross_column_signature gravitational+mc |
| `1d6b4be1305c…` | 7 | C_cross_column | option_contains_foreign_question_marker |
| `1d6b4be1305c…` | 12 | C_two_column_contamination | foreign Q marker in options |
| `b69d582ff457…` | 8 | C_cross_column | cross-column option bleed 2024 paper |
| `b69d582ff457…` | 18 | H_false_positive | fragment / false marker chemistry |
| `cd4583ce844d…` | 7 | C_cross_column | merged stem across columns 2024 |
| `d11cf53d4d8e…` | 18 | C_cross_column | biology cross-column merge page 18 |
| `f5378eb67857…` | 7 | C_cross_column | physics bridge question merge |
| `10030e374de7…` | 1 | F_instruction_bilingual | Second paper instruction page |
| `10030e374de7…` | 2 | C_two_column_contamination | UNKNOWN layout contamination alternate booklet |
| `10030e374de7…` | 5 | E_diagram | Diagram LCR / galvanometer page |
| `10030e374de7…` | 6 | D_one_column | Section B one-column style page |
| `2224099d43d7…` | 2 | H_false_positive | High orphan / false marker density |
| `2224099d43d7…` | 3 | G_page_boundary | Page 2→3 boundary continuation |
| `530db8cab5eb…` | 2 | C_two_column_contamination | 2025 paper TWO_COLUMN bleed sample |

## 3. Tesseract configuration

| Setting | Value |
|---------|-------|
| Engine | Local Tesseract CLI |
| Language | eng |
| PSM | 6 |
| Output | TSV (full word geometry) |
| DPI | 200 (matches P2.1 staging) |

## 4. BBOX persistence validation

| Metric | Value |
|--------|------:|
| Word records persisted | 24 pages |
| Pages geometry-valid | 24 |

## 5. Geometry detection results

| Layout | Pages |
|--------|------:|
| ONE_COLUMN | 3 |
| TWO_COLUMN | 21 |

## 6. Q5 before/after

### P2.1C (before)

Stem: `A from A to B through E
transformer, capacitor and a load resistance. 9
Which of these components remove the ac`

### P2.1E (after)

Stem: `An electric dipole is placed at an angle of
30° with an electric field of intensity
2x10°NC!. It experiences a torque equal to
4`
Options: ['', '', '', '']
Quality: PARTIAL

## 7. Q15/Q11 before/after

| Field | P2.1C | P2.1E |
|-------|-------|-------|
| Stem | `The net magnetic flux through any closed…` (partial) | `The net magnetic flux through any closed surface is :` ✓ |
| Options | Empty (not faithful) | `223K, 669°C…` — **wrong options** (Q20 bleed on right column) |
| Q11 error types | PASS (empty) | PASS (no Random/Instrumental/Personal error) |

**Interpretation:** P2.1E fixes Q15 **stem** and eliminates Q11 error-type contamination, but right-column option boundaries still need tightening (within-column bleed to Q20 options).

## 8. HR regression results

- **Q5_must_not_have_Q8_resistor_colors**: **PASS**
  - Stem contains `An electric dipole is placed…` (correct source region)
  - No `through E`, `transformer`, `capacitor` contamination
  - Options empty (PARTIAL — diagram/numeric OCR limits)
- **Q15_must_not_have_Q11_error_types**: **PASS** (forbidden-token check)
  - Stem correct; options not yet faithful (see §7)

## 9. Fidelity metrics

| Metric | P2.1E POC | P2.1B-HR baseline |
|--------|----------:|------------------:|
| fidelity_rate (A+B) | 64.0% | 1.8% |
| false_positive_rate (E) | 0.8% | 9.1% |
| fragment_rate (D) | 0.8% | 9.1% |

Class counts: `{'C': 27, 'A': 80, 'F': 16, 'D': 1, 'E': 1}`

## 10–12. Pipeline comparison / cross-column / idempotency

```json
{
  "p2_1": {
    "question_count": 9,
    "quality_breakdown": {
      "EXTRACTED": 8,
      "NEEDS_REVIEW": 1
    },
    "cross_column_flags": 0
  },
  "p2_1b": {
    "question_count": 89,
    "quality_breakdown": {
      "PARTIAL": 29,
      "VALID": 49,
      "NEEDS_REVIEW": 6,
      "DIAGRAM_DEPENDENT": 5
    },
    "cross_column_flags": 0
  },
  "p2_1c": {
    "question_count": 182,
    "quality_breakdown": {
      "VALID": 45,
      "PARTIAL": 86,
      "NEEDS_REVIEW": 36,
      "DIAGRAM_DEPENDENT": 15
    },
    "cross_column_flags": 8
  },
  "p2_1e": {
    "question_count": 125,
    "quality_breakdown": {
      "PARTIAL": 27,
      "VALID": 90,
      "DIAGRAM_DEPENDENT": 8
    },
    "cross_column_flags": 3,
    "fidelity": {
      "fidelity_rate": 64.0,
      "false_positive_rate": 0.8,
      "fragment_rate": 0.8,
      "counts": {
        "C": 27,
        "A": 80,
        "F": 16,
        "D": 1,
        "E": 1
      },
      "total": 125
    }
  }
}
```

**Idempotent:** words=True, questions=True

## 13. Tests

```
76 passed, 0 failed
```

New P2.1E tests (`test_pyq_p2_1e.py`): bbox persistence, column detection, Q5 false-marker rejection, Q3/Q7 bleed prevention, Q15 pipe-heal, instruction page, diagram handling.

## 14. Safety attestation

| Check | Status |
|-------|--------|
| production_db_writes | **0** |
| ai_provider_calls | **0** |
| network_calls | **0** |
| source_zip_modified | **0** |
| source_pdfs_modified | **0** |
| env_modified | **0** |
| full_corpus_ocr | **0** |
| force_flag_used | **0** |
| p3_run | **0** |
| p4_run | **0** |
| p5_run | **0** |
| Full 1,008-page OCR | **NOT RUN** |
| Full --force OCR | **NOT RUN** |

## 15. Recommendation for full-corpus implementation

**Authorize staging-only full-corpus P2.1E** with these conditions:

1. Persist `ocr.words.p2_1e.jsonl` per paper (new files — do **not** overwrite `ocr.pages.p2_1.jsonl`).
2. Re-segment using bbox column clustering + validated question markers + pipe-heal + duplicate-marker dedupe.
3. Keep question count subordinate to fidelity — expect **lower** VALID count than P2.1C with **higher** faithfulness.
4. Before P3: run human fidelity spot-check on ≥50 bbox-extracted questions; tighten option boundary rules (Q15 case).
5. Do **not** claim GREEN until full-corpus HR sample matches or exceeds POC fidelity rate.

### Key P2.1E techniques proven

| Technique | Purpose |
|-----------|---------|
| Tesseract TSV bbox persistence | True L/R column assignment |
| x-valley column split | Replace pipe/orphan heuristics |
| Validated question markers | Reject `(4) 5 A from…` false Q5 |
| Duplicate Q# dedupe | Prefer longest / question-context marker |
| Pipe-split heal (`Q11 text \| 15`) | Reattach orphaned Q15 to right column |

### Artifacts (isolated)

| File | Location |
|------|----------|
| Word geometry | `data/staging/pyq/2020-2025/p2_1e/ocr.words.p2_1e.jsonl` |
| Questions | `data/staging/pyq/2020-2025/p2_1e/questions.p2_1e_geometry.jsonl` |
| Manifest | `data/staging/pyq/2020-2025/p2_1e/manifest.p2_1e.json` |
| Code | `pyq_ocr.py` (bbox parse), `pyq_p2_1e.py`, `run_pyq_p2_1e_poc.py` |
