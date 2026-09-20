# TALOS Physics P0 — Pre-Implementation Review

**Date:** 2026-09-02  
**Reviewed artifact:** `docs/audits/TALOS_PHYSICS_MINIMUM_TAXONOMY_EXTENSION_DESIGN_20260902.md`  
**Mode:** READ-ONLY verification  

**Hard safety:** Database writes = **0**. No taxonomy or question mutations.

---

## 1. Executive Verdict

The P0 design is **academically coherent and implementable**, with **minor documentation / inventory fixes** required before Gate 4 database work.

| Check | Result |
|-------|--------|
| P0 claimed total = 77 | **FAIL to reconcile** — tree enumeration = **79** (see §2) |
| Duplicate vs live TALOS codes | **PASS** — no collision with existing Physics chapter/topic/concept codes |
| NCERT boundaries (P0) | **PASS** with SME notes on kinematics merge + Gravitation PDF gap |
| Kinematics Option A vs B | **Recommend Option A** (keep one chapter) with explicit analytics contract |
| Legacy 2,500 isolation | **PASS** — all still `concept_id IS NULL`; design forbids auto-classify |
| 1M scalability | **PASS** (with REVIEW on broad concepts at high volume) |

### Final recommendation

**AMBER — MINOR DESIGN CHANGES REQUIRED**

Do **not** implement until the design document’s P0 inventory is reconciled to a single authoritative node list and the minor flags in §9 are addressed.

---

## 2. P0 Count Reconciliation

### 2.1 Claimed (design §13 rollup)

| Level | Claimed |
|-------|--------:|
| New chapters | 5 |
| New topics | 26 |
| New concepts | 46 |
| Micro-competencies | 0 |
| **P0 total** | **77** (= 5+26+46) |

Supporting text: “22 under new chapters + 24 under stubs = 46 concepts”; “13 + 13 = 26 topics”.

### 2.2 Enumerated from design §6.1 tree (P0 only; P1/P2 excluded)

#### New chapters (5) — PASS vs claim

| code | name |
|------|------|
| `units-and-measurement` | Units and Measurement |
| `systems-of-particles-rotational-motion` | Systems of Particles and Rotational Motion |
| `mechanical-properties-of-solids` | Mechanical Properties of Solids |
| `mechanical-properties-of-fluids` | Mechanical Properties of Fluids |
| `kinetic-theory` | Kinetic Theory |

Existing chapters filled (not new): `kinematics`, `laws-of-motion`, `work-energy-power`, `gravitation`, `thermodynamics-physics`.

#### Topics (26) — PASS vs claim

| Parent chapter | Topic codes | n |
|----------------|-------------|--:|
| units-and-measurement | si-units-and-measurement; significant-figures-and-errors; dimensions-and-dimensional-analysis | 3 |
| kinematics | motion-in-a-straight-line; motion-in-a-plane | 2 |
| laws-of-motion | newtons-laws-and-momentum; friction-and-common-forces; dynamics-of-circular-motion | 3 |
| work-energy-power | work-and-kinetic-energy; potential-energy-and-conservation; power-and-collisions | 3 |
| systems-of-particles-rotational-motion | centre-of-mass; torque-and-angular-momentum; moment-of-inertia-rotational-dynamics | 3 |
| gravitation | newtons-law-of-gravitation; gravity-potential-satellites | 2 |
| mechanical-properties-of-solids | stress-and-strain; elastic-moduli | 2 |
| mechanical-properties-of-fluids | pressure-in-fluids; fluid-flow-and-bernoulli; viscosity-and-surface-tension | 3 |
| thermodynamics-physics | laws-of-thermodynamics; heat-work-internal-energy; thermodynamic-processes | 3 |
| kinetic-theory | kinetic-theory-ideal-gas; equipartition-and-mean-free-path | 2 |
| **Total topics** | | **26** |

#### Concepts (48) — FAIL vs claim of 46

| Parent chapter | Concept codes | n |
|----------------|---------------|--:|
| units-and-measurement | si-base-and-derived-units; significant-figures; dimensional-formulae; dimensional-analysis-applications | 4 |
| kinematics | instantaneous-velocity-acceleration; kinematic-equations; relative-velocity-1d; vectors-in-plane-motion; projectile-motion; uniform-circular-motion | 6 |
| laws-of-motion | newtons-laws; conservation-of-momentum; friction; dynamics-uniform-circular-motion | 4 |
| work-energy-power | work-by-a-force; work-energy-theorem; potential-energy; conservation-mechanical-energy; power; collisions | 6 |
| systems-of-particles-rotational-motion | centre-of-mass-system; motion-of-centre-of-mass; torque; angular-momentum; moment-of-inertia; rotational-kinematics; dynamics-of-rotational-motion | **7** |
| gravitation | universal-law-of-gravitation; acceleration-due-to-gravity; orbital-motion-satellites | 3 |
| mechanical-properties-of-solids | stress-strain-definitions; stress-strain-curve; youngs-modulus; shear-modulus; bulk-modulus | **5** |
| mechanical-properties-of-fluids | hydrostatic-pressure-pascal; streamline-flow; bernoullis-principle; viscosity; surface-tension | **5** |
| thermodynamics-physics | zeroth-and-first-law; second-law-and-carnot; heat-internal-energy-work; thermodynamic-process-types | 4 |
| kinetic-theory | behaviour-of-gases; kinetic-interpretation-temperature; law-of-equipartition; mean-free-path | 4 |
| **Total concepts** | | **48** |

Breakdown vs claim:

| Bucket | Claimed | Enumerated | Δ |
|--------|--------:|-----------:|--:|
| Concepts under 5 new chapters | 22 | 4+7+5+5+4 = **25** | **+3** |
| Concepts under 5 existing stubs | 24 | 6+4+6+3+4 = **23** | **−1** |
| **Concept total** | **46** | **48** | **+2** |

#### Micro-competencies

**0** in P0 (P2 only) — PASS vs claim.

### 2.3 Reconciliation result

```text
Claimed P0 total     = 5 + 26 + 46 + 0 = 77
Enumerated from tree = 5 + 26 + 48 + 0 = 79
Discrepancy          = +2 concepts (documentation rollup undercounted the §6.1 tree)
```

**Not silently corrected.**  
**Authoritative for implementation must be chosen explicitly:** either (a) update the design rollup to **79**, or (b) remove/merge exactly two concepts from the tree to match **77**. Until then, Gate 4 must not proceed.

Likely cause: §12/§13 used an earlier estimate (e.g. Solids 4 moduli concepts, Fluids 4, Rotational 6) while §6.1 expanded Young/Shear/Bulk and full rotational set.

---

## 3. Node-by-Node Validation

### 3.1 Method

For each P0 proposed `code`: checked against live `academic.*` Physics codes (SELECT-only). Validated parent linkage in the design tree, hierarchy level, and NCERT evidence from prior PDF-backed gap analysis.

### 3.2 Code uniqueness vs live TALOS

| Check | Result |
|-------|--------|
| Proposed chapter codes vs existing 8 | **No collision** |
| Proposed topic/concept codes vs Electrostatics / CE / Optics | **No collision** |
| DB unique constraint on chapter/topic/concept `code` | **None** (convention: unique within parent) — implementation must enforce `(parent_id, code)` idempotency |

### 3.3 Flags (SME / design)

| Node / area | Flag | Severity |
|-------------|------|----------|
| All P0 nodes | Proposed IDs are **`code` strings**, not UUIDs — correct for this schema | Info |
| Solids: topic name “Stress and Strain” + concept name “Stress and Strain” (`stress-strain-definitions`) | Duplicate **display name** within chapter (codes differ) | Minor — rename concept display to “Stress and Strain Definitions” |
| Gravitation topics/concepts | NCERT XI Ch 7 **PDF absent** from StudyMaterial; evidence weaker than other P0 chapters | **SME REVIEW** — provisional or defer fill |
| `power` concept code | Very generic short code; OK if scoped under topic parent | Info — prefer `mechanical-power` if global uniqueness ever added |
| Topic `thermodynamic-processes` vs concept `thermodynamic-process-types` | Slightly awkward naming | Minor |
| Kinematics merge | NCERT has two chapters; TALOS has one | **SME REVIEW** — see §4 |
| Kinetic Theory vs Thermodynamics | Correctly separate chapters | PASS |
| Uniform circular motion | Kinematic concept under Motion in a Plane **and** dynamics concept under Laws of Motion | PASS if kept chapter-specific (see §6) |

### 3.4 Validation summary by chapter

| Chapter | Parents valid | Codes unique in design | NCERT evidence | Verdict |
|---------|---------------|------------------------|----------------|---------|
| Units and Measurement (new) | Yes | Yes | XI Ch 1 PDF | PASS |
| Kinematics (fill) | Yes | Yes | XI Ch 2–3 PDFs via topics | PASS + SME on merge |
| Laws of Motion (fill) | Yes | Yes | XI Ch 4 PDF | PASS |
| Work, Energy and Power (fill) | Yes | Yes | XI Ch 5 PDF | PASS |
| Rotational Motion (new) | Yes | Yes | XI Ch 6 PDF | PASS |
| Gravitation (fill) | Yes | Yes | PDF missing | **CONDITIONAL** |
| Solids (new) | Yes | Yes | XI Ch 8 PDF | PASS (rename display) |
| Fluids (new) | Yes | Yes | XI Ch 9 PDF | PASS |
| Thermodynamics (fill) | Yes | Yes | XI Ch 11 PDF | PASS |
| Kinetic Theory (new) | Yes | Yes | XI Ch 12 PDF | PASS |

---

## 4. Kinematics Decision

### Context

NCERT: **two chapters** — Motion in a Straight Line (XI Ch 2), Motion in a Plane (XI Ch 3).  
TALOS today: **one empty chapter** — `kinematics` / “Kinematics”.  
Design: **Option A** — keep one chapter; two topic trees.

### Option A — One chapter `Kinematics` + two topics

| Dimension | Assessment |
|-----------|------------|
| NCERT structure | Partial — chapter boundary collapsed; topic codes restore NCERT identity |
| TALOS model | Fits additive rule; no rename/split migration |
| Student chapter analytics | Chapter score blends Ch 2+3 unless UI filters by topic |
| MCQ classification | Safe if `concept_id` + `ncert_reference` / topic used |
| AI generation | Safe if prompt binds topic/concept, not only chapter name “Kinematics” |

**Advantages:** No migration of existing chapter; matches current seed; NEET often treats “Kinematics” as a unit; lower chapter count.  
**Disadvantages:** NCERT chapter-level practice/reporting needs topic filters; risk of lazy classification at chapter-only granularity.

### Option B — Separate chapters `motion-in-a-straight-line` and `motion-in-a-plane`

| Dimension | Assessment |
|-----------|------------|
| NCERT structure | Full alignment |
| TALOS model | Requires retiring or emptying `kinematics` — **not additive**; may break any future FKs/mappings to `kinematics` |
| Analytics | Clean NCERT chapter reports |
| Classification / AI | Cleaner chapter targeting |

**Advantages:** Pure NCERT boundaries.  
**Disadvantages:** Conflicts with “do not change existing taxonomy names”; orphan/`kinematics` deprecation cost; ADR-0031 and seeds already use `kinematics`.

### Recommendation

**Option A — keep one `Kinematics` chapter with two topic trees.**

**Required contract (must be written into design before implement):**

1. NCERT Class XI Ch 2 ↔ topic `motion-in-a-straight-line`  
2. NCERT Class XI Ch 3 ↔ topic `motion-in-a-plane`  
3. Student “NCERT chapter practice” and weak-chapter reports for Ch 2/3 must use **topic** (or explicit crosswalk), not the parent chapter alone.  
4. Factory/AI prompts must pass **topic + concept**, not only `chapter_code=kinematics`.

This is academically acceptable for TALOS v1 given existing seed constraints. Option B remains a future migration if product requires first-class NCERT chapter entities.

---

## 5. Chapter Boundary Review

| Boundary | Assessment |
|----------|------------|
| Units vs all others | Clean — measurement/dimensions only |
| Kinematics vs Laws | Clean if UCM kinematics stay under Motion in a Plane and force/dynamics under Laws (`dynamics-uniform-circular-motion`) |
| Laws vs Work | Clean — forces/momentum vs energy |
| Work vs Rotational | Clean — translational energy vs COM/torque/MOI |
| Rotational vs Gravitation | Clean — rigid body / COM vs gravity field |
| Solids vs Fluids | Clean — elastic solids vs fluid statics/dynamics |
| Thermodynamics vs Kinetic Theory | Clean — macroscopic laws/processes vs molecular KT (NCERT Ch 11 vs 12) |
| Fluids Bernoulli vs Thermo | No material overlap in P0 tree |

**No material chapter overlap** in P0 if classification follows the tree. Risk is operational (mis-tagging), not structural.

---

## 6. Cross-Chapter Concept Review

| Theme | Appears in | Recommendation |
|-------|------------|----------------|
| Uniform circular motion | Kinematics (description) + Laws (dynamics) | **Chapter-specific concepts** (already proposed) — do not share one concept |
| Work / energy | Work–Energy chapter vs thermo “Heat, Work and Internal Energy” | **Chapter-specific concepts** — different physics contexts |
| Ideal gas / temperature | Kinetic Theory vs Thermodynamics processes | **Chapter-specific**; optional later `ncert_reference` cross-links — **no shared concept row** |
| Gravity / g | Gravitation vs kinematics freefall | Prefer Gravitation for gravity law; kinematics uses acceleration as kinematics — **do not duplicate Universal Gravitation** under kinematics (P0 complies) |

**Least complex safe solution:** keep **one concept row per (topic) parent**; do **not** introduce a shared-concept graph or many-to-many for v1. Use `ncert_reference` text and editorial tags for related reading. Matches ADR-0012 (no concept relationship table yet).

---

## 7. 1M-MCQ Scalability

| Scale | Classification | Mastery / analytics | Generation | Overload risk |
|------:|----------------|---------------------|------------|---------------|
| 10K | Fine | Fine | Fine | Low |
| 100K | Fine if topic+concept required | Fine | Fine | Medium on `newtons-laws`, `kinematic-equations` |
| 1M | Still workable | Chapter rollups coarse for Kinematics | Requires concept binding | **REVIEW** — add P2 micro-competencies on hottest concepts only |

**Ambiguity:** Low if factory forbids chapter-only tagging.  
**Chapter tests:** Meaningful for all P0 chapters except Kinematics (use topic-split tests — §4 contract).  
**Verdict:** **PASS** with documented REVIEW on high-volume concepts.

---

## 8. Legacy 2,500 Isolation

| Check | Evidence | Result |
|-------|----------|--------|
| Unresolved import rows | SELECT: 2500 rows with `talos_chapter:UNRESOLVED` | Confirmed |
| `concept_id` | All 2500 have `concept_id IS NULL` | Confirmed |
| Design scope | Explicitly excludes auto-classification of legacy bank | Confirmed |
| Implementation must | Insert taxonomy only; **no** UPDATE on `cms.content_items` for this batch | Required |

**Confirmed:** Taxonomy P0 implementation must leave `concept_id = NULL` on the 2,500 (and the full 5,000) until a separate remediation decision.

---

## 9. Required Changes (before GREEN)

Exact changes to clear AMBER:

1. **Reconcile P0 inventory** in the design doc: either set totals to **79** (5+26+48) matching §6.1, or delete/merge **exactly two** concepts and keep **77**. Publish one authoritative checklist.  
2. **Gravitation:** mark P0 Gravitation topic/concept fill as **provisional** pending XI Ch 7 PDF restore, **or** move Gravitation fill to T2-B.  
3. **Solids naming:** change concept display name from “Stress and Strain” to e.g. “Stress and Strain Definitions” (keep code `stress-strain-definitions`).  
4. **Kinematics contract:** add the four analytics/generation rules from §4 into the design (Option A confirmation).  
5. **Implementation ticket language:** “Taxonomy seed only — zero `content_items` updates; legacy batch concept_id remains NULL.”

No structural redesign of chapter set required.

---

## 10. Final Implementation Recommendation

### AMBER — MINOR DESIGN CHANGES REQUIRED

After items in §9 are reflected in the design document (still no DB writes in that step), a follow-up verification can flip to **GREEN — IMPLEMENT P0**.

**Not RED:** chapter set, NCERT alignment of the five new chapters, KT/Thermo separation, Solids/Fluids/Rotational/Units trees, and legacy isolation are sound.

---

## Database Safety Proof

```text
Database writes = 0
Existing taxonomy modified = 0
Questions modified = 0
concept_id assignments = 0
Publication changes = 0

Final recommendation =
AMBER — MINOR DESIGN CHANGES REQUIRED
```
