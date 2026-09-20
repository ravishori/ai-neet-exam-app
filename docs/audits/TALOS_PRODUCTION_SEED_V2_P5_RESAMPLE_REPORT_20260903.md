# Production Seed V2 — P5 Re-sample (post controlled rematerialization)

**Verdict: GREEN**  
**Date:** 2026-09-03  
**Sample key:** `sample-production-seed-v2-2026-09-03-batch-p5-resample-42`

---

## 1. Verdict

GREEN — active population is exactly 100; `factory_sample_v2` (seed 42) operated on the active cohort only; stratified sample + targeted rematerialization overlay reviewed; all applicable checks complete with **0 REJECT / 0 CORRECTION_REQUIRED**; four rematerialized slots **ACCEPT**; protected populations unchanged; no approve/publish/ECAEP/generation.

---

## 2. Active population

| Subject | Count |
|---------|------:|
| Physics | 35 |
| Chemistry | 35 |
| Botany | 15 |
| Zoology | 15 |
| **Total** | **100** |

Definition: P3/P4 slot map with replacements occupying **physics-05**, **physics-21**, **zoology-12**, **zoology-15**.

Population fact (not sample extrapolation): only **3** visual-required slots exist in the active 100.

---

## 3. Historical superseded records

**4** originals preserved under `seed-v2-rematerialization-superseded-20260903`:

| Slot | Historical ID |
|------|---------------|
| physics-05 | `2a22a821-d0bd-4c87-be2c-c35ef9664118` |
| physics-21 | `0de3dfa3-bc5a-4791-aa5d-8346dd08f0c2` |
| zoology-12 | `7580a952-0869-4f38-ae62-8c18a49bfb6f` |
| zoology-15 | `ef480cb5-8ede-451b-9444-940c7094e764` |

These are **not** counted in the active 100.

---

## 4–11. Sampler (`factory_sample_v2`)

| Field | Value |
|-------|-------|
| Seed | **42** |
| Requested / actual | **20 / 20** |
| Formula | `min(100, max(5, ceil(2.0*sqrt(100)))) = 20` |
| Operates on | Active 100 only (superseded excluded) |
| Reproducible same seed | **true** (within-run check) |

**Subject distribution:** Botany 9 · Chemistry 7 · Physics 3 · Zoology 1 (all four subjects represented)  
**Difficulty / archetype / visual / numerical:** see JSON `sampler.*_distribution`  
**Visual in stratified sample:** 1 visual-required · 19 non-visual  
**Exact sample IDs:** `docs/audits/TALOS_PRODUCTION_SEED_V2_P5_RESAMPLE_SAMPLE_20260903.json`

`factory_sample_v1` was **not** modified.

---

## 12. Decisions

| Scope | ACCEPT | CORRECTION_REQUIRED | REJECT |
|-------|-------:|--------------------:|-------:|
| Stratified sample (20) | 20 | 0 | 0 |
| + targeted remat overlay | 23 | 0 | 0 |

ACCEPT ≠ approve ≠ publish. Items remain **DRAFT**.

---

## 13. Four replacement reviews

| Slot | Original → Replacement | In sample? | Decision |
|------|------------------------|------------|----------|
| physics-05 | `2a22a821…` → `9c51f8a1…` | yes | **ACCEPT** |
| physics-21 | `0de3dfa3…` → `1633f068…` | targeted | **ACCEPT** |
| zoology-12 | `7580a952…` → `ca0e7a05…` | targeted | **ACCEPT** |
| zoology-15 | `ef480cb5…` → `03d1274b…` | targeted | **ACCEPT** |

Visual replacements: SVG + `visual_spec` present; type/archetype match; stem references figure; `ncert_evidence=false`; visual validation PASS.  
Zoology-15: dual-circuit A/D pattern **cleared**; correct_option **A**; soft `SEMANTIC_REVIEW_REQUIRED` (explanation multi-option mention) — **not** full uniqueness certification.

---

## 14. Graphical findings

- **Population:** 3 visual-required slots (known fact).
- **Sample:** 1 graphical / 19 non-graphical.
- Do **not** claim the entire V2 population is graphical.

---

## 15. Numerical findings

Sample includes numerical and non-numerical items (see sampler numerical distribution). Structural/consistency review only — not bank-wide independent recalculation certification.

---

## 16. Diversity observations

All four subjects appear in the seed-42 sample (improves on V1 Zoology-skew). Observation only — **not** Diversity Forensics.

---

## 17. Integrity

| Check | Result |
|-------|--------|
| Active 100 bodies unchanged by review | PASS |
| Historical superseded unchanged | PASS |
| V1 / T6-D / T6-F2 / legacy | UNCHANGED |
| Approvals / publications / ECAEP / generation | **0** |

---

## 18. Tests

```
pytest tests/test_seed_v2_p5_remediation.py tests/test_content_factory_p5.py \
       tests/test_content_factory_p3.py tests/test_content_factory_p4.py -q
→ 43 passed, 0 failed
```

(Includes `factory_sample_v2` unit coverage in remediation tests.)

---

## 19. Limitations

- P5 re-sample ≠ certification of all 100 items.
- Soft `SEMANTIC_REVIEW_REQUIRED` on some items is not a hard fail and is not semantic uniqueness certification.
- NCERT page/quotation certification not performed.
- Zoology under-weight in stratified sample (1/20) — still represented; remat zoology slots covered by targeted overlay.
- Only 1 of 3 visual slots entered the stratified sample; the other two were reviewed via targeted overlay.
- Diversity Forensics not run.

---

## 20. Next-gate recommendation

**Diversity Forensics** may be authorized as a **separate** next gate after this P5 re-sample close-out.  
It is **not** authorized to run automatically from this task.

Do **not** yet: NCERT certification, approve, publish, ECAEP, regenerate remaining slots.
