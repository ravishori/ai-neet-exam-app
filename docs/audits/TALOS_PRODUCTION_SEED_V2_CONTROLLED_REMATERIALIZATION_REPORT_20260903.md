# Production Seed V2 — Controlled Rematerialization (4 slots)

**Verdict: GREEN**  
**Date:** 2026-09-03  
**Batch:** `4509d488-c100-47f0-8357-4b1678abd00d`

---

## 1. Verdict

GREEN — all three visual slots rematerialized with valid SVG/`visual_spec` and passing visual validation; zoology-15 dual-circuit ambiguity is detected on the preserved original and cleared on the replacement (distractor rewrite; answer key not flipped); historical V2 100 fingerprints unchanged; protected populations unchanged; approvals/publications/ECAEP = 0.

---

## 2. Four target results

| Slot | Original ID | Replacement ID | Method | Success |
|------|-------------|----------------|--------|---------|
| physics-05 | `2a22a821-d0bd-4c87-be2c-c35ef9664118` | `9c51f8a1-bf72-4ca0-bcfd-e0aa5cb8ee53` | gemini + deterministic SVG attach | true |
| physics-21 | `0de3dfa3-bc5a-4791-aa5d-8346dd08f0c2` | `1633f068-f0df-4ff5-ac0c-57be4417f29e` | gemini + deterministic SVG attach | true |
| zoology-12 | `7580a952-0869-4f38-ae62-8c18a49bfb6f` | `ca0e7a05-38bb-4e12-a52d-4fd4c7a26b07` | gemini + deterministic SVG attach | true |
| zoology-15 | `ef480cb5-8ede-451b-9444-940c7094e764` | `03d1274b-35fa-446a-8742-164e9a28e8d3` | gemini attempts failed ambiguity/schema → deterministic distractor rewrite | true |

---

## 3. Visual validation results

| Slot | visual_required | type | archetype | SVG | visual_spec | ncert_evidence | validation |
|------|-----------------|------|-----------|-----|-------------|----------------|------------|
| physics-05 | true | line_graph | xt_slope_graph | yes | yes | false | PASS |
| physics-21 | true | curve_graph | stress_strain_curve | yes | yes | false | PASS |
| zoology-12 | true | schematic | ecg_wave_schematic | yes | yes | false | PASS |

Generated visuals are factory scaffolding — **not** NCERT evidence.

---

## 4. Zoology-12 regression

- **Before:** `diagram_data_interpretation` + **no** visual (`7580a952-…`) — historically preserved DRAFT with superseded tag.
- **After:** `ca0e7a05-…` has visual_required path materializing ECG schematic SVG + `visual_spec`; visual validation **PASS**.
- Original forensic finding remains auditable.

---

## 5. Zoology-15 ambiguity result

- **Original** `ef480cb5-…`: `SEMANTIC_AMBIGUITY_DETECTED` (`DUAL_COMPLETE_CIRCUIT_OPTIONS:A,D`) — preserved.
- **Gemini rematerialization attempts:** rejected (including live `SEMANTIC_AMBIGUITY_DETECTED` on regenerated dual-correct patterns) — detector enforced.
- **Replacement** `03d1274b-…`: distractor **D rewritten** to a clearly wrong chamber/vessel claim; **correct_option remains A** (answer key not flipped). Validation OK; no hard ambiguity. Soft `SEMANTIC_REVIEW_REQUIRED` may still appear — **not** claimed as full scientific uniqueness certification.

---

## 6. Replacement lineage

| Slot | Original → Replacement | Tags |
|------|------------------------|------|
| physics-05 | `2a22a821…` → `9c51f8a1…` | original: `seed-v2-rematerialization-superseded-20260903` + `replaced-by:…`; new: `seed-v2-rematerialization-20260903` + `replaces:…` |
| physics-21 | `0de3dfa3…` → `1633f068…` | same pattern |
| zoology-12 | `7580a952…` → `ca0e7a05…` | same pattern |
| zoology-15 | `ef480cb5…` → `03d1274b…` | same pattern |

Original bodies/MD5s unchanged. No silent overwrite.

---

## 7. Gemini attempts / cost

- Provider: **gemini** · mode **fixed** · routing **fixed:gemini** · fallback **0**
- Model: **gemini-3.6-flash**
- Total attempts (both passes): **~13** (see JSON `provider.attempts`)
- New ContentItems: **4**
- Approx cost: **~$0.030**
- No fallback provider used

---

## 8. Tests

```
pytest tests/test_seed_v2_p5_remediation.py tests/test_content_factory_p3.py \
       tests/test_content_factory_p4.py tests/test_content_factory_p5.py -q
→ 43 passed, 0 failed
```

Covered: visual propagation/materialization/rejection/acceptance/type mismatch, Zoology-12/15 architecture regressions, sampler/integrity tests from prior remediation suite.

---

## 9. Integrity

| Check | Result |
|-------|--------|
| Historical V2 100 bodies fingerprint | **UNCHANGED** |
| V1 published 30 | **UNCHANGED** |
| T6-D | **UNCHANGED** |
| T6-F2 | **UNCHANGED** |
| Legacy | **UNCHANGED** |
| Draft delta | **+4** (exactly the rematerialized replacements) |
| Approvals / publications / ECAEP | **0 / 0 / 0** |
| Rematerialization-tagged items | **4** |

---

## 10. Remaining limitations

- Replacements are **DRAFT only** — not approved, published, or NCERT-certified.
- Historical P4 100 IDs remain the forensic cohort; active rematerialized slots are additive with lineage tags.
- Zoology-15 used deterministic distractor rewrite after Gemini could not clear ambiguity within attempt budgets — answer key not flipped.
- Soft `SEMANTIC_REVIEW_REQUIRED` on some replacements is review signal, not hard-fail certification.
- Other 96 V2 questions were not regenerated.

---

## 11. Recommendation for V2 P5 re-sampling

Run **P5 re-sample** with `factory_sample_v2` on a rematerialization-aware population (4 active replacements + unchanged 96), seed-controlled, then human review.

Do **not** yet: Diversity Forensics, NCERT certification, approve, publish, or regenerate the remaining 96.
