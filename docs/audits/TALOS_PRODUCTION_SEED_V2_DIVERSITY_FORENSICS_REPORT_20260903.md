# Production Seed V2 — Diversity Forensics (Exact Active 100)

**Verdict: GREEN**  
**Captured:** 2026-09-03T18:16:23.889552+00:00  
**Evidence label:** `V2_cohort_evidence_not_global_bank` — V2 cohort only; **not** global-bank uniqueness.

---

## 1. Exact active population

| Metric | Value |
|--------|-------|
| Active n | **100** |
| Physics | 35 |
| Chemistry | 35 |
| Botany | 15 |
| Zoology | 15 |

Active membership = P3/P4 slots with rematerialization **replacements** for four remediated slots.

Replacements (active):
- physics-05 → `9c51f8a1-bf72-4ca0-bcfd-e0aa5cb8ee53`
- physics-21 → `1633f068-f0df-4ff5-ac0c-57be4417f29e`
- zoology-12 → `ca0e7a05-38bb-4e12-a52d-4fd4c7a26b07`
- zoology-15 → `03d1274b-35fa-446a-8742-164e9a28e8d3`

## 2. Historical exclusions

**n = 4** superseded originals — excluded from all active diversity metrics:

- `2a22a821-d0bd-4c87-be2c-c35ef9664118`
- `0de3dfa3-bc5a-4791-aa5d-8346dd08f0c2`
- `7580a952-0869-4f38-ae62-8c18a49bfb6f`
- `ef480cb5-8ede-451b-9444-940c7094e764`

Preserved for audit lineage only. Not counted as production questions. Active set is **100**, not 104.

## 3. Exact duplicate

- Body-duplicate groups: **0** (expected 0)
- Method: SHA-256 of canonical stem+options+correct+explanation JSON

## 4. Normalized duplicate

- Normalized-stem groups: **0** (expected 0)
- Method: `factory_candidate_validation.stem_hash` / `normalize_stem`

## 5. Near-duplicate

- Pair count (jaccard ≥ 0.72): **0**
- Method: `factory_seed_diversity.classify_against_prior`
- Threshold: **0.72** (source: `factory_seed_diversity.py` — not invented)

## 6. Template repetition

- Forbidden-template pairs: **0**
- Structure/archetype clusters: **0**
- Identical skeleton clusters: **0**
- Forbidden solo hits: **0**

## 7. Conceptual overlap

- Legitimate conceptual-overlap pairs: **1**
- Max chapter count: **5**
- Max concept count: **2** (`Chemistry/sp-sp2-sp3` = 2)
- Unique blueprints: **100**
- Excessive concentration flags: none
- Item labels: `{'UNIQUE': 98, 'LEGITIMATE_CONCEPTUAL_OVERLAP': 2}`

## 8. Subject distribution

Observed: {'Physics': 35, 'Chemistry': 35, 'Botany': 15, 'Zoology': 15}  
Match expected 35/35/15/15: **True**  
Note: subject allocation ≠ conceptual diversity.

## 9. Difficulty distribution

| Source | easy | medium | hard |
|--------|------|--------|------|
| Expected | 25 | 60 | 15 |
| Plan observed | 25 | 60 | 15 |
| Body observed | 25 | 60 | 15 |

Plan match: **True**

## 10. Archetype distribution

| Archetype | Count |
|-----------|------:|
| direct_ncert_conceptual | 42 |
| application | 22 |
| numerical_calculation | 14 |
| comparison | 14 |
| diagram_data_interpretation | 3 |
| sequence_order | 3 |
| statement_based | 2 |

Plan expected matches observed: **True**

## 11. Graphical analysis

| Metric | Value |
|--------|-------|
| visual_required | 3 |
| with SVG + visual_spec | 3 |
| unique visual_spec fingerprints | 3 |
| unique SVG fingerprints | 3 |
| repeated visual_spec | none |
| repeated SVG | none |

Slots: physics-05, physics-21, zoology-12  
Types: {'line_graph': 1, 'curve_graph': 1, 'schematic': 1}  
Archetypes: {'xt_slope_graph': 1, 'stress_strain_curve': 1, 'ecg_wave_schematic': 1}  

**Not** claiming 3/100 as the eventual 40% production graphical target — rematerialization validation cohort only.

## 12. Numerical analysis

- numerical_count: **14**
- calculation_types: {'suvat_1d': 1, 'projectile_range': 1, 'momentum_1d': 1, 'work_energy': 1, 'com_two_body': 1, 'youngs_modulus': 1, 'carnot_efficiency': 1, 'coulomb_force': 1, 'thin_lens': 1, 'ydse_fringe': 1, 'mole_conversion': 1, 'empirical_formula': 1, 'hess_law': 1, 'ph_strong_acid': 1}
- identical-skeleton clusters: **0**

## 13. Chemistry concentration

- Chemistry total: **35**
- Largest chapter count: **5** (tied: Chemical Bonding and Molecular Structure, Equilibrium, Some Basic Concepts of Chemistry, Structure of Atom)
- Unique concepts: **34** / 35
- Near-duplicate Chem pairs: **0**
- Template clusters involving Chem: **0**
- Chapter distribution: {'Some Basic Concepts of Chemistry': 5, 'Structure of Atom': 5, 'Chemical Bonding and Molecular Structure': 5, 'Thermodynamics': 4, 'Equilibrium': 5, 'Redox Reactions': 4, 'Organic Chemistry - Basic Principles': 4, 'Electrochemistry': 3}

V1-style single-chapter / single-family Chem concentration **not** observed.

## 14. Previous V1 pattern recurrence

Any present: **False**

| Pattern | Count | Status |
|---------|------:|--------|
| PHYS_STRETCH_20PCT_CURRENT | 0 | ABSENT |
| PHYS_STRETCH_2X_LENGTH_RATIO | 0 | ABSENT |
| PHYS_OHM_V_DOUBLED_R_CONSTANT | 0 | ABSENT |
| CHEM_LATTICE_COMPARISON | 0 | ABSENT |
| CHEM_LATTICE_FACTORS | 0 | ABSENT |
| BOT_NONCYCLIC_PHOTOPHOSPHORYLATION | 0 | ABSENT |
| ZOO_ABO_SEQUENCE | 0 | ABSENT |
| ZOO_ABO_ANTIGEN_IDENTIFY | 0 | ABSENT |

Extra keyword scans (all count 0):
- ABO_agglutination_keywords: 0
- noncyclic_photophosphorylation: 0
- ohm_v_doubled: 0
- stretch_20pct_or_2x: 0
- lattice_energy_compare: 0

## 15. Semantic dedupe

**SEMANTIC_DEDUPE_NOT_AVAILABLE**  
Method/model/threshold: none (deterministic lexical only).  
**No semantic uniqueness claim.**

## 16. Cluster tables

Top chapters:
- Chemistry/Chemical Bonding and Molecular Structure: 5 (5.0%)
- Chemistry/Equilibrium: 5 (5.0%)
- Chemistry/Some Basic Concepts of Chemistry: 5 (5.0%)
- Chemistry/Structure of Atom: 5 (5.0%)
- Chemistry/Organic Chemistry - Basic Principles: 4 (4.0%)
- Chemistry/Redox Reactions: 4 (4.0%)
- Chemistry/Thermodynamics: 4 (4.0%)
- Physics/Kinematics: 4 (4.0%)
- Physics/Systems of Particles and Rotational Motion: 4 (4.0%)
- Physics/Work, Energy and Power: 4 (4.0%)
- Zoology/Body Fluids and Circulation: 4 (4.0%)
- Botany/Cell - The Unit of Life: 3 (3.0%)

Top concepts:
- Chemistry/sp-sp2-sp3: 2 (2.0%)
- Botany/Algae classes / bryophyte haplodiplontic idea: 1 (1.0%)
- Botany/Auxin / gibberellin / cytokinin / ethylene / ABA roles: 1 (1.0%)
- Botany/Floral formula / placentation types: 1 (1.0%)
- Botany/Herbarium / botanical gardens / keys (qualitative): 1 (1.0%)
- Botany/Heterospory / gymnosperm seeds: 1 (1.0%)
- Botany/Modifications of root/stem/leaf: 1 (1.0%)
- Botany/SDP/LDP qualitative: 1 (1.0%)
- Botany/Syngamy and triple fusion: 1 (1.0%)
- Botany/Taxonomic hierarchy / binomial nomenclature: 1 (1.0%)

## 17. Integrity

| Check | Result |
|-------|--------|
| Active 100 unchanged | True |
| Historical 4 unchanged | True |
| V1 / T6-D / T6-F2 / legacy unchanged | True |
| Approvals | 0 |
| Publications | 0 |
| ECAEP | 0 |
| Body mutations | 0 |
| Status mutations | 0 |

Active status: {'DRAFT': 100} (all DRAFT)

## 18. Tests

- `test_factory_seed_diversity` + `test_seed_v2_p5_remediation`: **27 passed**
- `test_seed_v2_phase1_plan` + `test_factory_seed_diversity`: **12 passed**
- Thresholds not weakened; production content not mutated to pass metrics.

## 19. Limitations

- Cohort forensic only — not global-bank uniqueness proof.
- SEMANTIC_DEDUPE_NOT_AVAILABLE — no embeddings/pgvector in this wave; lexical/template classifiers only.
- Do not equate exact/normalized uniqueness with semantic uniqueness.
- 3/100 visual slots is rematerialization validation, not the eventual 40% production target.
- Legitimate conceptual overlap on shared NCERT topics is expected and not counted as duplication.

## 20. Remediation recommendation / next gate

No systemic remediation required before considering NCERT certification gate

**Recommended next gate:** NCERT certification gate (separate authorization) — still no approve/publish

### Rematerialized vs remaining 96

All four replacements classified **UNIQUE_VS_REMAINING_96** under the established lexical/template classifier.

---

**STOP** — Diversity Forensics complete. No generate / regenerate / approve / publish / NCERT certify / 1,000-scale start from this gate alone.
