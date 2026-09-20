# T6-F1 Scientific Failure Analysis
## 15 Vector-Magnitude Scientific Failures

**Date:** 2026-09-02  
**Batch:** `physics-t6f1-pilot-20260902`  
**Mode:** READ-ONLY forensic audit — no database or code modifications

---

## 1. Executive Verdict

**AMBER**

All 15 rejections are **validator false positives** caused by a **rounding/tolerance mismatch** between the T6-F1 parametric generator and the hardened numerical validator. The underlying MCQs are scientifically correct; none contain wrong vector magnitudes, wrong answer keys, or scalar/vector confusion.

The 938 staged T6-F1 DRAFT records are unaffected. T6-F2 may proceed **with conditions** (document and fix the `vector_mag` rounding contract before the next scaled generation batch).

---

## 2. Scope

| Item | Value |
|------|------:|
| T6-F1 batch | `physics-t6f1-pilot-20260902` |
| Total T6-F1 candidates | 1,000 |
| Vector-magnitude scientific failures analyzed | **15** |
| Accepted/staged DRAFT | 938 |
| Published from T6-F1 | 0 |
| Read-only confirmation | SELECT-only DB inspection; bank/gates replay from source |

**Exact 15 question IDs (all rejected, none persisted):**

`t6f1-0162`, `t6f1-0164`, `t6f1-0165`, `t6f1-0167`, `t6f1-0168`, `t6f1-0170`, `t6f1-0171`, `t6f1-0173`, `t6f1-0174`, `t6f1-0176`, `t6f1-0177`, `t6f1-0179`, `t6f1-0180`, `t6f1-0182`, `t6f1-0183`

Database check: **0 of 15 slugs exist** in `cms.content_items` (correctly rejected pre-staging).

---

## 3. Evidence Sources

| Source | Purpose |
|--------|---------|
| `docs/audits/TALOS_T6F1_1000_CANDIDATE_VALIDATION_AUDIT_20260902.md` | Failure register, rejection reasons |
| `apps/backend/app/modules/cms/acquisition/physics_t6f1_bank.py` | Generator: `vectors-in-plane-motion` template (lines 228–240) |
| `apps/backend/app/modules/cms/acquisition/physics_t6d_bank.py` | T6-D reference: stores **exact** `math.hypot` in calc (lines 347–360) |
| `apps/backend/app/modules/cms/services/numerical_validation.py` | Validator: `vector_mag` recompute with `1e-6` tolerance (lines 102–105) |
| `apps/backend/app/modules/cms/acquisition/physics_t6d_gates.py` | Gate wiring: `verify_calculation` → `classify_and_verify` |
| `apps/backend/pilot-t6e-audit-inventory.json` | Historical vector_mag inventory notes |
| `apps/backend/tests/test_t6e_fix_gates.py` | Numerical validation tests (no `vector_mag` rounding case) |
| `apps/backend/tests/test_physics_t6f1_pilot.py` | T6-F1 pipeline tests |
| Read-only DB query (`trinetra_db`) | Legacy/T6-D/T6-F1 inventory |

---

## 4. Candidate-by-Candidate Analysis

### Summary table

| # | Question ID | Chapter | Topic | Concept |
|---|-------------|---------|-------|---------|
| 1 | t6f1-0162 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 2 | t6f1-0164 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 3 | t6f1-0165 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 4 | t6f1-0167 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 5 | t6f1-0168 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 6 | t6f1-0170 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 7 | t6f1-0171 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 8 | t6f1-0173 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 9 | t6f1-0174 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 10 | t6f1-0176 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 11 | t6f1-0177 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 12 | t6f1-0179 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 13 | t6f1-0180 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 14 | t6f1-0182 | kinematics | motion-in-a-plane | vectors-in-plane-motion |
| 15 | t6f1-0183 | kinematics | motion-in-a-plane | vectors-in-plane-motion |

### Root mechanism (applies to all 15)

**Generator** (`physics_t6f1_bank.py`):

```python
mag = round(math.hypot(ax, ay), 2)
calc = {"formula": "vector_mag", "ax": ax, "ay": ay, "mag": mag, ...}
```

**Validator** (`numerical_validation.py`):

```python
if abs(math.hypot(calc["ax"], calc["ay"]) - calc["mag"]) > 1e-6:
    return False, "vector mag mismatch"
```

**T6-D reference** (passes validator): stores `mag = math.hypot(ax, ay)` **without rounding** in calc payload, displays rounded value in options via `_round_nice(mag)`.

---

### Per-candidate detail

#### 1. t6f1-0162

- **Generated problem:** Δx = 10 m, Δy = 13 m → |Δr| = ?
- **Options:** A 23 m, **B 16.4 m**, C 130 m, D 3 m → correct **B**
- **Numerical payload:** `{ax:10, ay:13, mag:16.4}`
- **Validator rejection:** `scientific:vector mag mismatch` → `NUMERICAL_INVALID`
- **Independent calculation:** |Δr| = √(10² + 13²) = √269 = **16.401219… m** → **16.4 m** (2 d.p.)
- **Payload vs exact delta:** 0.001219 m (> 1e-6 → fail)
- **Scientific diagnosis:** Question, answer key, and explanation are correct. Rejection is tolerance/rounding only.
- **Primary classification:** ROUNDING_OR_TOLERANCE_ERROR
- **Secondary:** VALIDATOR_FALSE_POSITIVE
- **Generator vs validator:** BOTH (generator rounds payload; validator too strict for display rounding)

#### 2. t6f1-0164

- **Components:** (6, 13) m → exact **14.317821 m**, stored **14.32 m**, correct **A (14.32 m)**
- **Delta:** 0.002179 m
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 3. t6f1-0165

- **Components:** (4, 13) m → exact **13.601471 m**, stored **13.6 m**, correct **A (13.6 m)**
- **Delta:** 0.001471 m
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 4. t6f1-0167

- **Components:** (10, 13) m → exact **16.401219 m**, stored **16.4 m**, correct **B (16.4 m)**
- **Delta:** 0.001219 m (duplicate parametric pair with #1, #11, #14)
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 5. t6f1-0168

- **Components:** (8, 13) m → exact **15.264338 m**, stored **15.26 m**, correct **A (15.26 m)**
- **Delta:** 0.004338 m
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 6. t6f1-0170

- **Components:** (4, 13) m → exact **13.601471 m**, stored **13.6 m**, correct **B (13.6 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 7. t6f1-0171

- **Components:** (12, 13) m → exact **17.691806 m**, stored **17.69 m**, correct **B (17.69 m)**
- **Delta:** 0.001806 m
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 8. t6f1-0173

- **Components:** (8, 13) m → exact **15.264338 m**, stored **15.26 m**, correct **B (15.26 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 9. t6f1-0174

- **Components:** (6, 13) m → exact **14.317821 m**, stored **14.32 m**, correct **B (14.32 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 10. t6f1-0176

- **Components:** (12, 13) m → exact **17.691806 m**, stored **17.69 m**, correct **B (17.69 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 11. t6f1-0177

- **Components:** (10, 13) m → exact **16.401219 m**, stored **16.4 m**, correct **A (16.4 m)** (post-shuffle position differs from #1)
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 12. t6f1-0179

- **Components:** (6, 13) m → exact **14.317821 m**, stored **14.32 m**, correct **D (14.32 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 13. t6f1-0180

- **Components:** (4, 13) m → exact **13.601471 m**, stored **13.6 m**, correct **B (13.6 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 14. t6f1-0182

- **Components:** (10, 13) m → exact **16.401219 m**, stored **16.4 m**, correct **B (16.4 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

#### 15. t6f1-0183

- **Components:** (8, 13) m → exact **15.264338 m**, stored **15.26 m**, correct **B (15.26 m)**
- **Primary:** ROUNDING_OR_TOLERANCE_ERROR | **Secondary:** VALIDATOR_FALSE_POSITIVE | **G vs V:** BOTH

### Cross-check: scalar vs vector, answer uniqueness

For all 15:

| Check | Result |
|-------|--------|
| Quantity asked | Vector displacement **magnitude** (scalar result of vector) |
| Formula | \|Δr\| = √(Δx² + Δy²) — correct |
| Dimensional consistency | m throughout — correct |
| Vector addition confusion | None — components given directly |
| Magnitude vs component confusion | None — distractors are ax+ay, ax×ay, \|ax−ay\| (classic traps, not the correct answer) |
| Unique defensible answer | Yes — exactly one option matches √(ax²+ay²) to 2 d.p. |
| Sufficient information | Yes |
| Explanation matches math | Yes — e.g. \|Δr\| = √(10²+13²) = 16.4 m |

**Conclusion for all 15:** Category **D) QUESTION IS VALID AND SHOULD HAVE PASSED** (validator implementation issue, not scientific incorrectness).

---

## 5. Failure Classification Summary

| Classification | Count | Percentage |
|---|---:|---:|
| ROUNDING_OR_TOLERANCE_ERROR | 15 | 100.0% |
| VALIDATOR_FALSE_POSITIVE (secondary) | 15 | 100.0% |
| GENERATOR_SCIENTIFIC_ERROR | 0 | 0.0% |
| VALIDATOR_CORRECT_REJECTION | 0 | 0.0% |
| INCOMPLETE_NUMERICAL_PAYLOAD | 0 | 0.0% |
| ANSWER_KEY_ERROR | 0 | 0.0% |
| VECTOR_MAGNITUDE_CALCULATION_ERROR | 0 | 0.0% |
| SCALAR_VECTOR_CONFUSION | 0 | 0.0% |
| OTHER | 0 | 0.0% |
| **Total** | **15** | **100.0%** |

---

## 6. Validator Accuracy

| Result | Count |
|---|---:|
| Correct rejection (scientifically wrong question) | 0 |
| False positive (valid question rejected) | **15** |
| Inconclusive | 0 |

The validator **correctly identified a payload inconsistency** but **incorrectly treated it as a scientific failure**. The stated reason (`vector mag mismatch`) is accurate at the byte level yet **misleading** as a scientific gate outcome — the physics is correct.

---

## 7. Generator Failure Patterns

| Pattern | Count | % of 15 |
|---------|---:|---:|
| `vectors-in-plane-motion` concept only | 15 | 100% |
| `motion-in-a-plane` topic only | 15 | 100% |
| `kinematics` chapter only | 15 | 100% |
| Formula `vector_mag` in calc payload | 15 | 100% |
| `mag = round(hypot(ax,ay), 2)` in generator | 15 | 100% |
| Parametric `(ax, ay)` with ay = 13 | 15 | 100% |
| Unique component pairs (deduped) | 5 | — |
| Numerical question type | 15 | 100% |
| Option shuffle applied (varied correct letter) | 15 | 100% |

**Unique (Δx, Δy) pairs:** (4,13)×3, (6,13)×3, (8,13)×3, (10,13)×4, (12,13)×2

**Precise generator defect:** T6-F1 parametric bank deviates from T6-D convention by storing **display-rounded** magnitude in the numerical payload instead of the **exact** recomputed value. Options and explanations use the rounded value consistently — so the MCQ is internally consistent and scientifically valid.

---

## 8. Validator Failure Patterns

| Pattern | Count | % of 15 |
|---------|---:|---:|
| Rule: `_recompute("vector_mag")` | 15 | 100% |
| Tolerance: `1e-6` absolute | 15 | 100% |
| Inconsistency vs `projectile_R` tolerance (`0.15`) | 15 | 100% |
| Payload field compared: `mag` vs `hypot(ax,ay)` | 15 | 100% |

**Validator weakness:** No rounding-aware comparison for `vector_mag`, despite generator/UX convention of 2-decimal display magnitudes.

---

## 9. Taxonomy Correlation

| Taxonomy node | Failures | Notes |
|---------------|---:|-------|
| Chapter: `kinematics` | 15 | 100% cluster |
| Topic: `motion-in-a-plane` | 15 | 100% cluster |
| Concept: `vectors-in-plane-motion` | 15 | 100% cluster — **sole concept affected** |

No failures in other P0 concepts. This is a **concept-specific generator/validator contract bug**, not a broad taxonomy misassignment issue. Kinematics topic isolation for accepted content remains intact.

---

## 10. NCERT / Source Alignment

- **Source reference:** NCERT XI Physics Ch 3 §3.2–3.7 (section-level, consistent with P0 manifest)
- **Verification level:** SECTION_VERIFIED (PDF presence gate — unchanged from T6-F1 main audit)
- **Page-level evidence:** NOT AVAILABLE — not fabricated
- **Physics alignment:** Vector magnitude from rectangular components is standard NCERT Class XI kinematics content; independent verification confirms formula correctness

No source-alignment failure contributed to these 15 rejections.

---

## 11. Legacy Safety

Read-only DB verification (`trinetra_db`, 2026-09-02):

| Invariant | Value | Status |
|-----------|------:|--------|
| Legacy Physics rows | 5,000 | MATCH |
| Legacy `concept_id IS NULL` | 5,000 | MATCH |
| Legacy published | 0 | MATCH |
| Legacy fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` | MATCH |
| T6-D total / published | 100 / 100 | UNCHANGED |
| T6-F1 total / published / draft | 938 / 0 / 938 | EXPECTED |
| 15 rejected slugs in DB | 0 | CORRECT (not staged) |

---

## 12. Tests Reviewed

| Test file | Coverage for this failure class |
|-----------|--------------------------------|
| `tests/test_t6e_fix_gates.py` | Partial — `classify_and_verify` for v=u+at complete/incomplete/invalid; **no vector_mag rounding case** |
| `tests/test_physics_t6f1_pilot.py` | Partial — incomplete numerical rejection; **no vector_mag rounding regression** |
| `tests/test_physics_t6d_pilot.py` | Not covered — T6-D bank uses exact hypot in payload |

**Coverage verdict:** **Not covered** — the specific F1 rounding-vs-1e-6 tolerance mismatch has no dedicated test.

---

## 13. Risk Assessment

| Domain | Risk | Rationale |
|--------|------|-----------|
| Scientific correctness (938 staged) | **LOW** | Staged set passed all gates; these 15 were rejected |
| Generator | **MEDIUM** | Parametric F1 template inconsistent with T6-D payload convention |
| Validator | **MEDIUM** | False positives possible for any future rounded `vector_mag` payloads |
| Taxonomy | **LOW** | Single concept; no misassignment |
| Publication (T6-F2) | **LOW** | 938 DRAFT records exclude these 15 |
| Practice | **N/A** | Not in T6-F2 scope for this analysis |

---

## 14. T6-F2 Recommendation

**PROCEED WITH CONDITIONS**

Conditions:

1. **Do not republish or restage the 15 rejected IDs** as part of T6-F2 — they remain rejected evidence.
2. **Before the next scaled generation batch**, align generator and validator on `vector_mag` rounding (either store exact `hypot` in payload like T6-D, or add display-tolerance e.g. `0.01` in validator — separate implementation task).
3. **Add a regression test** for rounded vector magnitude payloads (separate task; not done here).
4. T6-F2 publication review may proceed on the **938 staged DRAFT** records — no evidence that scientifically incorrect vector questions were accepted.

---

## 15. Database Writes

| Operation | Count |
|-----------|------:|
| INSERT | 0 |
| UPDATE | 0 |
| DELETE | 0 |
| PUBLISH | 0 |
| LEGACY MODIFICATIONS | 0 |

---

## Appendix: Parametric component pairs

| (Δx, Δy) | Exact \|Δr\| | Stored mag | Δ (exact − stored) | Question IDs |
|---------:|-------------:|-----------:|-------------------:|--------------|
| 4, 13 | 13.601471 | 13.6 | 0.001471 | 0165, 0170, 0180 |
| 6, 13 | 14.317821 | 14.32 | 0.002179 | 0164, 0174, 0179 |
| 8, 13 | 15.264338 | 15.26 | 0.004338 | 0168, 0173, 0183 |
| 10, 13 | 16.401219 | 16.4 | 0.001219 | 0162, 0167, 0177, 0182 |
| 12, 13 | 17.691806 | 17.69 | 0.001806 | 0171, 0176 |

All Δ values exceed validator tolerance `1e-6` but are within normal 2-decimal display rounding.
