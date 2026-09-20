# PRODUCTION SEED V2 — P5 AMBER FORENSIC / REMEDIATION INVESTIGATION

**Verdict:** AMBER  
**Captured:** 2026-09-03T17:29:18.424292+00:00  
**Scope:** Investigation + remediation design only (no generation / approve / publish / NCERT / diversity).

## 1. P5 finding summary
- P5 verdict AMBER; sample 20; ACCEPT 18 / CORRECTION_REQUIRED 2 / REJECT 0
- Graphical population 0/100; sample 0/20
- zoology-12: diagram archetype, no visual
- zoology-15: dual-defensible options A & D
- Sample skew: Zoology 15 / Chemistry 5 / Physics 0 / Botany 0

## 2. Graphical slot forensic
| Metric | Value |
|--------|------:|
| Planned visual slots | 3 |
| Slot IDs | physics-05, physics-21, zoology-12 |
| Generated with visuals | 0 |
| Planned but missing visuals | 3 |
| Incorrect visual metadata | 0 |

### Data-path loss (where visual dies)
1. **Plan** — OK (archetype set)
2. **Blueprint materialization** (
un_factory_production_seed_v2.py) — archetype stored in constraints textually; no isual_required
3. **Prompt** (actory_mcq.py SYSTEM_PROMPT / uild_user_prompt) — **LOSS**: JSON schema has no diagram fields; archetype not enforced as visual requirement
4. **Validation** (alidate_candidate_body) — **GAP**: no visual check
5. **Schema** (QuestionBody) — **STRIP/IGNORE**: no diagram_svg; extras dropped; DiagramBody unused by factory MCQ path
6. **VisualAsset persistence** — **NOT WIRED**

**Root cause:** FACTORY_IMPLEMENTATION_GAP_SYSTEMIC

## 3. Zoology-12 forensic
- Item 7580a952-0869-4f38-ae62-8c18a49bfb6f · DRAFT
- Planned/actual archetype: diagram_data_interpretation
- Visual fields: none
- Classification: **SYSTEMIC_MANIFESTATION** (1 of 3 identical planned-visual failures)

## 4. Zoology-15 forensic
- Item ef480cb5-8ede-451b-9444-940c7094e764 · DRAFT · stored answer **A**
- Option A and Option D are both scientifically defensible
- Structural validation passed (one label + unique texts)
- Semantic exactly-one-correct: **NOT IMPLEMENTED**
- Classification: **BOTH** (isolated content defect + validation gap)

## 5. Sampling forensic
actory_sample_v1 + unique blueprints ⇒ first 20 lexicographically sorted strata keys.  
Subject UUID order: **Zoology → Chemistry → Physics → Botany**.  
Observed skew is **deterministic**, not random bad luck.  
**Do not alter** actory_sample_v1. Recommend separate **V2 sampler** with minima for subject / difficulty / graphical / numerical / archetype.

## 6. Population vs sample
| Question | Sample evidence? | Population evidence? |
|----------|------------------|----------------------|
| Physics quality | No (0 sampled) | Not from P5 sample |
| Botany quality | No | Not from P5 sample |
| Graphical delivery | No | **Yes — 0/3 planned visuals generated** |
| Numerical | No (0 in sample; 14 planned) | Needs separate review |
| Zoology dual-correct | Yes (zoology-15) | Unknown bank-wide rate |
| Chemistry | Weak (5) | Incomplete |

## 7–8. Root causes & implicated files
See JSON 
oot_cause_classification_summary and implicated_files_functions.

## 9. Integrity
V2 bodies/status unchanged vs P5 · V1/T6-D/T6-F2/legacy **UNCHANGED** · approvals/publications/ECAEP **0**

## 10. Tests
pytest tests/test_content_factory_p4.py tests/test_content_factory_p5.py → **17 passed**

## 11. Minimum remediation before scale
| ID | Item | Priority |
|----|------|----------|
| A | Visual blueprint enforcement | Mandatory |
| B | Visual asset/spec generation | Mandatory |
| C | Visual validation gate | Mandatory |
| D | Exactly-one-answer / ambiguity hardening | Strongly recommended |
| E | V2 representative sampling policy | Strongly recommended |
| F | Semantic diversity detection | Next gate after A–E |

## 12. Diversity Forensics
**Do not proceed now.** Proceed **after** remediation A–E so diversity is not run on a text-only realization of a visual-intended plan.

**Artifact JSON:** docs/audits/TALOS_PRODUCTION_SEED_V2_P5_FORENSIC_20260903.json
