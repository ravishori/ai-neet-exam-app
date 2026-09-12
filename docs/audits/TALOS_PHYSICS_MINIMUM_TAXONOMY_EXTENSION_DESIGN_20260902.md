# TALOS Physics — Minimum Taxonomy Extension Design

**Date:** 2026-09-02  
**Status:** DESIGN PROPOSAL ONLY — awaiting human/project approval  
**Evidence base:** `docs/audits/TALOS_PHYSICS_TAXONOMY_GAP_ANALYSIS_20260902.md`, NCERT PDFs under `StudyMaterial/Physics/`, live `academic.*` schema, `seed.py`, ADR-0012, ADR-0021, ADR-0031  

**Hard safety:** Database writes = **0**. No taxonomy or question mutations. No `concept_id` assignments. No publication.

---

## 1. Executive Summary

TALOS Physics today has **8 chapters**, of which **5 are empty stubs** and **3** (Electrostatics, Current Electricity, Optics) have partial topic/concept trees. Relative to the NCERT Class XI/XII baseline in StudyMaterial, this is an **incomplete seed**, not a finished curriculum graph (ADR-0012 / `seed.py`).

This design proposes the **smallest durable extension** that:

1. Respects **NCERT chapter boundaries** (Principle A).  
2. Adds **missing Class XI chapters** that have no TALOS node (including the five previously unresolved titles).  
3. **Fills empty Class XI stubs** already present (`kinematics`, `laws-of-motion`, `work-energy-power`, `gravitation`, `thermodynamics-physics`) with topic/concept trees — without renaming existing chapters.  
4. Schedules remaining Class XII magnetism/EM and XI Oscillations/Waves/Thermal as **P1**.  
5. Defers micro-competency proliferation to **P2** (ADR-0021: handful per concept, after concepts are in use).

**Out of scope for this design:** classifying or remediating the 5,000 legacy import rows. Prior audits established those chapter labels are unreliable; taxonomy extension does **not** auto-classify them.

**Recommended next step after this document:** `APPROVE DESIGN` (with SME confirmation on two named decisions in §14).

---

## 2. Current TALOS State

### 2.1 Schema constraints (code)

| Level | Table | Stable key | Name limit | Notes |
|-------|-------|------------|------------|-------|
| Subject | `academic.subjects` | `code` | — | PHYSICS exists |
| Chapter | `academic.chapters` | `code` String(80) | String(200) | Unique per subject by convention |
| Topic | `academic.topics` | `code` String(80) | String(200) | Under chapter |
| Concept | `academic.concepts` | `code` String(80) | String(200) | Optional `ncert_reference` String(300) |
| MicroCompetency | `academic.micro_competencies` | `code` String(80) | String(300) | Optional layer; ADR-0021 |

IDs are UUIDs generated at insert time. This design proposes **`code` values only** (kebab-case), matching `seed.py` / Batch A (`laws-of-motion`, `ohms-law-concept`).

### 2.2 Live Physics hierarchy (unchanged by this proposal)

```
PHYSICS [EXISTING]
├── Kinematics [EXISTING] — empty
├── Laws of Motion [EXISTING] — empty
├── Work, Energy and Power [EXISTING] — empty
├── Gravitation [EXISTING] — empty
├── Thermodynamics [EXISTING] — empty
├── Electrostatics [EXISTING] — partial topics/concepts
├── Current Electricity [EXISTING] — deepest tree + 3 micro-competencies
└── Optics [EXISTING] — partial topics/concepts
```

**Naming convention in use:** kebab-case codes; Title Case / NCERT-style display names; Physics thermo uses `thermodynamics-physics` to avoid Chemistry clash.

### 2.3 Explicit design choices that reuse existing nodes

| Question | Decision | Rationale |
|----------|----------|-----------|
| Split `kinematics` into NCERT Ch 2 + Ch 3 chapters? | **No** — keep one chapter; add **two topic trees** | Existing chapter must not be renamed/split without migration; Crosswalk documented |
| Fold Kinetic Theory into Thermodynamics? | **No** — separate chapter | NCERT XI Ch 11 vs Ch 12 are distinct PDFs |
| Put mechanical Waves under Optics? | **No** — separate `waves` chapter (P1) | Optics = optical; XI Ch 14 = mechanical waves |
| Duplicate Electrostatics for XII Ch 1–2? | **No** — extend existing Electrostatics (P1 topic depth) | REUSE EXISTING NODE |

---

## 3. NCERT Baseline

Authoritative sources: `StudyMaterial/Physics/Class 11-Physics/*.pdf` and `Class 12-Physics/*.pdf` (extracted in gap analysis). Titles below match those PDFs.

### Class XI (14)

| # | Title | PDF present? |
|--:|-------|--------------|
| 1 | Units and Measurement | Yes |
| 2 | Motion in a Straight Line | Yes |
| 3 | Motion in a Plane | Yes |
| 4 | Laws of Motion | Yes |
| 5 | Work, Energy and Power | Yes |
| 6 | Systems of Particles and Rotational Motion | Yes |
| 7 | Gravitation | **No** (TALOS stub name exists) |
| 8 | Mechanical Properties of Solids | Yes |
| 9 | Mechanical Properties of Fluids | Yes |
| 10 | Thermal Properties of Matter | **No** |
| 11 | Thermodynamics | Yes |
| 12 | Kinetic Theory | Yes |
| 13 | Oscillations | Yes |
| 14 | Waves | Yes |

### Class XII Part 1 (8) — present in corpus

Electric Charges and Fields; Electrostatic Potential and Capacitance; Current Electricity; Moving Charges and Magnetism; Magnetism and Matter; Electromagnetic Induction; Alternating Current; Electromagnetic Waves.

### Class XII Part 2

Optics / Dual Nature / Atoms / Nuclei / Semiconductor — **not in local StudyMaterial tree**. Optics chapter already exists in TALOS from prior seeding/Batch A. Part 2 chapter **additions** wait until PDFs are registered (P1/P2).

---

## 4. Taxonomy Gap

| NCERT Chapter | Existing TALOS Coverage | Missing Chapter? | Missing Topics | Missing Concepts | Recommended Action |
| ------------- | ----------------------- | ---------------- | -------------- | ---------------- | ------------------ |
| XI 1 Units and Measurement | None | YES | all | all | **PROPOSE NEW** chapter + tree (P0) |
| XI 2 Motion in a Straight Line | Kinematics (name only) | No | all under kinematics | all | **PROPOSE** topics/concepts under [EXISTING] (P0) |
| XI 3 Motion in a Plane | Kinematics (merged) | No | all | all | **PROPOSE** topics/concepts under [EXISTING] (P0); document CROSSWALK |
| XI 4 Laws of Motion | Chapter stub | No | all | all | **PROPOSE** topics/concepts (P0) |
| XI 5 Work, Energy and Power | Chapter stub | No | all | all | **PROPOSE** topics/concepts (P0) |
| XI 6 Rotational Motion | None | YES | all | all | **PROPOSE NEW** (P0) |
| XI 7 Gravitation | Chapter stub; PDF missing | No | all | all | **PROPOSE** topics/concepts (P0); restore PDF for Gate 2 |
| XI 8 Solids | None | YES | all | all | **PROPOSE NEW** (P0) |
| XI 9 Fluids | None | YES | all | all | **PROPOSE NEW** (P0) |
| XI 10 Thermal Properties | None; PDF missing | YES | all | all | **PROPOSE NEW** (P1) after PDF |
| XI 11 Thermodynamics | Chapter stub | No | all | all | **PROPOSE** topics/concepts (P0) |
| XI 12 Kinetic Theory | None | YES | all | all | **PROPOSE NEW** (P0) |
| XI 13 Oscillations | None | YES | all | all | **PROPOSE NEW** (P1) |
| XI 14 Waves | None (Optics ≠ Waves) | YES | all | all | **PROPOSE NEW** (P1) |
| XII 1–2 Electrostatics | Partial Electrostatics | No | Gauss, dielectrics depth, … | several | **EXTEND** existing (P1) |
| XII 3 Current Electricity | Partial (best) | No | cells, Wheatstone, … | several | **EXTEND** existing (P1) |
| XII 4–8 Magnetism / EM | None | YES ×5 | all | all | **PROPOSE NEW** chapters (P1) |
| XII Optics Part 2 | Optics partial | No | ray/wave depth | some exist | **EXTEND** when Part 2 PDFs available (P1/P2) |

---

## 5. Design Principles

| ID | Principle | Application here |
|----|-----------|------------------|
| A | NCERT alignment | New chapters match NCERT titles; KT ≠ Thermodynamics; Waves ≠ Optics |
| B | No cosmetic duplication | REUSE `kinematics`, `electrostatics`, `optics`, etc. |
| C | Concept-level usefulness | ~3–6 concepts per chapter in P0 — enough for MCQ/mastery, not one-per-subsection |
| D | Reusability | Designed for factory + NEET, not legacy `PHY11-*` labels |
| E | Stable codes | kebab-case ≤80 chars; no DB UUIDs invented in this doc |
| F | Additive only | Do not rename/delete existing nodes |
| G | MicroCompetency restraint | ADR-0021 — P2 only, 2–4 per heavily used concept |

---

## 6. Proposed Taxonomy

### 6.1 Complete proposed Physics tree

Nodes marked `[EXISTING]` or `[PROPOSED]`. Existing names/codes unchanged.

```
Physics [EXISTING] code=PHYSICS
│
├── Units and Measurement [PROPOSED] code=units-and-measurement                    ← P0 NEW CHAPTER
│   ├── SI Units and Measurement [PROPOSED] code=si-units-and-measurement
│   │   └── SI Base and Derived Units [PROPOSED] code=si-base-and-derived-units
│   ├── Significant Figures and Errors [PROPOSED] code=significant-figures-and-errors
│   │   └── Significant Figures [PROPOSED] code=significant-figures
│   └── Dimensions and Dimensional Analysis [PROPOSED] code=dimensions-and-dimensional-analysis
│       ├── Dimensional Formulae [PROPOSED] code=dimensional-formulae
│       └── Dimensional Analysis Applications [PROPOSED] code=dimensional-analysis-applications
│
├── Kinematics [EXISTING] code=kinematics
│   ├── Motion in a Straight Line [PROPOSED] code=motion-in-a-straight-line         ← NCERT XI Ch 2
│   │   ├── Instantaneous Velocity and Acceleration [PROPOSED] code=instantaneous-velocity-acceleration
│   │   ├── Kinematic Equations [PROPOSED] code=kinematic-equations
│   │   └── Relative Velocity in One Dimension [PROPOSED] code=relative-velocity-1d
│   └── Motion in a Plane [PROPOSED] code=motion-in-a-plane                         ← NCERT XI Ch 3
│       ├── Vectors in Plane Motion [PROPOSED] code=vectors-in-plane-motion
│       ├── Projectile Motion [PROPOSED] code=projectile-motion
│       └── Uniform Circular Motion [PROPOSED] code=uniform-circular-motion
│
├── Laws of Motion [EXISTING] code=laws-of-motion
│   ├── Newton’s Laws and Momentum [PROPOSED] code=newtons-laws-and-momentum
│   │   ├── Newton’s Laws of Motion [PROPOSED] code=newtons-laws
│   │   └── Conservation of Momentum [PROPOSED] code=conservation-of-momentum
│   ├── Friction and Common Forces [PROPOSED] code=friction-and-common-forces
│   │   └── Friction [PROPOSED] code=friction
│   └── Dynamics of Circular Motion [PROPOSED] code=dynamics-of-circular-motion
│       └── Dynamics of Uniform Circular Motion [PROPOSED] code=dynamics-uniform-circular-motion
│
├── Work, Energy and Power [EXISTING] code=work-energy-power
│   ├── Work and Kinetic Energy [PROPOSED] code=work-and-kinetic-energy
│   │   ├── Work by a Force [PROPOSED] code=work-by-a-force
│   │   └── Work–Energy Theorem [PROPOSED] code=work-energy-theorem
│   ├── Potential Energy and Conservation [PROPOSED] code=potential-energy-and-conservation
│   │   ├── Potential Energy [PROPOSED] code=potential-energy
│   │   └── Conservation of Mechanical Energy [PROPOSED] code=conservation-mechanical-energy
│   └── Power and Collisions [PROPOSED] code=power-and-collisions
│       ├── Power [PROPOSED] code=power
│       └── Collisions [PROPOSED] code=collisions
│
├── Systems of Particles and Rotational Motion [PROPOSED] code=systems-of-particles-rotational-motion  ← P0
│   ├── Centre of Mass [PROPOSED] code=centre-of-mass
│   │   ├── Centre of Mass of a System [PROPOSED] code=centre-of-mass-system
│   │   └── Motion of the Centre of Mass [PROPOSED] code=motion-of-centre-of-mass
│   ├── Torque and Angular Momentum [PROPOSED] code=torque-and-angular-momentum
│   │   ├── Torque [PROPOSED] code=torque
│   │   └── Angular Momentum [PROPOSED] code=angular-momentum
│   └── Moment of Inertia and Rotational Dynamics [PROPOSED] code=moment-of-inertia-rotational-dynamics
│       ├── Moment of Inertia [PROPOSED] code=moment-of-inertia
│       ├── Rotational Kinematics [PROPOSED] code=rotational-kinematics
│       └── Dynamics of Rotational Motion [PROPOSED] code=dynamics-of-rotational-motion
│
├── Gravitation [EXISTING] code=gravitation
│   ├── Newton’s Law of Gravitation [PROPOSED] code=newtons-law-of-gravitation
│   │   └── Universal Law of Gravitation [PROPOSED] code=universal-law-of-gravitation
│   └── Gravity, Potential and Satellites [PROPOSED] code=gravity-potential-satellites
│       ├── Acceleration due to Gravity [PROPOSED] code=acceleration-due-to-gravity
│       └── Orbital Motion of Satellites [PROPOSED] code=orbital-motion-satellites
│       └── (SME: refine when XI Ch 7 PDF restored)
│
├── Mechanical Properties of Solids [PROPOSED] code=mechanical-properties-of-solids   ← P0
│   ├── Stress and Strain [PROPOSED] code=stress-and-strain
│   │   ├── Stress and Strain [PROPOSED] code=stress-strain-definitions
│   │   └── Stress–Strain Curve [PROPOSED] code=stress-strain-curve
│   └── Elastic Moduli [PROPOSED] code=elastic-moduli
│       ├── Young’s Modulus [PROPOSED] code=youngs-modulus
│       ├── Shear Modulus [PROPOSED] code=shear-modulus
│       └── Bulk Modulus [PROPOSED] code=bulk-modulus
│
├── Mechanical Properties of Fluids [PROPOSED] code=mechanical-properties-of-fluids   ← P0
│   ├── Pressure in Fluids [PROPOSED] code=pressure-in-fluids
│   │   └── Hydrostatic Pressure and Pascal’s Law [PROPOSED] code=hydrostatic-pressure-pascal
│   ├── Fluid Flow and Bernoulli [PROPOSED] code=fluid-flow-and-bernoulli
│   │   ├── Streamline Flow [PROPOSED] code=streamline-flow
│   │   └── Bernoulli’s Principle [PROPOSED] code=bernoullis-principle
│   └── Viscosity and Surface Tension [PROPOSED] code=viscosity-and-surface-tension
│       ├── Viscosity [PROPOSED] code=viscosity
│       └── Surface Tension [PROPOSED] code=surface-tension
│
├── Thermal Properties of Matter [PROPOSED] code=thermal-properties-of-matter         ← P1 (after PDF)
│   └── (topics deferred to T2-B design pass with PDF TOC)
│
├── Thermodynamics [EXISTING] code=thermodynamics-physics
│   ├── Laws of Thermodynamics [PROPOSED] code=laws-of-thermodynamics
│   │   ├── Zeroth and First Law [PROPOSED] code=zeroth-and-first-law
│   │   └── Second Law and Carnot Engine [PROPOSED] code=second-law-and-carnot
│   ├── Heat, Work and Internal Energy [PROPOSED] code=heat-work-internal-energy
│   │   └── Heat Internal Energy and Work [PROPOSED] code=heat-internal-energy-work
│   └── Thermodynamic Processes [PROPOSED] code=thermodynamic-processes
│       └── Thermodynamic Processes [PROPOSED] code=thermodynamic-process-types
│
├── Kinetic Theory [PROPOSED] code=kinetic-theory                                   ← P0
│   ├── Kinetic Theory of an Ideal Gas [PROPOSED] code=kinetic-theory-ideal-gas
│   │   ├── Behaviour of Gases [PROPOSED] code=behaviour-of-gases
│   │   └── Kinetic Interpretation of Temperature [PROPOSED] code=kinetic-interpretation-temperature
│   └── Equipartition and Mean Free Path [PROPOSED] code=equipartition-and-mean-free-path
│       ├── Law of Equipartition of Energy [PROPOSED] code=law-of-equipartition
│       └── Mean Free Path [PROPOSED] code=mean-free-path
│
├── Oscillations [PROPOSED] code=oscillations                                       ← P1
│   ├── Simple Harmonic Motion [PROPOSED] code=simple-harmonic-motion
│   │   ├── SHM Kinematics [PROPOSED] code=shm-kinematics
│   │   └── Energy in SHM [PROPOSED] code=energy-in-shm
│   └── Simple Pendulum [PROPOSED] code=simple-pendulum
│       └── Simple Pendulum [PROPOSED] code=simple-pendulum-concept
│
├── Waves [PROPOSED] code=waves                                                     ← P1 (mechanical)
│   ├── Travelling Waves [PROPOSED] code=travelling-waves
│   │   ├── Transverse and Longitudinal Waves [PROPOSED] code=transverse-longitudinal-waves
│   │   └── Speed of a Travelling Wave [PROPOSED] code=speed-of-travelling-wave
│   └── Superposition and Beats [PROPOSED] code=superposition-and-beats
│       ├── Principle of Superposition [PROPOSED] code=principle-of-superposition
│       └── Beats [PROPOSED] code=beats
│
├── Electrostatics [EXISTING] code=electrostatics
│   ├── Electric Charge and Coulomb's Law [EXISTING]
│   │   └── Coulomb's Law [EXISTING]
│   ├── Electric Field and Potential [EXISTING]
│   │   └── Electric Field and Potential [EXISTING]
│   ├── Capacitance [EXISTING]
│   │   └── Parallel Plate Capacitor [EXISTING]
│   ├── Electric Field and Gauss’s Law [PROPOSED] code=electric-field-gauss           ← P1
│   │   ├── Electric Field [PROPOSED] code=electric-field
│   │   └── Gauss’s Law [PROPOSED] code=gausss-law
│   └── Dielectrics and Capacitor Combinations [PROPOSED] code=dielectrics-capacitor-combinations  ← P1
│       ├── Dielectrics and Polarisation [PROPOSED] code=dielectrics-polarisation
│       └── Combination of Capacitors [PROPOSED] code=combination-of-capacitors
│
├── Current Electricity [EXISTING] code=current-electricity
│   ├── … [EXISTING] ohms-law / resistance / kirchhoff trees …
│   ├── Cells and Instruments [PROPOSED] code=cells-and-instruments                   ← P1
│   │   ├── Cells Emf and Internal Resistance [PROPOSED] code=cells-emf-internal-resistance
│   │   └── Wheatstone Bridge [PROPOSED] code=wheatstone-bridge
│   └── (existing micro-competencies under Ohm’s Law remain [EXISTING])
│
├── Moving Charges and Magnetism [PROPOSED] code=moving-charges-and-magnetism         ← P1
│   ├── Magnetic Force and Motion [PROPOSED] code=magnetic-force-and-motion
│   │   └── Magnetic Force on a Moving Charge [PROPOSED] code=magnetic-force-moving-charge
│   ├── Magnetic Field due to Current [PROPOSED] code=magnetic-field-due-to-current
│   │   ├── Biot–Savart Law [PROPOSED] code=biot-savart-law
│   │   └── Ampere’s Circuital Law [PROPOSED] code=amperes-circuital-law
│   └── Current Loop and Galvanometer [PROPOSED] code=current-loop-galvanometer
│       └── Moving Coil Galvanometer [PROPOSED] code=moving-coil-galvanometer
│
├── Magnetism and Matter [PROPOSED] code=magnetism-and-matter                         ← P1
│   └── Magnetic Properties of Materials [PROPOSED] code=magnetic-properties-materials
│       └── Magnetic Properties of Materials [PROPOSED] code=magnetic-properties-concept
│
├── Electromagnetic Induction [PROPOSED] code=electromagnetic-induction               ← P1
│   ├── Faraday and Lenz [PROPOSED] code=faraday-and-lenz
│   │   ├── Faraday’s Law [PROPOSED] code=faradays-law
│   │   └── Lenz’s Law [PROPOSED] code=lenzs-law
│   └── Inductance and Generators [PROPOSED] code=inductance-and-generators
│       └── Inductance [PROPOSED] code=inductance
│
├── Alternating Current [PROPOSED] code=alternating-current                           ← P1
│   ├── AC Circuits [PROPOSED] code=ac-circuits
│   │   └── Series LCR Circuit [PROPOSED] code=series-lcr-circuit
│   └── Transformers [PROPOSED] code=transformers
│       └── Transformer [PROPOSED] code=transformer
│
├── Electromagnetic Waves [PROPOSED] code=electromagnetic-waves                       ← P1
│   └── EM Waves and Spectrum [PROPOSED] code=em-waves-and-spectrum
│       ├── Displacement Current [PROPOSED] code=displacement-current
│       └── Electromagnetic Spectrum [PROPOSED] code=electromagnetic-spectrum
│
└── Optics [EXISTING] code=optics
    ├── Reflection and Mirrors [EXISTING] … concepts [EXISTING]
    ├── Refraction and Lenses [EXISTING] … concepts [EXISTING]
    └── Wave Optics Basics [EXISTING]
        └── Young's Double Slit [EXISTING]
```

### 6.2 Five previously unresolved chapters (detail)

#### Units and Measurement (NCERT XI Ch 1 PDF)

| Level | Code | Name | NCERT evidence |
|-------|------|------|----------------|
| Chapter | `units-and-measurement` | Units and Measurement | Ch 1 title |
| Topic | `si-units-and-measurement` | SI Units and Measurement | §1.2 |
| Concept | `si-base-and-derived-units` | SI Base and Derived Units | §1.2 |
| Topic | `significant-figures-and-errors` | Significant Figures and Errors | §1.3 |
| Concept | `significant-figures` | Significant Figures | §1.3 |
| Topic | `dimensions-and-dimensional-analysis` | Dimensions and Dimensional Analysis | §1.4–1.6 |
| Concept | `dimensional-formulae` | Dimensional Formulae | §1.4–1.5 |
| Concept | `dimensional-analysis-applications` | Dimensional Analysis Applications | §1.6 |

**Not included:** standalone “least count instruments” concept (fold into significant figures / measurement practice via MC tags if needed).

#### Systems of Particles and Rotational Motion (NCERT XI Ch 6 PDF)

| Level | Code | Name | NCERT evidence |
|-------|------|------|----------------|
| Chapter | `systems-of-particles-rotational-motion` | Systems of Particles and Rotational Motion | Ch 6 title |
| Topic | `centre-of-mass` | Centre of Mass | §6.2–6.3 |
| Concept | `centre-of-mass-system` | Centre of Mass of a System | §6.2 |
| Concept | `motion-of-centre-of-mass` | Motion of the Centre of Mass | §6.3 |
| Topic | `torque-and-angular-momentum` | Torque and Angular Momentum | §6.7 |
| Concept | `torque` | Torque | §6.7 |
| Concept | `angular-momentum` | Angular Momentum | §6.7 |
| Topic | `moment-of-inertia-rotational-dynamics` | Moment of Inertia and Rotational Dynamics | §6.9–6.11 |
| Concept | `moment-of-inertia` | Moment of Inertia | §6.9 |
| Concept | `rotational-kinematics` | Rotational Kinematics | §6.10 |
| Concept | `dynamics-of-rotational-motion` | Dynamics of Rotational Motion | §6.11 |

**Not included as separate concepts:** vector product identity (§6.5) — treat as skill under torque/angular momentum; rigid-body equilibrium — under torque.

#### Mechanical Properties of Solids (NCERT XI Ch 8 PDF)

| Level | Code | Name | NCERT evidence |
|-------|------|------|----------------|
| Chapter | `mechanical-properties-of-solids` | Mechanical Properties of Solids | Ch 8 title |
| Topic | `stress-and-strain` | Stress and Strain | §8.2, 8.4 |
| Concept | `stress-strain-definitions` | Stress and Strain | §8.2 |
| Concept | `stress-strain-curve` | Stress–Strain Curve | §8.4 |
| Topic | `elastic-moduli` | Elastic Moduli | §8.5 |
| Concept | `youngs-modulus` | Young’s Modulus | §8.5 |
| Concept | `shear-modulus` | Shear Modulus | §8.5 |
| Concept | `bulk-modulus` | Bulk Modulus | §8.5 |

**Not included:** separate “applications of elasticity” concept — tag under moduli / curve.

#### Mechanical Properties of Fluids (NCERT XI Ch 9 PDF)

| Level | Code | Name | NCERT evidence |
|-------|------|------|----------------|
| Chapter | `mechanical-properties-of-fluids` | Mechanical Properties of Fluids | Ch 9 title |
| Topic | `pressure-in-fluids` | Pressure in Fluids | §9.2 |
| Concept | `hydrostatic-pressure-pascal` | Hydrostatic Pressure and Pascal’s Law | §9.2 |
| Topic | `fluid-flow-and-bernoulli` | Fluid Flow and Bernoulli | §9.3–9.4 (Bernoulli in PDF text) |
| Concept | `streamline-flow` | Streamline Flow | §9.3 |
| Concept | `bernoullis-principle` | Bernoulli’s Principle | §9.4 |
| Topic | `viscosity-and-surface-tension` | Viscosity and Surface Tension | §9.5–9.6 |
| Concept | `viscosity` | Viscosity | §9.5 |
| Concept | `surface-tension` | Surface Tension | §9.6 |

#### Kinetic Theory (NCERT XI Ch 12 PDF)

| Level | Code | Name | NCERT evidence |
|-------|------|------|----------------|
| Chapter | `kinetic-theory` | Kinetic Theory | Ch 12 title |
| Topic | `kinetic-theory-ideal-gas` | Kinetic Theory of an Ideal Gas | §12.3–12.4 |
| Concept | `behaviour-of-gases` | Behaviour of Gases | §12.3 |
| Concept | `kinetic-interpretation-temperature` | Kinetic Interpretation of Temperature | §12.4 |
| Topic | `equipartition-and-mean-free-path` | Equipartition and Mean Free Path | §12.5–12.7 |
| Concept | `law-of-equipartition` | Law of Equipartition of Energy | §12.5 |
| Concept | `mean-free-path` | Mean Free Path | §12.7 |

**Not included:** duplicate “specific heat from KT” as separate from equipartition — keep under equipartition / thermo chapter as appropriate.

---

## 7. Existing vs Proposed Nodes

| Action | Count (this design) |
|--------|--------------------:|
| REUSE EXISTING chapters | 8 |
| REUSE EXISTING topics/concepts (Electrostatics, CE, Optics) | 3 topics + 13 concepts + 3 MCs (unchanged) |
| PROPOSE new chapters | **13** (5 P0 + 8 P1) |
| PROPOSE new topics | **48** (see §13) |
| PROPOSE new concepts | **72** (see §13) |
| PROPOSE micro-competencies | **12** (P2 exemplars only — not required to unblock) |

No existing node is renamed or deleted.

---

## 8. Five Previously Unresolved Chapters

Covered in §6.2. Summary:

| NCERT | Proposed chapter code | Priority | Blocks factory without it? |
|-------|----------------------|----------|----------------------------|
| XI 1 | `units-and-measurement` | P0 | Yes |
| XI 6 | `systems-of-particles-rotational-motion` | P0 | Yes |
| XI 8 | `mechanical-properties-of-solids` | P0 | Yes |
| XI 9 | `mechanical-properties-of-fluids` | P0 | Yes |
| XI 12 | `kinetic-theory` | P0 | Yes |

---

## 9. Additional Required NCERT Coverage

| Bucket | Items | Priority |
|--------|-------|----------|
| **REQUIRED NOW (P0)** | 5 new XI chapters above + topic/concept fill for existing XI stubs (kinematics, laws, work, gravitation, thermodynamics) | T2-A |
| **REQUIRED LATER (P1)** | Oscillations; Waves; Thermal Properties (after PDF); XII Ch 4–8; Electrostatics/CE depth | T2-B |
| **NOT REQUIRED now** | Full textbook subsection trees; Part 2 Optics chapters until PDFs exist; mass micro-competency fabrication; algorithm-named topics from legacy bank | — |

---

## 10. Legacy 5,000 Impact

**Do not modify questions.** Estimates from prior fidelity audits:

| Category | Questions |
| ------------------------------------------------- | --------: |
| Already safely classified (`concept_id` ready) | **0** |
| Potentially classifiable **after** taxonomy extension **and** stem-level remediation | **~1,900–3,500** (content buckets that match future concepts: kinematics, friction, work, Young’s modulus, ideal gas/thermo, fluids manometer, etc.) |
| Still requiring legacy-data remediation (wrong/cosmetic chapter labels) | **5,000** |
| Cannot safely classify by legacy chapter label alone | **2,500** unresolved IDs; effectively **5,000** if labels are treated as truth |

**Creating these chapters does not validate the 2,500.** Classification remains a separate ECAEP/content program.

---

## 11. 1M-MCQ Scalability Assessment

| Concern | Assessment |
|---------|------------|
| AI classification | **PASS** — Chapter→Topic→Concept with NCERT `ncert_reference` on concepts matches existing ingestion/factory patterns |
| Deduplication | **PASS** — stem-hash within concept (existing Batch A pattern) scales; concepts must not be too broad |
| Difficulty | **PASS** — per-concept difficulty metadata already on `concepts.difficulty` + question body difficulty |
| Student mastery | **PASS** — concept-level mastery (ADR-0015); optional MC rollup (ADR-0021) |
| Analytics (weak chapter/topic/concept) | **PASS** — hierarchy depth supports all three rollups |
| Generation against concept | **PASS** if prompts bind `concept_id` + NCERT excerpt (existing factory) |
| Cross-subject consistency | **PASS** — same Subject→…→Concept model already used for Chem/Botany/Zoology |
| Overcrowding at 1M | **REVIEW** — broad concepts (e.g. Newton’s Laws) may hold large volumes → mitigate with **P2 micro-competencies** and Content Factory blueprints, not endless chapters |
| JEE later | **PASS** — additive chapters/topics; exam weights via existing `neet_weightage_percent` / exams layer |

**Overall:** `PASS` with `REVIEW` on micro-competency timing at >100k/concept.

---

## 12. Implementation Batches (NOT IMPLEMENTED)

### Batch T2-A — Unblock Class XI Physics classification foundation

| Metric | Estimate |
|--------|----------:|
| New chapters | **5** |
| New topics | **26** (13 under new chapters + 13 under existing XI stubs) |
| New concepts | **46** (22 under new + 24 under stubs) |
| New micro-competencies | **0** |
| Dependencies | SME Gate 1–3; restore Gravitation PDF preferred for Gate 2; seed/registry update design |
| Risks | Over-mapping legacy questions; Gravitation concepts without PDF verification |

### Batch T2-B — Remaining NCERT Physics

| Metric | Estimate |
|--------|----------:|
| New chapters | **8** (Oscillations, Waves, Thermal, Moving Charges, Magnetism & Matter, EMI, AC, EM Waves) |
| New topics | **~18** |
| New concepts | **~22** |
| Plus | Electrostatics/CE topic extensions (~4 topics, ~6 concepts) |
| Dependencies | T2-A live; Thermal PDF restored; ADR-0031 mapping entries |
| Risks | Optics vs Waves confusion if codes/names collide — use `waves` vs `optics` |

### Batch T2-C — Micro-competency refinement

| Metric | Estimate |
|--------|----------:|
| Chapters | 0 |
| Topics | 0 |
| Concepts | 0 |
| Micro-competencies | **12–24** (2–3 under highest-volume P0 concepts only) |
| Dependencies | Real MCQ volume under concepts; learning mastery telemetry |
| Risks | ADR-0021 anti-pattern (~21k fabrication) |

---

## 13. Formal Proposal Matrix (summary)

Priority: **P0** core / **P1** full NCERT / **P2** enhancement.

| Level | ID Proposal (`code`) | Name | Parent | Status | NCERT Evidence | Existing Equivalent | Rationale | Priority |
| ----- | -------------------- | ---- | ------ | ------ | -------------- | ------------------- | --------- | -------- |
| Chapter | `units-and-measurement` | Units and Measurement | PHYSICS | PROPOSED | XI Ch 1 PDF | none | Missing chapter | P0 |
| Topic | `si-units-and-measurement` | SI Units and Measurement | units-and-measurement | PROPOSED | §1.2 | none | Core topic | P0 |
| Concept | `si-base-and-derived-units` | SI Base and Derived Units | si-units… | PROPOSED | §1.2 | none | MCQ/mastery unit | P0 |
| Topic | `significant-figures-and-errors` | Significant Figures and Errors | units-and-measurement | PROPOSED | §1.3 | none | Core topic | P0 |
| Concept | `significant-figures` | Significant Figures | significant-figures… | PROPOSED | §1.3 | none | MCQ unit | P0 |
| Topic | `dimensions-and-dimensional-analysis` | Dimensions and Dimensional Analysis | units-and-measurement | PROPOSED | §1.4–1.6 | none | Core topic | P0 |
| Concept | `dimensional-formulae` | Dimensional Formulae | dimensions… | PROPOSED | §1.4–1.5 | none | MCQ unit | P0 |
| Concept | `dimensional-analysis-applications` | Dimensional Analysis Applications | dimensions… | PROPOSED | §1.6 | none | MCQ unit | P0 |
| Chapter | `systems-of-particles-rotational-motion` | Systems of Particles and Rotational Motion | PHYSICS | PROPOSED | XI Ch 6 PDF | none | Missing chapter | P0 |
| Topic | `centre-of-mass` | Centre of Mass | systems… | PROPOSED | §6.2–6.3 | none | Core | P0 |
| Concept | `centre-of-mass-system` | Centre of Mass of a System | centre-of-mass | PROPOSED | §6.2 | none | Core | P0 |
| Concept | `motion-of-centre-of-mass` | Motion of the Centre of Mass | centre-of-mass | PROPOSED | §6.3 | none | Core | P0 |
| Topic | `torque-and-angular-momentum` | Torque and Angular Momentum | systems… | PROPOSED | §6.7 | none | Core | P0 |
| Concept | `torque` | Torque | torque… | PROPOSED | §6.7 | none | Core | P0 |
| Concept | `angular-momentum` | Angular Momentum | torque… | PROPOSED | §6.7 | none | Core | P0 |
| Topic | `moment-of-inertia-rotational-dynamics` | Moment of Inertia and Rotational Dynamics | systems… | PROPOSED | §6.9–6.11 | none | Core | P0 |
| Concept | `moment-of-inertia` | Moment of Inertia | MOI topic | PROPOSED | §6.9 | none | Core | P0 |
| Concept | `rotational-kinematics` | Rotational Kinematics | MOI topic | PROPOSED | §6.10 | none | Core | P0 |
| Concept | `dynamics-of-rotational-motion` | Dynamics of Rotational Motion | MOI topic | PROPOSED | §6.11 | none | Core | P0 |
| Chapter | `mechanical-properties-of-solids` | Mechanical Properties of Solids | PHYSICS | PROPOSED | XI Ch 8 PDF | none | Missing | P0 |
| Topic | `stress-and-strain` | Stress and Strain | solids | PROPOSED | §8.2, 8.4 | none | Core | P0 |
| Concept | `stress-strain-definitions` | Stress and Strain | stress-and-strain | PROPOSED | §8.2 | none | Core | P0 |
| Concept | `stress-strain-curve` | Stress–Strain Curve | stress-and-strain | PROPOSED | §8.4 | none | Core | P0 |
| Topic | `elastic-moduli` | Elastic Moduli | solids | PROPOSED | §8.5 | none | Core | P0 |
| Concept | `youngs-modulus` | Young’s Modulus | elastic-moduli | PROPOSED | §8.5 | none | High NEET frequency | P0 |
| Concept | `shear-modulus` | Shear Modulus | elastic-moduli | PROPOSED | §8.5 | none | Distinct mastery | P0 |
| Concept | `bulk-modulus` | Bulk Modulus | elastic-moduli | PROPOSED | §8.5 | none | Distinct mastery | P0 |
| Chapter | `mechanical-properties-of-fluids` | Mechanical Properties of Fluids | PHYSICS | PROPOSED | XI Ch 9 PDF | none | Missing | P0 |
| Topic | `pressure-in-fluids` | Pressure in Fluids | fluids | PROPOSED | §9.2 | none | Core | P0 |
| Concept | `hydrostatic-pressure-pascal` | Hydrostatic Pressure and Pascal’s Law | pressure… | PROPOSED | §9.2 | none | Core | P0 |
| Topic | `fluid-flow-and-bernoulli` | Fluid Flow and Bernoulli | fluids | PROPOSED | §9.3–9.4 | none | Core | P0 |
| Concept | `streamline-flow` | Streamline Flow | fluid-flow… | PROPOSED | §9.3 | none | Core | P0 |
| Concept | `bernoullis-principle` | Bernoulli’s Principle | fluid-flow… | PROPOSED | §9.4 PDF | none | Core | P0 |
| Topic | `viscosity-and-surface-tension` | Viscosity and Surface Tension | fluids | PROPOSED | §9.5–9.6 | none | Core | P0 |
| Concept | `viscosity` | Viscosity | viscosity… | PROPOSED | §9.5 | none | Core | P0 |
| Concept | `surface-tension` | Surface Tension | viscosity… | PROPOSED | §9.6 | none | Core | P0 |
| Chapter | `kinetic-theory` | Kinetic Theory | PHYSICS | PROPOSED | XI Ch 12 PDF | none (≠ thermo) | Missing; keep separate | P0 |
| Topic | `kinetic-theory-ideal-gas` | Kinetic Theory of an Ideal Gas | kinetic-theory | PROPOSED | §12.3–12.4 | none | Core | P0 |
| Concept | `behaviour-of-gases` | Behaviour of Gases | KT ideal gas | PROPOSED | §12.3 | none | Core | P0 |
| Concept | `kinetic-interpretation-temperature` | Kinetic Interpretation of Temperature | KT ideal gas | PROPOSED | §12.4 | none | Core | P0 |
| Topic | `equipartition-and-mean-free-path` | Equipartition and Mean Free Path | kinetic-theory | PROPOSED | §12.5, 12.7 | none | Core | P0 |
| Concept | `law-of-equipartition` | Law of Equipartition of Energy | equipartition… | PROPOSED | §12.5 | none | Core | P0 |
| Concept | `mean-free-path` | Mean Free Path | equipartition… | PROPOSED | §12.7 | none | Core | P0 |
| Topic | `motion-in-a-straight-line` | Motion in a Straight Line | **kinematics [EXISTING]** | PROPOSED | XI Ch 2 | kinematics chapter | Fill stub | P0 |
| Topic | `motion-in-a-plane` | Motion in a Plane | **kinematics [EXISTING]** | PROPOSED | XI Ch 3 | kinematics chapter | CROSSWALK keep one chapter | P0 |
| Chapter | `oscillations` | Oscillations | PHYSICS | PROPOSED | XI Ch 13 | none | Completeness | P1 |
| Chapter | `waves` | Waves | PHYSICS | PROPOSED | XI Ch 14 | none (≠ optics) | Completeness | P1 |
| Chapter | `thermal-properties-of-matter` | Thermal Properties of Matter | PHYSICS | PROPOSED | XI Ch 10 (PDF missing) | none | After PDF | P1 |
| Chapter | `moving-charges-and-magnetism` | Moving Charges and Magnetism | PHYSICS | PROPOSED | XII Ch 4 | none | Completeness | P1 |
| Chapter | `magnetism-and-matter` | Magnetism and Matter | PHYSICS | PROPOSED | XII Ch 5 | none | Completeness | P1 |
| Chapter | `electromagnetic-induction` | Electromagnetic Induction | PHYSICS | PROPOSED | XII Ch 6 | none | Completeness | P1 |
| Chapter | `alternating-current` | Alternating Current | PHYSICS | PROPOSED | XII Ch 7 | none | Completeness | P1 |
| Chapter | `electromagnetic-waves` | Electromagnetic Waves | PHYSICS | PROPOSED | XII Ch 8 | none | Completeness | P1 |
| MicroCompetency | `youngs-modulus-compute-from-stress-strain` | Compute Young’s modulus from stress and strain | youngs-modulus | PROPOSED | §8.5 | none | Exemplar only | P2 |
| MicroCompetency | `bernoulli-apply-to-flow` | Apply Bernoulli’s equation to streamline flow | bernoullis-principle | PROPOSED | §9.4 | none | Exemplar only | P2 |

*(Full P0 stub fill concepts for laws/work/gravitation/thermo listed in §6.1 tree — all Priority P0.)*

### Node count rollup

| Priority | Chapters | Topics | Concepts | MicroCompetencies | Total nodes |
|----------|--------:|-------:|---------:|------------------:|------------:|
| P0 | 5 new + 0 rename | 26 | 46 | 0 | **77** |
| P1 | 8 | ~18 | ~22 (+~6 CE/ES extend) | 0 | **~54** |
| P2 | 0 | 0 | 0 | 12 (exemplars) | **12** |

---

## 14. Approval Gates

| Gate | Name | Exit criteria | Blocks |
|------|------|---------------|--------|
| **1** | Taxonomy design approved | This document accepted; SME signs two decisions below | Implementation |
| **2** | NCERT alignment verified | Spot-check proposed codes vs PDF TOC; Gravitation/Thermal PDF restore plan | Seed write |
| **3** | Duplicate/overlap audit passed | No code collision with existing `academic.*`; Waves ≠ Optics; KT ≠ Thermo | Seed write |
| **4** | Database implementation approved | Explicit change ticket; migration/seed PR; **no question updates** | Runtime use |
| **5** | Post-implementation validation | SELECT counts; ADR-0031 mappings added only for new chapters; zero question `concept_id` churn unless separate ECAEP ticket | Factory use |

**SME decisions required at Gate 1:**

1. Keep single `kinematics` chapter with two topic trees (recommended) **vs** future split.  
2. Keep `kinetic-theory` separate from `thermodynamics-physics` (recommended).

**No database implementation before Gate 4.**

---

## 15. Risks

| Risk | Mitigation |
|------|------------|
| Implementing taxonomy then bulk-assigning legacy `PHY11-*` by chapter | Forbidden; separate RED remediation |
| Creating textbook-scale trees | Caps in this design (~3–6 concepts/chapter P0) |
| Code collision (`waves` vs wave-optics) | Distinct chapter `waves`; Optics topics stay under `optics` |
| Gravitation concepts without PDF | Gate 2; mark Gravitation concepts provisional until PDF restored |
| Chemistry `thermodynamics` clash | Already using `thermodynamics-physics` — keep |
| Scope creep into Part 2 Optics chapters | P1/P2 only after StudyMaterial registration |

---

## 16. Database Safety Proof

| Check | Result |
|-------|--------|
| Database writes | **0** |
| Existing taxonomy modified | **0** |
| Questions modified | **0** |
| `concept_id` assignments | **0** |
| Publication changes | **0** |
| Source / NCERT PDF modifications | **0** |
| Artifact | This markdown file only |

---

## 17. Final Verdict

```text
TALOS PHYSICS MINIMUM TAXONOMY EXTENSION
=========================================
Database writes                  = 0
Existing taxonomy modified       = 0
Questions modified               = 0
concept_id assignments           = 0
Publication changes              = 0

Proposed new chapters            = 13
Proposed new topics              = 48
Proposed new concepts            = 72
Proposed micro-competencies      = 12

P0 taxonomy nodes                = 77
P1 taxonomy nodes                = 54
P2 taxonomy nodes                = 12

NCERT alignment status           = SME REVIEW
Duplicate taxonomy risk          = LOW
1M-MCQ scalability               = PASS

Recommended next step:
APPROVE DESIGN
```

**Notes on the verdict line items**

- **SME REVIEW** (not FAIL): alignment is evidence-backed from NCERT PDFs, but Gate 1 requires explicit SME sign-off on kinematics merge and KT separation.  
- **APPROVE DESIGN**: proceed to Gate 1 human approval; **do not** implement until Gate 4.  
- Legacy 5,000 remediation remains a **separate** workstream and is not unblocked by approval of this design alone.
