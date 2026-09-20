# Physics PHY-01–PHY-10 — Final SME Proposals (Refined)

**Status:** PROPOSAL ONLY — **not applied** to any database.  
**Pilot:** `batch-a-sme-pilot-40`  
**Batch:** `acquisition-batch-A-diversify-p0`  
**Hierarchy audit DB:** development `trinetra_db` (SELECT only)  
**Export basis:** `docs/product/ECAEP_SME_REVIEW_PHY_01_10.md`

Provenance remains as stored for all items: `human-authored-batch-a` · SME review required · **not** official NTA/NEET/NCERT.  
No NCERT citations invented. No academic UUIDs invented.

---

## Hierarchy findings (read-only)

Under **Physics → Optics**, the live seed currently contains **exactly three** concepts:

| Chapter | Topic | Concept (existing) | Concept UUID |
|---------|-------|--------------------|--------------|
| Optics | Reflection and Mirrors | Spherical Mirror Formula | `a44cd8ef-9881-4812-9848-bac03dde7e61` |
| Optics | Refraction and Lenses | Thin Lens Formula | `dea4d8e9-aa27-45e3-b142-04a1d1a6b98b` |
| Optics | Wave Optics Basics | Young's Double Slit | `77964f04-bd90-4cef-9b64-4b810b01ae6d` |

### Gaps relevant to this packet

| Needed for | Desired KU themes | Existing match? |
|------------|-------------------|-----------------|
| PHY-02 | principal focus · reflection at spherical mirrors · parallel rays | **No dedicated concept.** Closest existing: `Spherical Mirror Formula` (same topic). |
| PHY-08 | refractive index · absolute refractive index · refraction | **No dedicated concept.** Must **not** use `Thin Lens Formula`. Topic `Refraction and Lenses` exists without a refractive-index KU. |
| PHY-10 | lens power · P = 1/f · sign/magnitude of power | **No dedicated “Lens power” concept.** Only `Thin Lens Formula` under Refraction and Lenses. |

**Recommendation (process, not a write):** seed missing concepts under the existing topics before remapping PHY-08 (mandatory) and preferably PHY-02 / PHY-10. Until then, proposals below state interim vs blocked mapping explicitly.

Electrostatics concepts used by PHY-01/03/05/07/09 exist and are adequate (`Parallel Plate Capacitor`, `Coulomb's Law`).

---

## PHY-01

**ID:** `8721e193-2d6e-433a-81d9-ceb2b31aef01`

### Current question

- Stem: Capacitance of a parallel plate capacitor (vacuum) is proportional to:
- A. d/A · B. A/d · C. A·d · D. 1/(A·d)
- Answer: **B** · Difficulty: easy  
- Mapping: Physics · Electrostatics · Capacitance · Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)

### SME decision

Use **improved-distractor** version. Retain Easy, answer B, existing mapping. **No** numerical alternative.

### Final proposed version

- **Title:** Parallel plate capacitance dependence  
- **Stem:** Capacitance of a vacuum parallel-plate capacitor is proportional to:  
- **A.** Separation between plates only  
- **B.** Area of plates / separation between plates  
- **C.** Square of the plate area  
- **D.** Product of plate area and separation  
- **Answer:** B  
- **Explanation:** For a vacuum parallel-plate capacitor, C = ε₀A/d, so C ∝ A/d. Options that depend only on separation, on A², or on A·d do not match this dependence.  
- **Difficulty:** easy  
- **Proposed academic mapping:** unchanged — Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)

### Reason

Removes reciprocal “junk” distractors while keeping Easy recognition demand.

### Hierarchy dependency

None.

### SME approval required

**Yes** before any database edit.

---

## PHY-02

**ID:** `f51bd10d-70c1-4bc1-98f3-490f723ec549`

### Current question

- Stem: Rays parallel to the principal axis of a concave mirror, after reflection, pass through:
- A. Centre of curvature · B. Pole · C. Focus · D. Infinity only  
- Answer: **C** · Difficulty: easy  
- Mapping: Reflection and Mirrors · **Spherical Mirror Formula** (`a44cd8ef-9881-4812-9848-bac03dde7e61`)

### SME decision

Improved distractor (replace “Infinity only”). Prefer concept for principal focus / parallel-ray reflection if it exists.

### Final proposed version (content)

- **Title:** Concave mirror principal focus  
- **Stem:** Rays parallel to the principal axis of a concave mirror, after reflection, pass through:  
- **A.** Centre of curvature  
- **B.** Pole  
- **C.** Principal focus  
- **D.** Midpoint between pole and centre of curvature only if the aperture is large  
- **Answer:** C  
- **Explanation:** By definition, paraxial rays parallel to the principal axis converge, after reflection from a concave mirror, at the principal focus. The centre of curvature applies to rays directed toward C; the pole lies on the mirror surface.  
- **Difficulty:** easy  

### Proposed academic mapping

| Preference | Mapping |
|------------|---------|
| **Ideal** | Concept for principal focus / parallel-ray reflection at spherical mirrors — **does not exist in current hierarchy (GAP).** |
| **Interim (until KU seeded)** | Keep topic Reflection and Mirrors; concept remains existing **Spherical Mirror Formula** (`a44cd8ef-9881-4812-9848-bac03dde7e61`) with editorial note that the label is broader than ideal. |
| **Blocked** | Do **not** invent a UUID. |

### Reason

Fixes weak distractor D; option C wording matches the definition tested.

### Hierarchy dependency

**Gap:** no dedicated principal-focus KU. Content can ship after approval with interim mapping; remap when a suitable concept is seeded.

### SME approval required

**Yes** (content + whether to accept interim mapping).

---

## PHY-03

**ID:** `fbfa14ed-b9cc-4016-8c4b-d08f997ecdd6`

### Current question

- Stem: Inserting a dielectric of dielectric constant K > 1 between capacitor plates (battery disconnected) generally:
- A. Decreases capacitance · B. Increases capacitance · C. Leaves capacitance unchanged · D. Makes capacitance infinite  
- Answer: **B** · Difficulty: medium (SME: inappropriate for this stem)

### SME decision

**Alternative B** — disconnected battery must be meaningful; test C↑, Q constant, V↓; difficulty **MEDIUM**.

### Final proposed version

- **Title:** Dielectric after battery disconnection  
- **Stem:** A parallel-plate capacitor is charged by a battery and then **disconnected**. A dielectric of dielectric constant K > 1 is then inserted to completely fill the gap. Which statement is correct?  
- **A.** Capacitance decreases and charge on the plates increases  
- **B.** Capacitance increases, charge on the plates remains constant, and potential difference decreases  
- **C.** Capacitance and potential difference both remain constant  
- **D.** Capacitance becomes infinite and energy stored becomes zero  
- **Answer:** B  
- **Explanation:** After disconnection, charge Q on the plates is fixed. Inserting the dielectric increases capacitance to C′ = KC. From V = Q/C, the potential difference decreases. Capacitance does not become infinite for finite K; charge does not increase after disconnection.  
- **Difficulty:** medium  
- **Proposed academic mapping:** unchanged — Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)

### Reason

Requires knowing which quantity is constrained (Q) and relating C, Q, and V — genuine Medium, not inflated Hard.

### Hierarchy dependency

None.

### SME approval required

**Yes.**

---

## PHY-04

**ID:** `4d0ab71e-a997-4ac1-ad17-ba24f030a19c`

### Current question

- Stem: The spherical mirror formula is:
- A. 1/v − 1/u = 1/f · B. 1/v + 1/u = 1/f · C. v + u = f · D. vu = f  
- Answer: **B** · Difficulty: easy · Mapping: Spherical Mirror Formula (`a44cd8ef-…`)

### SME decision

Stronger-distractor formula version. Retain Easy, answer B, existing mapping (hierarchy audit supports it).

### Final proposed version

- **Title:** Spherical mirror formula  
- **Stem:** Under the Cartesian sign convention used for spherical mirrors, the mirror formula is:  
- **A.** 1/v − 1/u = 1/f  
- **B.** 1/v + 1/u = 1/f  
- **C.** 1/f = 1/u − 1/v  
- **D.** f = (u + v)/2  
- **Answer:** B  
- **Explanation:** The standard spherical-mirror relation is 1/v + 1/u = 1/f (Cartesian signs). Option A is a difference form that is not the usual mirror formula; C rearranges incorrectly; D is not the mirror formula.  
- **Difficulty:** easy  
- **Proposed academic mapping:** Spherical Mirror Formula (`a44cd8ef-9881-4812-9848-bac03dde7e61`) — **confirmed appropriate**

### Reason

Same Easy recall skill with less trivial algebra distractors.

### Hierarchy dependency

None.

### SME approval required

**Yes.**

---

## PHY-05

**ID:** `f7b0f62f-1fcb-4a69-9052-455e00f7cb84`

### Current question

- Stem: Energy stored in a capacitor charged to voltage V is:
- A. CV · B. ½CV² · C. C²V · D. 2CV²  
- Answer: **B** · Difficulty: **hard** (incorrect classification)

### SME decision

Do **not** auto-apply the previous Hard redesign. Provide **two** alternatives; SME chooses.

---

### Alternative A — reclassify only (Easy)

- **Stem / options / answer / explanation / mapping:** **unchanged** from current stored content  
- **Difficulty:** easy  
- **Proposed academic mapping:** Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)  
- **Reason:** Cognitive demand is formula recognition → Easy, not Hard.

---

### Alternative B — genuine MEDIUM (energy with a constrained change)

- **Title:** Capacitor energy at constant charge  
- **Stem:** A capacitor of capacitance C carries charge Q. If the capacitance is doubled while the charge remains constant, the energy stored becomes:  
- **A.** Twice the original energy  
- **B.** Half the original energy  
- **C.** Four times the original energy  
- **D.** Unchanged  
- **Answer:** B  
- **Explanation:** With charge fixed, U = Q²/(2C). Doubling C halves U. (If voltage were fixed instead, U = ½CV² would double — that is a different constraint.)  
- **Difficulty:** medium  
- **Proposed academic mapping:** Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)  
- **Reason:** One conceptual branch (which quantity is fixed) plus substitution — Medium, not multi-stage Hard.

---

### Note on Hard

A Hard item would need substantially more than two-step substitution (e.g. combined dielectric + series/parallel network + energy comparison). **No Hard proposal is forced here.**

### Hierarchy dependency

None.

### SME approval required

**Yes — choose Alternative A or B** before any DB change.

---

## PHY-06

**ID:** `9a0ae17f-38f3-4141-8dad-389ae265195c`

### Current question

- Stem: For a spherical mirror of small aperture, f is approximately:
- A. R · B. R/2 · C. 2R · D. R/4 · Answer **B** · easy · Spherical Mirror Formula

### SME decision

Clearer wording; retain Easy; f ≈ R/2; foundation-level; do not overcomplicate.

### Final proposed version

- **Title:** Focal length and radius of curvature  
- **Stem:** For a spherical mirror of small aperture, the focal length f is related to the radius of curvature R approximately by:  
- **A.** f = R  
- **B.** f = R/2  
- **C.** f = 2R  
- **D.** f = √R  
- **Answer:** B  
- **Explanation:** Under the paraxial (small-aperture) approximation, f = R/2 for a spherical mirror.  
- **Difficulty:** easy  
- **Proposed academic mapping:** Spherical Mirror Formula (`a44cd8ef-9881-4812-9848-bac03dde7e61`)

### Reason

Foundation relation with slightly clearer stem and one non-ratio distractor (√R) without raising difficulty.

### Hierarchy dependency

None (same note as PHY-02: ideal “focus geometry” KU does not exist; formula KU is acceptable for f–R).

### SME approval required

**Yes.**

---

## PHY-07

**ID:** `4b928b5f-da43-4361-89db-312b6c6950a4`

### Current question

- Stem: Two like point charges placed in vacuum will: … Answer **B** (repel) · easy

### SME decision

Conceptual **symmetry** version; geometry precise; answer **ZERO**; difficulty **EASY**; explain superposition.

### Final proposed version

- **Title:** Net force at midpoint of two like charges  
- **Stem:** Two equal positive point charges are fixed on the x-axis at x = −a and x = +a (a > 0). A third positive point charge is placed at the origin (x = 0). The net electrostatic force on the charge at the origin is:  
- **A.** Along the positive x-direction  
- **B.** Along the negative x-direction  
- **C.** Zero  
- **D.** Perpendicular to the x-axis  
- **Answer:** C  
- **Explanation:** By Coulomb’s law, the force from the charge at +a on the positive test charge at the origin is equal in magnitude to the force from the charge at −a, and the two forces are opposite along the x-axis. By superposition, the vector sum is zero.  
- **Difficulty:** easy  
- **Proposed academic mapping:** Coulomb's Law (`38563952-1621-4afa-b82d-4804adbfb18b`)

### Reason

Tests superposition/symmetry at Easy depth; geometry is fully specified (equal charges, symmetric placement, positive test charge at origin).

### Hierarchy dependency

None.

### SME approval required

**Yes.**

---

## PHY-08 (**mandatory mapping correction**)

**ID:** `6d7b9e60-e56f-46e0-b553-654aba9c4a47`

### Current question

- Stem: Absolute refractive index of a medium is:
- A. Speed of light in medium / speed in vacuum  
- B. Speed of light in vacuum / speed in medium  
- C. Always less than 1  
- D. Equal to wavelength only  
- Answer: **B** · easy  
- **Current concept: Thin Lens Formula (`dea4d8e9-…`) — INCORRECT**

### SME decision

Mandatory remapping away from Thin Lens Formula. Improved explanation with n = c/v. Retain Easy, answer B. Query hierarchy for refractive-index KU.

### Final proposed version (content)

- **Title:** Absolute refractive index  
- **Stem:** Absolute refractive index of a medium is:  
- **A.** Speed of light in medium / speed in vacuum  
- **B.** Speed of light in vacuum / speed in medium  
- **C.** Always less than 1  
- **D.** Equal to wavelength only  
- **Answer:** B  
- **Explanation:** Absolute refractive index is defined as n = c/v, where c is the speed of light in vacuum and v is the speed of light in the medium. Option A inverts this definition. Absolute refractive index is not “always less than 1,” and it is not equal to wavelength alone.  
- **Difficulty:** easy  

### Proposed academic mapping

| Layer | Proposal |
|-------|----------|
| Subject | Physics |
| Chapter | Optics |
| Topic | Refraction and Lenses (existing topic — OK for refraction themes) |
| Concept | **GAP — no existing “refractive index” / “absolute refractive index” concept UUID in `trinetra_db`.** |
| Must not use | Thin Lens Formula (`dea4d8e9-aa27-45e3-b142-04a1d1a6b98b`) |

**Hierarchy dependency (blocking for correct remap):** seed a concept such as “Absolute refractive index” (or equivalent) under `Refraction and Lenses`, then map this item to that **real** UUID. Until seeded, **do not** “fix” Thin Lens Formula and **do not invent** a UUID.

### Reason

Definition n = c/v is Easy; mapping must match the skill tested.

### SME approval required

**Yes.** Content explanation can be approved independently of KU seed; remap must wait for hierarchy work.

---

## PHY-09

**ID:** `961327ff-e291-4c57-a5c2-4f2de51f9004`

### Current question

- Stem: If the separation between two point charges is doubled, the Coulomb force becomes: … Answer **D** (1/4) · easy

### SME decision

Two-variable scaling; F unchanged; **MEDIUM**; verify maths.

### Final proposed version

- **Title:** Coulomb force two-factor scaling  
- **Stem:** The Coulomb force between two point charges is F when they are separated by distance r. If both charges are doubled and the separation is also doubled, the new force is:  
- **A.** F/4  
- **B.** F  
- **C.** 2F  
- **D.** 4F  
- **Answer:** B  
- **Explanation:** F ∝ q₁q₂ / r². New force F′ ∝ (2q₁)(2q₂) / (2r)² = 4 q₁q₂ / (4 r²) = q₁q₂ / r² ∝ F. Therefore F′ = F.  
- **Difficulty:** medium  
- **Proposed academic mapping:** Coulomb's Law (`38563952-1621-4afa-b82d-4804adbfb18b`)

### Reason

Two simultaneous scalings (numerator ×4, denominator ×4) is Medium reasoning; not mere single-factor 1/r² recall.

### Hierarchy dependency

None.

### SME approval required

**Yes.**

---

## PHY-10

**ID:** `18238e36-2102-4aea-acca-9c9709d0722e`

### Current question

- Title “Convex lens power” vs stem about converging-lens focal-length sign; answer B; difficulty medium (too high for sign recall); distractor D weak; mapped to Thin Lens Formula.

### SME decision

Do **not** use +2 D → +50 cm as the sole final Medium item. Provide a genuine Medium lens-power question with ≥2 reasoning elements; align title/stem/options/mapping; query hierarchy.

### Final proposed version (genuinely Medium)

- **Title:** Combined thin-lens power  
- **Stem:** Two thin lenses in contact in air have powers +2.0 D and −0.5 D. The focal length of the combination is:  
- **A.** +0.67 m  
- **B.** +2.5 m  
- **C.** −2.0 m  
- **D.** +0.40 m  
- **Answer:** A  
- **Explanation:** For thin lenses in contact, powers add: P = P₁ + P₂ = 2.0 + (−0.5) = +1.5 D. Focal length of the combination is f = 1/P = 1/1.5 m = 2/3 m ≈ +0.67 m. The positive net power means a converging combination. Option B uses 1/(2.0−0.5) incorrectly as if subtracting focal lengths; D is 1/2.5; C has the wrong sign/magnitude.  
- **Difficulty:** medium  

**Reasoning elements:** (1) add signed powers for lenses in contact; (2) convert net power to focal length with correct sign/units.

### Proposed academic mapping

| Layer | Proposal |
|-------|----------|
| Subject | Physics |
| Chapter | Optics |
| Topic | Refraction and Lenses |
| Concept | **GAP — no dedicated “Lens power” KU.** Closest existing: Thin Lens Formula (`dea4d8e9-aa27-45e3-b142-04a1d1a6b98b`) — **only partial fit** (formula family adjacent to power, but P = 1/f / combination not named). |
| Ideal | Seed “Lens power” (or “Power of a lens”) under Refraction and Lenses, then map to that real UUID. |

### Alternative Medium (comparison of signs — if SME prefers simpler two-step)

- **Title:** Comparing lens powers  
- **Stem:** Lens X has power +2 D and lens Y has power −2 D (thin lenses in air). Which statement is correct?  
- **A.** Both are converging and have equal focal lengths  
- **B.** X is converging with f = +0.5 m; Y is diverging with f = −0.5 m  
- **C.** Both have f = +2 m  
- **D.** X has f = −0.5 m and Y has f = +0.5 m  
- **Answer:** B  
- **Explanation:** P = 1/f with f in metres. For X, f = 1/(+2) = +0.5 m (converging). For Y, f = 1/(−2) = −0.5 m (diverging). Equal |P| ⇒ equal |f| with opposite signs.  
- **Difficulty:** medium  
- **Mapping:** same hierarchy dependency as above  

### Hierarchy dependency

**Gap** for lens-power KU. Prefer seeding before final remap; interim use of Thin Lens Formula only if SME explicitly accepts partial fit — **do not invent UUID**.

### SME approval required

**Yes** (choose combined-power vs comparison variant + mapping path).

---

## Packet checklist (refined)

| ID | Final intent | Difficulty | Mapping status |
|----|--------------|------------|----------------|
| PHY-01 | Improved distractors | Easy | OK (existing) |
| PHY-02 | Improved distractors | Easy | Interim Spherical Mirror Formula; **gap** for principal-focus KU |
| PHY-03 | Battery-disconnected dielectric (Alt B) | Medium | OK |
| PHY-04 | Stronger formula distractors | Easy | OK |
| PHY-05 | **A** reclass Easy **or** **B** Medium energy | Easy / Medium | OK |
| PHY-06 | Clearer f = R/2 wording | Easy | OK |
| PHY-07 | Symmetry / net force zero | Easy | OK |
| PHY-08 | Explanation + **mandatory remap** | Easy | **GAP — cannot stay on Thin Lens Formula** |
| PHY-09 | Two-factor Coulomb scaling | Medium | OK |
| PHY-10 | Combined powers → f (or sign comparison) | Medium | **GAP — prefer Lens power KU** |

---

## Database safety

| Check | Result |
|-------|--------|
| Database | `trinetra_db` (development) |
| Operations | Hierarchy SELECT only |
| Question writes | **Zero** |
| Status changes | **Zero** |
| Submit / approve / publish | **None** |

---

## Global approval gate

**No proposal in this file may be written to CMS until an authorized human SME explicitly approves the chosen text (and PHY-05 alternative), and hierarchy gaps for PHY-08 (and preferably PHY-02 / PHY-10) are resolved with real concept UUIDs.**

END OF FINAL PROPOSALS.
