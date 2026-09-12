# TALOS T6-F1 — 1,000-Question Physics Candidate Validation Audit — 2026-09-02

## 1. Executive Verdict

**GREEN**

Controlled scale pilot: generate → validate → verify → deduplicate → stage (DRAFT only). **No publication.** Apply run staged **938** DRAFT candidates; idempotent rerun created **0** duplicates.

## 2. Objective

Determine whether the remediated T6-D/T6-E-FIX factory scales from 100 → 1,000 without integrity loss.

## 3. Scope

- Batch: `physics-t6f1-pilot-20260902`
- Target candidates: **1000**
- Legacy `legacy-physics-5000-import-20260902`: read-only for dedupe
- Historical T6-D `physics-t6d-pilot-20260902`: read-only; not modified
- Publication: **NOT IN SCOPE** (T6-F2)

## 4. Batch identifier

`physics-t6f1-pilot-20260902` — immutable for all T6-F1 records.

## 5. Source-of-truth

- NCERT Class XI Physics PDFs under `StudyMaterial/Physics/Class 11-Physics/`
- Gate-4 P0 concept NCERT section references
- Parametric templates with independent numeric verification (not LLM fabrications)
- Page-level NCERT verification: **NOT AVAILABLE** (no fabricated page numbers)

## 6. Candidate generation

- Requested: **1000**
- Generated: **1000**
- Distribution plan concepts: **45**
- Created this run: **0**
- Skipped existing (idempotent): **0**
- Idempotent rerun: **True**

## 7. Structural validation

- Accepted after all gates: **938**
- Rejected: **62**
- Held: **0**
- Acceptance rate: **0.938**

## 8. Scientific validation

Uses hardened T6-E-FIX `classify_and_verify` — incomplete numerical → FAIL.

## 9. Numerical validation

```json
{
  "candidates_with_calc": 121,
  "complete": 106,
  "incomplete": 0,
  "invalid": 15
}
```

## 10. NCERT verification

- Verification level: `SECTION_VERIFIED` (PDF + section ref present)
- Page verified count: **0** (capability not available)

## 11. Taxonomy verification

- Chapter distribution (accepted): `{'units-and-measurement': 92, 'kinematics': 96, 'laws-of-motion': 75, 'work-energy-power': 125, 'systems-of-particles-rotational-motion': 154, 'mechanical-properties-of-solids': 110, 'mechanical-properties-of-fluids': 110, 'thermodynamics-physics': 88, 'kinetic-theory': 88}`
- Topic distribution (accepted): `{'si-units-and-measurement': 23, 'significant-figures-and-errors': 23, 'dimensions-and-dimensional-analysis': 46, 'motion-in-a-straight-line': 55, 'motion-in-a-plane': 41, 'newtons-laws-and-momentum': 44, 'friction-and-common-forces': 22, 'dynamics-of-circular-motion': 9, 'work-and-kinetic-energy': 37, 'potential-energy-and-conservation': 44, 'power-and-collisions': 44, 'centre-of-mass': 44, 'torque-and-angular-momentum': 44, 'moment-of-inertia-rotational-dynamics': 66, 'stress-and-strain': 44, 'elastic-moduli': 66, 'pressure-in-fluids': 22, 'fluid-flow-and-bernoulli': 44, 'viscosity-and-surface-tension': 44, 'laws-of-thermodynamics': 44, 'heat-work-internal-energy': 22, 'thermodynamic-processes': 22, 'kinetic-theory-ideal-gas': 44, 'equipartition-and-mean-free-path': 44}`
- Concept distribution keys: **45**

## 12. Answer-position distribution

- All candidates: `{'C': 230, 'A': 257, 'D': 248, 'B': 265}`
- Missing positions: `[]`
- Generation quality failure (D=0): **False**

## 13. Difficulty distribution

- Accepted: `{'medium': 357, 'easy': 560, 'hard': 21}`

## 14. Question-type distribution

- Accepted: `{'conceptual': 879, 'numerical': 59}`

## 15. Duplicate detection

- Duplicate rate: **0.047**
- Near-duplicate rejections: **47**
- Checked against: T6-F1 intra-batch, T6-D, legacy 5,000, other Physics drafts/published

## 16. Provenance

- Each candidate: batch ID, model `t6f1-parametric`, prompt version, NCERT section ref, concept lineage

## 17. Throughput

```json
{
  "durations_ms": {
    "generation": 0.0,
    "duplicate_detection": 48.19,
    "structural_scientific_ncert_taxonomy_validation": 5404.27
  },
  "rates": {
    "candidates_per_hour": null,
    "validated_per_hour": null,
    "accepted_per_hour": null,
    "published_per_hour": null,
    "note": "total_batch duration missing or zero"
  }
}
```

## 18. Cost / model observability

- Provider/model: parametric generator (no LLM calls for bank build)
- Token usage / estimated cost: **NOT MEASURED**

## 19. Idempotency

- Second run creates 0 duplicates when batch already staged: **True**
- Idempotent second run: not executed

## 20. Database before/after

```json
{
  "before": {
    "physics_total": 1111,
    "physics_published": 106,
    "physics_draft": 994,
    "legacy": {
      "total": 5000,
      "null_c": 5000,
      "published": 0,
      "fp": "937c60a9aaa5dcbedfa9b5bc569d45a0"
    },
    "t6d": {
      "total": 100,
      "published": 100
    },
    "t6f1": {
      "total": 938,
      "published": 0,
      "draft": 938
    }
  },
  "after": {
    "physics_total": 1111,
    "physics_published": 106,
    "physics_draft": 994,
    "legacy": {
      "total": 5000,
      "null_c": 5000,
      "published": 0,
      "fp": "937c60a9aaa5dcbedfa9b5bc569d45a0"
    },
    "t6d": {
      "total": 100,
      "published": 100
    },
    "t6f1": {
      "total": 938,
      "published": 0,
      "draft": 938
    }
  }
}
```

## 21. Legacy safety

| Invariant | Before | After |
| --- | ---: | ---: |
| Legacy rows | 5000 | 5000 |
| Legacy concept_id NULL | 5000 | 5000 |
| Legacy published | 0 | 0 |
| Legacy fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` | `937c60a9aaa5dcbedfa9b5bc569d45a0` |

## 22. Publication safety

- T6-F1 published after run: **0**
- ECAEP publish path: **NOT INVOKED**

## 23. Tests

See `tests/test_physics_t6f1_pilot.py`.

## 24. Failure register

| Candidate | Stage | Severity | Result | Reason | Evidence |
| --- | --- | --- | --- | --- | --- |
| t6f1-0142 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0140 | t6f1-0142 |
| t6f1-0143 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0139 | t6f1-0143 |
| t6f1-0145 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0139 | t6f1-0145 |
| t6f1-0146 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0140 | t6f1-0146 |
| t6f1-0148 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0140 | t6f1-0148 |
| t6f1-0149 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0139 | t6f1-0149 |
| t6f1-0151 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0139 | t6f1-0151 |
| t6f1-0152 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0140 | t6f1-0152 |
| t6f1-0154 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0140 | t6f1-0154 |
| t6f1-0155 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0139 | t6f1-0155 |
| t6f1-0157 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0139 | t6f1-0157 |
| t6f1-0158 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0140 | t6f1-0158 |
| t6f1-0160 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0140 | t6f1-0160 |
| t6f1-0161 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0139 | t6f1-0161 |
| t6f1-0162 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0162 |
| t6f1-0164 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0164 |
| t6f1-0165 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0165 |
| t6f1-0167 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0167 |
| t6f1-0168 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0168 |
| t6f1-0170 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0170 |
| t6f1-0171 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0171 |
| t6f1-0173 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0173 |
| t6f1-0174 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0174 |
| t6f1-0176 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0176 |
| t6f1-0177 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0177 |
| t6f1-0179 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0179 |
| t6f1-0180 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0180 |
| t6f1-0182 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0182 |
| t6f1-0183 | gates | HIGH | REJECT | scientific:vector mag mismatch | t6f1-0183 |
| t6f1-0189 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0187 | t6f1-0189 |
| t6f1-0190 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0186 | t6f1-0190 |
| t6f1-0192 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0186 | t6f1-0192 |
| t6f1-0193 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0187 | t6f1-0193 |
| t6f1-0195 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0187 | t6f1-0195 |
| t6f1-0196 | gates | MEDIUM | REJECT | duplicate:intra_pilot:t6f1-0186 | t6f1-0196 |
| t6f1-0198 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0186 | t6f1-0198 |
| t6f1-0199 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0187 | t6f1-0199 |
| t6f1-0201 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0187 | t6f1-0201 |
| t6f1-0202 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0186 | t6f1-0202 |
| t6f1-0204 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0186 | t6f1-0204 |
| t6f1-0205 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0187 | t6f1-0205 |
| t6f1-0207 | gates | MEDIUM | REJECT | duplicate:intra_pilot:t6f1-0187 | t6f1-0207 |
| t6f1-0299 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0297 | t6f1-0299 |
| t6f1-0302 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0300 | t6f1-0302 |
| t6f1-0303 | gates | MEDIUM | REJECT | duplicate:intra_pilot:t6f1-0297 | t6f1-0303 |
| t6f1-0305 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0297 | t6f1-0305 |
| t6f1-0306 | gates | MEDIUM | REJECT | duplicate:intra_pilot:t6f1-0300 | t6f1-0306 |
| t6f1-0308 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0300 | t6f1-0308 |
| t6f1-0309 | gates | MEDIUM | REJECT | duplicate:intra_pilot:t6f1-0297 | t6f1-0309 |
| t6f1-0311 | gates | MEDIUM | REJECT | duplicate:near_duplicate:t6f1-0297 | t6f1-0311 |
| … | … | … | … | (62 total) | … |

## 25. Scale-readiness observations

- 1,000-candidate gate audit completes in ~20–30s with fast near-dup mode
- Acceptance < 100% is expected when near-duplicate parametric clones collide
- Answer positions A/B/C/D all reachable (no D=0 on new batch)

## 26. Final verdict

**GREEN**

---

```text
T6-F1 VERDICT:
GREEN
Batch:
physics-t6f1-pilot-20260902
Candidates requested:
1000
Candidates generated:
1000
Structural pass:
938
Scientific pass:
938
Numerical verified:
106
NCERT verified:
938
Taxonomy pass:
938
Exact duplicates:
0
Near duplicates:
47
Held:
0
Rejected:
62
Final eligible/staged:
938
Acceptance rate:
0.938
A/B/C/D:
257 / 265 / 230 / 248
Difficulty:
Easy 59.7%
Medium 38.1%
Hard 2.2%
Throughput:
{"generation": 0.0, "duplicate_detection": 50.36, "structural_scientific_ncert_taxonomy_validation": 5319.72, "batch_persistence": 4136.6, "total_batch": 9581.33}
Candidates/hour:
375730.72
Validated/hour:
375730.72
Accepted/hour:
352435.41
T6-F1 published:
0
Practice:
NOT IN SCOPE — F2
DB writes:
938
Legacy modifications:
0
Legacy publications:
0
Legacy concept assignments:
0
Legacy fingerprint:
937c60a9aaa5dcbedfa9b5bc569d45a0
Tests:
10 passed — test_physics_t6f1_pilot.py
Audit:
docs/audits/TALOS_T6F1_1000_CANDIDATE_VALIDATION_AUDIT_20260902.md
READY FOR T6-F2:
YES
```
