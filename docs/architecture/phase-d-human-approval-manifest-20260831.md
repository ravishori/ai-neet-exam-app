# Phase D.5A — Human-Approval Manifest

**Banner:** HUMAN-APPROVAL MANIFEST ONLY — NO DATABASE CHANGES — NO ECAEP ACTION — NO PUBLICATION

**Phase:** D.5A
**Generated:** 2026-08-31T13:46:59.399650+00:00
**Database:** trinetra_db
**Pilot:** phase-d-30-mcq-authorized-20260825

---

## Release boundary

`	ext
Only explicitly approved items may be applied in Phase D.5B.
No implied approval.
No approval-by-default.
No "apply all proposals."
Do not proceed to Phase D.5B automatically.
`

---

## Live verification (read-only)

- Questions: **30**
- DRAFT: **30**
- PUBLISHED: **0**

## Proposed final set

`	ext
21 unchanged originals
+ 1 KEEP
+ 6 REVISE
+ 2 REPLACE
= 30 candidate questions
`

Questions requiring human decision: **9**
Taxonomy concepts requiring human decision: **1**

---

## Taxonomy proposal (SEPARATE)

`	ext
Taxonomy creation = SEPARATE APPROVAL REQUIRED
`

| Field | Value |
|-------|-------|
| Name | Limiting Factors (Blackman's Law) |
| Code | limiting-factors |
| Parent | factors-affecting-photosynthesis |
| Subject | BOTANY |
| Chapter | photosynthesis |
| NCERT | Class 11 Biology Chapter 11 §11.10 |
| Affected | e6b9fb1e, 8d50e829 |

**Remap rule:** Do not apply concept remap for Blackman items until this concept is explicitly approved **and** created.

### HUMAN DECISION — Taxonomy

- [ ] APPROVE NEW CONCEPT
- [ ] REJECT NEW CONCEPT

Reviewer comments:

Reviewer:

Review date:

---

## Versioning & KU rules (plan only)

For every **REVISE / REPLACE**:

`	ext
old version_no
new version_no = old + 1
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
existing KU relationship(s) → copied to new content_version
`

**Why KU copy is required:** CMS pilot filter joins latest_version_id → content_version_knowledge_units. Failing to copy can drop the revised question from pilot lineage/filter.

Prefer: ContentWorkflowService.update_draft (plus explicit KU copy). **Do not create versions in D.5A.**

---

## Index of changes

| # | ID | Action | Subject | Versioning | Special |
|--:|----|--------|---------|------------|---------|
| 1 | e6b9fb1e | KEEP | BOTANY | no new version | taxonomy deferred |
| 2 | 8d50e829 | REVISE | BOTANY | v1→v2 | taxonomy deferred |
| 3 | 85fee888 | REPLACE | BOTANY | v1→v2 | pathway consequences; ans B |
| 4 | 87f621ab | REVISE | CHEMISTRY | v1→v2 |  |
| 5 | 863f1289 | REVISE | CHEMISTRY | v1→v2 |  |
| 6 | ade9900b | REVISE | PHYSICS | v1→v2 | metadata → ohms-law |
| 7 | c7a54ae9 | REPLACE | PHYSICS | v1→v2 | fixed-R: HUMAN DECISION REQUIRED |
| 8 | 7b80d6db | REVISE | PHYSICS | v1→v2 | answer A preserved |
| 9 | a42a3589 | REVISE | PHYSICS | v1→v2 |  |

---

## Change detail (9)

### 1. e6b9fb1e-f022-4172-88c5-318213bc511b — **KEEP**

- **current_content_version_id:** f89eded3-f96a-4f98-ae81-bb4022353c48
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=f89eded3… latest=f89eded3… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** BOTANY / photosynthesis / factors-affecting-photosynthesis / photorespiration
- **Difficulty / Answer:** easy / **A**
- **Stem:** According to Blackman's Law of Limiting Factors (1905), which of the following correctly defines the 'limiting factor' in a chemical process affected by multiple factors?
- **Options:**
`	ext
  A. The factor that is nearest to its minimal value and directly controls the rate of the process
  B. The factor present in the highest concentration that accelerates the process
  C. The factor that remains constant while all other factors vary
  D. The factor that is at its optimal level and sustains the maximum rate of the process
`
- **Explanation:** Blackman's Law of Limiting Factors (1905) states that if a chemical process is affected by more than one factor, its rate will be determined by the factor nearest to its minimal value. This is the limiting factor — the one that directly affects the process if its quantity is changed.
- **KU:** 6f938534-fbdb-4ce0-9ca0-140d717b3876 v1 status=PASSED
- **Section:** 11.10 FACTORS AFFECTING PHOTOSYNTHESIS (page 19)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Biology\Class 11-Biology\ncert-books-class-11-biology-chapter-11.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — UNCHANGED
  (same as original)
- **options** — UNCHANGED
- **correct_answer** — UNCHANGED → A
- **explanation** — UNCHANGED
- **difficulty** — UNCHANGED → easy
- **topic** — UNCHANGED → factors-affecting-photosynthesis
- **chapter** — UNCHANGED → photosynthesis
- **subject** — UNCHANGED → BOTANY
- **concept** — DEFERRED — SEPARATE TAXONOMY APPROVAL REQUIRED
  - current: photorespiration
  - after taxonomy approval: limiting-factors
  - apply without taxonomy approval: **NO**
- **ku** — UNCHANGED
- **provenance** — UNCHANGED

#### Versioning plan

`	ext
new content_version required = NO
KEEP body — no content_version write for body
`

#### KU relationship plan

- Copy required: NO — No new content_version for KEEP body

#### Special notes

`json
[
  {
    "taxonomy": "Concept remap NOT until limiting-factors explicitly approved and created"
  }
]
`

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 2. 8d50e829-6540-44bc-882a-6b140a33da17 — **REVISE**

- **current_content_version_id:** a614bc69-58be-4486-8468-01e40ced2548
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=a614bc69… latest=a614bc69… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** BOTANY / photosynthesis / factors-affecting-photosynthesis / photorespiration
- **Difficulty / Answer:** hard / **A**
- **Stem:** A plant is provided with optimal light intensity and an abundant supply of CO2, yet its rate of photosynthesis remains very low. Which of the following best explains this observation, and which internal factor could additionally limit photosynthesis even if external conditions were made optimal?
- **Options:**
`	ext
  A. Very low temperature is the external limiting factor as per Blackman's Law; internally, reduced amount of chlorophyll could further limit photosynthesis
  B. High CO2 concentration is the limiting factor; internally, a large number of leaves would reduce the rate of photosynthesis
  C. Excess light is inhibiting photosynthesis; internally, increased mesophyll cell number is the limiting internal factor
  D. Water availability is always the primary limiting factor regardless of other conditions; internal CO2 concentration has no role
`
- **Explanation:** Blackman's Law of Limiting Factors explains that despite optimal light and CO2, a very low temperature can limit photosynthesis because temperature is the factor nearest to its minimal value. Additionally, internal factors such as the amount of chlorophyll are listed as internal determinants of photosynthesis; reduced chlorophyll would limit photosynthesis even if all external factors were made optimal.
- **KU:** 6f938534-fbdb-4ce0-9ca0-140d717b3876 v1 status=PASSED
- **Section:** 11.10 FACTORS AFFECTING PHOTOSYNTHESIS (page 19)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Biology\Class 11-Biology\ncert-books-class-11-biology-chapter-11.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > A crop plant is given optimal light and abundant CO2, yet its photosynthetic rate remains very low. Using Blackman's Law of Limiting Factors, which statement is correct?
- **options** — PROPOSED CHANGE
`	ext
  A. Temperature nearest its minimal value is limiting the rate; reduced chlorophyll can also limit the rate as an internal factor.
  B. Abundant CO2 itself is the limiting factor; more leaves would further lower the rate.
  C. Optimal light is inhibiting photosynthesis; more mesophyll cells would lower the rate.
  D. Water is always the sole limiting factor, so internal CO2 and chlorophyll cannot affect the rate.
`
- **correct_answer** — UNCHANGED → A
- **explanation** — PROPOSED CHANGE
  > Blackman's Law states that when several factors affect a process, the rate is set by the factor nearest its minimal value. With light and CO2 already optimal, a very low temperature can still limit photosynthesis. Separately, NCERT lists amount of chlorophyll among internal factors that can limit photosynthesis even when external factors are favourable. Option B misidentifies abundant CO2 as limiting. Option C contradicts optimal light. Option D wrongly makes water exclusive.
- **difficulty** — PROPOSED CHANGE → medium (from hard)
- **topic** — UNCHANGED → factors-affecting-photosynthesis
- **chapter** — UNCHANGED → photosynthesis
- **subject** — UNCHANGED → BOTANY
- **concept** — DEFERRED — SEPARATE TAXONOMY APPROVAL REQUIRED
  - current: photorespiration
  - after taxonomy approval: limiting-factors
  - apply without taxonomy approval: **NO**
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### Special notes

`json
[
  {
    "taxonomy": "Concept remap NOT until limiting-factors explicitly approved and created"
  }
]
`

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 3. 85fee888-47f6-408d-ab05-39b131233322 — **REPLACE**

- **current_content_version_id:** d4c89a95-b134-4c1b-bfc8-645679d14c74
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=d4c89a95… latest=d4c89a95… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** BOTANY / photosynthesis / factors-affecting-photosynthesis / photorespiration
- **Difficulty / Answer:** medium / **A**
- **Stem:** In the photorespiratory pathway of C3 plants, RuBP reacts with O2 at the active site of RuBisCO to produce which of the following products?
- **Options:**
`	ext
  A. One molecule of phosphoglycerate and one molecule of phosphoglycolate
  B. Two molecules of phosphoglycerate
  C. One molecule of phosphoglycerate and one molecule of ATP
  D. Two molecules of phosphoglycolate and one molecule of NADPH
`
- **Explanation:** When O2 binds to RuBisCO in C3 plants, RuBP combines with O2 instead of CO2, producing one molecule of phosphoglycerate and one molecule of phosphoglycolate (a 2-carbon compound). This pathway neither produces sugars, ATP, nor NADPH, but instead consumes ATP and releases CO2.
- **KU:** f01e615a-6cba-4611-b0ec-2a0a23a482d8 v1 status=PASSED
- **Section:** 11.9 PHOTORESPIRATION (page 17)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Biology\Class 11-Biology\ncert-books-class-11-biology-chapter-11.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > Which statement correctly describes the photorespiratory pathway in C3 plants?
- **options** — PROPOSED CHANGE
`	ext
  A. It synthesises sugars and NADPH but no ATP.
  B. It releases CO2 and utilises ATP, with no synthesis of sugars, ATP or NADPH.
  C. It produces ATP and NADPH while fixing extra CO2.
  D. It occurs in C4 plants to concentrate CO2 at RuBisCO.
`
- **correct_answer** — PROPOSED CHANGE → B (from A)
- **explanation** — PROPOSED CHANGE
  > NCERT states that in the photorespiratory pathway there is neither synthesis of sugars nor of ATP or NADPH; instead CO2 is released with utilisation of ATP. Option A invents sugar/NADPH synthesis. Option C reverses the energetics. Option D is false: photorespiration does not occur in C4 plants in the NCERT account. This tests pathway consequences, not the oxygenation product pair (covered by 10d4d997).
- **difficulty** — UNCHANGED → medium
- **topic** — UNCHANGED → factors-affecting-photosynthesis
- **chapter** — UNCHANGED → photosynthesis
- **subject** — UNCHANGED → BOTANY
- **concept** — UNCHANGED
  - photorespiration
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### Special notes

`json
[
  {
    "replace_objective": "photorespiration pathway consequences",
    "answer": "B",
    "proposal_complete": true,
    "includes": [
      "stem",
      "A/B/C/D",
      "answer B",
      "explanation",
      "difficulty",
      "concept photorespiration",
      "source provenance"
    ]
  }
]
`

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 4. 87f621ab-a1d8-4097-8152-573b6fa46914 — **REVISE**

- **current_content_version_id:** 012ca4ee-911e-4e0a-aaa3-7fb112685f55
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=012ca4ee… latest=012ca4ee… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** CHEMISTRY / chemical-bonding / covalent-bonding-vsepr / vsepr-theory
- **Difficulty / Answer:** hard / **C**
- **Stem:** A student argues that VSEPR theory is sufficient for all purposes of studying molecular bonding because it successfully predicts molecular geometry. Which of the following statements BEST refutes this argument using the context of Valence Bond theory?
- **Options:**
`	ext
  A. VSEPR theory incorrectly predicts the geometry of H2, whereas VB theory predicts a bond length of 74 pm and bond enthalpy of 435.8 kJ mol⁻¹
  B. VSEPR theory has unlimited applications but VB theory is more mathematically elegant
  C. VSEPR theory only predicts geometry without theoretical explanation and has limited applications, whereas VB theory explains bond formation in terms of a balance between attractive and repulsive forces leading to minimum potential energy
  D. VSEPR theory correctly explains why repulsive forces between nuclei and electrons outweigh attractive forces in H2 formation
`
- **Explanation:** VSEPR theory is limited because it predicts geometry of simple molecules but does not theoretically explain bond formation and has limited applications. VB theory, introduced by Heitler and London in 1927, provides a theoretical basis by showing that bond formation in H2 results from attractive forces (NA–eB, NB–eA) outweighing repulsive forces, leading to minimum energy at a bond length of 74 pm with a bond enthalpy of 435.8 kJ mol⁻¹. Option A is incorrect as VSEPR does not incorrectly predict …
- **KU:** e86cfd41-ae62-48f8-8011-6ee21650fa89 v1 status=PASSED
- **Section:** 4.5 Valence Bond Theory (page 18)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Chemistry\Class 11- Chemistry\ncert-books-class-11-chemistry-chapter-4.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > NCERT notes a limitation of VSEPR theory when introducing Valence Bond theory. Which statement is correct?
- **options** — PROPOSED CHANGE
`	ext
  A. VSEPR wrongly predicts the geometry of H2, while VB cannot give bond length or bond enthalpy.
  B. VSEPR has unlimited applications, so VB theory is unnecessary.
  C. VSEPR predicts geometry of simple molecules but does not theoretically explain bonding and has limited applications; VB theory explains bond formation via attractive and repulsive forces leading to a minimum-energy state.
  D. In H2 formation, repulsive forces outweigh attractive forces according to VB theory.
`
- **correct_answer** — UNCHANGED → C
- **explanation** — PROPOSED CHANGE
  > NCERT states that VSEPR gives geometry of simple molecules but does not theoretically explain them and has limited applications; VB theory (Heitler–London) explains bond formation as attractive forces outweighing repulsive forces, giving a stable molecule at minimum potential energy (e.g. H2 bond length 74 pm). A is false (VSEPR is not said to mis-predict H2). B contradicts 'limited applications'. D inverts the VB force balance.
- **difficulty** — PROPOSED CHANGE → medium (from hard)
- **topic** — UNCHANGED → covalent-bonding-vsepr
- **chapter** — UNCHANGED → chemical-bonding
- **subject** — UNCHANGED → CHEMISTRY
- **concept** — UNCHANGED
  - vsepr-theory
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 5. 863f1289-87a0-4253-b996-c0aff8c47988 — **REVISE**

- **current_content_version_id:** e8c46c44-9cb3-48c8-96db-21ec8bcc527a
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=e8c46c44… latest=e8c46c44… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** CHEMISTRY / chemical-bonding / hybridization / sp-sp2-sp3
- **Difficulty / Answer:** hard / **B**
- **Stem:** A student argues that hybridisation involving 3p, 3d, and 4s orbitals should be feasible because 3d orbitals have comparable energy to 4s and 4p orbitals. Why is this argument incorrect according to NCERT?
- **Options:**
`	ext
  A. Because 3d orbitals can only hybridise with 3s and 3p orbitals, not with any 4th-shell orbitals
  B. Because the energy difference between 3p and 4s orbitals is significant, ruling out their co-hybridisation, even though 3d is comparable in energy to both 3s/3p and 4s/4p
  C. Because 4s orbitals are always lower in energy than 3d orbitals, so mixing 3p with 4s would produce unstable hybrids
  D. Because hybridisation across different principal quantum number shells is never permitted in any element
`
- **Explanation:** The NCERT text explicitly states that while 3d orbitals have comparable energy to both 3s/3p and 4s/4p orbitals (enabling sp3d or sp3d2 with 3s/3p/3d, and similar with 4s/4p/3d), hybridisation involving 3p, 3d, and 4s together is not possible because the energy difference between 3p and 4s is significant. The student's error is assuming that transitivity of comparable energies applies — just because 3d ≈ 3p and 3d ≈ 4s does not mean 3p ≈ 4s.
- **KU:** fe335b26-62bf-4aee-948c-ff913eb3efaa v1 status=PASSED
- **Section:** 4.6.3 Hybridisation of Elements (page 25)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Chemistry\Class 11- Chemistry\ncert-books-class-11-chemistry-chapter-4.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > Why does NCERT say hybridisation involving 3p, 3d and 4s orbitals together is not possible, even though 3d energy is comparable to both 3s/3p and 4s/4p?
- **options** — PROPOSED CHANGE
`	ext
  A. 3d orbitals can never mix with any n=4 orbitals.
  B. The energy difference between 3p and 4s is significant, so those orbitals cannot co-hybridise with 3d.
  C. 4s is always lower than 3d, so any hybrid with 3d is impossible.
  D. Hybridisation across different principal shells is forbidden for all elements.
`
- **correct_answer** — UNCHANGED → B
- **explanation** — PROPOSED CHANGE
  > NCERT states 3d is comparable in energy to 3s/3p and also to 4s/4p, allowing sets such as 3s+3p+3d or 3d+4s+4p, but hybridisation involving 3p, 3d and 4s together is not possible because the 3p–4s energy gap is significant. A is too absolute (3d+4s+4p is allowed). C overstates a universal 4s<3d rule as the NCERT reason. D is false (cross-shell mixes appear in the allowed sets).
- **difficulty** — UNCHANGED → hard
- **topic** — UNCHANGED → hybridization
- **chapter** — UNCHANGED → chemical-bonding
- **subject** — UNCHANGED → CHEMISTRY
- **concept** — UNCHANGED
  - sp-sp2-sp3
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 6. ade9900b-1ab2-4a5d-aa29-a5f4a605366e — **REVISE**

- **current_content_version_id:** 32b58f53-daf9-4d68-9cc9-8bc4f766156b
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=32b58f53… latest=32b58f53… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** PHYSICS / current-electricity / kirchhoffs-laws / kcl-kvl
- **Difficulty / Answer:** hard / **A**
- **Stem:** A conductor carries a non-steady current. In a small interval Δt around time t, a net charge ΔQ flows across a cross-section. As Δt → 0, ΔQ → 0 but ΔQ/Δt → 2 A. Simultaneously, in a separate steady scenario, a net negative charge of 6 C flows in the forward direction and a net positive charge of 2 C flows in the forward direction over 2 s. Which of the following correctly compares the two currents and their directions?
- **Options:**
`	ext
  A. The non-steady current is 2 A in the forward direction; the steady current is –2 A, implying it flows in the backward direction
  B. The non-steady current is 0 A because ΔQ → 0; the steady current is –2 A in the forward direction
  C. The non-steady current is 2 A in the forward direction; the steady current is 2 A also in the forward direction
  D. The non-steady current is undefined since the current is non-steady; the steady current is –4 A in the backward direction
`
- **Explanation:** For the non-steady current, I(t) = lim(Δt→0) ΔQ/Δt = 2 A (positive, so forward direction). For the steady case, q = q+ – q– = 2 – 6 = –4 C, and I = q/t = –4/2 = –2 A. A negative value implies the current flows in the backward direction. Hence the non-steady current is 2 A forward and the steady current is –2 A (backward direction).
- **KU:** 11d6fb7f-13e3-425b-ae37-a0e2aa781f94 v1 status=PASSED
- **Section:** 3.2 ELECTRIC CURRENT (page 1)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Physics\Class 12-Physics\ncert-book-class-12-physics-part-1-chapter-3.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > For a non-steady current, lim(Δt→0) ΔQ/Δt = 2 A. In a separate steady case over 2 s, a net positive charge of 2 C and a net negative charge of 6 C both flow in the forward direction. Using q = q+ − q− and I = q/t, which comparison is correct?
- **options** — PROPOSED CHANGE
`	ext
  A. Non-steady current = 2 A forward; steady current = −2 A (backward).
  B. Non-steady current = 0 A because ΔQ → 0; steady current = −2 A forward.
  C. Non-steady current = 2 A forward; steady current = 2 A forward.
  D. Non-steady current is undefined; steady current = −4 A backward.
`
- **correct_answer** — UNCHANGED → A
- **explanation** — PROPOSED CHANGE
  > Non-steady: I(t)=lim ΔQ/Δt=2 A (forward). Steady: q=q+−q−=2−6=−4 C; I=q/t=−4/2=−2 A; negative means backward. B confuses ΔQ→0 with I→0. C uses wrong q. D invents −4 A as current instead of charge.
- **difficulty** — UNCHANGED → hard
- **topic** — PROPOSED CHANGE → ohms-law (from kirchhoffs-laws)
- **chapter** — UNCHANGED → current-electricity
- **subject** — UNCHANGED → PHYSICS
- **concept** — PROPOSED CHANGE
  - proposed: ohms-law / ohms-law-concept (9071ef5d-b62f-4159-91b6-90436a7705e6)
  - operation: content_item metadata change (cms.content_items.concept_id)
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### Special notes

`json
[
  {
    "metadata_remap": {
      "current": "kirchhoffs-laws / kcl-kvl",
      "proposed": "ohms-law / ohms-law-concept",
      "operation": "content_item metadata change"
    }
  }
]
`

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 7. c7a54ae9-5044-44d3-bfa4-8a5bbc6c5ef2 — **REPLACE**

- **current_content_version_id:** 4117b472-cea2-469b-9f76-0c3be97c4760
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=4117b472… latest=4117b472… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** PHYSICS / current-electricity / ohms-law / ohms-law-concept
- **Difficulty / Answer:** easy / **A**
- **Stem:** According to Ohm's law, the SI unit of resistance is:
- **Options:**
`	ext
  A. Ohm (Ω)
  B. Siemens (S)
  C. Ampere (A)
  D. Volt per ampere squared (V/A²)
`
- **Explanation:** The SI unit of resistance is the ohm, denoted by the symbol Ω. This is a direct fact stated in the textbook section on Ohm's law (V = RI, where R is the resistance measured in ohms).
- **KU:** fcff25f5-f369-4dde-b700-1a3a44b961eb v1 status=PASSED
- **Section:** 3.4 OHM’S LAW (page 3)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Physics\Class 12-Physics\ncert-book-class-12-physics-part-1-chapter-3.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > Ohm's law is written as V = RI. If the potential difference across a conductor is doubled while the current through it is halved, the resistance R of the conductor:
- **options** — PROPOSED CHANGE
`	ext
  A. becomes four times the original value.
  B. becomes twice the original value.
  C. remains unchanged.
  D. becomes one-fourth of the original value.
`
- **correct_answer** — UNCHANGED → A
- **explanation** — PROPOSED CHANGE
  > From V=RI, R=V/I. If V→2V and I→I/2, then R'=(2V)/(I/2)=4(V/I)=4R. Resistance is a property depending on material and dimensions (R=ρl/A), but for this ohmic relation under the stated V and I changes, the ratio V/I increases fourfold. B undercounts. C would require V/I constant. D inverts the ratio.
- **difficulty** — UNCHANGED → easy
- **topic** — UNCHANGED → ohms-law
- **chapter** — UNCHANGED → current-electricity
- **subject** — UNCHANGED → PHYSICS
- **concept** — UNCHANGED
  - ohms-law-concept
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### Special notes

`json
[
  {
    "independent_review_soft_note": "fixed-R wording should be explicit",
    "status": "HUMAN DECISION REQUIRED",
    "resolved_in_proposal": false,
    "detail": "Proposal does not rewrite stem to explicit V/I; human may APPROVE as-is or APPROVE WITH MODIFICATION"
  }
]
`

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 8. 7b80d6db-9c07-4b42-a92d-df74ab8428b3 — **REVISE**

- **current_content_version_id:** fef85035-402e-4c8d-9db4-024745bca160
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=fef85035… latest=fef85035… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** PHYSICS / current-electricity / kirchhoffs-laws / kcl-kvl
- **Difficulty / Answer:** hard / **A**
- **Stem:** In a circuit loop, a cell of EMF ε and internal resistance r has a current I flowing from its positive terminal P to its negative terminal N (i.e., opposite to the conventional internal current direction). Using Kirchhoff's Loop Rule and the correct expression for terminal potential difference in this scenario, which equation correctly represents the potential change across this cell as current moves from P to N, and what does this imply physically?
- **Options:**
`	ext
  A. V(N) – V(P) = –ε – Ir, implying the cell is being charged (acts as a load) and potential drops by more than ε
  B. V(N) – V(P) = ε – Ir, implying the cell is discharging and gains potential in the direction of current
  C. V(N) – V(P) = –ε + Ir, implying the cell is discharging and the terminal voltage is reduced by internal resistance
  D. V(N) – V(P) = ε + Ir, implying the cell always gains potential regardless of current direction
`
- **Explanation:** When current I flows from P (positive terminal) to N (negative terminal) through the cell, the potential difference is given by V(P) – V(N) = ε + Ir. Therefore, V(N) – V(P) = –ε – Ir. This scenario (current entering the positive terminal) corresponds to the cell being charged — it acts as a load rather than a source. The potential falls by (ε + Ir) in going from P to N, which is consistent with the Loop Rule requiring the algebraic sum of all potential changes around the loop to equal zero.
- **KU:** e5f8f04d-d353-4d6b-aa3c-c9baa12b488c v1 status=PASSED
- **Section:** 3.12 KIRCHHOFF’S RULES (page 17)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Physics\Class 12-Physics\ncert-book-class-12-physics-part-1-chapter-3.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > In Kirchhoff labelling, a cell of emf ε and internal resistance r has current I marked from the positive terminal P toward the negative terminal N. NCERT gives V(P) − V(N) = ε + Ir for this labelling. Which statement is correct?
- **options** — PROPOSED CHANGE
`	ext
  A. V(N) − V(P) = −ε − Ir; current enters the positive terminal (cell being charged / acting as a load).
  B. V(N) − V(P) = ε − Ir; the cell is discharging with terminal voltage ε − Ir.
  C. V(N) − V(P) = −ε + Ir; the Ir term always opposes ε when going from N to P.
  D. V(N) − V(P) = ε + Ir; potential always rises from P to N.
`
- **correct_answer** — UNCHANGED → A
- **explanation** — PROPOSED CHANGE
  > KU/NCERT: if I is labelled P→N, V(P)−V(N)=ε+Ir. Therefore V(N)−V(P)=−(ε+Ir)=−ε−Ir. Current into the positive terminal means the cell is being charged (acts as a load), so the potential fall from P to N exceeds ε by Ir. B matches the opposite labelling (N→P), where V(P)−V(N)=ε−Ir. C and D rearrange signs incorrectly.
- **difficulty** — UNCHANGED → hard
- **topic** — UNCHANGED → kirchhoffs-laws
- **chapter** — UNCHANGED → current-electricity
- **subject** — UNCHANGED → PHYSICS
- **concept** — UNCHANGED
  - kcl-kvl
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### Special notes

`json
[
  {
    "answer_preserved": "A",
    "purpose": "wording/sign-convention clarity"
  }
]
`

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

### 9. a42a3589-8070-40c2-9181-f76642b33a85 — **REVISE**

- **current_content_version_id:** 8d39848a-8a60-47c8-8997-09a827fa3e6e
- **current_version_no:** 1
- **publication_status / workflow:** DRAFT / DRAFT
- **pointers:** current=8d39848a… latest=8d39848a… equal=True

#### Original

- **Subject / Chapter / Topic / Concept:** PHYSICS / current-electricity / ohms-law / drift-velocity
- **Difficulty / Answer:** medium / **A**
- **Stem:** In a copper wire of cross-sectional area 1.0 × 10⁻⁷ m² carrying a current of 1.5 A, the drift speed of conduction electrons is approximately 1.1 × 10⁻³ m s⁻¹. This drift speed is approximately how many times smaller than the typical thermal speed of copper atoms at ordinary temperatures?
- **Options:**
`	ext
  A. 10⁻⁵ times
  B. 10⁻³ times
  C. 10⁻⁷ times
  D. 10⁻¹ times
`
- **Explanation:** According to the textbook, the drift speed of conduction electrons in a copper wire carrying 1.5 A through a cross-sectional area of 1.0 × 10⁻⁷ m² is approximately 1.1 × 10⁻³ m s⁻¹, which is about 10⁻⁵ times the typical thermal speed of copper atoms at ordinary temperatures. This illustrates that drift speeds in typical conductors are extremely small compared to thermal speeds.
- **KU:** 4f40e57b-77ee-460b-a3e1-2719621c2c07 v1 status=PASSED
- **Section:** 3.5 DRIFT OF ELECTRONS AND THE ORIGIN (page 5)
- **Source:** D:\ravishori\AI Neet Exam App\StudyMaterial\Physics\Class 12-Physics\ncert-book-class-12-physics-part-1-chapter-3.pdf
- **pilot_run_id:** phase-d-30-mcq-authorized-20260825
- **Provenance model/prompt:** claude-sonnet-4-6 / v2

#### Proposed

- **stem** — PROPOSED CHANGE
  > Example values in NCERT give electron drift speed vd ≈ 1.1 × 10⁻³ m s⁻¹ in a copper wire (A = 1.0 × 10⁻⁷ m², I = 1.5 A). Which conclusion is correct?
- **options** — PROPOSED CHANGE
`	ext
  A. vd is about 10⁻⁵ times a typical thermal speed of copper atoms at ordinary temperatures, so drift is extremely slow compared with thermal motion.
  B. vd is comparable to thermal speeds, so drift dominates transport time across a laboratory wire.
  C. vd equals the thermal speed divided by 10 only, so the two speeds differ by one order of magnitude.
  D. vd is larger than thermal speed; current is carried mainly by thermal motion.
`
- **correct_answer** — UNCHANGED → A
- **explanation** — PROPOSED CHANGE
  > NCERT Example 3.1 compares the estimated drift speed with thermal speeds and notes drift speeds are much smaller (about 10⁻⁵ times thermal). B and D contradict that comparison. C understates the ratio (10⁻¹ vs ~10⁻⁵).
- **difficulty** — PROPOSED CHANGE → easy (from medium)
- **topic** — UNCHANGED → ohms-law
- **chapter** — UNCHANGED → current-electricity
- **subject** — UNCHANGED → PHYSICS
- **concept** — UNCHANGED
  - drift-velocity
- **ku** — UNCHANGED (copy to new version)
- **provenance** — UNCHANGED (carry forward via KU copy)

#### Versioning plan

`	ext
old version_no = 1
new version_no = 2
new content_version required = YES
latest_version_id → new version
current_version_id → unchanged
workflow_state = DRAFT
publication status = unchanged
`

#### KU relationship plan

- Copy required: **YES**
- Plan: existing KU relationship(s) → copied to new content_version
- Why: CMS pilot filter depends on latest_version_id -> content_version_knowledge_units; failing to copy can remove the revised question from pilot lineage/filter
- Modify now: **NO**

#### HUMAN DECISION

- [ ] APPROVE
- [ ] APPROVE WITH MODIFICATION
- [ ] REJECT

Reviewer comments:

Reviewer:

Review date:

---

## Safety check

`	ext
Database writes = 0
MCQ modifications = 0
Taxonomy modifications = 0
ECAEP actions = 0
Publication = 0
`

## Authority

Built only from Phase-D audit trail + read-only live pointers. No invented changes.
