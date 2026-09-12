# PYQ P2.1D — OCR Geometry Feasibility + Within-Column Bleed Diagnostic

**Phase:** FACTORY-PYQ-P2.1D  
**Date:** 2026-09-01  
**Mode:** Diagnostic only (no re-OCR, no `--force`, no P3+)  
**Input corpora:** P2.1 OCR staging + P2.1C geometry resegmentation  
**Diagnostic artifact:** `data/staging/pyq/2020-2025/diagnostics_p2_1d_feasibility.json`  
**Prior verdict:** P2.1C **YELLOW**

---

## 1. Executive verdict

**YELLOW — within-column OCR bleed is not reliably remediable without persisted word-level geometry.**

P2.1C successfully reduced **cross-column** option swaps (Q5 no longer carries Q8 colour-code options; Q15/Q11 regression PASS). The dominant remaining failure mode is **within-column text merge** on scanned NEET pages where Tesseract emits interleaved L↔R reading order **without** pipe (` | `) separators on most lines (~93% of lines on typical question pages are orphan lines).

**Word-level OCR geometry is unavailable in existing P2.1 artifacts.** Tesseract TSV is generated transiently during P2.1 OCR and coordinates are discarded before persistence. Reconstructing x/y positions from flattened `raw_text` is not valid.

| Path | Feasibility |
|------|-------------|
| Deterministic non-OCR filters (section Q#, instruction skip, option-like stem rejection) | **Partial** — reduces false positives (~410 records in probe) but **cannot** fix merged stems like Q5 |
| Stronger pipe/orphan heuristics on existing text | **Low** — 439/1008 pages have >30 orphan lines; orphan assignment uses numbering context that misfires when OCR embeds `"5 A from..."` as a false Q5 marker |
| Geometry-first column assignment without re-OCR | **Not feasible** — PDF word layer is empty (`word_count=0` on all 1008 pages); no persisted Tesseract boxes |
| Re-OCR with TSV/bbox persistence (future P2.1E) | **Required** for faithful 2-column segmentation on image-only PDFs |

**Recommendation:** Do **not** proceed to P3/P4/P5. Next implementation should be **P2.1E — OCR geometry persistence + column assignment from x-coordinates**, followed by re-segmentation. Until then, treat P2.1C `VALID` (1,465 / 6,217) as an upper-bound quality gate, not source fidelity.

**Source fidelity remains the primary metric**, not question count.

---

## 2. Available geometry evidence

Evidence was searched in: `pyq_ocr.py`, `pyq_extraction.py`, `pyq_geometry.py`, `pyq_p2_1c.py`, P2.1 manifest, `ocr.pages.p2_1.jsonl`, P2.1C annotations, and all staging JSON/JSONL (grep for `x0`, `y0`, `block_num`, `word_num`, `bbox` — **zero matches**).

| ID | Evidence type | Available? | Where / notes |
|----|---------------|------------|---------------|
| A | Original PDF page dimensions (mediabox) | **YES** | PyMuPDF `page.rect` — consistently **595×841** pt; stored in `ocr.pages.p2_1c_geometry_annotations.json` per paper |
| B | PDF embedded word layer | **NO** | `page.get_text("words")` → **0 words** on all 1,008 OCR pages across 31 papers |
| C | OCR pipe column markers (` \| `) | **YES** | In `raw_text` only; mean pipe_line_ratio **0.054** (max 0.218); page 2 regression paper: **0.068** (3 pipe lines / 44 total) |
| D | OCR line boundaries | **YES** | Newline-separated lines in `raw_text`; block/line order used internally during TSV parse |
| E | OCR block boundaries | **PARTIAL** | `block_num` + `line_num` used in `_text_and_confidence_from_tsv()` to join words into lines; **not persisted** |
| F | Tesseract word bounding boxes | **NO** | TSV columns 6–9 (`left`, `top`, `width`, `height`) exist at OCR time but are **discarded** |
| G | Tesseract TSV files | **NO** | Written to temp dir (`pyq_ocr_*`); deleted on exit |
| H | Image/pixel coordinates | **NO** | Page PNGs not retained in staging |
| I | P2.1C layout metadata | **YES** | `layout`, `split_x`, `pipe_line_ratio`, `orphan_lines`, `word_count` in per-paper geometry annotations |

**Orphan-line scale (P2.1C annotations, 1,008 pages):**

| Metric | Value |
|--------|------:|
| Mean orphan lines per 2-column page | 18.9 |
| Max orphan lines (single page) | 78 |
| Pages with orphan_lines > 30 | 439 |

Orphan lines are assigned to L/R columns by question-number heuristics (`_assign_orphan_lines` in `pyq_geometry.py`) — effective only when OCR question markers are clean.

---

## 3. Whether Tesseract word boxes exist

**No. Word-level OCR geometry is unavailable in existing P2.1 artifacts.**

### Implementation trace (`pyq_ocr.py`)

During P2.1 OCR, Tesseract is invoked with `tsv` output:

```186:209:apps/backend/app/modules/cms/pyq/pyq_ocr.py
        cmd_tsv = [
            executable,
            str(img_path),
            str(base),
            "-l",
            lang,
            "--psm",
            "6",
            "tsv",
        ]
        ...
        tsv_path = Path(str(base) + ".tsv")
```

`_text_and_confidence_from_tsv()` reads TSV but extracts only **`block_num` (col 2), `line_num` (col 4), word text (col 11), confidence (col 10)**. Columns for **`left`, `top`, `width`, `height`** are never read or stored. The temp directory is removed when the function returns.

### Persisted OCR page schema (`ocr.pages.p2_1.jsonl`)

Fields per page: `page_number`, `status`, `validation_status`, `ocr_confidence`, `text_chars`, `raw_text`, `anomalies`. **No coordinate fields.**

### Staging grep

No `x0`, `y0`, `x1`, `y1`, `block_num`, `word_num`, or bounding-box keys in any staging JSON/JSONL.

**Conclusion:** Coordinates cannot be recovered without re-OCR (or re-running P2.1 with a modified pipeline that persists TSV/bboxes). Do not infer fake coordinates from text order.

---

## 4. Q5 forensic analysis (P2.1B-HR regression case)

| Field | Value |
|-------|-------|
| Source file | `NEET_PYQ_OFFICIAL/2023/Paper_20231108005448.pdf` |
| SHA256 | `00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5` |
| Source page | **2** |
| P2.1C column | **LEFT** |
| P2.1C quality | **VALID** (incorrect — stem not faithful) |
| HR regression | Q5 colour options: **IMPROVED**; Q5 stem: **FAIL** |

### Extracted vs ground truth

**Real Q5 (PDF, left column):**  
*"An electric dipole is placed at an angle of 30° with an electric field… Calculate the magnitude of charge on the dipole…"*  
Options: (1) 2 mC (2) 8 mC (3) 6 mC (4) 4 mC

**P2.1C Q5 stem (contaminated):**

```
A from A to B through E
transformer, capacitor and a load resistance. 9
Which of these components remove the ac
```

**P2.1C Q5 options:** `2 mC`, `8 mC 3) _ 12Gm 4) _16Gm`, `6 mC`, `-—-`  
→ Dipole charge options (**2 mC, 6 mC, 8 mC**) are partially correct; stem is from **Q3/Q7**, not Q5.

### Unwanted text and likely sources (same page, same column)

| Phrase in stem | Source in raw OCR (page 2) | Likely origin |
|----------------|---------------------------|---------------|
| `through E` | `(4) 5 A from A to B through E` (and Q7 option lines) | **Q7** circuit current option (4), not question 5 |
| `transformer, capacitor` | `transformer, capacitor and a load resistance. 9` | **Q3** full-wave rectifier stem (continues from prior lines) |
| `remove the ac ripple` | `Which of these components remove the ac ripple from the rectified output?` | **Q3** stem tail |

**True Q5 text in raw OCR:** `"5 An electric dipole is placed at an angle of 30°..."` — present in `raw_text` and in LEFT column corpus (`true_q5_snippet_in_raw: true`, `true_q5_in_left_column: true`).

### Root cause chain

1. **OCR merge (category A):** Tesseract PSM 6 on page 2 produces heavily interleaved L↔R text; only **6.8%** of lines contain pipe separators; **41 orphan lines** on page 2.
2. **False question marker (category D):** Regex `QUESTION_NUM_RE = r'^\s*(\d{1,3})(?:\.\s+|\s+)(?=[A-Z(])'` matches **`5 A from A to B through E`** as question **5** (digit + space + capital `A`), not as Q7 option (4).
3. **Segmentation boundary (category C):** Segmenter attaches Q3 rectifier paragraph + Q7 option phrasing to the false Q5 block; true dipole stem appears **later** in the column stream under the same false Q5 anchor.
4. **Option association (category E):** Options `(1) 2 mC (2) 8 mC` following the **real** dipole text are bound to the corrupted Q5 record — classic **stem/options split**.

### Can existing OCR evidence distinguish bleed?

| Technique | Q5 fixable? |
|-----------|-------------|
| Pipe-based column split | **No** — bleed is within left column after split |
| Section Q# validation | **No** — Q5 is valid for Physics Section A |
| Reject `"N A from..."` as Q# | **Would reject this record** — but does not recover true Q5 stem from later lines without re-segmentation logic + reliable markers |
| Min stem length / topic coherence | **Flag only** — dipole options with rectifier stem should be NEEDS_REVIEW, not auto-repair |

**Same column?** **Yes** — all contamination sources are assigned to LEFT column in P2.1C geometry corpus.

---

## 5. False-marker analysis

Automated classification over **6,217** P2.1C records (`diag_pyq_p2_1d_feasibility.py`):

| Cause class | Count | Deterministic elimination? |
|-------------|------:|----------------------------|
| Other / legitimate question | 2,710 | N/A — keep with QA |
| Unknown layout extraction | 1,339 | Partial — skip UNKNOWN layout pages (already NEEDS_REVIEW); does not fix TWO_COLUMN bleed |
| Legitimate statement-type question | 493 | No — valid NEET format |
| Short partial fragment | 560 | **Yes** — reject stems <40 chars with ≤1 option |
| Empty stem | 354 | **Yes** — reject or merge cautiously |
| OCR glyph hallucination (`Cc`, `Q`, `ATP`, …) | 319 | **Yes** — blocklist + min length |
| Section Q# mismatch (e.g. Q>35 on early physics pages) | 293 | **Yes** — section-aware bounds |
| Statement fragment (statement header, no options) | 85 | **Yes** — require options for statement items |
| Impossible Q# for page (e.g. Q≥70 on page ≤7) | 64 | **Yes** — page×section ceiling |

**Extended pattern probes:**

| Pattern | Count |
|---------|------:|
| Statement headers (`Given below are two statements`) | 638 |
| Circuit-amp false Q# (`N A from A to B`) | 1 (Q5 case; regex anchor issue) |
| Option number as stem start `(1)…` | rare in classifier; present in bleed |

**Manifest false-positive candidates:** 539 (P2.1C manifest).

### Cause taxonomy (user checklist)

| User category | Finding |
|---------------|---------|
| Page number | Footer lines (`G2_English \| 2 [ Contd...]`) mostly stripped; isolated digit stems rare |
| Instruction number | Page 1 instruction list (1–17) — **skipped** via `is_instruction_page`; residual empty-stem records on page 1: low |
| Statement number | 493 legitimate + 85 fragments — need option completeness check |
| Option number | OCR lines like `(4) 5 A from…` misparsed as Q#5; option-as-stem: **7** TWO_COLUMN records |
| Bilingual numbering | Hindi booklet variants not primary in 2023 EN sample; bilingual instruction page handled |
| OCR hallucinated marker | 319 glyph records; mid-line merges creating fake `N.` markers |
| Legitimate question | Majority of corpus |
| Other | UNKNOWN layout (1,339), long merged stems (541) |

### Stricter Q# validation probe (read-only)

| Action | Count |
|--------|------:|
| Would reject | 410 |
| Would keep | 5,807 |
| Early page high Q# | 93 |
| Physics page + Physics B Q# (36–50) | 317 |

**Caution:** Blind rejection improves precision but **does not repair** merged records; it shrinks the corpus. Q5 would **not** be rejected by section rules (Q5 valid on page 2).

---

## 6. Within-column bleed analysis

Analysis restricted to **TWO_COLUMN** records (3,566 questions from TWO_COLUMN pages; layout pages: 490).

| Category | Description | TWO_COLUMN count | Notes |
|----------|-------------|------------------:|-------|
| **A** | OCR merged physically separated text | **546** | Stems >200 chars — dominant failure |
| **B** | Column split boundary incorrect | **8** | `geometry_quality_flags` cross-column / foreign markers |
| **C** | Question segmentation boundary incorrect | **24** | Duplicate Q# on same page+column |
| **D** | OCR marker detection incorrect | **≥1** | Q5: `5 A from…` → false Q5; option-like stem flags: **10** corpus-wide |
| **E** | Options associated incorrectly | **8+** | `option_contains_foreign_question_marker`; Q5 stem/options split |
| **F** | Continuation across pages mishandled | **979** | Long stems not ending in `?` `.` `:` — includes truncation + mid-page merge |

**Cross-column (remaining):** 9 flagged records corpus-wide; **8** on TWO_COLUMN pages. P2.1C pipe split addressed the worst L↔R option swaps; residual cross-column is minor vs within-column.

**Pipe/orphan diagnosis:** Mean pipe ratio **0.054** — far below the **0.20** threshold for strong 2-column evidence. Pages still classified TWO_COLUMN via weak pipe evidence (≥2 pipe lines). Most content rides orphan assignment → **within-column merge**.

---

## 7. Option-association analysis

Option association uses sequential `(1)–(4)` lines after question markers in `segment_questions_from_text` (via P2.1C column corpus). Failures when stem boundaries are wrong:

| Pattern | Count (indicative) | Example |
|---------|-------------------:|---------|
| Correct options, wrong stem | **15** | Q5: mC options from dipole, stem from Q3/Q7 |
| Options without meaningful stem (TWO_COLUMN) | **156** | Options present, stem <5 chars |
| Foreign question text inside options | **8** | e.g. option_d contains `"27. A thin spherical shell..."` |
| Option-like text promoted to stem | **7–11** | `from A to B through E`, `along east` |
| Dipole/charge options with non-dipole stem | **15** | Heuristic: mC in options, no "dipole" in stem |

**Q15/Q11 (regression PASS):** Options emptied — contamination removed but **not faithful** (PARTIAL). Prefer empty options over wrong options for fidelity metric.

**Deterministic option guards (non-OCR, probe-only):**

- Reject options containing mid-line `\d{1,3}\.\s+[A-Z]` (foreign Q marker in option field) — already flagged in 8 records.
- Reject stem/option topic mismatch (e.g. mC options + rectifier stem) → downgrade to NEEDS_REVIEW.
- Do **not** auto-attach orphan `(1)–(4)` blocks without same-question stem evidence.

None of these **reconstruct** correct association without reliable spatial or marker boundaries.

---

## 8. Deterministic fixes possible without re-OCR

Safe, **quality-reducing** filters (demonstrated by read-only probes only):

| Fix | Expected effect | Q5 impact |
|-----|-----------------|-----------|
| Section-aware Q# bounds (page × section matrix) | Reject ~410 records | **No** — Q5 passes |
| Skip instruction page numbering | Remove page-1 noise | **No** |
| Reject impossible early-page Q# (Q≥70 on p≤7) | Reject ~64 | **No** |
| OCR glyph / ultra-short stem rejection | Reject ~675 | **No** |
| Reject option-like stems (`N A from…`, `from A to B through`) | Flag ~10 | **Would flag/reject Q5** — does not recover true stem |
| UNKNOWN layout → no auto-VALID | 1,339 already NEEDS_REVIEW-heavy | **No** |
| Stem/option topic coherence check | Downgrade suspect VALID | **Would downgrade Q5** |
| Stronger orphan-line policy (drop vs guess) | Reduce false merges | Risk: lose legitimate questions |

**Not feasible without re-OCR:**

- Assign orphan lines to correct column by x-coordinate
- Split interleaved OCR lines using spatial clustering
- Recover true reading order on pages with 30–78 orphan lines
- Fix Q5 by joining `"An electric dipole..."` to its options while excluding Q3/Q7 text

---

## 9. Fixes requiring re-OCR

| Fix | Requirement |
|-----|-------------|
| Persist Tesseract TSV (all columns) or `pytesseract.image_to_data` output per page | **P2.1 OCR pipeline change** |
| Column assignment by word `left`/`width` vs page midline | Needs persisted boxes |
| Line reconstruction per column before question segmentation | Needs persisted boxes |
| Optional: PDF word layer for TEXT/MIXED papers | N/A for current NEET scans (all image-only) |
| Re-run segmentation on geometry-enriched corpus | After persistence — **not** `--force` on current artifacts |

Re-OCR scope should be **staging-only**, with new artifact names (e.g. `ocr.pages.p2_1e_geometry.jsonl`) — do not overwrite P2.1 source OCR until validated.

---

## 10. Recommended next step

**STOP — do not implement P3/P4/P5 or a new segmentation algorithm in P2.1D.**

Recommended sequence:

1. **P2.1E — OCR geometry persistence (design + staging run)**
   - Extend `pyq_ocr.py` to persist word-level TSV fields: `left`, `top`, `width`, `height`, `block_num`, `par_num`, `line_num`, `word_num`, `conf`, `text`.
   - Store per-page JSONL alongside existing `raw_text` (new file; preserve P2.1).
   - Assign each word to LEFT/RIGHT by `left + width/2` vs page `split_x`.

2. **P2.1F — Geometry-first resegmentation (after P2.1E)**
   - Rebuild column corpora from x-clustered lines, then run question segmentation.
   - Re-run HR regression (Q5 stem must contain `electric dipole`; Q15/Q11 unchanged).

3. **Interim quality gate (optional, no re-OCR)**
   - Tighten VALID criteria: reject option-like stems, stem/option mismatch, foreign Q markers in options.
   - Expect VALID count **below 1,465** — acceptable per source-fidelity principle.

**Do not** increase question count at the expense of merged records.

---

## 11. Safety attestation

| Check | Status |
|-------|--------|
| AI calls | **0** |
| Network calls | **0** |
| Production DB writes | **0** |
| Source ZIP modifications | **0** |
| Source PDF modifications | **0** |
| `.env` modifications | **0** |
| Tesseract calls | **0** |
| Full OCR | **NOT RUN** |
| `--force` | **NOT RUN** |
| P3 | **NOT RUN** |
| P4 | **NOT RUN** |
| P5 | **NOT RUN** |

**Staging writes:** One new diagnostic output only — `diagnostics_p2_1d_feasibility.json` (read-only probe results). P2.1 / P2.1B / P2.1C source artifacts were not modified.

**Tests:** Existing suite unchanged (63 passed at P2.1C completion).

---

## Appendix — P2.1D corpus snapshot

| Corpus | Questions | VALID |
|--------|----------:|------:|
| P2.1 | 238 | — |
| P2.1B | 3,949 | 2,187 |
| P2.1C | 6,217 | 1,465 |

| Layout (pages) | Count |
|----------------|------:|
| TWO_COLUMN | 490 |
| ONE_COLUMN | 209 |
| UNKNOWN | 309 |

| P2.1C quality by layout | VALID | PARTIAL | NEEDS_REVIEW |
|-------------------------|------:|--------:|-------------:|
| TWO_COLUMN | 1,156 | 1,769 | 520 |
| UNKNOWN | 0 | 820 | 1,159 |
| ONE_COLUMN | 309 | 225 | 62 |

---

*End of P2.1D feasibility report. Awaiting decision before P2.1E implementation.*
