# TALOS Physics Taxonomy Gap Analysis — 2026-09-02

**Mode:** READ-ONLY audit (proposal only)  
**Scope:** NCERT Class XI/XII Physics (StudyMaterial corpus) vs current TALOS Physics taxonomy vs 5 unresolved legacy import chapters  
**Batch context:** `legacy-physics-5000-import-20260902`  

**Hard safety:** No PostgreSQL writes. No taxonomy INSERT/UPDATE. No `concept_id` / `chapter_id` assignments. No publication. No source modifications.

---

## 1. Executive Verdict

TALOS Physics has a **genuine curriculum-taxonomy gap**: the live hierarchy is an intentionally incomplete seed subset (ADR-0012 / `seed.py`), not a full NCERT Class XI/XII graph.

Separately, the **2,500 unresolved legacy questions cannot be unlocked by taxonomy extension alone**. Their `legacy_chapter_id` labels do not match stem subject matter (documented in `PHYSICS_5000_TAXONOMY_RESOLUTION_AUDIT_20260902.md`). That is a **legacy source/classification problem**.

| Finding | Classification |
|---------|----------------|
| Missing NCERT chapters/topics/concepts in TALOS | **Curriculum gap — taxonomy extension justified** |
| 2,500 unresolved questions vs those chapters | **RED — SOURCE/CLASSIFICATION PROBLEM** |
| Operational decision for the 2,500 | Do **not** assign `concept_id`; remediate content classification first |

**Recommended action for the 2,500 unresolved questions:**  
`RED — SOURCE/CLASSIFICATION PROBLEM`

**Parallel platform recommendation (not a substitute for remediating the 2,500):** approve a minimum NCERT-aligned Physics taxonomy extension so the future MCQ factory has durable nodes.

---

## 2. NCERT Baseline

### 2.1 Corpus examined

Root: `StudyMaterial/Physics/`

| Class | Files present | Missing from corpus |
|-------|---------------|---------------------|
| XI | chapters **1–6, 8–9, 11–14** (12 PDFs) | **Ch 7 (Gravitation)**, **Ch 10 (Thermal Properties of Matter)** — PDFs not in StudyMaterial |
| XII Part 1 | chapters **1–8** (8 PDFs) | Part 2 Optics / Dual Nature / Atoms / Nuclei / Semiconductor not present under this tree |

**Total NCERT Physics chapter PDFs examined = 20**  
(12 Class XI + 8 Class XII Part 1)

Titles and sections extracted with PyMuPDF from the actual PDFs (not inferred from general knowledge). Truncated OCR/layout lines noted where the PDF split letters across spans; full titles confirmed from large-font title reconstruction + section content.

### 2.2 Class XI — complete chapter list from corpus + known gaps

| NCERT Ch | Exact title (from PDF) | Source filename | Major sections (evidence) |
|--------:|------------------------|-----------------|---------------------------|
| 1 | UNITS AND MEASUREMENT | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf` | 1.1 Introduction; 1.2 SI Units; 1.3 Significant Figures; 1.4 Dimensions of Physical Quantities; 1.5–1.6 Dimensional formulae / analysis |
| 2 | MOTION IN A STRAIGHT LINE | `…chapter-2.pdf` | Instantaneous velocity/speed; Acceleration; Kinematic equations; Relative velocity |
| 3 | MOTION IN A PLANE | `…chapter-3.pdf` | Scalars/vectors; Resolution; Motion in a plane; Projectile; Uniform circular motion |
| 4 | LAWS OF MOTION | `…chapter-4.pdf` | Inertia; Newton’s laws; Momentum; Equilibrium; Common forces; Circular motion |
| 5 | WORK, ENERGY AND POWER | `…chapter-5.pdf` | Work; KE; Variable force; PE; Conservation; Spring; Power; Collisions |
| 6 | SYSTEMS OF PARTICLES AND ROTATIONAL MOTION | `…chapter-6.pdf` | Centre of mass; Angular velocity; Torque & angular momentum; Rigid body equilibrium; Moment of inertia; Rotational kinematics/dynamics |
| 7 | **GRAVITATION** | **PDF ABSENT from StudyMaterial** | Not extractable from local corpus; TALOS already has a `gravitation` chapter name |
| 8 | MECHANICAL PROPERTIES OF SOLIDS | `…chapter-8.pdf` | Stress and strain; Stress–strain curve; Elastic moduli; Applications of elasticity |
| 9 | MECHANICAL PROPERTIES OF FLUIDS | `…chapter-9.pdf` | Pressure; Streamline flow; **Bernoulli** (text present); Viscosity; Surface tension |
| 10 | **THERMAL PROPERTIES OF MATTER** | **PDF ABSENT** | Not extractable from local corpus |
| 11 | THERMODYNAMICS | `…chapter-11.pdf` | Thermal equilibrium; Zeroth/First/Second law; Heat & internal energy; Processes; Carnot |
| 12 | KINETIC THEORY | `…chapter-12.pdf` | Molecular nature; Behaviour of gases; KT of ideal gas; Equipartition; Specific heat; Mean free path |
| 13 | OSCILLATIONS | `…chapter-13.pdf` | Periodic/oscillatory; SHM; Force law; Energy in SHM |
| 14 | WAVES | `…chapter-14.pdf` | Transverse/longitudinal; Travelling wave speed; Superposition; Reflection; Beats |

### 2.3 Class XII Part 1 (examined)

| NCERT Ch | Title (from PDF / section evidence) | Source filename | Major topics |
|--------:|-------------------------------------|----------------|--------------|
| 1 | Electric Charges and Fields | `…part-1-chapter-1.pdf` | Charge; Coulomb; Field; Flux; Dipole; Gauss |
| 2 | Electrostatic Potential and Capacitance | `…chapter-2.pdf` | Potential; Conductors; Dielectrics; Capacitors |
| 3 | Current Electricity | `…chapter-3.pdf` | Current; Ohm; Drift; Resistivity; Cells; Kirchhoff; Wheatstone |
| 4 | Moving Charges and Magnetism | `…chapter-4.pdf` | Magnetic force; Biot–Savart; Ampere; Solenoid; Galvanometer |
| 5 | Magnetism and Matter | `…chapter-5.pdf` | Magnetisation; Magnetic materials |
| 6 | Electromagnetic Induction | `…chapter-6.pdf` | Flux; Faraday/Lenz; Motional emf; Inductance; AC generator |
| 7 | Alternating Current | `…chapter-7.pdf` | AC on R/L/C/LCR; Transformers |
| 8 | Electromagnetic Waves | `…chapter-8.pdf` | Displacement current; EM waves; Spectrum |

### 2.4 Legacy bank numbering ≠ NCERT chapter numbers

`physics-question-bank/config.py` defines a **10-chapter Class 11 subset** with its own IDs 1–10:

| Legacy ID | Legacy title | Actual NCERT Class XI chapter # |
|----------:|--------------|--------------------------------:|
| 1 | Units and Measurement | 1 |
| 2 | Motion in a Straight Line | 2 |
| 3 | Motion in a Plane | 3 |
| 4 | Laws of Motion | 4 |
| 5 | Work, Energy and Power | 5 |
| 6 | Systems of Particles and Rotational Motion | 6 |
| 7 | Mechanical Properties of Solids | **8** |
| 8 | Mechanical Properties of Fluids | **9** |
| 9 | Thermodynamics | **11** |
| 10 | Kinetic Theory | **12** |

Skipped in the legacy bank: Gravitation (7), Thermal Properties (10), Oscillations (13), Waves (14).

---

## 3. Current TALOS Taxonomy

**Subject:** PHYSICS  
- `id` = `8546ab39-2401-4e1f-91e7-a22e27afe147`  
- `code` = `PHYSICS`  
- `name` = `Physics`

### 3.1 Complete hierarchy (exact DB values)

```
PHYSICS (8546ab39-2401-4e1f-91e7-a22e27afe147)
├── Kinematics                          ch=b20f8158-cba8-41d2-a88e-3fbd1b2261d2  code=kinematics
│   └── (no topics / concepts / micro-competencies)
├── Laws of Motion                      ch=433d0aa4-5edd-4ddf-9729-e3cfc9299e1f  code=laws-of-motion
│   └── (empty)
├── Work, Energy and Power              ch=81f3a1f9-8348-401f-b35d-0a196c97f2ea  code=work-energy-power
│   └── (empty)
├── Gravitation                         ch=d1f5f09d-037a-4e1d-abcb-1a760a4be031  code=gravitation
│   └── (empty)
├── Thermodynamics                      ch=2f62c566-16e5-4996-a5e3-d003592dd35b  code=thermodynamics-physics
│   └── (empty)
├── Electrostatics                      ch=ed3e1c7b-f27a-483a-85ee-9a851f3c0963  code=electrostatics
│   ├── Electric Charge and Coulomb's Law   t=310c5182-2357-48f3-8d14-f3cfd6f6b36a  code=coulombs-law
│   │   └── Coulomb's Law                   c=38563952-1621-4afa-b82d-4804adbfb18b  code=coulomb-force
│   ├── Electric Field and Potential        t=a1fe3192-754d-4728-82bc-a9065d5a3b31  code=electric-field-potential
│   │   └── Electric Field and Potential    c=46b902b1-6feb-4d05-94c2-7381a342f1f0  code=field-potential-relation
│   └── Capacitance                         t=b42b4a63-6dc9-4098-bef5-0cbad98e85b2  code=capacitance
│       └── Parallel Plate Capacitor        c=29560b80-2c9d-4093-98cf-9ee7533fba3a  code=parallel-plate-capacitor
├── Current Electricity                 ch=44e651c0-5346-4439-a60d-6424e0768a9f  code=current-electricity
│   ├── Electric Current and Ohm's Law      t=9c5ee8f8-4234-4618-a24e-e0251711bebc  code=ohms-law
│   │   ├── Ohm's Law                       c=9071ef5d-b62f-4159-91b6-90436a7705e6  code=ohms-law-concept
│   │   │   ├── Apply V=IR…                 mc=bbcbf967-28e3-49dc-9476-ffd48c95cfc3  code=ohms-law-apply-vir
│   │   │   ├── Explain resistance factors  mc=feb58644-2072-49ad-83f3-b4a7453ca634  code=ohms-law-resistance-factors
│   │   │   └── Distinguish ohmic/non-ohmic mc=879aab8a-3bd3-4b9c-abfe-61c23e6292f4  code=ohms-law-ohmic-vs-nonohmic
│   │   └── Drift Velocity                  c=e8ad87ae-b886-4314-b8cb-aa6024104895  code=drift-velocity
│   ├── Resistance and Resistivity          t=22dfee57-f8c4-45fd-8290-bb1c3be6d3a4  code=resistance-resistivity
│   │   └── Factors Affecting Resistance    c=61e7ae09-2ca1-4b26-ba8c-fbc9d56b0f53  code=factors-affecting-resistance
│   └── Kirchhoff's Laws                    t=db865c3f-5956-4289-a337-0b2b841f2f99  code=kirchhoffs-laws
│       └── Kirchhoff's Current and Voltage Laws  c=1237625c-0742-436b-b970-de5279fbca74  code=kcl-kvl
└── Optics                              ch=b35e04b3-ab7b-4bb5-bfc4-ad7e914297c1  code=optics
    ├── Reflection and Mirrors              t=f563bd71-1d86-4f71-82b4-9545b83ed372  code=reflection-mirrors
    │   ├── Spherical Mirror Formula        c=a44cd8ef-9881-4812-9848-bac03dde7e61  code=mirror-formula
    │   └── Principal Focus of Spherical Mirror  c=9f91ab55-6fb7-41b9-beb3-60400693fe20  code=principal-focus-spherical-mirror
    ├── Refraction and Lenses               t=aebaf878-4048-451a-a585-0b5c9ed3c8bb  code=refraction-lenses
    │   ├── Thin Lens Formula               c=dea4d8e9-aa27-45e3-b142-04a1d1a6b98b  code=lens-formula
    │   ├── Refractive Index                c=537dff93-6e0a-4a5c-9a58-2ebac1b4eea8  code=refractive-index
    │   └── Lens Power and Focal Length     c=77aa17aa-8f6b-4604-bad0-691b1172e5e8  code=lens-power-focal-length
    └── Wave Optics Basics                  t=6d90e78c-715e-48cb-9997-aaaa6cfaae4c  code=wave-optics-basics
        └── Young's Double Slit             c=77964f04-bd90-4cef-9b64-4b810b01ae6d  code=interference-young
```

**Counts:** 8 chapters · topics only under Electrostatics / Current Electricity / Optics · micro-competencies only under Ohm’s Law (3).

**Evidence of intentional incompleteness:** `apps/backend/app/modules/academic/seed.py` states *“representative subset… One chapter per subject is fully fleshed… rest exist as chapters only”*; ADR-0012 confirms scoped-down hierarchy for v1.

**ADR-0031 registry:** only **one** Physics NCERT mapping approved — Class 12 Ch 3 → `current-electricity`. All other Physics PDFs remain unmapped by design.

---

## 4. NCERT → TALOS Crosswalk

Coverage: **FULL** / **PARTIAL** / **NONE**  
Decision: **EXISTING** / **EXTEND** / **CROSSWALK** / **SME REVIEW** / **NO SAFE MAPPING**

### 4.1 Class XI

| NCERT Class | NCERT Ch | NCERT Chapter | TALOS Chapter Candidate | TALOS Chapter ID | Coverage | Missing Topics | Missing Concepts | Decision |
| ----------- | -------: | ------------- | ----------------------- | ---------------- | -------- | -------------- | ---------------- | -------- |
| 11 | 1 | Units and Measurement | — | — | **NONE** | all (SI, significant figures, dimensions) | all | **EXTEND** |
| 11 | 2 | Motion in a Straight Line | Kinematics | `b20f8158-…` | **PARTIAL** | velocity, acceleration, kinematic equations, relative velocity as topics | all concepts | **EXTEND** (+ SME: whether to keep one `kinematics` vs split XI Ch2/Ch3) |
| 11 | 3 | Motion in a Plane | Kinematics | `b20f8158-…` | **PARTIAL** | vectors, projectile, UCM | all | **CROSSWALK** or **EXTEND** (split chapter) — **SME REVIEW** |
| 11 | 4 | Laws of Motion | Laws of Motion | `433d0aa4-…` | **PARTIAL** | Newton laws, friction, momentum, circular | all | **EXTEND** |
| 11 | 5 | Work, Energy and Power | Work, Energy and Power | `81f3a1f9-…` | **PARTIAL** | work, KE/PE, conservation, power, collisions | all | **EXTEND** |
| 11 | 6 | Systems of Particles and Rotational Motion | — | — | **NONE** | COM, torque, MOI, rolling | all | **EXTEND** |
| 11 | 7 | Gravitation | Gravitation | `d1f5f09d-…` | **PARTIAL** | (PDF missing locally; chapter stub only) | all | **EXTEND** (topics/concepts) · **SME REVIEW** vs PDF when restored |
| 11 | 8 | Mechanical Properties of Solids | — | — | **NONE** | stress–strain, elastic moduli | all | **EXTEND** |
| 11 | 9 | Mechanical Properties of Fluids | — | — | **NONE** | pressure, Bernoulli, viscosity, surface tension | all | **EXTEND** |
| 11 | 10 | Thermal Properties of Matter | — | — | **NONE** | (PDF absent) | all | **EXTEND** after PDF restore · **SME REVIEW** |
| 11 | 11 | Thermodynamics | Thermodynamics | `2f62c566-…` | **PARTIAL** | laws, processes, Carnot | all | **EXTEND** |
| 11 | 12 | Kinetic Theory | — | — | **NONE** | ideal gas KT, equipartition, mean free path | all | **EXTEND** (do **not** fold into Thermodynamics without SME) |
| 11 | 13 | Oscillations | — | — | **NONE** | SHM, pendulum | all | **EXTEND** |
| 11 | 14 | Waves | Optics? (wave optics only) | `b35e04b3-…` | **NONE** for mechanical waves | travelling waves, superposition, beats | mechanical-wave concepts | **EXTEND** (separate Waves chapter; do not overload Optics) |

### 4.2 Class XII Part 1

| NCERT Class | NCERT Ch | NCERT Chapter | TALOS Candidate | TALOS Chapter ID | Coverage | Missing Topics/Concepts | Decision |
| ----------- | -------: | ------------- | --------------- | ---------------- | -------- | ----------------------- | -------- |
| 12 | 1–2 | Electric Charges & Fields / Electrostatic Potential & Capacitance | Electrostatics | `ed3e1c7b-…` | **PARTIAL** | Gauss, dipole detail, dielectrics, capacitor combinations, energy | **EXTEND** under Electrostatics |
| 12 | 3 | Current Electricity | Current Electricity | `44e651c0-…` | **PARTIAL** (best-seeded) | cells, Wheatstone, power, temperature resistivity | **EXISTING** + **EXTEND** |
| 12 | 4 | Moving Charges and Magnetism | — | — | **NONE** | all | **EXTEND** |
| 12 | 5 | Magnetism and Matter | — | — | **NONE** | all | **EXTEND** |
| 12 | 6 | Electromagnetic Induction | — | — | **NONE** | all | **EXTEND** |
| 12 | 7 | Alternating Current | — | — | **NONE** | all | **EXTEND** |
| 12 | 8 | Electromagnetic Waves | — | — | **NONE** | all | **EXTEND** |

### 4.3 Coverage tally (Class XI chapters with PDF or known stub)

| Coverage | Count | Chapters |
|----------|------:|----------|
| FULL | **0** | — |
| PARTIAL | **6** | XI 2–5, 7, 11 (chapter stubs or merged kinematics) |
| NONE | **8** | XI 1, 6, 8, 9, 10, 12, 13, 14 |

(Class XII: 1 PARTIAL-best Current Electricity; Electrostatics PARTIAL; 5 NONE for magnetism/EM.)

---

## 5. Five Unresolved Legacy Chapters

### CH01 — Units and Measurement (legacy 500 Q)

1. **NCERT distinct chapter?** Yes — XI Ch 1 PDF title **UNITS AND MEASUREMENT**.  
2. **Major sections:** SI units, significant figures, dimensions, dimensional analysis.  
3. **TALOS equivalent chapter?** **No.**  
4. **Distributed elsewhere?** No Units topics/concepts under any TALOS chapter.  
5. **Forcing into existing chapters?** Distorts graph (stems in this legacy slice are mostly non-units content anyway — see §6).  
6. **Extend taxonomy?** **Yes** for curriculum/factory. **Does not** auto-resolve these 500 rows.

### CH06 — Systems of Particles and Rotational Motion (500 Q)

1. **NCERT distinct?** Yes — XI Ch 6 PDF.  
2. **Sections:** COM, torque, angular momentum, MOI, rotational kinematics/dynamics.  
3. **TALOS equivalent?** **No.**  
4. **Distributed?** No.  
5. **Force into Laws of Motion?** Distorts NCERT boundaries (friction/Atwood ≠ rotational chapter).  
6. **Extend?** **Yes** for curriculum. Legacy stems show **0** rotational content after title strip → extension alone insufficient for these rows.

### CH07 — Mechanical Properties of Solids (500 Q)

1. **NCERT distinct?** Yes — XI Ch **8** (legacy ID 7 ≠ NCERT number).  
2. **Sections:** stress–strain, elastic moduli.  
3. **TALOS equivalent?** **No.**  
4. **Distributed?** No.  
5. **Force elsewhere?** Unsafe.  
6. **Extend?** **Yes.** Only ~88/500 stems are Young-modulus–aligned; rest mislabeled.

### CH08 — Mechanical Properties of Fluids (500 Q)

1. **NCERT distinct?** Yes — XI Ch **9**.  
2. **Sections:** pressure, streamline, Bernoulli (in PDF), viscosity, surface tension.  
3. **TALOS equivalent?** **No.**  
4. **Distributed?** No.  
5. **Force?** Unsafe.  
6. **Extend?** **Yes.** Manometer-aligned subset small; most stems mislabeled.

### CH10 — Kinetic Theory (500 Q)

1. **NCERT distinct?** Yes — XI Ch **12** (not Ch 10).  
2. **Sections:** ideal-gas KT, equipartition, mean free path.  
3. **TALOS equivalent?** **No.** Do not equate with `thermodynamics-physics` without SME (NCERT separates Ch 11 vs 12).  
4. **Distributed?** Ideal-gas stems resemble thermo-adjacent content only.  
5. **Force into Thermodynamics?** Blurs NCERT chapter boundary; still leaves majority of 500 as kinematics/solids/work.  
6. **Extend?** **Yes** for curriculum. Legacy rows still need content remediation.

---

## 6. Existing 8-Chapter Analysis

| TALOS chapter | ID | Topics | Concepts | Micro-competencies | NCERT represented | Coverage | Obvious gaps |
|---------------|-----|--------|----------|--------------------|-------------------|----------|--------------|
| Kinematics | `b20f8158-…` | 0 | 0 | 0 | XI Ch 2 + possibly Ch 3 | PARTIAL name-only | No topics; merges two NCERT chapters |
| Laws of Motion | `433d0aa4-…` | 0 | 0 | 0 | XI Ch 4 | PARTIAL name-only | Empty tree |
| Work, Energy and Power | `81f3a1f9-…` | 0 | 0 | 0 | XI Ch 5 | PARTIAL name-only | Empty tree |
| Gravitation | `d1f5f09d-…` | 0 | 0 | 0 | XI Ch 7 (PDF missing locally) | PARTIAL name-only | Empty; PDF gap |
| Thermodynamics | `2f62c566-…` | 0 | 0 | 0 | XI Ch 11 | PARTIAL name-only | Empty; KT separate |
| Electrostatics | `ed3e1c7b-…` | 3 | 3 | 0 | XII Ch 1–2 (coarse) | PARTIAL | Missing Gauss, dielectrics depth, etc. |
| Current Electricity | `44e651c0-…` | 3 | 4 | 3 | XII Ch 3 | PARTIAL (deepest) | Cells, bridges, etc. |
| Optics | `b35e04b3-…` | 3 | 6 | 0 | XII Optics (Part 2 not in corpus) | PARTIAL | No mechanical Waves (XI Ch 14) |

### Structure diagnosis (evidence-based)

**B. Incomplete NCERT mapping** — primary.

Evidence:
- `seed.py` explicitly: “representative subset… not the full ~20 chapters”
- ADR-0012: scoped for first content pass
- ADR-0031: only Current Electricity pilot mapping approved
- 5/8 chapters are empty stubs; Class XI Units/Rotation/Solids/Fluids/KT/Oscillations/Waves absent

Not A (deliberately non-NCERT pedagogy) as primary: chapter **names** track NCERT/NEET titles where present.  
Not purely C (accidental): incompleteness is documented policy.  
**D** only for: whether `kinematics` should remain one chapter or split XI Ch2/Ch3; whether KT stays separate from Thermodynamics (NCERT says yes).

---

## 7. Taxonomy Gaps & Misplacement

| Issue | Evidence | Type |
|-------|----------|------|
| Missing NCERT chapters in TALOS | Units, Rotational, Solids, Fluids, KT, Oscillations, Waves, magnetism/EM set | **TALOS-TAXONOMY** |
| Chapter stubs without topics/concepts | kinematics, laws-of-motion, work-energy-power, gravitation, thermodynamics-physics | **TALOS-TAXONOMY** |
| `kinematics` merges two NCERT chapters | XI Ch 2 + Ch 3 both map to one code | **TALOS-TAXONOMY** (needs SME) |
| Optics ≠ Waves | XI Ch 14 mechanical waves have no home; Optics has wave-optics interference only | **TALOS-TAXONOMY** |
| Electrostatics collapses XII Ch 1–2 | Coarse relative to NCERT | **TALOS-TAXONOMY** (acceptable if topics expand) |
| Legacy chapter labels cosmetic | Same 8 algorithmic topics across all 10 legacy chapters; title parentheticals | **LEGACY-DATA** |
| Legacy ID ≠ NCERT chapter # | Solids=legacy7/NCERT8; Fluids=8/9; Thermo=9/11; KT=10/12 | **LEGACY-DATA** |
| Generic algorithmic topics used as if curriculum chapters | `Young modulus`, `kinematic equations`, etc. recycled under wrong chapter titles | **LEGACY-DATA** |
| Wrong to treat prior LOW/MEDIUM `talos_chapter:*` tags as concept authority | Same pollution on “resolved” chapters 2–5, 9 | **BOTH** |

**Both problems exist.** Fixing TALOS taxonomy is necessary for the factory. Fixing taxonomy does **not** repair the 5,000-row classification.

---

## 8. 5,000-Question Impact

Using import tags + prior content-fidelity audit (stem subject matter, not legacy chapter name):

| Classification | Questions |
| --------------------------------------- | --------: |
| Existing safe TALOS mapping (concept-ready) | **0** |
| Taxonomy extension potentially required (curriculum nodes for factory + Solids/Fluids content buckets) | **~579** stems need Solids/Fluids chapters; **entire Class XI/XII gap** blocks future NCERT MCQs |
| Cannot map until taxonomy **and** content-level remediation | **2500** unresolved by chapter label; practically **5000** need stem-based reclassification before `concept_id` |
| Other issue (legacy mislabel / cosmetic chapters) | **5000** |

### Can the 2,500 be solved by…?

| Approach | Sufficient alone? |
|----------|-------------------|
| Adding missing taxonomy nodes | **No** — labels ≠ content |
| Mapping individual questions to existing concepts | **No** — no concepts under mechanics/thermo stubs; Electrostatics/Optics/CE concepts wrong for these stems |
| Documented crosswalk (legacy_chapter → TALOS chapter) | **No** — crosswalk on false chapter identity would encode errors |
| Combination: taxonomy extension **+** stem-level reclassification **+** ECAEP | **Yes** (only path) |

---

## 9. Minimum Taxonomy Extension (PROPOSAL ONLY — DO NOT CREATE)

Avoid one-node-per-NCERT-heading. Target durable NEET/MCQ factory granularity.

### 9.1 Chapters to add (Class XI priority for unresolved set + completeness)

| Level | Proposed Name | Parent | NCERT Evidence | Required? | Confidence |
| ----- | ------------- | ------ | -------------- | --------- | ---------- |
| Chapter | Units and Measurement | PHYSICS | XI Ch 1 PDF | YES | HIGH |
| Chapter | Systems of Particles and Rotational Motion | PHYSICS | XI Ch 6 PDF | YES | HIGH |
| Chapter | Mechanical Properties of Solids | PHYSICS | XI Ch 8 PDF | YES | HIGH |
| Chapter | Mechanical Properties of Fluids | PHYSICS | XI Ch 9 PDF | YES | HIGH |
| Chapter | Kinetic Theory | PHYSICS | XI Ch 12 PDF | YES | HIGH |
| Chapter | Oscillations | PHYSICS | XI Ch 13 PDF | YES (factory) | HIGH |
| Chapter | Waves | PHYSICS | XI Ch 14 PDF | YES (factory) | HIGH |
| Chapter | Thermal Properties of Matter | PHYSICS | XI Ch 10 (PDF missing — restore first) | YES after PDF | MEDIUM |
| Chapter | Moving Charges and Magnetism | PHYSICS | XII Ch 4 PDF | YES (factory) | HIGH |
| Chapter | Magnetism and Matter | PHYSICS | XII Ch 5 | YES (scale) | HIGH |
| Chapter | Electromagnetic Induction | PHYSICS | XII Ch 6 | YES (scale) | HIGH |
| Chapter | Alternating Current | PHYSICS | XII Ch 7 | YES (scale) | HIGH |
| Chapter | Electromagnetic Waves | PHYSICS | XII Ch 8 | YES (scale) | HIGH |

Optional SME: split `kinematics` → “Motion in a Straight Line” + “Motion in a Plane” **or** keep one chapter with two topic trees.

### 9.2 Minimum topics/concepts for the five unresolved NCERT chapters

| Level | Proposed Name | Parent | NCERT Evidence | Required? | Confidence |
| ----- | ------------- | ------ | -------------- | --------- | ---------- |
| Topic | SI Units and Measurement | Units and Measurement | 1.2 | YES | HIGH |
| Topic | Significant Figures and Errors | Units and Measurement | 1.3 | YES | HIGH |
| Topic | Dimensions and Dimensional Analysis | Units and Measurement | 1.4–1.6 | YES | HIGH |
| Concept | SI Base Units | SI Units… | 1.2 | YES | HIGH |
| Concept | Significant Figures | Significant Figures… | 1.3 | YES | HIGH |
| Concept | Dimensional Formulae | Dimensions… | 1.4–1.5 | YES | HIGH |
| Topic | Centre of Mass | Rotational Motion | 6.2–6.3 | YES | HIGH |
| Topic | Torque and Angular Momentum | Rotational Motion | 6.7 | YES | HIGH |
| Topic | Moment of Inertia and Rotational Dynamics | Rotational Motion | 6.9–6.11 | YES | HIGH |
| Concept | Centre of Mass | Centre of Mass | 6.2 | YES | HIGH |
| Concept | Torque | Torque and Angular Momentum | 6.7 | YES | HIGH |
| Concept | Moment of Inertia | MOI topic | 6.9 | YES | HIGH |
| Topic | Stress and Strain | Solids | 8.2, 8.4 | YES | HIGH |
| Topic | Elastic Moduli | Solids | 8.5 | YES | HIGH |
| Concept | Young’s Modulus | Elastic Moduli | 8.5 | YES | HIGH |
| Concept | Stress–Strain Curve | Stress and Strain | 8.4 | YES | HIGH |
| Topic | Pressure in Fluids | Fluids | 9.2 | YES | HIGH |
| Topic | Bernoulli and Streamline Flow | Fluids | 9.3–9.4 | YES | HIGH |
| Topic | Viscosity and Surface Tension | Fluids | 9.5–9.6 | YES | HIGH |
| Concept | Hydrostatic Pressure / Manometer | Pressure | 9.2 | YES | HIGH |
| Concept | Bernoulli’s Principle | Bernoulli topic | 9.4 (PDF) | YES | HIGH |
| Topic | Kinetic Theory of Ideal Gas | Kinetic Theory | 12.4 | YES | HIGH |
| Topic | Equipartition and Mean Free Path | Kinetic Theory | 12.5, 12.7 | YES | HIGH |
| Concept | Ideal Gas from Kinetic Theory | KT of ideal gas | 12.4 | YES | HIGH |
| Concept | Mean Free Path | Equipartition topic | 12.7 | YES | HIGH |
| MicroCompetency | (defer until concept load > pilot) | — | ADR-0021 pattern | NO initially | — |

Also **EXTEND** empty stubs: add topic/concept trees under existing `kinematics`, `laws-of-motion`, `work-energy-power`, `thermodynamics-physics`, `gravitation` before assigning `concept_id` at scale.

**Do not** create micro-competencies for every concept at once — follow Current Electricity pilot pattern (few MCs under one concept).

---

## 10. Scalability Assessment

| Scale | Assessment |
|------:|------------|
| 10K–25K | Proposed chapter/topic/concept depth is sufficient if concepts stay NEET-skill sized |
| 100K–250K | Concepts may hold thousands of MCQs each — acceptable if mastery is concept-level and tags carry difficulty/PYQ metadata |
| 500K–1M | Risk of overcrowding on broad concepts (e.g. “Newton’s Laws”) — mitigate with micro-competencies **and** blueprint/family layers already in Content Factory (not by exploding chapter count) |

Answers:
- **Overcrowding?** Possible on broad concepts → use MicroCompetency selectively (ADR-0021).  
- **Incorrect shared concepts?** Risk if AI classifies by keyword only → require NCERT section provenance + ECAEP.  
- **AI classification?** Yes, against Chapter→Topic→Concept with NCERT PDF grounding (existing ingestion pattern).  
- **Student mastery?** Meaningful at Concept; Chapter too coarse; MicroCompetency for weak-skill drills.  
- **Weak-topic analysis?** Works if topics are stable NCERT-aligned (proposed).  
- **Bio/Chem same model?** Yes — already `Subject→Chapter→Topic→Concept→MC` (ADR-0012).  
- **JEE later?** Additive chapters/topics under PHYSICS; do not fork hierarchy — use exam weightage / tags (existing `exams` level).

**No schema redesign required.** Additive rows only.

---

## 11. Recommended Final Architecture

Keep:

`Exam → Subject → Chapter → Topic → Concept → MicroCompetency`

Physics target (additive):

1. **Complete Class XI chapter set** (add missing; flesh stubs).  
2. **Complete Class XII Part 1 chapter set** (add magnetism/EM).  
3. **Optics** remains; add Part 2 chapters when PDFs are registered.  
4. **SME decision:** keep or split `kinematics`; keep Kinetic Theory separate from Thermodynamics (NCERT-aligned default: **separate**).  
5. **Provenance:** continue ADR-0031 explicit NCERT PDF → chapter registry (expand mappings after nodes exist).  
6. **Legacy 5k:** never bulk-map by `legacy_chapter_id`; stem-level reclassify into the new graph under ECAEP.

Academic remains the stable foundation; CMS questions hang off `concept_id` only after nodes exist and classification is verified.

---

## 12. Decision for the 2,500 Unresolved Questions

### RED — SOURCE/CLASSIFICATION PROBLEM

Taxonomy extension is **necessary for TALOS** but **not sufficient** for these rows. Evidence: after stripping chapter titles, Units/Rotation/KT fidelity ≈ 0%; Solids/Fluids only partial; topics recycled across all chapters.

**Do not assign `concept_id`.**  
**Do not** create a legacy_chapter→TALOS_chapter crosswalk that treats chapter IDs as truth.

---

## 13. Recommendation

1. **Approve** minimum Physics taxonomy extension (Class XI missing chapters + topic/concept fill for stubs) as a **separate** change-controlled migration.  
2. **Restore** missing StudyMaterial PDFs (XI Ch 7, 10) before claiming FULL coverage.  
3. **Expand** ADR-0031 explicit mappings only after chapters exist.  
4. **Remediate** the 5,000 legacy bank with stem-based classification (or regenerate) before ECAEP publish.  
5. **Keep** all imported rows `DRAFT` / `concept_id NULL` until (4) completes.

---

## 14. Risks

| Risk | Impact |
|------|--------|
| Extending taxonomy then bulk-assigning by legacy chapter | Encodes wrong academic graph at scale |
| Folding Kinetic Theory into Thermodynamics | Breaks NCERT boundaries / mastery reports |
| Overloading Optics with XI Waves | Mis-teaches mechanical vs optical waves |
| Creating one concept per NCERT subsection | Unmaintainable at 1M MCQs |
| Leaving stubs empty while generating MCQs | `concept_id` NULL forever / publish blocked |

---

## 15. Required Approval

| Item | Approver |
|------|----------|
| Taxonomy extension scope (chapter list) | Academic / SME + Architecture |
| Split vs keep `kinematics` | SME |
| KT separate from Thermodynamics | SME (recommend separate) |
| Legacy 5k remediation program | Content + Product |
| Any future `concept_id` writes | ECAEP only |

**This audit creates no taxonomy and assigns no IDs.**

---

## 16. Database Safety Proof

| Check | Result |
|-------|--------|
| Database writes | **0** (SELECT + PDF read only) |
| Question modifications | **0** |
| `concept_id` assignments | **0** |
| Chapter/topic/concept INSERT | **0** |
| Publication changes | **0** |
| Source / NCERT PDF modifications | **0** |
| Artifact written | `docs/audits/TALOS_PHYSICS_TAXONOMY_GAP_ANALYSIS_20260902.md` only |

---

## Required executive verdict

```text
NCERT Physics chapters examined = 20
Current TALOS Physics chapters = 8
Full coverage = 0
Partial coverage = 6 (Class XI name-level stubs / coarse XII)
No safe coverage = 8 (Class XI chapters with PDF/known gap lacking TALOS chapter)
Legacy questions affected = 2500
Recommended action =
RED — SOURCE/CLASSIFICATION PROBLEM
Database writes = 0
Question modifications = 0
concept_id assignments = 0
Publication changes = 0
```

**Note:** Platform-level **GREEN — TAXONOMY EXTENSION** remains justified as a **separate** approved workstream for the NCERT knowledge graph and future MCQ factory. It must not be conflated with auto-resolving the 2,500 mislabeled legacy rows.
