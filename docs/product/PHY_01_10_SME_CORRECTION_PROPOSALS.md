# Physics PHY-01–PHY-10 — SME Correction Proposals

**Status:** PROPOSAL ONLY — **not applied** to any database.  
**Pilot:** `batch-a-sme-pilot-40`  
**Batch:** `acquisition-batch-A-diversify-p0`  
**Source export:** `docs/product/ECAEP_SME_REVIEW_PHY_01_10.md`  
**Database check:** development `trinetra_db` — SELECT only; **zero writes**, zero status/content changes.

Provenance for all items remains as stored: `human-authored-batch-a` · SME review required · not official NTA/NEET/NCERT.  
**No proposal invents NCERT citations or official labels.**

---

## Summary (for triage)

| ID | Change needed? | Main issues | Mapping | Difficulty | Distractors |
|----|----------------|-------------|---------|------------|-------------|
| PHY-01 | Yes | Weak distractors | OK | OK (Easy) | Yes |
| PHY-02 | Yes (optional mapping + distractor) | Weak D; concept name | Review | OK | Yes |
| PHY-03 | Yes | Wording; unused battery clause; difficulty | OK | Medium→Easy or redesign | Partial |
| PHY-04 | Yes | Weak distractors / formula recall | OK | OK | Yes |
| PHY-05 | Yes | Difficulty Hard inappropriate | OK | Hard→Easy **or** redesign Hard | Partial |
| PHY-06 | Yes (optional) | Weak distractors | OK | OK / retain Easy | Yes |
| PHY-07 | Yes (optional retain vs upgrade) | Very basic | OK | OK if retain | Weak |
| PHY-08 | **Yes — critical mapping** | Wrong concept; weak explanation | **Incorrect** | OK | Partial |
| PHY-09 | Yes | Too easy; weak distractors | OK | OK→Medium if upgraded | Yes |
| PHY-10 | **Yes — redesign** | Title/mismatch; difficulty; D; mapping; explanation | Questionable | Medium→reassess | Yes |

**Questions requiring changes:** **10/10** (all have at least an optional improvement; PHY-08 and PHY-10 are critical).  
**Mapping issues:** PHY-02 (review), **PHY-08 (critical)**, **PHY-10 (questionable)**.  
**Difficulty issues:** PHY-03, **PHY-05**, PHY-10 (and PHY-09 if upgraded).  
**Distractor issues:** PHY-01, PHY-02, PHY-04, PHY-06, PHY-07, PHY-09, PHY-10.

Where a proposal names a **Concept**, the exact concept UUID must be confirmed in the academic hierarchy by an editor after SME approval — do not invent UUIDs.

---

## PHY-01 — Capacitance formula

**ID:** `8721e193-2d6e-433a-81d9-ceb2b31aef01`

### Current Question

- **Stem:** Capacitance of a parallel plate capacitor (vacuum) is proportional to:
- **A.** d/A  
- **B.** A/d  
- **C.** A·d  
- **D.** 1/(A·d)  
- **Answer:** B  
- **Explanation:** C = ε₀A/d for a vacuum parallel plate capacitor.  
- **Mapping:** Physics · Electrostatics · Capacitance · Parallel Plate Capacitor  
- **Difficulty:** easy  

### SME Findings

Distractors are too obvious (formula reciprocals / products). Scientific answer **B** is correct.

### Scientific Status

**Correct** (stored answer B).

### Proposed Correction (improved distractors — retain Easy)

- **Title:** Parallel plate capacitance dependence  
- **Stem:** Capacitance of a vacuum parallel-plate capacitor is proportional to:
- **A.** Separation between plates only  
- **B.** Area of plates / separation between plates  
- **C.** Square of the plate area  
- **D.** Product of plate area and separation  
- **Answer:** B  
- **Explanation:** For a vacuum parallel-plate capacitor, C = ε₀A/d, so C ∝ A/d. Options that keep only d, use A², or use A·d do not match this dependence.  
- **Difficulty:** easy  
- **Mapping:** unchanged (Parallel Plate Capacitor)

### Alternative (simple numerical application — Easy)

- **Stem:** A vacuum parallel-plate capacitor has plate area A and separation d. If A is doubled and d is halved, the capacitance becomes:
- **A.** Unchanged  
- **B.** 2 times  
- **C.** 4 times  
- **D.** 1/2  
- **Answer:** C  
- **Explanation:** C = ε₀A/d. Doubling A multiplies C by 2; halving d multiplies C by 2; overall factor 4.  
- **Difficulty:** easy  
- **Mapping:** unchanged  

### Reason

Removes reciprocal “trick” distractors; tests recognition of A/d dependence or a one-step application suitable for Easy foundation content.

### SME Approval Required

**Yes.** Do not modify the database until a human SME approves one of the above (or a revised draft).

---

## PHY-02 — Concave mirror focus

**ID:** `f51bd10d-70c1-4bc1-98f3-490f723ec549`

### Current Question

- **Stem:** Rays parallel to the principal axis of a concave mirror, after reflection, pass through:
- **A.** Centre of curvature  
- **B.** Pole  
- **C.** Focus  
- **D.** Infinity only  
- **Answer:** C  
- **Explanation:** By definition, paraxial parallel rays converge at the focal point after reflection.  
- **Mapping:** Optics · Reflection and Mirrors · **Spherical Mirror Formula**  
- **Difficulty:** easy  

### SME Findings

- Distractor D (“Infinity only”) is weak/awkward.  
- Concept mapping may fit **principal focus / reflection** better than **Spherical Mirror Formula**.  

### Scientific Status

**Correct** (stored answer C). Mapping accuracy: **requires SME confirmation**.

### Proposed Correction

**Content (distractor only):**

- **Stem:** (unchanged) Rays parallel to the principal axis of a concave mirror, after reflection, pass through:
- **A.** Centre of curvature  
- **B.** Pole  
- **C.** Principal focus  
- **D.** Midpoint between pole and centre of curvature only if the aperture is large  
- **Answer:** C  
- **Explanation:** By definition, paraxial rays parallel to the principal axis converge (after reflection) at the principal focus of a concave mirror. The centre of curvature is for rays directed toward C; the pole is on the mirror surface.  
- **Difficulty:** easy  

**Mapping proposal:**

- Subject / Chapter / Topic: unchanged (Optics · Reflection and Mirrors)  
- **Concept:** prefer a concept aligned with **principal focus / reflection at spherical mirrors** (confirm exact concept name/UUID in academic seed).  
- Do **not** keep “Spherical Mirror Formula” if that KU is reserved for the mirror formula 1/v + 1/u = 1/f.

### Alternative

Retain stem and A–C; only replace D with: **“Any point on the principal axis beyond the centre of curvature.”** Keep mapping change as a separate editorial decision.

### Reason

Keeps a valid Easy definitional NEET item; replaces a nonsense distractor; aligns concept label with what is actually tested.

### SME Approval Required

**Yes.** Mapping change must be human-approved before any DB edit.

---

## PHY-03 — Dielectric effect

**ID:** `fbfa14ed-b9cc-4016-8c4b-d08f997ecdd6`

### Current Question

- **Stem:** Inserting a dielectric of dielectric constant K > 1 between capacitor plates (battery disconnected) generally:
- **A.** Decreases capacitance  
- **B.** Increases capacitance  
- **C.** Leaves capacitance unchanged  
- **D.** Makes capacitance infinite  
- **Answer:** B  
- **Explanation:** With dielectric, C = Kε₀A/d increases for K > 1.  
- **Mapping:** Electrostatics · Capacitance · Parallel Plate Capacitor  
- **Difficulty:** medium  

### SME Findings

- “Battery disconnected” is unnecessary if only capacitance is asked.  
- “Generally” is imprecise.  
- Medium may be too high.  
- Or: make disconnected-battery condition meaningful (ask charge/potential/energy).  

### Scientific Status

**Correct** that C increases for K > 1 (answer B). Difficulty classification: **inappropriate as Medium** for this stem.

### Proposed Correction — Alternative A (keep capacitance focus; Easy)

- **Title:** Dielectric and capacitance  
- **Stem:** A dielectric slab of dielectric constant K > 1 completely fills the space between the plates of a parallel-plate capacitor. The capacitance:
- **A.** Decreases  
- **B.** Increases by factor K  
- **C.** Remains unchanged  
- **D.** Becomes infinite  
- **Answer:** B  
- **Explanation:** With a dielectric filling the gap, C = Kε₀A/d, so capacitance increases by factor K relative to vacuum. Capacitance depends on geometry and dielectric, not on whether a battery is connected.  
- **Difficulty:** easy  
- **Mapping:** unchanged  

### Alternative B (use battery-disconnected meaningfully — Medium)

- **Stem:** A parallel-plate capacitor is charged by a battery and then **disconnected**. A dielectric of constant K > 1 is then inserted to fill the gap. Which statement is correct?
- **A.** Capacitance decreases and charge on plates increases  
- **B.** Capacitance increases, charge remains constant, potential difference decreases  
- **C.** Capacitance and potential both remain constant  
- **D.** Capacitance becomes infinite and energy stored becomes zero  
- **Answer:** B  
- **Explanation:** After disconnection, Q is fixed. Inserting dielectric increases C (C′ = KC). From V = Q/C, V decreases. Energy U = Q²/(2C) also decreases. Capacitance does not become infinite for finite K.  
- **Difficulty:** medium  
- **Mapping:** unchanged  

### Reason

A matches Easy recognition of C = KC₀. B makes the disconnected condition do real work (Q fixed → V and U change), which is NEET-typical Medium reasoning.

### SME Approval Required

**Yes.** Choose A or B (or revise); do not apply until approved.

---

## PHY-04 — Mirror formula relation

**ID:** `4d0ab71e-a997-4ac1-ad17-ba24f030a19c`

### Current Question

- **Stem:** The spherical mirror formula is:
- **A.** 1/v − 1/u = 1/f  
- **B.** 1/v + 1/u = 1/f  
- **C.** v + u = f  
- **D.** vu = f  
- **Answer:** B  
- **Explanation:** For spherical mirrors (Cartesian sign convention), 1/v + 1/u = 1/f.  
- **Mapping:** Reflection and Mirrors · Spherical Mirror Formula  
- **Difficulty:** easy  

### SME Findings

Formula-recall with weak distractors. Stored answer **B** is scientifically correct.

### Scientific Status

**Correct** (B).

### Proposed Correction (stronger Easy distractors)

- **Stem:** Under the Cartesian sign convention used for spherical mirrors, the mirror formula is:
- **A.** 1/v − 1/u = 1/f  
- **B.** 1/v + 1/u = 1/f  
- **C.** 1/f = 1/u − 1/v  
- **D.** f = (u + v)/2  
- **Answer:** B  
- **Explanation:** The standard spherical-mirror relation is 1/v + 1/u = 1/f (Cartesian signs). Option A resembles a lens-like difference form and is incorrect for the usual mirror formula; C rearranges incorrectly; D is not the mirror formula.  
- **Difficulty:** easy  
- **Mapping:** unchanged  

### Alternative (simple application — Easy/Medium border → recommend Easy)

- **Stem:** For a concave mirror, object distance u = −30 cm and focal length f = −10 cm (Cartesian signs). The image distance v is:
- **A.** −15 cm  
- **B.** −7.5 cm  
- **C.** +15 cm  
- **D.** −20 cm  
- **Answer:** A  
- **Explanation:** 1/v + 1/u = 1/f ⇒ 1/v = 1/f − 1/u = −1/10 − (−1/30) = −1/10 + 1/30 = −2/30 = −1/15 ⇒ v = −15 cm.  
- **Difficulty:** easy (one-step formula use)  
- **Mapping:** unchanged  

### Reason

Keeps formula identity testing with less “junk” algebra distractors, or converts to a short numerical check common in NEET practice.

### SME Approval Required

**Yes.**

---

## PHY-05 — Energy stored

**ID:** `f7b0f62f-1fcb-4a69-9052-455e00f7cb84`

### Current Question

- **Stem:** Energy stored in a capacitor charged to voltage V is:
- **A.** CV  
- **B.** ½CV²  
- **C.** C²V  
- **D.** 2CV²  
- **Answer:** B  
- **Explanation:** U = ½CV² = Q²/(2C) = ½QV.  
- **Mapping:** Capacitance · Parallel Plate Capacitor  
- **Difficulty:** hard  

### SME Findings

Hard is inappropriate for straightforward formula recall. Either reclassify Easy **or** redesign a genuine Hard problem. **Do not auto-choose.**

### Scientific Status

**Correct** (B). Difficulty: **incorrect as Hard**.

### Proposed Correction — Alternative 1 (difficulty only)

- Keep stem, options, answer, explanation, mapping **unchanged**.  
- **Difficulty:** easy  

### Proposed Correction — Alternative 2 (genuine Hard redesign)

- **Title:** Capacitor energy with dielectric (battery disconnected)  
- **Stem:** A capacitor of capacitance C₀ is charged to potential V₀ and then disconnected from the battery. A dielectric of constant K fills the gap completely. The energy stored after insertion is:
- **A.** ½ C₀ V₀²  
- **B.** ½ K C₀ V₀²  
- **C.** (1/(2K)) C₀ V₀²  
- **D.** K² C₀ V₀²  
- **Answer:** C  
- **Explanation:** After disconnection, charge Q = C₀V₀ is constant. Capacitance becomes KC₀. Energy U = Q²/(2C) = (C₀² V₀²)/(2 K C₀) = C₀ V₀²/(2K) = (1/(2K)) C₀ V₀². Option A is the energy before insertion; B would apply if voltage were held constant by a battery.  
- **Difficulty:** hard  
- **Mapping:** Capacitance · Parallel Plate Capacitor (unchanged subject/chapter/topic/concept family)  

### Reason

Alt 1 matches actual cognitive load. Alt 2 requires knowing which quantity is fixed and applying U = Q²/(2C) — multi-step Hard reasoning.

### SME Approval Required

**Yes.** SME must choose Alt 1 or Alt 2 (or another design). **Do not auto-apply.**

---

## PHY-06 — Focal length and radius

**ID:** `9a0ae17f-38f3-4141-8dad-389ae265195c`

### Current Question

- **Stem:** For a spherical mirror of small aperture, f is approximately:
- **A.** R  
- **B.** R/2  
- **C.** 2R  
- **D.** R/4  
- **Answer:** B  
- **Explanation:** f ≈ R/2 for a spherical mirror.  
- **Mapping:** Spherical Mirror Formula  
- **Difficulty:** easy  

### SME Findings

Formula recall with weak distractors. Answer **B** correct. Improve **or** explicitly retain as foundation Easy.

### Scientific Status

**Correct** (B).

### Proposed Correction (retain Easy, clearer distractors)

- **Stem:** For a spherical mirror of small aperture, the focal length f is related to the radius of curvature R approximately by:
- **A.** f = R  
- **B.** f = R/2  
- **C.** f = 2R  
- **D.** f = √R  
- **Answer:** B  
- **Explanation:** Under the paraxial (small-aperture) approximation, f = R/2 for a spherical mirror.  
- **Difficulty:** easy  
- **Mapping:** unchanged (or same mapping note as PHY-02 if “Spherical Mirror Formula” is reserved for 1/v+1/u=1/f — SME decide)

### Alternative (retain as-is)

Keep current stem/options/explanation/difficulty as **foundation Easy** inventory. No content change — only an editorial “retain” decision.

### Reason

Relation f = R/2 is standard Easy syllabus content; mild distractor cleanup avoids √R / nonsense ratios without inflating difficulty.

### SME Approval Required

**Yes** (including “retain as-is”).

---

## PHY-07 — Coulomb force direction

**ID:** `4b928b5f-da43-4361-89db-312b6c6950a4`

### Current Question

- **Stem:** Two like point charges placed in vacuum will:
- **A.** Attract each other  
- **B.** Repel each other  
- **C.** Experience no force  
- **D.** Orbit each other without force  
- **Answer:** B  
- **Explanation:** Like charges repel; unlike charges attract, as described by Coulomb's law.  
- **Mapping:** Electric Charge and Coulomb's Law · Coulomb's Law  
- **Difficulty:** easy  

### SME Findings

Very basic recall; scientifically correct. Decide: retain Easy foundation **or** upgrade to NEET-relevant conceptual/vector item.

### Scientific Status

**Correct** (B).

### Proposed Correction — Alternative 1 (retain)

No content change. Mark as **Easy foundation** for early Electrostatics.

### Proposed Correction — Alternative 2 (conceptual upgrade — Easy/Medium → recommend Easy)

- **Title:** Coulomb force direction (vector)  
- **Stem:** Two positive point charges are fixed on the x-axis at x = −a and x = +a. The net electric force on a third positive charge placed at the origin is:
- **A.** Along +x  
- **B.** Along −x  
- **C.** Zero  
- **D.** Perpendicular to the x-axis  
- **Answer:** C  
- **Explanation:** Forces from the two equal positive charges on a positive test charge at the midpoint are equal in magnitude and opposite in direction, so the net force is zero.  
- **Difficulty:** easy  
- **Mapping:** Coulomb's Law (unchanged topic)  

### Reason

Alt 1 preserves a valid primer item. Alt 2 tests superposition/symmetry without jumping to Hard multi-step algebra.

### SME Approval Required

**Yes.** Choose retain vs upgrade.

---

## PHY-08 — Refractive index (**CRITICAL MAPPING**)

**ID:** `6d7b9e60-e56f-46e0-b553-654aba9c4a47`

### Current Question

- **Stem:** Absolute refractive index of a medium is:
- **A.** Speed of light in medium / speed in vacuum  
- **B.** Speed of light in vacuum / speed in medium  
- **C.** Always less than 1  
- **D.** Equal to wavelength only  
- **Answer:** B  
- **Explanation:** n = c/v; denser media generally have n > 1.  
- **Mapping:** Refraction and Lenses · **Thin Lens Formula** ← incorrect for this stem  
- **Difficulty:** easy  

### SME Findings

- Academic mapping wrong: question tests **absolute refractive index / refraction**, not thin-lens formula.  
- Explanation wording “denser media generally have n > 1” needs clarity.  
- Do not change the question automatically.

### Scientific Status

**Answer B correct.** Mapping: **incorrect**. Explanation: **needs improvement** (not scientifically false that n > 1 for usual optical media vs vacuum, but wording is vague).

### Proposed Correction

**Mapping (primary fix):**

| Field | Current | Proposed |
|-------|---------|----------|
| Subject | Physics | Physics (unchanged) |
| Chapter | Optics | Optics (unchanged) |
| Topic | Refraction and Lenses | Refraction and Lenses (OK) **or** a dedicated Refraction topic if present in hierarchy |
| Concept | Thin Lens Formula | **Absolute refractive index / refraction** (confirm exact concept name & UUID in academic seed — e.g. refractive index, Snell’s law prerequisites). **Do not leave Thin Lens Formula.** |

**Content (optional wording cleanup — same Easy level):**

- **Stem:** (unchanged preferred) Absolute refractive index of a medium is:
- **Options:** unchanged A–D; **Answer:** B  
- **Explanation (proposed):** Absolute refractive index is n = c/v, where c is the speed of light in vacuum and v is the speed in the medium. For ordinary transparent media, v < c, so n > 1. Option A inverts the definition; n is not always less than 1; n is not “equal to wavelength only.”  
- **Difficulty:** easy  
- **Title:** Absolute refractive index (optional rename from “Refractive index”)

### Alternative

Mapping-only correction; leave stem/options/explanation as stored until a second SME pass on explanation tone.

### Reason

Assessment validity requires concept labels to match the skill tested. Thin Lens Formula belongs to lens equation items (e.g. PHY-10 redesign), not n = c/v.

### SME Approval Required

**Yes — mandatory before any DB change.** Critical mapping fix.

---

## PHY-09 — Coulomb force distance dependence

**ID:** `961327ff-e291-4c57-a5c2-4f2de51f9004`

### Current Question

- **Stem:** If the separation between two point charges is doubled, the Coulomb force becomes:
- **A.** 2 times  
- **B.** 4 times  
- **C.** 1/2  
- **D.** 1/4  
- **Answer:** D  
- **Explanation:** F ∝ 1/r², so doubling r reduces force to one-fourth.  
- **Mapping:** Coulomb's Law  
- **Difficulty:** easy  

### SME Findings

Correct 1/r² application but very easy; weak distractors. Prepare improved conceptual/application version.

### Scientific Status

**Correct** (D).

### Proposed Correction (application — Easy → light Medium; recommend **easy** if single factor, **medium** if two variables)

**Version recommended (Medium — two-factor):**

- **Title:** Coulomb force scaling  
- **Stem:** The Coulomb force between two point charges is F when they are separated by distance r. If both charges are doubled and the separation is also doubled, the new force is:
- **A.** F/4  
- **B.** F  
- **C.** 2F  
- **D.** 4F  
- **Answer:** B  
- **Explanation:** F ∝ q₁q₂/r². Doubling each charge multiplies the force by 4; doubling r multiplies by 1/4; net factor 1, so the force remains F.  
- **Difficulty:** medium  
- **Mapping:** unchanged  

### Alternative (keep Easy, better distractors)

- **Stem:** If the separation between two point charges is doubled, keeping charges fixed, the Coulomb force becomes:
- **A.** Twice  
- **B.** Four times  
- **C.** Half  
- **D.** One-fourth  
- **Answer:** D  
- **Explanation:** F ∝ 1/r²; (2r)² = 4r² ⇒ force becomes F/4. “Half” is the incorrect linear guess.  
- **Difficulty:** easy  

### Reason

Two-factor scaling is a common NEET trap (confusing q and r powers) without requiring lengthy calculation.

### SME Approval Required

**Yes.**

---

## PHY-10 — Convex lens power (**CRITICAL REDESIGN**)

**ID:** `18238e36-2102-4aea-acca-9c9709d0722e`

### Current Question

- **Title:** Convex lens power  
- **Stem:** A converging thin lens in air has:
- **A.** Negative focal length  
- **B.** Positive focal length  
- **C.** Zero focal length  
- **D.** Infinite power only  
- **Answer:** B  
- **Explanation:** In the usual sign convention for lenses in air, a converging lens has positive f.  
- **Mapping:** Refraction and Lenses · Thin Lens Formula  
- **Difficulty:** medium  

### SME Findings

- Title does not match (power vs focal-length sign).  
- Medium inappropriate for sign-recall.  
- Option D poor.  
- Mapping to Thin Lens Formula questionable.  
- Explanation too minimal.  
- Prepare redesigned **Medium** NEET item on lens power / focal length. **Do not apply.**

### Scientific Status

**Answer B correct** under usual Cartesian lens convention in air. Difficulty/title/mapping/distractor quality: **inadequate**.

### Proposed Correction (redesigned Medium)

- **Title:** Lens power and focal length  
- **Stem:** The power of a thin lens in air is +2.0 D. Its focal length is:
- **A.** +50 cm  
- **B.** −50 cm  
- **C.** +2.0 cm  
- **D.** +0.5 cm  
- **Answer:** A  
- **Explanation:** Power P (in dioptres) and focal length f (in metres) are related by P = 1/f. For P = +2.0 D, f = 1/2 = 0.5 m = +50 cm. Positive P means a converging lens; the focal length is positive in the usual sign convention for thin lenses in air. −50 cm would be a diverging lens of the same |f|; +2.0 cm and +0.5 cm misuse units.  
- **Difficulty:** medium  
- **Mapping proposal:**
  - Subject: Physics  
  - Chapter: Optics  
  - Topic: Refraction and Lenses  
  - Concept: **Lens power / focal length** (or equivalent KU — confirm UUID). Thin Lens Formula (1/v − 1/u = 1/f) is optional related context but **power P = 1/f** is the skill under test.

### Alternative (if SME prefers to keep sign convention Easy)

- **Title:** Sign of focal length (converging lens)  
- **Stem:** Under the Cartesian sign convention for thin lenses in air, a converging lens has:
- **A.** Negative focal length  
- **B.** Positive focal length  
- **C.** Zero focal length  
- **D.** Undefined focal length  
- **Answer:** B  
- **Explanation:** A converging thin lens in air is assigned a positive focal length in the Cartesian convention commonly used in school/NEET optics.  
- **Difficulty:** easy  
- **Mapping:** Lens power / focal length sign (not Thin Lens Formula unless no better KU exists)

### Reason

Proposed Medium item matches the title intent (power), requires unit conversion (D ↔ cm), and replaces “Infinite power only.” Alternative honestly lowers difficulty if only sign recall is desired.

### SME Approval Required

**Yes — mandatory.** Redesign must not be applied without human approval.

---

## Database safety verification

| Check | Result |
|-------|--------|
| Target DB | development `trinetra_db` (SELECT probe only) |
| Production | Not used |
| Writes | **Zero** |
| Status changes | **Zero** |
| Content changes | **Zero** |
| Submit / approve / publish | **None** |

This document is advisory only.

---

## SME approval gate (global)

**No proposal in this file may be written to CMS until an authorized human SME explicitly approves the chosen alternative per question and an authorized editor applies changes through the normal ECAEP workflow (edit → review → approve → publish as separate steps).**

END OF PROPOSALS.
