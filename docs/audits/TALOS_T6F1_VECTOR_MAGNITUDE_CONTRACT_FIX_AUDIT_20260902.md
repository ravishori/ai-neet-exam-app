# T6-F1 Vector-Magnitude Contract Fix Audit

**Date:** 2026-09-02  
**Mode:** Code + tests only — zero database writes

---

## 1. Executive Verdict

**GREEN**

The vector-magnitude generator/validator contract is now explicit and precision-aware. All 15 historical failure payloads pass under the corrected validator. Incorrect magnitudes, incomplete payloads, and invalid payloads still hard-fail. No database records were modified.

---

## 2. Original Failure

T6-F1 parametric generator (`physics_t6f1_bank.py`) stored:

```python
mag = round(math.hypot(ax, ay), 2)
```

The validator (`numerical_validation.py`) compared `mag` against **exact** `hypot(ax, ay)` with tolerance `1e-6`. Fifteen scientifically correct questions were rejected because display-rounded magnitudes differed from exact floats by ~0.001–0.004 m.

---

## 3. Root Cause

| Layer | Issue |
|-------|-------|
| **Generator** | Stored 2-decimal display magnitude without declaring presentation precision |
| **Validator** | Applied exact-match tolerance (`1e-6`) to all `vector_mag` payloads regardless of display intent |
| **Contract gap** | No distinction between calculation precision and presentation precision |

T6-D bank (`physics_t6d_bank.py`) was unaffected — it stores exact `math.hypot(ax, ay)` in the calc payload.

---

## 4. Contract Implemented

### Calculation precision

Internal math always uses `exact_mag = hypot(ax, ay)` (full float precision).

### Presentation precision

T6-F1 generator now declares:

```python
calc = {
    "formula": "vector_mag",
    "ax": ax,
    "ay": ay,
    "mag": round(exact_mag, 2),
    "mag_precision": 2,
    "unit": "m",
}
```

### Validation rules (`_verify_vector_mag`)

1. **`mag_precision` declared** → pass iff `mag == round(exact_mag, mag_precision)` (within `1e-9` float artefact tolerance)
2. **No `mag_precision`, exact match** → pass iff `|exact_mag - mag| ≤ 1e-6` (T6-D backward compat)
3. **No `mag_precision`, implicit 2 d.p.** → pass iff `mag == round(exact_mag, 2)` (T6-F1 historical payloads)
4. **Otherwise** → `NUMERICAL_INVALID` / `vector mag mismatch`

No global tolerance weakening. Other formulas unchanged.

---

## 5. Validator Behavior

| Case | Result |
|------|--------|
| Exact integer magnitude (3,4 → 5) | PASS |
| Declared 2 d.p. correct magnitude | PASS |
| Implicit 2 d.p. (historical payloads) | PASS |
| Wrong magnitude (+0.01 at 2 d.p.) | HARD FAIL |
| Missing `ax`/`ay`/`mag` | INCOMPLETE |
| Non-numeric components | INVALID |
| T6-D exact payloads (no precision field) | PASS (unchanged) |
| `projectile_R`, `F=ma`, etc. | Unchanged |

---

## 6. 15 Historical Failures

| Metric | Value |
|--------|------:|
| Analyzed | 15 |
| Replayed (exact pre-fix calc payloads) | 15 |
| Passed under corrected contract | **15** |
| Still failed | **0** |

Historical records remain rejected/unstaged in DB — not modified.

Read-only gate replay on full 1,000-candidate bank: **953 accepted, 47 rejected** (15 vector-magnitude items now pass; 47 near-duplicate rejections unchanged).

---

## 7. Regression Tests

| Test | Expected | Actual |
|------|----------|--------|
| `test_vector_mag_exact_value_passes` | PASS | PASS |
| `test_vector_mag_two_decimal_rounding_passes` | PASS | PASS |
| `test_vector_mag_legitimate_rounding_pairs_pass` (×5) | PASS | PASS |
| `test_vector_mag_incorrect_value_fails` | HARD FAIL | PASS |
| `test_vector_mag_incomplete_payload_fails` | HARD FAIL | PASS |
| `test_vector_mag_invalid_payload_fails` | HARD FAIL | PASS |
| `test_vector_mag_precision_boundary_fails_one_centimeter_off` | HARD FAIL | PASS |
| `test_vector_mag_precision_boundary_passes_at_exact_round` | PASS | PASS |
| `test_vector_mag_without_precision_still_requires_exact_or_valid_round` | mixed | PASS |
| `test_historical_15_exact_payloads_pass` | 15/15 PASS | PASS |
| `test_historical_15_regenerated_bank_passes` | 15/15 PASS | PASS |
| `test_f1_bank_vector_items_include_mag_precision` | PASS | PASS |

File: `tests/test_vector_mag_contract.py`

---

## 8. Regression Safety

| Validator | Protected |
|-----------|-----------|
| `v=u+at` | YES — 1e-6 unchanged |
| `projectile_R` | YES — 0.15 tolerance unchanged |
| `F=ma`, `W=Fs`, etc. | YES — 1e-6 unchanged |
| Incomplete payload detection | YES |
| Invalid payload detection | YES |

T6-E regression (`test_t6e_fix_gates.py`): **18/18 passed**  
T6-F1 pilot tests (`test_physics_t6f1_pilot.py`): **10/10 passed**

---

## 9. T6-F1 Bank Safety

| Metric | Value |
|--------|------:|
| Staged DRAFT | 938 |
| Published | 0 |
| DB records modified | 0 |

Code fix affects future generation/validation only. Existing 938 DRAFT rows untouched.

---

## 10. T6-D Safety

| Metric | Value |
|--------|------:|
| Total | 100 |
| Published | 100 |
| Modified | 0 |

T6-D `vector_mag` payloads use exact hypot — continue to pass via exact-match path.

---

## 11. Legacy Safety

| Invariant | Value | Status |
|-----------|------:|--------|
| Legacy rows | 5,000 | MATCH |
| `concept_id IS NULL` | 5,000 | MATCH |
| Published | 0 | MATCH |
| Fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` | MATCH |

---

## 12. Database Writes

| Operation | Count |
|-----------|------:|
| INSERT | 0 |
| UPDATE | 0 |
| DELETE | 0 |
| PUBLISH | 0 |

---

## 13. Test Results

| Suite | Passed | Failed | Skipped |
|-------|-------:|-------:|--------:|
| `test_vector_mag_contract.py` | 12 | 0 | 0 |
| `test_t6e_fix_gates.py` | 18 | 0 | 0 |
| `test_physics_t6f1_pilot.py` | 10 | 0 | 0 |
| **Combined focused run** | **40** | **0** | **0** |

---

## 14. Final Gate

**GREEN** — All GREEN requirements satisfied. T6-F2 may proceed on the 938 staged DRAFT batch.

**Note:** The 15 historical rejections remain unstaged evidence. A future generation rerun would accept them; this task did not restage or regenerate them.
