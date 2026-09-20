# PHY-01–PHY-10 Implementation Audit — WAVE-P0-11B

**Database:** `trinetra_db`  
**Committed:** `2026-08-31T18:29:16.359013+00:00`  
**Transaction:** `COMMITTED`  
**Rollback status:** `not triggered`  
**Actor user id:** `88914ce4-92d7-41c3-9187-0c1884f03cd0`  
**SME reference:** `docs/product/PHY_01_10_FINAL_SME_PROPOSALS.md + WAVE-P0-11B`  

## Summary table

| ID     | Updated | Mapping | Difficulty | Answer | Status |
| ------ | ------- | ------- | ---------- | ------ | ------ |
| PHY-01 | yes | Parallel Plate Capacitor | easy | B | DRAFT |
| PHY-02 | yes | Principal Focus of Spherical Mirror | easy | C | DRAFT |
| PHY-03 | yes | Parallel Plate Capacitor | medium | B | DRAFT |
| PHY-04 | yes | Spherical Mirror Formula | easy | B | DRAFT |
| PHY-05 | yes | Parallel Plate Capacitor | medium | B | DRAFT |
| PHY-06 | yes | Spherical Mirror Formula | easy | B | DRAFT |
| PHY-07 | yes | Coulomb's Law | easy | C | DRAFT |
| PHY-08 | yes | Refractive Index | easy | B | DRAFT |
| PHY-09 | yes | Coulomb's Law | medium | B | DRAFT |
| PHY-10 | yes | Lens Power and Focal Length | medium | A | DRAFT |

## Validation

- Structural validation (assert_body_publishable): **PASS**
- All remain DRAFT: **True**
- Provenance model_used unchanged: **True**
- Unrelated questions modified: **0**
- Audit log action: `content.sme_edit` count **10**

## Per-question before/after

### PHY-01

- **ID:** `8721e193-2d6e-433a-81d9-ceb2b31aef01`
- **Changed fields:** title, stem, A, B, C, D, explanation
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `ed6aa3df52eb0383aea065eefe283aa4d1b78d690e52b6472cc618d708fa21fa`
- **After body SHA:** `397cf069179194939e73d08dcd5c74f59e702d9dfbe176459be2e6b99b6e96f5`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `bc925ef0-1e6e-4192-9e73-9a8f0b55b08e`

**After stem:** Capacitance of a vacuum parallel-plate capacitor is proportional to:

**After options:** A. Separation between plates only · B. Area of plates / separation between plates · C. Square of the plate area · D. Product of plate area and separation

**Answer:** B · **Difficulty:** easy

**Explanation:** For a vacuum parallel-plate capacitor, C = ε₀A/d, so C ∝ A/d. Options that depend only on separation, on A², or on A·d do not match this dependence.

**Mapping:** Physics / Electrostatics / Capacitance / Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)

---

### PHY-02

- **ID:** `f51bd10d-70c1-4bc1-98f3-490f723ec549`
- **Changed fields:** title, C, D, explanation, concept_id
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `00e8ea11f86591a7373391faf4037fdaca5e52578015ffdc48e7f0ca422504fb`
- **After body SHA:** `4786d9ed4f5935031c2eb2dabdaa706078d8b96724c7d6ed873509796903ed66`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `647ea9ff-7ecf-433f-b224-040562a82ff2`

**After stem:** Rays parallel to the principal axis of a concave mirror, after reflection, pass through:

**After options:** A. Centre of curvature · B. Pole · C. Principal focus · D. Midpoint between pole and centre of curvature only if the aperture is large

**Answer:** C · **Difficulty:** easy

**Explanation:** By definition, paraxial rays parallel to the principal axis converge, after reflection from a concave mirror, at the principal focus. The centre of curvature applies to rays directed toward C; the pole lies on the mirror surface.

**Mapping:** Physics / Optics / Reflection and Mirrors / Principal Focus of Spherical Mirror (`9f91ab55-6fb7-41b9-beb3-60400693fe20`)

---

### PHY-03

- **ID:** `fbfa14ed-b9cc-4016-8c4b-d08f997ecdd6`
- **Changed fields:** title, stem, A, B, C, D, explanation
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `c696ef74b7ab00dda873d1218afed16110cbb870c052666a516b9f702b67fac8`
- **After body SHA:** `6eb1160479a2a87b93077b4f67aee62f6bf0dad385f4919c596e0e8a48719dd1`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `f1ab5c96-b9fb-4871-88c4-6ed614344674`

**After stem:** A parallel-plate capacitor is charged by a battery and then disconnected. A dielectric of dielectric constant K > 1 is then inserted to completely fill the gap. Which statement is correct?

**After options:** A. Capacitance decreases and charge on the plates increases · B. Capacitance increases, charge on the plates remains constant, and potential difference decreases · C. Capacitance and potential difference both remain constant · D. Capacitance becomes infinite and energy stored becomes zero

**Answer:** B · **Difficulty:** medium

**Explanation:** After disconnection, charge Q on the plates is fixed. Inserting the dielectric increases capacitance to C′ = KC. From V = Q/C, the potential difference decreases. Capacitance does not become infinite for finite K; charge does not increase after disconnection.

**Mapping:** Physics / Electrostatics / Capacitance / Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)

---

### PHY-04

- **ID:** `4d0ab71e-a997-4ac1-ad17-ba24f030a19c`
- **Changed fields:** title, stem, C, D, explanation
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `c40745286970d43b54238ce065ceafe53c47ef4d538405d02e1780dad8506adc`
- **After body SHA:** `88b1badfc8226970169225bd1c4d587de1fe0795dae4de5de83d8d1a41652110`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `a75a7f85-50e3-4002-b49e-bcf71bd92b37`

**After stem:** Under the Cartesian sign convention used for spherical mirrors, the mirror formula is:

**After options:** A. 1/v − 1/u = 1/f · B. 1/v + 1/u = 1/f · C. 1/f = 1/u − 1/v · D. f = (u + v)/2

**Answer:** B · **Difficulty:** easy

**Explanation:** The standard spherical-mirror relation is 1/v + 1/u = 1/f (Cartesian signs). Option A is a difference form that is not the usual mirror formula; C rearranges incorrectly; D is not the mirror formula.

**Mapping:** Physics / Optics / Reflection and Mirrors / Spherical Mirror Formula (`a44cd8ef-9881-4812-9848-bac03dde7e61`)

---

### PHY-05

- **ID:** `f7b0f62f-1fcb-4a69-9052-455e00f7cb84`
- **Changed fields:** title, stem, A, B, C, D, explanation, difficulty
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `29a7b2d0765c88a8d23562d4ccb5206482ccd6ecfe7e814c606ec256a763f247`
- **After body SHA:** `d449af3bb2d5516fe37d323bda1f07a2795e331d6dd96d426a44fe01ffb4914a`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `300166c5-f27c-4ed8-920a-e42f4e14a6d3`

**After stem:** A capacitor of capacitance C carries charge Q. If the capacitance is doubled while the charge remains constant, the energy stored becomes:

**After options:** A. Twice the original energy · B. Half the original energy · C. Four times the original energy · D. Unchanged

**Answer:** B · **Difficulty:** medium

**Explanation:** With charge fixed, U = Q²/(2C). Doubling C halves U. (If voltage were fixed instead, U = ½CV² would double — that is a different constraint.)

**Mapping:** Physics / Electrostatics / Capacitance / Parallel Plate Capacitor (`29560b80-2c9d-4093-98cf-9ee7533fba3a`)

---

### PHY-06

- **ID:** `9a0ae17f-38f3-4141-8dad-389ae265195c`
- **Changed fields:** title, stem, A, B, C, D, explanation
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `ce1b9f9035bf62ce037288560dad27ac62ad41b2c4fedc37f1d9dfe0d0133abd`
- **After body SHA:** `47c4f8d5a0e8bd2cca8f386cce8cf1d7edb98dfa0fa538c534e327c86d6f671e`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `55ba6a49-9282-40ab-af9b-c4584aadf75f`

**After stem:** For a spherical mirror of small aperture, the focal length f is related to the radius of curvature R approximately by:

**After options:** A. f = R · B. f = R/2 · C. f = 2R · D. f = √R

**Answer:** B · **Difficulty:** easy

**Explanation:** Under the paraxial (small-aperture) approximation, f = R/2 for a spherical mirror.

**Mapping:** Physics / Optics / Reflection and Mirrors / Spherical Mirror Formula (`a44cd8ef-9881-4812-9848-bac03dde7e61`)

---

### PHY-07

- **ID:** `4b928b5f-da43-4361-89db-312b6c6950a4`
- **Changed fields:** title, stem, A, B, C, D, correct_option, explanation
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `ac57cbb888871ac0ea9036571b0bb6427490b2206c3c3c3064d127aeb8132221`
- **After body SHA:** `1d235e2eeb13c46342a78333d45f79c46e1c92a31a61057b17626b81e0d3e7a3`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `da466c47-ab81-49ac-866b-2bda3a89c713`

**After stem:** Two equal positive point charges are fixed on the x-axis at x = −a and x = +a (a > 0). A third positive point charge is placed at the origin (x = 0). The net electrostatic force on the charge at the origin is:

**After options:** A. Along the positive x-direction · B. Along the negative x-direction · C. Zero · D. Perpendicular to the x-axis

**Answer:** C · **Difficulty:** easy

**Explanation:** By Coulomb's law, the force from the charge at +a on the positive test charge at the origin is equal in magnitude to the force from the charge at −a, and the two forces are opposite along the x-axis. By superposition, the vector sum is zero.

**Mapping:** Physics / Electrostatics / Electric Charge and Coulomb's Law / Coulomb's Law (`38563952-1621-4afa-b82d-4804adbfb18b`)

---

### PHY-08

- **ID:** `6d7b9e60-e56f-46e0-b553-654aba9c4a47`
- **Changed fields:** title, explanation, concept_id
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `74f77412ffd9dc686e12b231f9e9e31abb5e55d9ebf5fc043cb2c0d4ca7547a2`
- **After body SHA:** `3f2c26e0e6be50b73dd9e036190a166a6992d31d3e453bc3394072409adbf153`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `abf58ecf-18f1-4814-b22f-23e24fdd9f46`

**After stem:** Absolute refractive index of a medium is:

**After options:** A. Speed of light in medium / speed in vacuum · B. Speed of light in vacuum / speed in medium · C. Always less than 1 · D. Equal to wavelength only

**Answer:** B · **Difficulty:** easy

**Explanation:** Absolute refractive index is defined as n = c/v, where c is the speed of light in vacuum and v is the speed of light in the medium. Option A inverts this definition. Absolute refractive index is not "always less than 1," and it is not equal to wavelength alone.

**Mapping:** Physics / Optics / Refraction and Lenses / Refractive Index (`537dff93-6e0a-4a5c-9a58-2ebac1b4eea8`)

---

### PHY-09

- **ID:** `961327ff-e291-4c57-a5c2-4f2de51f9004`
- **Changed fields:** title, stem, A, B, C, D, correct_option, explanation, difficulty
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `cdb3844386cf6fec4f4f249d493f414b02dfc72198befa3c28274dbd076be84b`
- **After body SHA:** `15ae090762ca3c1c05f4960c6b52b8c77a23f408bdda049971c11611d715df5a`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `be182728-3de3-4275-8ccb-e55f4dad0379`

**After stem:** The Coulomb force between two point charges is F when they are separated by distance r. If both charges are doubled and the separation is also doubled, the new force is:

**After options:** A. F/4 · B. F · C. 2F · D. 4F

**Answer:** B · **Difficulty:** medium

**Explanation:** F ∝ q₁q₂ / r². New force F′ ∝ (2q₁)(2q₂) / (2r)² = 4 q₁q₂ / (4 r²) = q₁q₂ / r² ∝ F. Therefore F′ = F.

**Mapping:** Physics / Electrostatics / Electric Charge and Coulomb's Law / Coulomb's Law (`38563952-1621-4afa-b82d-4804adbfb18b`)

---

### PHY-10

- **ID:** `18238e36-2102-4aea-acca-9c9709d0722e`
- **Changed fields:** title, stem, A, B, C, D, correct_option, explanation, concept_id
- **Unchanged (status/provenance):** status=DRAFT, model_used=`human-authored-batch-a`
- **Before body SHA:** `0c974fae4c1c943e9db603045f284a57a0de2b68ee40d4511119cc0ee7e97a19`
- **After body SHA:** `46d80ee45c20e7a244a7788138834b6f5b2778c9a291b9c1df344f8360c8958a`
- **Item version:** 1 → 2
- **Content version_no:** 1 → 2
- **Audit log id:** `281900e3-db78-4e0a-8cd4-e12a67e44979`

**After stem:** Two thin lenses in contact in air have powers +2.0 D and −0.5 D. The focal length of the combination is:

**After options:** A. +0.67 m · B. +2.5 m · C. −2.0 m · D. +0.40 m

**Answer:** A · **Difficulty:** medium

**Explanation:** For thin lenses in contact, powers add: P = P₁ + P₂ = 2.0 + (−0.5) = +1.5 D. Focal length of the combination is f = 1/P = 1/1.5 m = 2/3 m ≈ +0.67 m. The positive net power means a converging combination. Option B uses 1/(2.0−0.5) incorrectly as if subtracting focal lengths; D is 1/2.5; C has the wrong sign/magnitude.

**Mapping:** Physics / Optics / Refraction and Lenses / Lens Power and Focal Length (`77aa17aa-8f6b-4604-bad0-691b1172e5e8`)

---

## Tests

Passed: `test_phy_sme_edits`, `test_editorial_review`, `test_practice_availability`, `test_optics_gap_concepts`, `test_batch_a_pilot` (and related editorial suite).

Also corrected review-packet so Batch-A provenance display_note applies only when `is_batch_a` is true.

## Notes

Content-only wave. No submit / approve / publish. Next step: human ECAEP review.
