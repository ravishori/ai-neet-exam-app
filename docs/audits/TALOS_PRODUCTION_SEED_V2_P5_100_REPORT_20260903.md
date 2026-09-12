# PRODUCTION SEED V2 — P5 HUMAN SAMPLING / REVIEW (Exact 100)

**Verdict:** `AMBER`  
**Captured:** 2026-09-03T17:20:17.811083+00:00  
**Sample key:** `sample-production-seed-v2-2026-09-03-batch-p5-100-42`  
**Seed:** `42`

## 1. Exact population
- Population: **100** P3/P4 IDs (exact membership)
- All remain **DRAFT**; approvals/publications/ECAEP transitions from this gate: **0**

## 2. Sampling methodology
- Policy: **factory_sample_v1**
- Formula: `min(100, max(5, ceil(2.0*sqrt(100)))) = 20`
- Algorithm: stratified round-robin by `subject|family|difficulty|blueprint`
- Reproducible seed: **42**
- Graphical stratification: **NOT SUPPORTED** (limitation recorded; algorithm not altered)

## 3. Sample size
**20 / 100**

## 4. Distributions (sample)
- Subjects: `{'Chemistry': 5, 'Zoology': 15}`
- Difficulty: `{'medium': 10, 'easy': 7, 'hard': 3}`
- Archetypes: `{'direct_ncert_conceptual': 10, 'sequence_order': 2, 'application': 4, 'diagram_data_interpretation': 1, 'comparison': 3}`
- Graphical: sample 0 / population 0

## 5. Decisions
| Decision | Count |
|----------|------:|
| ACCEPT | 18 |
| CORRECTION_REQUIRED | 2 |
| REJECT | 0 |

## 6. Major findings
- **zoology-15** (`ef480cb5-…`): dual-defensible options A and D → CORRECTION_REQUIRED (AMBIGUOUS/BAD_DISTRACTOR).
- **zoology-12** (`7580a952-…`): diagram_data_interpretation archetype without visual → CORRECTION_REQUIRED (WRONG_MAPPING).
- Sample **missing Physics and Botany** under factory_sample_v1 unique-blueprint strata ordering.

## 7. Diversity findings
- Sample subject skew: Zoology 15 / Chemistry 5 / Physics 0 / Botany 0 — factory_sample_v1 round-robin over unique subject|family|difficulty|blueprint keys sorts by UUID and does not enforce subject quotas.
- No ABO agglutination / non-cyclic photophosphorylation / Ohm V-doubled / 20% stretch / lattice-energy cluster repetition observed in the 20-item sample.
- Within-sample chapter concentration: Breathing/Exchange, Body Fluids/Circulation, Animal Kingdom appear multiple times (expected under Zoology-heavy draw).
- Semantic uniqueness across full 100 is NOT claimed by P5.

## 8. Graphical findings
- Population graphical bodies (diagram_svg/figure heuristics): 0/100.
- Sample graphical bodies: 0/20.
- Plan lists 3 diagram_data_interpretation slots; sampled zoology-12 is that archetype but lacks a visual asset → CORRECTION_REQUIRED.
- factory_sample_v1 does not stratify graphical vs non-graphical (limitation recorded; algorithm not altered).

## 9. Numerical findings
- chemistry-05 equal-mass limiting reagent independently mole-checked → PASS.
- No other sampled item required formal numerical certification in this gate.
- P5 does not claim bank-wide independent numerical certification.

## 10. Integrity
- V2 bodies/status unchanged: **{pre_v2['bodies_fp'] == post_v2['bodies_fp']}**
- V1 / T6-D / T6-F2 / legacy: **UNCHANGED**
- Unexpected mutations: `{unexpected}`

## 11. Tests
- `tests/test_content_factory_p5.py`: **{'PASS' if proc.returncode == 0 else 'FAIL'}** (rc={proc.returncode})
- V2-specific P5 tests: **NOT_PRESENT**

## 12. Limitations
- P5 sample ≠ certification of all 100 items.
- factory_sample_v1 did not enforce subject or graphical quotas; sample is Zoology/Chemistry skewed.
- Not NCERT certified; no fabricated page/quotation evidence.
- Not scientifically certified as a bank.
- Not an independent multi-SME panel.
- ACCEPT marks ecaep_submit_eligible only; ContentItem remains DRAFT.
- Diversity forensic remains a separate gate.

## 13. Stop
- Diversity Forensics is the **recommended next separate gate** — **not authorized/executed** by this P5 run.
- Do not approve, publish, run NCERT certification, or student practice from this gate alone.

**Artifacts:**  
- `{OUT_JSON.relative_to(ROOT).as_posix()}`  
- `{OUT_MD.relative_to(ROOT).as_posix()}`  
