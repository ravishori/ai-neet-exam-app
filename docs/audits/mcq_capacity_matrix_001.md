# MCQ-CAPACITY-MATRIX-001 — Verified-usable capacity plan

**Generated:** 2026-09-14T02:17:30.361308+00:00
**Mode:** planning / read-only (no generation, no publish, no DB mutation)
**Syllabus:** `D:\ravishori\AI Neet Exam App\NEETSyllabus.txt`
**NCERT root:** `D:\ravishori\AI Neet Exam App\NCERT Books`

## Objective

Final **verified usable** targets (not raw generation):

| Subject | Target usable |
|---|---:|
| Physics | 10,000 |
| Chemistry | 10,000 |
| Biology | 10,000 |
| **Total** | **30,000** |

## Loss model (measured telemetry only)

Primary planning scenario: **A** = P3 forensic `created/attempt` × VERIFY-001 NCERT pass among created.

| Scenario | Yield / attempt | Attempts for 10k usable | Attempts for 30k usable | Reserve × |
|---|---:|---:|---:|---:|
| `A_content_gates_provider_ok_p3_x_ncert_verify` | 0.3986 | 25088 | 75264 | 2.5088× |
| `B_operational_pilot001_x_ncert_verify` | 0.1935 | 51680 | 155039 | 5.168× |
| `C_historical_created_x_ncert_verify` | 0.4010 | 24937 | 74810 | 2.4937× |

### Measured component rates

```json
{
  "p3_created_given_attempt": 0.664336,
  "p3_validation_reject_given_attempt": 0.041958,
  "p3_duplicate_reject_given_attempt": 0.167832,
  "p3_parse_fail_given_attempt": 0.125874,
  "historical_created_given_candidate": 0.668367,
  "historical_validation_reject_given_candidate": 0.079082,
  "historical_duplicate_reject_given_candidate": 0.061224,
  "historical_parse_fail_given_candidate": 0.130102,
  "pilot001_created_rate": 0.3225,
  "pilot001_provider_fail_rate": 0.6158,
  "pilot001_validation_reject_rate": 0.0169,
  "pilot001_duplicate_rate": 0.0,
  "ncert_pass_among_created_verify001": 0.6,
  "ncert_loss_among_created_verify001": 0.4,
  "ncert_sample_size": 5,
  "ncert_rate_confidence": "LOW \u2014 n=5 independent verify; post-GROUNDING-001 scale rate unknown"
}
```

### Caveats

- NCERT grounding loss uses VERIFY-001 (n=5). Do not treat as high-confidence until a larger post-GROUNDING-001 audit.
- PILOT-001 yield was dominated by provider failures, not content gates — use scenario B for ops capacity, A for content-quality sizing when provider is healthy.
- No measured assertion/reasoning or archetype-specific yield rates exist yet.

## Subject / unit capacity (usable targets)

### PHYSICS

- Target usable: **10000**
- Syllabus units: **20**
- Syllabus topic bullets: **56**
- GENERATION_READY blueprints mapped to units: **67**
- Required generation attempts (scenario A): **25088**

| Unit | Title | Topics | Usable target | Ready BPs | Ready concepts |
|---:|---|---:|---:|---:|---:|
| 1 | PHYSICS AND MEASUREMENT | 1 | 179 | 4 | 4 |
| 2 | KINEMATICS | 1 | 179 | 6 | 6 |
| 3 | LAWS OF MOTION | 3 | 536 | 5 | 5 |
| 4 | WORK, ENERGY, AND POWER | 2 | 357 | 6 | 6 |
| 5 | ROTATIONAL MOTION | 2 | 357 | 7 | 7 |
| 6 | GRAVITATION | 2 | 357 | 9 | 9 |
| 7 | PROPERTIES OF SOLIDS AND LIQUIDS | 3 | 536 | 10 | 10 |
| 8 | THERMODYNAMICS | 2 | 358 | 3 | 3 |
| 9 | KINETIC THEORY OF GASES | 1 | 179 | 4 | 4 |
| 10 | OSCILLATIONS AND WAVES | 3 | 536 | 0 | 0 |
| 11 | ELECTROSTATICS | 5 | 892 | 3 | 3 |
| 12 | CURRENT ELECTRICITY | 2 | 358 | 4 | 4 |
| 13 | MAGNETIC EFFECTS OF CURRENT AND MAGNETISM | 3 | 536 | 0 | 0 |
| 14 | ELECTROMAGNETIC INDUCTION AND ALTERNATING CURRENTS | 1 | 179 | 0 | 0 |
| 15 | ELECTROMAGNETIC WAVES | 1 | 179 | 0 | 0 |
| 16 | OPTICS | 2 | 358 | 6 | 6 |
| 17 | DUAL NATURE OF MATTER AND RADIATION | 1 | 179 | 0 | 0 |
| 18 | ATOMS AND NUCLEI | 1 | 179 | 0 | 0 |
| 19 | ELECTRONIC DEVICES | 1 | 179 | 0 | 0 |
| 20 | EXPERIMENTAL SKILLS | 19 | 3387 | 0 | 0 |

**Difficulty plan (policy, not measured):** easy=3000, medium=5000, hard=2000

**Archetype plan (policy; only fit archetypes — do not force):**

| Archetype | Target usable |
|---|---:|
| conceptual | 1800 |
| numerical | 2800 |
| application | 1400 |
| graph_table | 800 |
| experimental_practical | 800 |
| comparison | 600 |
| statement_based | 600 |
| diagram_based | 500 |
| multi_concept_integration | 500 |
| sequence_order | 200 |

### CHEMISTRY

- Target usable: **10000**
- Syllabus units: **20**
- Syllabus topic bullets: **61**
- GENERATION_READY blueprints mapped to units: **90**
- Required generation attempts (scenario A): **25088**

| Unit | Title | Topics | Usable target | Ready BPs | Ready concepts |
|---:|---|---:|---:|---:|---:|
| 1 | SOME BASIC CONCEPTS IN CHEMISTRY | 1 | 164 | 4 | 4 |
| 2 | ATOMIC STRUCTURE | 1 | 164 | 5 | 5 |
| 3 | CHEMICAL BONDING AND MOLECULAR STRUCTURE | 5 | 819 | 4 | 4 |
| 4 | CHEMICAL THERMODYNAMICS | 3 | 492 | 4 | 4 |
| 5 | SOLUTIONS | 1 | 164 | 6 | 6 |
| 6 | EQUILIBRIUM | 4 | 655 | 4 | 4 |
| 7 | REDOX REACTIONS AND ELECTROCHEMISTRY | 3 | 492 | 8 | 8 |
| 8 | CHEMICAL KINETICS | 1 | 165 | 8 | 8 |
| 9 | CLASSIFICATION OF ELEMENTS AND PERIODICITY IN PROPERTIES | 1 | 165 | 0 | 0 |
| 10 | P-BLOCK ELEMENTS | 1 | 165 | 0 | 0 |
| 11 | d and f-BLOCK ELEMENTS | 2 | 328 | 6 | 6 |
| 12 | CO-ORDINATION COMPOUNDS | 1 | 165 | 7 | 7 |
| 13 | PURIFICATION AND CHARACTERISATION OF ORGANIC COMPOUNDS | 3 | 492 | 0 | 0 |
| 14 | SOME BASIC PRINCIPLES OF ORGANIC CHEMISTRY | 4 | 655 | 4 | 4 |
| 15 | HYDROCARBONS | 5 | 819 | 2 | 2 |
| 16 | ORGANIC COMPOUNDS CONTAINING HALOGENS | 1 | 165 | 0 | 0 |
| 17 | ORGANIC COMPOUNDS CONTAINING OXYGEN | 4 | 655 | 16 | 16 |
| 18 | ORGANIC COMPOUNDS CONTAINING NITROGEN | 3 | 492 | 6 | 6 |
| 19 | BIOMOLECULES | 6 | 983 | 6 | 6 |
| 20 | PRINCIPLES RELATED TO PRACTICAL CHEMISTRY | 11 | 1801 | 0 | 0 |

**Difficulty plan (policy, not measured):** easy=3000, medium=5000, hard=2000

**Archetype plan (policy; only fit archetypes — do not force):**

| Archetype | Target usable |
|---|---:|
| conceptual | 2200 |
| application | 1600 |
| numerical | 1800 |
| comparison | 1000 |
| statement_based | 800 |
| experimental_practical | 800 |
| diagram_based | 600 |
| graph_table | 400 |
| multi_concept_integration | 500 |
| sequence_order | 300 |

### BIOLOGY

- Target usable: **10000**
- Syllabus units: **10**
- Syllabus topic bullets: **31**
- GENERATION_READY blueprints mapped to units: **121**
- Required generation attempts (scenario A): **25088**

| Unit | Title | Topics | Usable target | Ready BPs | Ready concepts |
|---:|---|---:|---:|---:|---:|
| 1 | Diversity in Living World | 4 | 1290 | 25 | 25 |
| 2 | Structural Organisation in Animals and Plants | 2 | 645 | 10 | 10 |
| 3 | Cell Structure and Function | 3 | 968 | 7 | 7 |
| 4 | Plant Physiology | 3 | 968 | 18 | 18 |
| 5 | Human Physiology | 6 | 1935 | 6 | 6 |
| 6 | Reproduction | 3 | 968 | 14 | 14 |
| 7 | Genetics and Evolution | 3 | 968 | 17 | 17 |
| 8 | Biology and Human Welfare | 2 | 645 | 8 | 8 |
| 9 | Biotechnology and Its Applications | 2 | 645 | 9 | 9 |
| 10 | Ecology and Environment | 3 | 968 | 7 | 7 |

**Difficulty plan (policy, not measured):** easy=3000, medium=5000, hard=2000

**Archetype plan (policy; only fit archetypes — do not force):**

| Archetype | Target usable |
|---|---:|
| conceptual | 2400 |
| statement_based | 1400 |
| application | 1400 |
| diagram_based | 1200 |
| comparison | 1000 |
| sequence_order | 800 |
| experimental_practical | 600 |
| multi_concept_integration | 600 |
| graph_table | 400 |
| numerical | 200 |

## Uncovered concepts / units

Units with usable target but **no** `GENERATION_READY` blueprint mapped: **13**

- PHYSICS Unit 10: OSCILLATIONS AND WAVES (assigned usable 536) — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 13: MAGNETIC EFFECTS OF CURRENT AND MAGNETISM (assigned usable 536) — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 14: ELECTROMAGNETIC INDUCTION AND ALTERNATING CURRENTS (assigned usable 179) — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 15: ELECTROMAGNETIC WAVES (assigned usable 179) — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 17: DUAL NATURE OF MATTER AND RADIATION (assigned usable 179) — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 18: ATOMS AND NUCLEI (assigned usable 179) — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 19: ELECTRONIC DEVICES (assigned usable 179) — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 20: EXPERIMENTAL SKILLS (assigned usable 3387) — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 9: CLASSIFICATION OF ELEMENTS AND PERIODICITY IN PROPERTIES (assigned usable 165) — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 10: P-BLOCK ELEMENTS (assigned usable 165) — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 13: PURIFICATION AND CHARACTERISATION OF ORGANIC COMPOUNDS (assigned usable 492) — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 16: ORGANIC COMPOUNDS CONTAINING HALOGENS (assigned usable 165) — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 20: PRINCIPLES RELATED TO PRACTICAL CHEMISTRY (assigned usable 1801) — no_GENERATION_READY_blueprint_mapped_to_unit

## Hierarchy used

NEET-2026 syllabus → unit → topic/subtopic (syllabus bullets) → canonical NCERT chapter (via GENERATION_READY blueprints) → concept → archetype/difficulty plan → target count

## Diversity / anti-paraphrase rule

- Every blueprint must identify the underlying concept.
- Do not create 100 near-paraphrases or trivial number swaps.
- Track diversity across difficulty, archetype, concept, and question pattern.

## Estimated raw generation requirement (summary)

- Scenario A (primary): **75264** attempts for 30k usable
- Scenario B (ops / provider outages): **155039**
- Scenario C (historical mix): **74810**

## Safety

- No MCQs generated
- No publication
- No database mutation
- No commit/push

## Next steps

1. Remediate uncovered units (see also MCQ-EVIDENCE-COVERAGE-001).
2. Re-measure NCERT grounding pass rate post-GROUNDING-001 at n≥50 before locking reserves.
3. Only run factory on `GENERATION_READY` blueprints under dual gates.
