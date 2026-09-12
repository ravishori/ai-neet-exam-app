# TALOS Physics P0 — Gate-4 Final Design Reconciliation

**Date:** 2026-09-02  
**Mode:** READ-ONLY final reconciliation (no implementation)  
**Supersedes for implementation inventory:** rollup counts in `TALOS_PHYSICS_MINIMUM_TAXONOMY_EXTENSION_DESIGN_20260902.md` §12–§13  
**Prior review:** `TALOS_PHYSICS_P0_PREIMPLEMENTATION_REVIEW_20260902.md` (AMBER)

---

## 1. Executive Verdict

```text
GREEN — READY FOR P0 IMPLEMENTATION
```

**Conditional implementation scope (mandatory):**

| Scope | Nodes | Rule |
|-------|------:|------|
| **Authoritative P0 design inventory** | **79** | 5 chapters + 26 topics + 48 concepts + 0 micro-competencies |
| **Gate-4 implementable (NCERT-verified)** | **74** | Exclude Gravitation topic/concept fill (5 nodes) until XI Ch 7 PDF is restored |
| **Existing `gravitation` chapter** | — | Remains in DB as empty stub; **do not** invent topic/concept fill without PDF |

All prior AMBER items are resolved in this document as the **authoritative Gate-4 design contract**. The earlier design markdown is **not silently rewritten**; where it conflicts on counts or Solids display naming, **this report wins**.

---

## 2. Scope and Read-Only Safety

| Allowed | Performed |
|---------|-----------|
| Inspect design/audit markdown | Yes |
| Inspect NCERT PDFs / StudyMaterial listing | Yes |
| Inspect schema/models/seed/ADRs | Yes |
| Read-only SQL | Yes |
| Write taxonomy / questions / migrations / seeds | **No** |
| Assign `concept_id` | **No** |

---

## 3. Source Documents Inspected

1. `docs/audits/TALOS_PHYSICS_MINIMUM_TAXONOMY_EXTENSION_DESIGN_20260902.md`  
2. `docs/audits/TALOS_PHYSICS_P0_PREIMPLEMENTATION_REVIEW_20260902.md`  
3. `docs/audits/TALOS_PHYSICS_TAXONOMY_GAP_ANALYSIS_20260902.md`  
4. `apps/backend/app/modules/academic/seed.py`, models, ADR-0012 / ADR-0021 / ADR-0031  
5. `StudyMaterial/Physics/Class 11-Physics/*.pdf` (listing + prior PDF TOC extractions)  
6. Live `academic.chapters` / CMS legacy batch via SELECT-only  

**Confirmed:** `ncert-books-class-11-physics-chapter-7.pdf` is **absent** from StudyMaterial.

---

## 4. Previous AMBER Findings

| # | Finding | Gate-4 resolution |
|---|---------|-------------------|
| 1 | Count 77 vs 79 | Authoritative = **79**; see §6 |
| 2 | Kinematics Option A + contract | Finalized Option A; contract in §7 |
| 3 | Gravitation provisional / PDF missing | **Defer fill** from implementable P0; §8 |
| 4 | Solids display-name collision | Concept display renamed in §9 |
| 5 | Legacy 2,500 must stay NULL | Reconfirmed; §10 |

---

## 5. P0 Inventory Reconstruction

IDs below are **proposed `code` values** (kebab-case). UUIDs are assigned only at insert time by the ORM — none invented here.

### 5.1 New chapters (PROPOSED) — 5

| Chapter code | Chapter name | NCERT | Evidence | Status |
|--------------|--------------|-------|----------|--------|
| `units-and-measurement` | Units and Measurement | XI Ch 1 | PDF `…chapter-1.pdf` | NCERT VERIFIED |
| `systems-of-particles-rotational-motion` | Systems of Particles and Rotational Motion | XI Ch 6 | PDF `…chapter-6.pdf` | NCERT VERIFIED |
| `mechanical-properties-of-solids` | Mechanical Properties of Solids | XI Ch 8 | PDF `…chapter-8.pdf` | NCERT VERIFIED |
| `mechanical-properties-of-fluids` | Mechanical Properties of Fluids | XI Ch 9 | PDF `…chapter-9.pdf` | NCERT VERIFIED |
| `kinetic-theory` | Kinetic Theory | XI Ch 12 | PDF `…chapter-12.pdf` | NCERT VERIFIED |

### 5.2 Topics + concepts under new chapters

#### Units and Measurement — 3 topics, 4 concepts

| Topic code | Topic name | Concept code | Concept name | NCERT | Label |
|------------|------------|--------------|--------------|-------|-------|
| `si-units-and-measurement` | SI Units and Measurement | `si-base-and-derived-units` | SI Base and Derived Units | 1.2 | NCERT VERIFIED |
| `significant-figures-and-errors` | Significant Figures and Errors | `significant-figures` | Significant Figures | 1.3 | NCERT VERIFIED |
| `dimensions-and-dimensional-analysis` | Dimensions and Dimensional Analysis | `dimensional-formulae` | Dimensional Formulae | 1.4–1.5 | NCERT VERIFIED |
| *(same topic)* | | `dimensional-analysis-applications` | Dimensional Analysis Applications | 1.6 | NCERT VERIFIED |

#### Systems of Particles and Rotational Motion — 3 topics, 7 concepts

| Topic code | Concept code | Concept name | NCERT | Label |
|------------|--------------|--------------|-------|-------|
| `centre-of-mass` | `centre-of-mass-system` | Centre of Mass of a System | 6.2 | NCERT VERIFIED |
| `centre-of-mass` | `motion-of-centre-of-mass` | Motion of the Centre of Mass | 6.3 | NCERT VERIFIED |
| `torque-and-angular-momentum` | `torque` | Torque | 6.7 | NCERT VERIFIED |
| `torque-and-angular-momentum` | `angular-momentum` | Angular Momentum | 6.7 | NCERT VERIFIED |
| `moment-of-inertia-rotational-dynamics` | `moment-of-inertia` | Moment of Inertia | 6.9 | NCERT VERIFIED |
| `moment-of-inertia-rotational-dynamics` | `rotational-kinematics` | Rotational Kinematics | 6.10 | NCERT VERIFIED |
| `moment-of-inertia-rotational-dynamics` | `dynamics-of-rotational-motion` | Dynamics of Rotational Motion | 6.11 | NCERT VERIFIED |

#### Mechanical Properties of Solids — 2 topics, 5 concepts

| Topic code | Concept code | Concept **display** name (Gate-4) | NCERT | Label |
|------------|--------------|-----------------------------------|-------|-------|
| `stress-and-strain` | `stress-strain-definitions` | **Definitions of Stress and Strain** | 8.2 | NCERT VERIFIED |
| `stress-and-strain` | `stress-strain-curve` | Stress–Strain Curve | 8.4 | NCERT VERIFIED |
| `elastic-moduli` | `youngs-modulus` | Young’s Modulus | 8.5 | NCERT VERIFIED |
| `elastic-moduli` | `shear-modulus` | Shear Modulus | 8.5 | NCERT VERIFIED |
| `elastic-moduli` | `bulk-modulus` | Bulk Modulus | 8.5 | NCERT VERIFIED |

#### Mechanical Properties of Fluids — 3 topics, 5 concepts

| Topic code | Concept code | Concept name | NCERT | Label |
|------------|--------------|--------------|-------|-------|
| `pressure-in-fluids` | `hydrostatic-pressure-pascal` | Hydrostatic Pressure and Pascal’s Law | 9.2 | NCERT VERIFIED |
| `fluid-flow-and-bernoulli` | `streamline-flow` | Streamline Flow | 9.3 | NCERT VERIFIED |
| `fluid-flow-and-bernoulli` | `bernoullis-principle` | Bernoulli’s Principle | 9.4 | NCERT VERIFIED |
| `viscosity-and-surface-tension` | `viscosity` | Viscosity | 9.5 | NCERT VERIFIED |
| `viscosity-and-surface-tension` | `surface-tension` | Surface Tension | 9.6 | NCERT VERIFIED |

#### Kinetic Theory — 2 topics, 4 concepts

| Topic code | Concept code | Concept name | NCERT | Label |
|------------|--------------|--------------|-------|-------|
| `kinetic-theory-ideal-gas` | `behaviour-of-gases` | Behaviour of Gases | 12.3 | NCERT VERIFIED |
| `kinetic-theory-ideal-gas` | `kinetic-interpretation-temperature` | Kinetic Interpretation of Temperature | 12.4 | NCERT VERIFIED |
| `equipartition-and-mean-free-path` | `law-of-equipartition` | Law of Equipartition of Energy | 12.5 | NCERT VERIFIED |
| `equipartition-and-mean-free-path` | `mean-free-path` | Mean Free Path | 12.7 | NCERT VERIFIED |

**New-chapter subtotal:** 5 chapters + 13 topics + 25 concepts = **43**

### 5.3 Fills under existing chapters

#### Kinematics `[EXISTING]` — 2 topics, 6 concepts

| Topic code | Maps to NCERT | Concept codes |
|------------|---------------|---------------|
| `motion-in-a-straight-line` | XI Ch 2 | `instantaneous-velocity-acceleration`, `kinematic-equations`, `relative-velocity-1d` |
| `motion-in-a-plane` | XI Ch 3 | `vectors-in-plane-motion`, `projectile-motion`, `uniform-circular-motion` |

Label: **NCERT VERIFIED** (PDFs chapter-2, chapter-3) · **SOURCE-SUPPORTED DECOMPOSITION** into concepts.

#### Laws of Motion `[EXISTING]` — 3 topics, 4 concepts

| Topic | Concepts | NCERT |
|-------|----------|-------|
| `newtons-laws-and-momentum` | `newtons-laws`, `conservation-of-momentum` | Ch 4 |
| `friction-and-common-forces` | `friction` | 4.9 |
| `dynamics-of-circular-motion` | `dynamics-uniform-circular-motion` | 4.10 |

#### Work, Energy and Power `[EXISTING]` — 3 topics, 6 concepts

| Topic | Concepts | NCERT |
|-------|----------|-------|
| `work-and-kinetic-energy` | `work-by-a-force`, `work-energy-theorem` | 5.3, 5.6 |
| `potential-energy-and-conservation` | `potential-energy`, `conservation-mechanical-energy` | 5.7–5.8 |
| `power-and-collisions` | `power`, `collisions` | 5.10–5.11 |

#### Gravitation `[EXISTING]` — 2 topics, 3 concepts — **NOT implementable without PDF**

| Topic code | Concept codes | Status |
|------------|---------------|--------|
| `newtons-law-of-gravitation` | `universal-law-of-gravitation` | **PROVISIONAL — SOURCE VERIFICATION PENDING** |
| `gravity-potential-satellites` | `acceleration-due-to-gravity`, `orbital-motion-satellites` | **PROVISIONAL — SOURCE VERIFICATION PENDING** |

#### Thermodynamics `[EXISTING]` `thermodynamics-physics` — 3 topics, 4 concepts

| Topic | Concepts | NCERT |
|-------|----------|-------|
| `laws-of-thermodynamics` | `zeroth-and-first-law`, `second-law-and-carnot` | 11.3–11.5, 11.9–11.11 |
| `heat-work-internal-energy` | `heat-internal-energy-work` | 11.4 |
| `thermodynamic-processes` | `thermodynamic-process-types` | 11.8 |

**Existing-fill subtotal:** 0 new chapters + 13 topics + 23 concepts = **36** (of which **5** are Gravitation provisional)

### 5.4 MicroCompetencies

**P0 MicroCompetencies = 0** (deferred to T2-C / P2 per ADR-0021).

---

## 6. 77 vs 79 Count Reconciliation

### Arithmetic from reconstructed inventory

```text
P0 Chapters          = 5   (proposed new only; existing fills do not add chapters)
P0 Topics            = 26  (13 under new + 13 under existing stubs)
P0 Concepts          = 48  (25 under new + 23 under existing stubs)
P0 MicroCompetencies = 0

TOTAL P0 NODES       = 5 + 26 + 48 + 0 = 79
```

### Discrepancy statement

```text
Previous claimed count:     77   (= 5 + 26 + 46 + 0)
Enumerated count:           79   (= 5 + 26 + 48 + 0)
Reconciled authoritative count: 79

Reason for difference:
  Design §13 rollup claimed Concepts = 46 (“22 under new + 24 under stubs”).
  Design §6.1 tree actually contains Concepts = 48 (“25 under new + 23 under stubs”).
  Net concept delta = +2.
  This is a documentation rollup error, not a missing-node mystery in the tree.
```

### Where the +2 concepts come from (rollup vs tree)

| Bucket | Rollup claim | Tree count | Δ |
|--------|-------------:|-----------:|--:|
| Concepts under 5 **new** chapters | 22 | **25** | **+3** |
| Concepts under 5 **existing** stubs | 24 | **23** | **−1** |
| **Net** | 46 | **48** | **+2** |

**Most likely rollup assumptions that undercounted new chapters by 3** (relative to a 4+6+4+4+4 = 22 model):

1. Rotational: tree has **7** concepts (rollup likely assumed **6**) → +1  
2. Solids: tree has **5** (Young + Shear + Bulk + 2 stress concepts; rollup likely assumed **4**) → +1  
3. Fluids: tree has **5** (rollup likely assumed **4**) → +1  

**Stub side −1:** Laws of Motion tree has **4** concepts; rollup likely assumed **5**.

There are not two “orphan” concepts floating outside the tree. The two-net discrepancy is entirely **summary arithmetic lagging the §6.1 enumeration**.

**Authoritative for implementation planning:** **79** design nodes; **74** NCERT-verified implementable nodes (exclude Gravitation’s 2 topics + 3 concepts).

---

## 7. Kinematics Final Decision and Contract

### Decision

**OPTION A — CONFIRMED**

```text
Chapter = Kinematics [EXISTING] code=kinematics
Topic   = distinguishes NCERT Ch 2 vs Ch 3
Concept = precise scientific classification
MicroCompetency = optional future fine-grained skill (not in P0)
```

| Topic code | NCERT chapter |
|------------|---------------|
| `motion-in-a-straight-line` | Class XI Ch 2 — Motion in a Straight Line |
| `motion-in-a-plane` | Class XI Ch 3 — Motion in a Plane |

### Why Option A remains correct

- Matches current TALOS seed (`kinematics` already exists; additive fill only).  
- Option B would rename/split/deprecate an existing chapter — out of scope for P0 and higher migration risk.  
- NCERT identity is preserved at **topic** level.  
- No material architectural defect found against schema, analytics, or factory patterns.

### Implementation contract (mandatory)

#### Practice

```text
MUST NOT assume:  chapter = Kinematics
is sufficient to distinguish NCERT Ch 2 from Ch 3.

Where NCERT chapter-specific practice is required, filter MUST use:
  chapter_code = kinematics
  AND topic_code IN (motion-in-a-straight-line | motion-in-a-plane)
or an equivalent taxonomy-safe mechanism (topic_id / concept→topic join).
```

#### AI generation / classification

```text
Prompts and metadata MUST receive at minimum where relevant:
  subject, chapter, topic, concept
so the two topic trees are distinguishable.
Chapter-only context is FORBIDDEN for Ch2/Ch3-specific generation.
```

#### Analytics

```text
Chapter-level “Kinematics” mastery = aggregate of both topics (allowed).
NCERT Ch 2 / Ch 3 weak-area reports = topic-level (required).
```

---

## 8. Gravitation Verification Status

```text
PROVISIONAL — SOURCE VERIFICATION PENDING
```

| Fact | Evidence |
|------|----------|
| TALOS chapter exists | Live DB: `gravitation` / “Gravitation” |
| NCERT XI Ch 7 PDF | **Missing** from `StudyMaterial/Physics/Class 11-Physics/` |
| Full NCERT verification of proposed topics/concepts | **Not possible** without inventing content |

### Recommendation

**B — Move Gravitation topic/concept fill out of Gate-4 implementable P0** until the Class XI Ch 7 PDF is available in StudyMaterial.

- Do **not** insert the 2 provisional topics / 3 provisional concepts in the first implementation PR.  
- Do **not** substitute internet/generic Gravitation outlines.  
- Leave existing empty `gravitation` chapter unchanged.  
- Re-admit fill in a follow-up batch after PDF restore + Gate-2 style TOC check.

Design inventory still **lists** those 5 nodes (status PROVISIONAL) so the 79 count remains complete; they are **out of implementation scope** for the first P0 write.

---

## 9. Mechanical Properties of Solids Naming Resolution

```text
Old topic name:   Stress and Strain
Old concept name: Stress and Strain          (code: stress-strain-definitions)
New concept name: Definitions of Stress and Strain
Reason:           Parent topic and child concept must not share the same display label;
                  NCERT §8.2 is the definitions/relations content under the broader
                  Stress and Strain topic (curve remains a sibling concept).
```

| Field | Value |
|-------|-------|
| Topic code (unchanged) | `stress-and-strain` |
| Topic display (unchanged) | Stress and Strain |
| Concept code (unchanged) | `stress-strain-definitions` |
| Concept display (**Gate-4 authoritative**) | **Definitions of Stress and Strain** |

No database change in this task — implementers must use the new display name at insert time.

---

## 10. Legacy 2,500 Protection Check

Read-only SELECT on batch `legacy-physics-5000-import-20260902`:

| Metric | Value |
|--------|------:|
| Total batch questions | 5000 |
| `concept_id IS NULL` | **5000** |
| `concept_id` assigned | **0** |
| `talos_chapter:UNRESOLVED` | **2500** |
| Published in batch | **0** |

```text
taxonomy implementation ≠ legacy question remediation
Legacy questions modified = 0
concept_id assignments = 0
Legacy publication changes = 0
```

**Hard rule for P0 implementation PR:** taxonomy seed/insert only. **Zero** `UPDATE cms.content_items`. The 2,500 unresolved (and all 5,000) remain `concept_id = NULL` until a separate remediation decision.

**No RED inconsistency found.**

---

## 11. NCERT Alignment

| Area | Label |
|------|-------|
| 5 new chapters + their topics/concepts | **NCERT VERIFIED** (PDFs present) |
| Kinematics / Laws / Work / Thermo fills | **NCERT VERIFIED** + **SOURCE-SUPPORTED DECOMPOSITION** |
| Gravitation fill | **SOURCE PENDING** / **PROVISIONAL** — out of implementable scope |
| Concept granularity | Implementation-oriented decomposition of NCERT sections — not 1:1 every heading |

No generic internet syllabus was used to invent missing Ch 7 content.

---

## 12. Duplicate and Collision Check

| Check | Result |
|-------|--------|
| Proposed new chapter codes vs live Physics chapters | **No collision** |
| Proposed topic/concept codes vs Electrostatics / CE / Optics | **No collision** (spot-checked against live tree) |
| Duplicate codes within P0 inventory | **None** (chapters 5, topics 26, concepts 48 unique) |
| Solids display collision | **Resolved** in §9 |
| DB unique constraint on chapter/topic/concept `code` | **None** — implement with `(parent_id, code)` idempotency |
| Accidental reuse of existing node | New chapters only; fills attach to existing empty stubs |

```text
Duplicate risk = LOW
```

---

## 13. Hierarchy Integrity

```text
PHYSICS (Subject)
  ↓
Chapter (5 new + fills under 5 existing)
  ↓
Topic (exactly one parent chapter each)
  ↓
Concept (exactly one parent topic each)
  ↓
MicroCompetency (none in P0)
```

| Check | Result |
|-------|--------|
| Orphan topics/concepts | **0** |
| Concept used as topic | **No** |
| Topic used as chapter substitute | **No** (Kinematics topics are topics under existing chapter) |
| KT vs Thermo separation | **Intact** |
| UCM kinematics vs dynamics | Separate concepts under Kinematics vs Laws — correct |

---

## 14. 1M-MCQ Scalability Assessment

| Scale | Assessment |
|------:|------------|
| 10K–100K | Comfortable at concept granularity |
| 250K–500K | Stable IDs (`code` + UUID); index by `concept_id` / topic / chapter |
| 1M | Aggregation remains chapter→topic→concept; hot concepts may need P2 micro-competencies later — **no hierarchy redesign** |

AI generation ambiguity controlled by Kinematics contract (§7). Deduplication can retain taxonomy provenance via `concept_id` + tags. Future micro-competencies attach under concepts without restructuring.

**Result:** **PASS** (with known REVIEW on hottest concepts at extreme volume — acceptable).

---

## 15. Final Authoritative P0 Inventory Summary

| Level | Previous Design Claim | Enumerated | Reconciled | Difference | Explanation |
| ----------------- | --------------------: | ---------: | ---------: | ---------: | ----------- |
| Chapters | 5 | 5 | **5** | 0 | New chapters only |
| Topics | 26 | 26 | **26** | 0 | Includes 2 Gravitation provisional topics |
| Concepts | 46 | 48 | **48** | **+2 vs claim** | Rollup undercounted tree |
| MicroCompetencies | 0 | 0 | **0** | 0 | P2 only |
| **Total** | **77** | **79** | **79** | **+2** | Authoritative = tree enumeration |

### Implementation subsets

| Subset | Chapters | Topics | Concepts | Total | Action |
|--------|--------:|-------:|---------:|------:|--------|
| Design inventory (authoritative) | 5 | 26 | 48 | **79** | Record-keeping |
| **Gate-4 implementable** | 5 | **24** | **45** | **74** | **Allowed to insert** |
| Gravitation provisional (deferred) | 0 | 2 | 3 | **5** | **Do not insert yet** |

---

## 16. Implementation Readiness Decision

```text
GREEN — READY FOR P0 IMPLEMENTATION
```

All Gate-4 GREEN conditions are met **when** the implementation PR follows the contracts in this report (especially §7–§10 and the 74-node implementable set).

---

## 17. Required Changes Before Implementation

These are **implementation constraints**, not further design blockers:

1. Use **authoritative counts: design 79 / implement 74** (ignore design-doc rollup “77”).  
2. Apply Solids concept display **Definitions of Stress and Strain**.  
3. Enforce **Kinematics practice/AI contract** (§7) in any practice or factory code that consumes taxonomy.  
4. **Exclude** Gravitation topic/concept inserts until Ch 7 PDF is restored.  
5. **Zero** updates to `cms.content_items` / legacy `concept_id`.  
6. Prefer idempotent seed by `(parent, code)`.

No further design redesign required.

---

## 18. Safety Proof

```text
Database writes = 0
Database rows modified = 0
Questions modified = 0
concept_id assignments = 0
Publication changes = 0
Legacy source files modified = 0
Schema changes = 0
Migration executed = 0
Seed executed = 0
Final recommendation = GREEN
```

---

## 19. Recommended Next Step

Issue a **separate P0 implementation task** that:

1. Inserts the **74** NCERT-verified nodes only.  
2. Applies Gate-4 Solids naming and Kinematics contracts.  
3. Leaves Gravitation fill and all legacy questions untouched.  
4. Ends with a post-implementation SELECT validation (counts, no question churn, published pool unchanged).

**Do not implement in this Gate-4 task** — completed here.
