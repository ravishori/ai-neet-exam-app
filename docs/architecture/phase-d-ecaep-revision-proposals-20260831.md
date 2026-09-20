# Phase D.2 — Controlled Revision Proposals (9 Flagged MCQs)

**PROPOSALS ONLY — NOT APPLIED TO DATABASE**

**Date:** 2026-08-31  
**Pilot:** `phase-d-30-mcq-authorized-20260825`  
**Database:** `trinetra_db`  
**Writes:** 0  
**Overall verdict:** **AMBER**

## Flagged nine (from pre-screen)

| # | Question ID | Subject | Severity | Original finding | Previous recommendation |
|---|---|---|---|---|---|
| 1 | `e6b9fb1e-f022-4172-88c5-318213bc511b` | BOTANY | P2 | Blackman content tagged photorespiration | REVISE |
| 2 | `8d50e829-6540-44bc-882a-6b140a33da17` | BOTANY | P2 | Compound Blackman stem; photorespiration tag; difficulty | REVISE |
| 3 | `85fee888-47f6-408d-ab05-39b131233322` | BOTANY | P1 | Near-duplicate of 10d4d997 | REVISE |
| 4 | `87f621ab-a1d8-4097-8152-573b6fa46914` | CHEMISTRY | P2 | Overlong VSEPR vs VB stem | REVISE |
| 5 | `863f1289-87a0-4253-b996-c0aff8c47988` | CHEMISTRY | P2 | Heavy 3p/3d/4s hybridisation wording | REVISE |
| 6 | `ade9900b-1ab2-4a5d-aa29-a5f4a605366e` | PHYSICS | P2 | Kirchhoff tags on §3.2 current item | REVISE |
| 7 | `c7a54ae9-5044-44d3-bfa4-8a5bbc6c5ef2` | PHYSICS | P2 | Trivial ohm unit recall | REVISE |
| 8 | `7b80d6db-9c07-4b42-a92d-df74ab8428b3` | PHYSICS | P1 | Kirchhoff sign-convention wording | REVISE |
| 9 | `a42a3589-8070-40c2-9181-f76642b33a85` | PHYSICS | P2 | Verbatim 10⁻⁵ drift/thermal recall | REVISE |

## Actions summary

```text
KEEP    = 1
REVISE  = 6
REPLACE = 2
RETIRE  = 0
```

## Severity before → after (proposals)

```text
Before: P0=0 P1=3 P2=8 P3=2
After:  P0=0 P1=0 P2=2 P3=0
Remaining P2 = taxonomy gaps (Blackman concept seed missing)
```

## Special analyses

### Near-duplicate (10d4d997 vs 85fee888)

- Classification: **NEAR-DUPLICATES** (same LO: oxygenation products; identical correct option text).
- Retain: `10d4d997` (APPROVED in pre-screen).
- Replace slot: `85fee888` with pathway-consequence item (no sugar/ATP/NADPH; CO₂ released using ATP).

### Kirchhoff (`7b80d6db`) independent derivation

```text
NCERT/KU: I labelled N→P  ⇒  V(P)−V(N) = ε − Ir
NCERT/KU: I labelled P→N  ⇒  V(P)−V(N) = ε + Ir
Stem direction: I from P to N
Therefore: V(N)−V(P) = −ε − Ir
Physical meaning: current into +ve terminal ⇒ charging/load
Original key A: CORRECT
Issue type: wording ambiguity (P1), not wrong answer
```

## Question `e6b9fb1e-f022-4172-88c5-318213bc511b`

**Action:** KEEP  
**Finding:** PARTIALLY CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Stem correctly tests Blackman's limiting-factor definition from §11.10. Tag photorespiration is misleading, but academic taxonomy under topic factors-affecting-photosynthesis currently contains ONLY concept photorespiration — TAXONOMY GAP, not an MCQ body defect.

### Original

```text
Stem: According to Blackman's Law of Limiting Factors (1905), which of the following correctly defines the 'limiting factor' in a chemical process affected by multiple factors?
A. The factor that is nearest to its minimal value and directly controls the rate of the process
B. The factor present in the highest concentration that accelerates the process
C. The factor that remains constant while all other factors vary
D. The factor that is at its optimal level and sustains the maximum rate of the process
Correct: A
Explanation: Blackman's Law of Limiting Factors (1905) states that if a chemical process is affected by more than one factor, its rate will be determined by the factor nearest to its minimal value. This is the limiting factor — the one that directly affects the process if its quantity is changed.
Difficulty: easy
Metadata: BOTANY / photosynthesis / factors-affecting-photosynthesis / photorespiration
Source: Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf p.19 (11.10 FACTORS AFFECTING PHOTOSYNTHESIS)
```

### Proposed revision

```text
None — KEEP original body.
```

### Metadata proposal

```text
Current: {'topic': 'factors-affecting-photosynthesis', 'concept': 'photorespiration'}
Recommended: {'topic': 'factors-affecting-photosynthesis', 'concept': 'limiting-factors (NOT IN DB — requires future concept seed)'}
Evidence: Section heading 11.10 FACTORS AFFECTING PHOTOSYNTHESIS; KU facts cite Blackman/sub-optimal factor language.
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_correctness": "PASS",
  "ncert_alignment": "PASS",
  "concept_alignment": "WARNING",
  "duplicate_risk": "PASS",
  "note": "Original retained"
}
```

Explanation score: **4/5**  
Duplicate check: **PASS**  
Final status: **GREEN — content keep; metadata taxonomy gap documented**

---

## Question `8d50e829-6540-44bc-882a-6b140a33da17`

**Action:** REVISE  
**Finding:** CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Compound stem was hard to parse; difficulty hard was overstated; concept tag photorespiration mismatches content (taxonomy gap same as e6b9fb1e).

### Original

```text
Stem: A plant is provided with optimal light intensity and an abundant supply of CO2, yet its rate of photosynthesis remains very low. Which of the following best explains this observation, and which internal factor could additionally limit photosynthesis even if external conditions were made optimal?
A. Very low temperature is the external limiting factor as per Blackman's Law; internally, reduced amount of chlorophyll could further limit photosynthesis
B. High CO2 concentration is the limiting factor; internally, a large number of leaves would reduce the rate of photosynthesis
C. Excess light is inhibiting photosynthesis; internally, increased mesophyll cell number is the limiting internal factor
D. Water availability is always the primary limiting factor regardless of other conditions; internal CO2 concentration has no role
Correct: A
Explanation: Blackman's Law of Limiting Factors explains that despite optimal light and CO2, a very low temperature can limit photosynthesis because temperature is the factor nearest to its minimal value. Additionally, internal factors such as the amount of chlorophyll are listed as internal determinants of photosynthesis; reduced chlorophyll would limit photosynthesis even if all external factors were made optimal.
Difficulty: hard
Metadata: BOTANY / photosynthesis / factors-affecting-photosynthesis / photorespiration
Source: Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf p.19 (11.10 FACTORS AFFECTING PHOTOSYNTHESIS)
```

### Proposed revision

```text
Stem: A crop plant is given optimal light and abundant CO2, yet its photosynthetic rate remains very low. Using Blackman's Law of Limiting Factors, which statement is correct?
A. Temperature nearest its minimal value is limiting the rate; reduced chlorophyll can also limit the rate as an internal factor.
B. Abundant CO2 itself is the limiting factor; more leaves would further lower the rate.
C. Optimal light is inhibiting photosynthesis; more mesophyll cells would lower the rate.
D. Water is always the sole limiting factor, so internal CO2 and chlorophyll cannot affect the rate.
Correct: A
Explanation: Blackman's Law states that when several factors affect a process, the rate is set by the factor nearest its minimal value. With light and CO2 already optimal, a very low temperature can still limit photosynthesis. Separately, NCERT lists amount of chlorophyll among internal factors that can limit photosynthesis even when external factors are favourable. Option B misidentifies abundant CO2 as limiting. Option C contradicts optimal light. Option D wrongly makes water exclusive.
Difficulty: medium
```

### What changed

- **Stem:** Simplified to one clear Blackman scenario question.
- **Options:** Compressed distractors; same scientific targets.
- **Correct answer:** Still A.
- **Explanation:** Rewritten to map each distractor.
- **Difficulty:** hard → medium.

### Why better

Single assessment objective, clearer wording, defensible difficulty.

### Metadata proposal

```text
Current: {'topic': 'factors-affecting-photosynthesis', 'concept': 'photorespiration'}
Recommended: {'topic': 'factors-affecting-photosynthesis', 'concept': 'limiting-factors (NOT IN DB — requires future concept seed)'}
Evidence: §11.10 FACTORS AFFECTING PHOTOSYNTHESIS; external/internal factor lists in KU facts.
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "WARNING",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **5/5**  
Duplicate check: **PASS**  
Final status: **GREEN — clearer stem; taxonomy gap remains for concept seed**

---

## Question `85fee888-47f6-408d-ab05-39b131233322`

**Action:** REPLACE  
**Finding:** CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

TRUE NEAR-DUPLICATE of 10d4d997: same oxygenation products objective, identical correct-option text for PGA+phosphoglycolate, stem Jaccard≈0.50. Retain stronger/clearer products item 10d4d997; replace this slot with pathway-consequence objective from same §11.9.

### Original

```text
Stem: In the photorespiratory pathway of C3 plants, RuBP reacts with O2 at the active site of RuBisCO to produce which of the following products?
A. One molecule of phosphoglycerate and one molecule of phosphoglycolate
B. Two molecules of phosphoglycerate
C. One molecule of phosphoglycerate and one molecule of ATP
D. Two molecules of phosphoglycolate and one molecule of NADPH
Correct: A
Explanation: When O2 binds to RuBisCO in C3 plants, RuBP combines with O2 instead of CO2, producing one molecule of phosphoglycerate and one molecule of phosphoglycolate (a 2-carbon compound). This pathway neither produces sugars, ATP, nor NADPH, but instead consumes ATP and releases CO2.
Difficulty: medium
Metadata: BOTANY / photosynthesis / factors-affecting-photosynthesis / photorespiration
Source: Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf p.17 (11.9 PHOTORESPIRATION)
```

### Proposed revision

```text
Stem: Which statement correctly describes the photorespiratory pathway in C3 plants?
A. It synthesises sugars and NADPH but no ATP.
B. It releases CO2 and utilises ATP, with no synthesis of sugars, ATP or NADPH.
C. It produces ATP and NADPH while fixing extra CO2.
D. It occurs in C4 plants to concentrate CO2 at RuBisCO.
Correct: B
Explanation: NCERT states that in the photorespiratory pathway there is neither synthesis of sugars nor of ATP or NADPH; instead CO2 is released with utilisation of ATP. Option A invents sugar/NADPH synthesis. Option C reverses the energetics. Option D is false: photorespiration does not occur in C4 plants in the NCERT account. This tests pathway consequences, not the oxygenation product pair (covered by 10d4d997).
Difficulty: medium
```

### What changed

- **Stem:** From products of RuBP+O2 to pathway consequences.
- **Options:** Fully redesigned.
- **Correct answer:** A → B.
- **Explanation:** New, keyed to no sugar/ATP/NADPH + ATP use + CO2 release.
- **Difficulty:** medium (unchanged band).

### Why better

Removes redundancy while staying on cited photorespiration page.

### Metadata proposal

```text
Current: {'topic': 'factors-affecting-photosynthesis', 'concept': 'photorespiration'}
Recommended: {'topic': 'factors-affecting-photosynthesis', 'concept': 'photorespiration'}
Evidence: Same §11.9 PHOTORESPIRATION; concept now matches.
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "PASS",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **5/5**  
Duplicate check: **PASS**  
Final status: **GREEN — distinct LO from twin**

---

## Question `87f621ab-a1d8-4097-8152-573b6fa46914`

**Action:** REVISE  
**Finding:** CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Original stem was a long student-argument scenario; cognitively heavy for one MCQ though scientifically sound.

### Original

```text
Stem: A student argues that VSEPR theory is sufficient for all purposes of studying molecular bonding because it successfully predicts molecular geometry. Which of the following statements BEST refutes this argument using the context of Valence Bond theory?
A. VSEPR theory incorrectly predicts the geometry of H2, whereas VB theory predicts a bond length of 74 pm and bond enthalpy of 435.8 kJ mol⁻¹
B. VSEPR theory has unlimited applications but VB theory is more mathematically elegant
C. VSEPR theory only predicts geometry without theoretical explanation and has limited applications, whereas VB theory explains bond formation in terms of a balance between attractive and repulsive forces leading to minimum potential energy
D. VSEPR theory correctly explains why repulsive forces between nuclei and electrons outweigh attractive forces in H2 formation
Correct: C
Explanation: VSEPR theory is limited because it predicts geometry of simple molecules but does not theoretically explain bond formation and has limited applications. VB theory, introduced by Heitler and London in 1927, provides a theoretical basis by showing that bond formation in H2 results from attractive forces (NA–eB, NB–eA) outweighing repulsive forces, leading to minimum energy at a bond length of 74 pm with a bond enthalpy of 435.8 kJ mol⁻¹. Option A is incorrect as VSEPR does not incorrectly predict H2 geometry; option D is factually inverted; option B is unsupported by the given facts.
Difficulty: hard
Metadata: CHEMISTRY / chemical-bonding / covalent-bonding-vsepr / vsepr-theory
Source: Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf p.18 (4.5 Valence Bond Theory)
```

### Proposed revision

```text
Stem: NCERT notes a limitation of VSEPR theory when introducing Valence Bond theory. Which statement is correct?
A. VSEPR wrongly predicts the geometry of H2, while VB cannot give bond length or bond enthalpy.
B. VSEPR has unlimited applications, so VB theory is unnecessary.
C. VSEPR predicts geometry of simple molecules but does not theoretically explain bonding and has limited applications; VB theory explains bond formation via attractive and repulsive forces leading to a minimum-energy state.
D. In H2 formation, repulsive forces outweigh attractive forces according to VB theory.
Correct: C
Explanation: NCERT states that VSEPR gives geometry of simple molecules but does not theoretically explain them and has limited applications; VB theory (Heitler–London) explains bond formation as attractive forces outweighing repulsive forces, giving a stable molecule at minimum potential energy (e.g. H2 bond length 74 pm). A is false (VSEPR is not said to mis-predict H2). B contradicts 'limited applications'. D inverts the VB force balance.
Difficulty: medium
```

### What changed

- **Stem:** Shortened; removed nested argument framing.
- **Options:** Tightened; correct remains C.
- **Correct answer:** Still C.
- **Explanation:** Rewritten; distractor elimination explicit.
- **Difficulty:** hard → medium.

### Why better

Same LO, NEET-appropriate length.

### Metadata proposal

```text
Current: {'topic': 'covalent-bonding-vsepr', 'concept': 'vsepr-theory'}
Recommended: {'topic': 'covalent-bonding-vsepr', 'concept': 'vsepr-theory'}
Evidence: Section 4.5 Valence Bond Theory opens by contrasting VSEPR limits; concept remains appropriate for the contrast item.
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "PASS",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **5/5**  
Duplicate check: **PASS**  
Final status: **GREEN**

---

## Question `863f1289-87a0-4253-b996-c0aff8c47988`

**Action:** REVISE  
**Finding:** CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Science correct; original student-argument stem was unnecessarily dense.

### Original

```text
Stem: A student argues that hybridisation involving 3p, 3d, and 4s orbitals should be feasible because 3d orbitals have comparable energy to 4s and 4p orbitals. Why is this argument incorrect according to NCERT?
A. Because 3d orbitals can only hybridise with 3s and 3p orbitals, not with any 4th-shell orbitals
B. Because the energy difference between 3p and 4s orbitals is significant, ruling out their co-hybridisation, even though 3d is comparable in energy to both 3s/3p and 4s/4p
C. Because 4s orbitals are always lower in energy than 3d orbitals, so mixing 3p with 4s would produce unstable hybrids
D. Because hybridisation across different principal quantum number shells is never permitted in any element
Correct: B
Explanation: The NCERT text explicitly states that while 3d orbitals have comparable energy to both 3s/3p and 4s/4p orbitals (enabling sp3d or sp3d2 with 3s/3p/3d, and similar with 4s/4p/3d), hybridisation involving 3p, 3d, and 4s together is not possible because the energy difference between 3p and 4s is significant. The student's error is assuming that transitivity of comparable energies applies — just because 3d ≈ 3p and 3d ≈ 4s does not mean 3p ≈ 4s.
Difficulty: hard
Metadata: CHEMISTRY / chemical-bonding / hybridization / sp-sp2-sp3
Source: Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf p.25 (4.6.3 Hybridisation of Elements)
```

### Proposed revision

```text
Stem: Why does NCERT say hybridisation involving 3p, 3d and 4s orbitals together is not possible, even though 3d energy is comparable to both 3s/3p and 4s/4p?
A. 3d orbitals can never mix with any n=4 orbitals.
B. The energy difference between 3p and 4s is significant, so those orbitals cannot co-hybridise with 3d.
C. 4s is always lower than 3d, so any hybrid with 3d is impossible.
D. Hybridisation across different principal shells is forbidden for all elements.
Correct: B
Explanation: NCERT states 3d is comparable in energy to 3s/3p and also to 4s/4p, allowing sets such as 3s+3p+3d or 3d+4s+4p, but hybridisation involving 3p, 3d and 4s together is not possible because the 3p–4s energy gap is significant. A is too absolute (3d+4s+4p is allowed). C overstates a universal 4s<3d rule as the NCERT reason. D is false (cross-shell mixes appear in the allowed sets).
Difficulty: hard
```

### What changed

- **Stem:** Direct why-question.
- **Options:** Same misconceptions, shorter.
- **Correct answer:** Still B.
- **Explanation:** Clarified allowed vs disallowed orbital sets.
- **Difficulty:** Unchanged hard.

### Why better

Same LO with less parse load.

### Metadata proposal

```text
Current: {'topic': 'hybridization', 'concept': 'sp-sp2-sp3'}
Recommended: {'topic': 'hybridization', 'concept': 'sp-sp2-sp3'}
Evidence: §4.6.3 Hybridisation of Elements — 3p/3d/4s paragraph in section text.
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "PASS",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **5/5**  
Duplicate check: **PASS**  
Final status: **GREEN**

---

## Question `ade9900b-1ab2-4a5d-aa29-a5f4a605366e`

**Action:** REVISE  
**Finding:** CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Calculation correct; academic tags kirchhoffs-laws/kcl-kvl contradict §3.2 ELECTRIC CURRENT provenance.

### Original

```text
Stem: A conductor carries a non-steady current. In a small interval Δt around time t, a net charge ΔQ flows across a cross-section. As Δt → 0, ΔQ → 0 but ΔQ/Δt → 2 A. Simultaneously, in a separate steady scenario, a net negative charge of 6 C flows in the forward direction and a net positive charge of 2 C flows in the forward direction over 2 s. Which of the following correctly compares the two currents and their directions?
A. The non-steady current is 2 A in the forward direction; the steady current is –2 A, implying it flows in the backward direction
B. The non-steady current is 0 A because ΔQ → 0; the steady current is –2 A in the forward direction
C. The non-steady current is 2 A in the forward direction; the steady current is 2 A also in the forward direction
D. The non-steady current is undefined since the current is non-steady; the steady current is –4 A in the backward direction
Correct: A
Explanation: For the non-steady current, I(t) = lim(Δt→0) ΔQ/Δt = 2 A (positive, so forward direction). For the steady case, q = q+ – q– = 2 – 6 = –4 C, and I = q/t = –4/2 = –2 A. A negative value implies the current flows in the backward direction. Hence the non-steady current is 2 A forward and the steady current is –2 A (backward direction).
Difficulty: hard
Metadata: PHYSICS / current-electricity / kirchhoffs-laws / kcl-kvl
Source: Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf p.1 (3.2 ELECTRIC CURRENT)
```

### Proposed revision

```text
Stem: For a non-steady current, lim(Δt→0) ΔQ/Δt = 2 A. In a separate steady case over 2 s, a net positive charge of 2 C and a net negative charge of 6 C both flow in the forward direction. Using q = q+ − q− and I = q/t, which comparison is correct?
A. Non-steady current = 2 A forward; steady current = −2 A (backward).
B. Non-steady current = 0 A because ΔQ → 0; steady current = −2 A forward.
C. Non-steady current = 2 A forward; steady current = 2 A forward.
D. Non-steady current is undefined; steady current = −4 A backward.
Correct: A
Explanation: Non-steady: I(t)=lim ΔQ/Δt=2 A (forward). Steady: q=q+−q−=2−6=−4 C; I=q/t=−4/2=−2 A; negative means backward. B confuses ΔQ→0 with I→0. C uses wrong q. D invents −4 A as current instead of charge.
Difficulty: hard
```

### What changed

- **Stem:** Made definitions explicit in stem.
- **Options:** Shortened.
- **Correct answer:** Still A.
- **Explanation:** Stepwise arithmetic.
- **Difficulty:** Unchanged.

### Why better

Fixes metadata mismatch risk and reduces wording noise.

### Metadata proposal

```text
Current: {'topic': 'kirchhoffs-laws', 'concept': 'kcl-kvl'}
Recommended: {'topic': 'ohms-law', 'concept': 'ohms-law-concept'}
Evidence: Section heading 3.2 ELECTRIC CURRENT; KU facts define I=q/t and lim ΔQ/Δt. Closest existing concept under current-electricity without a dedicated 'electric-current' concept is ohms-law-concept under ohms-law (taxonomy still imperfect but far better than Kirchhoff).
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "PASS",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **5/5**  
Duplicate check: **PASS**  
Final status: **GREEN — retag required when applying**

---

## Question `c7a54ae9-5044-44d3-bfa4-8a5bbc6c5ef2`

**Action:** REPLACE  
**Finding:** CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Original SI-unit recall has negligible discrimination for a pilot bank.

### Original

```text
Stem: According to Ohm's law, the SI unit of resistance is:
A. Ohm (Ω)
B. Siemens (S)
C. Ampere (A)
D. Volt per ampere squared (V/A²)
Correct: A
Explanation: The SI unit of resistance is the ohm, denoted by the symbol Ω. This is a direct fact stated in the textbook section on Ohm's law (V = RI, where R is the resistance measured in ohms).
Difficulty: easy
Metadata: PHYSICS / current-electricity / ohms-law / ohms-law-concept
Source: Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf p.3 (3.4 OHM’S LAW)
```

### Proposed revision

```text
Stem: Ohm's law is written as V = RI. If the potential difference across a conductor is doubled while the current through it is halved, the resistance R of the conductor:
A. becomes four times the original value.
B. becomes twice the original value.
C. remains unchanged.
D. becomes one-fourth of the original value.
Correct: A
Explanation: From V=RI, R=V/I. If V→2V and I→I/2, then R'=(2V)/(I/2)=4(V/I)=4R. Resistance is a property depending on material and dimensions (R=ρl/A), but for this ohmic relation under the stated V and I changes, the ratio V/I increases fourfold. B undercounts. C would require V/I constant. D inverts the ratio.
Difficulty: easy
```

### What changed

- **Stem:** From unit recall to V=RI application.
- **Options:** New quantitative distractors.
- **Correct answer:** Still A (new item).
- **Explanation:** Algebraic proof.
- **Difficulty:** easy (unchanged band).

### Why better

Tests Ohm's law use, still NEET-easy, same section.

### Metadata proposal

```text
Current: {'topic': 'ohms-law', 'concept': 'ohms-law-concept'}
Recommended: {'topic': 'ohms-law', 'concept': 'ohms-law-concept'}
Evidence: §3.4 OHM’S LAW; V=RI and R=ρl/A in KU facts.
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "PASS",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **5/5**  
Duplicate check: **PASS**  
Final status: **GREEN**

---

## Question `7b80d6db-9c07-4b42-a92d-df74ab8428b3`

**Action:** REVISE  
**Finding:** PARTIALLY CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Answer A is scientifically correct under NCERT labelling; the P1 issue is ambiguity/density of the original stem, not a wrong key. Independent derivation confirms A.

### Original

```text
Stem: In a circuit loop, a cell of EMF ε and internal resistance r has a current I flowing from its positive terminal P to its negative terminal N (i.e., opposite to the conventional internal current direction). Using Kirchhoff's Loop Rule and the correct expression for terminal potential difference in this scenario, which equation correctly represents the potential change across this cell as current moves from P to N, and what does this imply physically?
A. V(N) – V(P) = –ε – Ir, implying the cell is being charged (acts as a load) and potential drops by more than ε
B. V(N) – V(P) = ε – Ir, implying the cell is discharging and gains potential in the direction of current
C. V(N) – V(P) = –ε + Ir, implying the cell is discharging and the terminal voltage is reduced by internal resistance
D. V(N) – V(P) = ε + Ir, implying the cell always gains potential regardless of current direction
Correct: A
Explanation: When current I flows from P (positive terminal) to N (negative terminal) through the cell, the potential difference is given by V(P) – V(N) = ε + Ir. Therefore, V(N) – V(P) = –ε – Ir. This scenario (current entering the positive terminal) corresponds to the cell being charged — it acts as a load rather than a source. The potential falls by (ε + Ir) in going from P to N, which is consistent with the Loop Rule requiring the algebraic sum of all potential changes around the loop to equal zero.
Difficulty: hard
Metadata: PHYSICS / current-electricity / kirchhoffs-laws / kcl-kvl
Source: Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf p.17 (3.12 KIRCHHOFF’S RULES)
```

### Proposed revision

```text
Stem: In Kirchhoff labelling, a cell of emf ε and internal resistance r has current I marked from the positive terminal P toward the negative terminal N. NCERT gives V(P) − V(N) = ε + Ir for this labelling. Which statement is correct?
A. V(N) − V(P) = −ε − Ir; current enters the positive terminal (cell being charged / acting as a load).
B. V(N) − V(P) = ε − Ir; the cell is discharging with terminal voltage ε − Ir.
C. V(N) − V(P) = −ε + Ir; the Ir term always opposes ε when going from N to P.
D. V(N) − V(P) = ε + Ir; potential always rises from P to N.
Correct: A
Explanation: KU/NCERT: if I is labelled P→N, V(P)−V(N)=ε+Ir. Therefore V(N)−V(P)=−(ε+Ir)=−ε−Ir. Current into the positive terminal means the cell is being charged (acts as a load), so the potential fall from P to N exceeds ε by Ir. B matches the opposite labelling (N→P), where V(P)−V(N)=ε−Ir. C and D rearrange signs incorrectly.
Difficulty: hard
```

### What changed

- **Stem:** States NCERT formula and terminal labels explicitly.
- **Options:** Aligned to derivation; same correct physics as A.
- **Correct answer:** Still A.
- **Explanation:** Derivation-first.
- **Difficulty:** Unchanged hard.

### Why better

Single defensible answer; removes prior NEEDS REVIEW ambiguity.

### Metadata proposal

```text
Current: {'topic': 'kirchhoffs-laws', 'concept': 'kcl-kvl'}
Recommended: {'topic': 'kirchhoffs-laws', 'concept': 'kcl-kvl'}
Evidence: §3.12 KIRCHHOFF’S RULES; KU facts include both cell labelling formulae.
Applied to DB: False
```

### Independent derivation

```json
{
  "convention": "NCERT: I from N\u2192P \u21d2 V(P)\u2212V(N)=\u03b5\u2212Ir; I from P\u2192N \u21d2 V(P)\u2212V(N)=\u03b5+Ir (KU facts 4\u20135).",
  "stem_direction": "I: P \u2192 N",
  "therefore": "V(P)\u2212V(N)=\u03b5+Ir \u21d2 V(N)\u2212V(P)=\u2212\u03b5\u2212Ir",
  "physical_meaning": "Current into positive terminal \u21d2 charging/load",
  "other_options_defensible": false,
  "residual_risk_if_unrevised": "Students may confuse which terminal traversal gives \u00b1Ir without explicit labelling."
}
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "PASS",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **5/5**  
Duplicate check: **PASS**  
Final status: **GREEN — answer confirmed; wording clarified**

---

## Question `a42a3589-8070-40c2-9181-f76642b33a85`

**Action:** REVISE  
**Finding:** CONFIRMED  
**ECAEP readiness (proposed):** GREEN  

### Reason for revision

Original asked only for the memorised factor; low discrimination.

### Original

```text
Stem: In a copper wire of cross-sectional area 1.0 × 10⁻⁷ m² carrying a current of 1.5 A, the drift speed of conduction electrons is approximately 1.1 × 10⁻³ m s⁻¹. This drift speed is approximately how many times smaller than the typical thermal speed of copper atoms at ordinary temperatures?
A. 10⁻⁵ times
B. 10⁻³ times
C. 10⁻⁷ times
D. 10⁻¹ times
Correct: A
Explanation: According to the textbook, the drift speed of conduction electrons in a copper wire carrying 1.5 A through a cross-sectional area of 1.0 × 10⁻⁷ m² is approximately 1.1 × 10⁻³ m s⁻¹, which is about 10⁻⁵ times the typical thermal speed of copper atoms at ordinary temperatures. This illustrates that drift speeds in typical conductors are extremely small compared to thermal speeds.
Difficulty: medium
Metadata: PHYSICS / current-electricity / ohms-law / drift-velocity
Source: Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf p.5 (3.5 DRIFT OF ELECTRONS AND THE ORIGIN)
```

### Proposed revision

```text
Stem: Example values in NCERT give electron drift speed vd ≈ 1.1 × 10⁻³ m s⁻¹ in a copper wire (A = 1.0 × 10⁻⁷ m², I = 1.5 A). Which conclusion is correct?
A. vd is about 10⁻⁵ times a typical thermal speed of copper atoms at ordinary temperatures, so drift is extremely slow compared with thermal motion.
B. vd is comparable to thermal speeds, so drift dominates transport time across a laboratory wire.
C. vd equals the thermal speed divided by 10 only, so the two speeds differ by one order of magnitude.
D. vd is larger than thermal speed; current is carried mainly by thermal motion.
Correct: A
Explanation: NCERT Example 3.1 compares the estimated drift speed with thermal speeds and notes drift speeds are much smaller (about 10⁻⁵ times thermal). B and D contradict that comparison. C understates the ratio (10⁻¹ vs ~10⁻⁵).
Difficulty: easy
```

### What changed

- **Stem:** Provides example numbers; asks for correct conclusion.
- **Options:** Conceptual, not bare powers of ten alone.
- **Correct answer:** Still A.
- **Explanation:** Focus on drift ≪ thermal.
- **Difficulty:** medium → easy.

### Why better

Assesses understanding of the comparison, not rote exponent.

### Metadata proposal

```text
Current: {'topic': 'ohms-law', 'concept': 'drift-velocity'}
Recommended: {'topic': 'ohms-law', 'concept': 'drift-velocity'}
Evidence: §3.5 DRIFT OF ELECTRONS; Example 3.1 comparison in section text.
Applied to DB: False
```

### Re-audit of proposal

```json
{
  "structural": "PASS",
  "answer_uniqueness": "PASS",
  "answer_correctness": "PASS",
  "explanation": "PASS",
  "ncert_alignment": "PASS",
  "subject_alignment": "PASS",
  "chapter_alignment": "PASS",
  "topic_alignment": "PASS",
  "concept_alignment": "PASS",
  "difficulty": "PASS",
  "distractors": "PASS",
  "ambiguity": "PASS",
  "neet_suitability": "PASS",
  "duplicate_risk": "PASS"
}
```

Explanation score: **4/5**  
Duplicate check: **PASS**  
Final status: **GREEN**

---

## Final 9-question revision matrix

| ID | Sev | Original issue | Confirmed? | Action | Proposed? | NCERT | Answer | Diff | Dup | Final |
|---|---|---|---|---|---|---|---|---|---|---|
| `e6b9fb1e` | P2 | Blackman content tagged photorespiration | PARTIALLY CONFIRMED | KEEP | N | Y | PASS | easy→easy | PASS | GREEN |
| `8d50e829` | P2 | Compound Blackman stem; photorespiration | CONFIRMED | REVISE | Y | Y | PASS | hard→medium | PASS | GREEN |
| `85fee888` | P1 | Near-duplicate of 10d4d997 | CONFIRMED | REPLACE | Y | Y | PASS | medium→medium | PASS | GREEN |
| `87f621ab` | P2 | Overlong VSEPR vs VB stem | CONFIRMED | REVISE | Y | Y | PASS | hard→medium | PASS | GREEN |
| `863f1289` | P2 | Heavy 3p/3d/4s hybridisation wording | CONFIRMED | REVISE | Y | Y | PASS | hard→hard | PASS | GREEN |
| `ade9900b` | P2 | Kirchhoff tags on §3.2 current item | CONFIRMED | REVISE | Y | Y | PASS | hard→hard | PASS | GREEN |
| `c7a54ae9` | P2 | Trivial ohm unit recall | CONFIRMED | REPLACE | Y | Y | PASS | easy→easy | PASS | GREEN |
| `7b80d6db` | P1 | Kirchhoff sign-convention wording | PARTIALLY CONFIRMED | REVISE | Y | Y | PASS | hard→hard | PASS | GREEN |
| `a42a3589` | P2 | Verbatim 10⁻⁵ drift/thermal recall | CONFIRMED | REVISE | Y | Y | PASS | medium→easy | PASS | GREEN |

## Integrity

```text
Database writes by this task = 0
Pilot MCQs unchanged
ECAEP submit/approve/publish = not performed
AI proposed revision ≠ Human ECAEP approval
```
