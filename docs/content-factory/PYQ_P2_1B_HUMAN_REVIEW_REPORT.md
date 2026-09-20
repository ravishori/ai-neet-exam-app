# PYQ P2.1B Human Fidelity Review Report

**Phase:** FACTORY-PYQ-P2.1B-HR  
**Date:** 2026-09-01  
**Input corpus:** `questions.p2_1_resegmented.jsonl` (NEW = 3,949)  
**Sample file:** `data/staging/pyq/2020-2025/samples.p2_1b.json`  
**Visual pack:** `data/staging/pyq/2020-2025/human_review_p2_1b/`  
**Prior pipeline verdict:** YELLOW  

---

## 1. Executive verdict

**YELLOW-QUALITY (fidelity-poor).** Do **not** treat the 3,949-question count as a faithful corpus.

Resegmentation successfully **recovered question markers** that P2.1 missed (238 → 3,949), and safety gates held. Human comparison of sample extractions against **original scanned PDF page images** shows that a large majority of records—including many labeled `VALID`—are **column-merged, option-swapped, truncated, or otherwise incomplete**.

| Decision | Choice |
|----------|--------|
| Recommendation | **2. TARGETED SEGMENTATION FIX REQUIRED** |
| Accept resegmentation as-is | No |
| Major redesign | Not yet — root cause is localized |
| Blocked on source quality | No — scans are readable; geometry is clear |
| Claim GREEN | **Forbidden / not claimed** |

**One-line summary:** Quantity recovered; fidelity did not. Text-only multi-column normalization is insufficient.

---

## 2. Review methodology

1. Loaded every sample bucket in `samples.p2_1b.json` (55 unique records after de-duplicating across overlapping buckets).
2. Rendered corresponding **original ZIP PDF pages** to PNG (no re-OCR, no `--force`) under `human_review_p2_1b/renders/`, with side-by-side OCR text snippets from existing `ocr.pages.p2_1.jsonl`.
3. For each sample, compared extracted stem/options against the visual page (left/right columns, diagrams, Q#).
4. Classified fidelity **A–G** without inventing missing text, options, answers, subjects, or diagrams.
5. Reviewed all **40** `duplicate_within_paper` hash-flagged records and all fragment candidates (70 unique; analyzer tally 77 — see §8).
6. Did **not** extrapolate sample rates as exact corpus percentages; used them to judge algorithm quality class only.

Priority order followed: PARTIAL → DIAGRAM_DEPENDENT → NEEDS_REVIEW → fragments → previously missed → 2-column → missing-period → page-boundary.

---

## 3. Sample counts

| Sample bucket | N in file | Notes |
|---------------|----------:|-------|
| ordinary_20 | 20 | Heavily overlaps two_column / with_options |
| two_column_20 | 20 | Same papers; column bleed dominant |
| missing_period_10 | 5 | Bucket under-filled (de-interleave often restores `N.`) |
| page_boundary_10 | 10 | Includes early-page / high-page cases |
| with_options_10 | 10 | `options_filled=4` ≠ faithful |
| diagram_dependent_10 | 10 | Pipeline label confirmed visually |
| bilingual_instruction_10 | 0 | Empty bucket |
| previously_missed_high_qnum_10 | 10 | Mix of real Chemistry Q51+ and false Q# |
| **Unique records reviewed** | **55** | After cross-bucket dedupe |

Supporting artifacts:
- `human_review_p2_1b/samples_enriched.json`
- `human_review_p2_1b/fidelity_classifications.json`
- `human_review_p2_1b/hash_duplicates.json`
- `human_review_p2_1b/fragment_candidates.json`

---

## 4. Fidelity metrics (reviewed sample)

| Class | Label | Count |
|-------|-------|------:|
| A | EXACT / FAITHFUL | **0** |
| B | MINOR OCR ERROR | **1** |
| C | PARTIAL (merged / incomplete) | **34** |
| D | FRAGMENTED | **5** |
| E | FALSE POSITIVE | **5** |
| F | DIAGRAM_DEPENDENT | **10** |
| G | DUPLICATE (sample is a dup of another sample) | **0** |
| | **reviewed_total** | **55** |

```
fidelity_rate        = (A + B) / reviewed_total = (0 + 1) / 55 = 0.018  (1.8%)
false_positive_rate  = E / reviewed_total       = 5 / 55      = 0.091  (9.1%)
fragment_rate        = D / reviewed_total       = 5 / 55      = 0.091  (9.1%)
```

**Critical finding:** Pipeline `VALID` (4 options present) is **not** a fidelity signal. Of unique `VALID` samples reviewed, nearly all are class **C** (wrong stem/options due to L↔R merge).

---

## 5. PARTIAL analysis

### 5.1 Pipeline `PARTIAL` (sample)

Typical failure: question marker found, but stem truncated and/or options never attached after column interleave.

| Example | Source | Visual truth | Extraction defect |
|---------|--------|--------------|-------------------|
| Q1 p2 | `Paper_20231108005448.pdf` | Full kinematics MCQ with 4 fractional options | Stem stops at “with speed”; **0 options** → **D** |
| Q51 p8 | same | Full Lewis-acid MCQ with OH⁻/NH₃/H₂O/BF₃ | Stem truncated mid-sentence; **0 options** → **D** |
| Q56 p8 | same | Distinct “species NOT having eight electrons” MCQ | Stem merged with Q51 Lewis-acid wording → **C** |
| Q2 p2 | same | Half-life MCQ | Stem interleaved with circuit-diagram OCR noise → **C** |

### 5.2 Pipeline `VALID` that is human-class **C**

These dominate `ordinary_20` / `two_column_20` / `with_options_10`.

| Example | Visual truth (PDF) | Extraction |
|---------|--------------------|------------|
| Q5 p2 | Electric dipole / 2 mC… options | Stem from Q3/Q7 bleed (“through E”, “transformer…”); options **Yellow/Red/Green/Orange** = **Q8** |
| Q9 p2 | Metal-wire % error | Stem interleaved with Q4 football-player text; options mix % and directions |
| Q15 p3 | “Net magnetic flux… closed surface” → Zero/Negative/… | Stem interleaved with Q11 “unpredictable fluctuations”; options are **Q11’s** Random/Instrumental/… |
| Q12 p3 | Statement I/II photovoltaic | Merged with suspended-wire stress question; options contaminated |
| Q57 p8 | Limestone / CO₂ mass | Stem merged with Q52 conductivity; options are conductivity values |

**Root cause:** OCR reading order is left→right across the vertical rule; `normalize_ocr_multicolumn_text` does not reliably restore column order. Option detectors then attach the **wrong** `(1)(2)(3)(4)` block, which still yields `options_filled=4` → false `VALID`.

---

## 6. DIAGRAM_DEPENDENT analysis

All 10 sample `DIAGRAM_DEPENDENT` records were confirmed against page images as **F**.

| Pattern | Evidence |
|---------|----------|
| Explicit “as shown in the figure / circuit” | Q37 p6, Q44 p7, Q129 p19 — figure present; OCR has no diagram payload |
| Diagram + column bleed | Q4 p2 2024 paper — wheel diagram (left) merged into wire-resistance stem (right); pipeline still diagram-flagged |
| Circuit / logic / seed / restriction-map figures | Q9, Q36, Q48, Q50, Q13, Q179 — unusable without image |

Diagram dependence is a **real content property**, not a false alarm. Separate from segmentation: even perfect column split leaves these needing image capture / diagram staging (out of scope for P2.1B).

---

## 7. NEEDS_REVIEW analysis

All 5 unique `NEEDS_REVIEW` samples in the review set are **E (false positive)** under visual check:

| Record | Page | Why false positive |
|--------|-----:|--------------------|
| Q70 stem=`Cc` | 2 | No Q70 on Physics p2; OCR of circuit labels / glyphs (`70`, `Cc`) |
| Q3 empty stem | 2 | Marker noise; option slot holds “3 7 The magnitude…” from Q7 |
| Q164 empty + temperature options | 3 | Impossible Q# on early Physics page; options from Q18/Q20 region + page footer |
| Q100 empty | 6 | Impossible Q#; stray option |
| Q73 empty stem + 30/27/24/28 cm | 7 | Options belong to bullet/wood-block diagram item; Q73 not a real stem on that page |

**Root cause:** false-positive number detection (diagram labels, option digits, OCR garbage interpreted as Q#).

`previously_missed_high_qnum_10` therefore mixes **real** Chemistry section starts (Q51+) with **spurious** high numbers on Physics pages.

---

## 8. Duplicate analysis (40 within-paper hash flags)

- Flag definition: `mark_within_paper_duplicates` marks the **2nd+** occurrence of `normalized_question_hash` within a paper (`duplicate_within_paper=True`).
- **40** records flagged; **0** within-paper duplicate **question_number** groups.
- Export: `human_review_p2_1b/hash_duplicates.json` (27 hash keys; member counts 1–3 among flagged rows).

### Disposition (all groups inspected)

| Disposition | Approx. share | Meaning |
|-------------|---------------|---------|
| **OCR-equivalent duplicate** | ~all material groups | Distinct source questions share a **truncated boilerplate stem** after option loss |
| Legitimate identical question in source | **0 observed** | Not seen in reviewed pages |
| Duplicate extraction of same Q# | **0** | Q# groups within paper = 0 |
| Repeated bilingual translation as separate records | Partial factor on Hindi+English papers | Same boilerplate in EN/HI columns can collide after truncation |

### Representative examples (with source pages)

1. **`Paper_20231108005448.pdf`** hash `d00083f0…`  
   - Flagged: Q113 p18, Q114 p18, Q145 p22 — stems all start `Given below are two statements : One is` with **0 options**.  
   - **PDF p18:** Q113 and Q114 are **different** Assertion–Reason items (full distinct bodies + vertical options).  
   - **Verdict:** OCR-equivalent stub collision — **not** legitimate repeats; **not** same-question double extraction.

2. **`Paper_20250124132822.pdf`**  
   - Q142 & Q144 p21 — both `Match List I with List II`, 0 options.  
   - **PDF:** two different Match-List items on the same page.  
   - **Verdict:** OCR-equivalent duplicate.

3. Singleton flagged rows (e.g. Q189 p29 “Which of the following statements are”)  
   - First hash occurrence earlier in the same paper is unflagged; 2nd+ is flagged.  
   - Same truncated-boilerplate mechanism.

**Do not auto-delete.** Prefer fixing stem/option completeness so hashes diverge for distinct questions; then re-evaluate.

---

## 9. Fragment analysis (77 analyzer / 70 unique)

Analyzer `fragment_candidates=77` can **double-count** stems that are both `len<20` and option-marker-only. Unique fragment-like records under the same predicates: **70**.

| Kind (human) | Count (≈) | Notes |
|--------------|----------:|-------|
| partial question | 28 | Truncated real stems |
| empty / header-like empty stem | 21 | Marker with no stem text |
| option fragment | 9 | Stem is only `(1)(2)…` style |
| false-positive / OCR glyph | 9 | e.g. `Cc`, `Q`, `ATP` |
| left/right-column fragment | 1 | Residual pipe / half-column scrap |
| false-positive number (wrong Q# vs page) | 2 | e.g. Q40 claimed on a page that only shows Q145–150 |

### Examples

| Claimed | File / page | Visual | Kind |
|---------|-------------|--------|------|
| Q40 p22 | `Paper_20231108010819.pdf` | Page shows Biology Q145–150 only | false-positive number / page-boundary |
| Q2 p2 | `Paper_20231108005837.pdf` | Real Q2 exists (transformer lamp) | Often short/partial after split failure |
| stem `Cc` / empty | various | Diagram OCR | glyph / empty fragment |

**Do not auto-delete.** Use as a quarantine class for the next segmentation pass.

---

## 10. False-positive analysis

| Source of FP | In sample | Corpus implication (qualitative) |
|--------------|-----------|----------------------------------|
| Diagram label / digit → Q# | Q70, Q3 noise | Present wherever circuit OCR emits numbers |
| Empty stem + borrowed options | Q164, Q73, Q100 | Inflates NEEDS_REVIEW |
| Boilerplate hash twins | 40 flags | Not FP questions, but FP “duplicate” semantics |

False-positive **rate in sample** = 9.1%. Not extrapolated as a corpus %.

---

## 11. Representative examples (side-by-side)

### Example A — False `VALID` (class C)

- **PDF:** `Paper_20231108005448.pdf` p2, Q8 = carbon resistor colour codes (Yellow/Red/Green/Orange).  
- **Extraction labeled Q5 VALID:** options Yellow/Red/Green/Orange; stem mentions rectifier + “through E”.  
- **Fidelity:** C — identifiable as “some physics MCQ” only; **not** faithful to Q5.

### Example B — True diagram dependence (class F)

- **PDF:** same paper / similar years, “as shown in the figure” circuit or seed figure.  
- **Extraction:** stem acknowledges figure; options missing.  
- **Fidelity:** F — correct quarantine class.

### Example C — Minor usable (class B)

- **PDF:** p8 Q53 pyridine σ/π/lone-pair counts; options `(1) 12,2,1` … `(4) 11,3,1`.  
- **Extraction:** stem incomplete but on-topic; options mostly correct; option_d bleeds into Q58.  
- **Fidelity:** B — usable with minor defect.

### Example D — False positive (class E)

- **PDF:** p2 has Q1–Q10 only.  
- **Extraction:** Q70 = `Cc` with circuit current options.  
- **Fidelity:** E.

### Example E — Hash “duplicate” that is not a source repeat (class analysis G at corpus level)

- **PDF p18:** Q113 ≠ Q114 (different Assertion/Reason).  
- **Extraction:** identical truncated hash stubs.  
- **Disposition:** OCR-equivalent duplicate.

---

## 12. Root causes (material defects)

| Rank | Root cause | Where observed |
|-----:|------------|----------------|
| 1 | **Column de-interleaving failure** | Almost all 2-column English papers; bilingual EN\|HI pages |
| 2 | **OCR reading order** (row-wise across gutter) | OCR snippets show `left \| right` line pairs |
| 3 | **Option detection** attaching neighbor’s `(1)–(4)` | False `VALID` |
| 4 | **Question-marker detection** (digits in diagrams / no period) | NEEDS_REVIEW FPs; some missing_period cases |
| 5 | **Diagram / image dependency** | 71 corpus / 10 sample F — expected |
| 6 | **Page-boundary / footer bleed** | `G2_English`, `<<<PAGE:>>>` in options |
| 7 | **OCR character error** | `em`/`cm`, `Q`/`Ω`, fractions — secondary vs merge |
| 8 | **Bilingual layout** | Hindi column text inside English stems (e.g. Q115/Q118 samples) |
| 9 | **False-positive number detection** | Q70/Q100/Q164 class |
| 10 | **Truncated-stem hashing** | 40 within-paper hash flags |

P2.1A’s text-normalization fix **increased recall** but did **not** achieve human-faithful segmentation.

---

## 13. Extrapolation (quality class, not %)

Do **not** multiply 1.8% fidelity by 3,949 and call that “true questions.”

| Signal | Interpretation |
|--------|----------------|
| Recall of Q markers | Improved (238 → 3,949) — real |
| Share `VALID` ≈ 55% | **Overstates** fidelity (sample VALID ≈ almost all C) |
| PARTIAL + NEEDS_REVIEW + DIAGRAM ≈ 44% | Understates damage if many VALID are also unfaithful |
| Algorithm quality | **YELLOW-QUALITY**, leaning **RED on faithfulness** |

**GREEN-QUALITY** would require sample fidelity_rate ≫ 0.85 with A/B dominant among non-diagram items.  
**RED-QUALITY** would mean unusable recall or majority E.  
**This review:** YELLOW — usable as a **diagnostic / quarantine corpus**, not as import-ready PYQ content.

---

## 14. Recommended remediation

**Recommend: 2. TARGETED SEGMENTATION FIX REQUIRED**

Do **not** implement in this HR phase. Next engineering focus (when authorized):

1. **Geometry-first 2-column split** before question segmentation (detect vertical rule / column bbox; OCR or re-slice left then right). Text-only pipe heuristics are proven insufficient.
2. **Tighten Q# candidates** (reject numbers from diagram regions; enforce section ranges; require nearby option blocks).
3. Keep **DIAGRAM_DEPENDENT** quarantine; add image crop staging later (not P3 content import).
4. Recompute hashes only after stems/options are column-clean; then revisit the 40 flags.
5. Re-run **`--resegment-only`** (or equivalent) on existing OCR pages — **no full corpus OCR** unless geometry fix needs new page crops.
6. Repeat human fidelity review on a fresh sample before any ACCEPT.

**Not recommended now:** ACCEPT RESEGMENTATION, MAJOR REDESIGN of the whole factory, P3/P4/P5, DB import, or GREEN claims.

---

## 15. Safety attestation

| Gate | Status |
|------|--------|
| Production DB writes | **0** |
| AI / API calls | **0** |
| Network calls (for review processing) | **0** (local ZIP/PDF read + local renders only) |
| Source ZIP modifications | **0** |
| Source PDF modifications | **0** |
| `.env` modifications | **0** |
| Full OCR | **NOT RUN** |
| `--force` | **NOT RUN** |
| P3 | **NOT RUN** |
| P4 | **NOT RUN** |
| P5 | **NOT RUN** |
| Manual content repair / invented answers | **NOT DONE** |
| Segmentation code changes this phase | **NOT DONE** (review only) |

---

## 16. STOP

Human fidelity review complete.  
**Verdict remains YELLOW.**  
**Recommendation: TARGETED SEGMENTATION FIX REQUIRED.**  
No further segmentation implementation in this phase unless explicitly authorized after this report.
