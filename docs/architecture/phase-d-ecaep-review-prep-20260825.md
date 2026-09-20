# Phase D ECAEP Reviewer Evidence Report

**Pilot run:** `phase-d-30-mcq-authorized-20260825`

**Scope:** Exactly 30 CMS DRAFT questions from this pilot only. Historical `phase-d-30-mcq-v1` excluded.

**Authority:** AI checks below are advisory signals only. Human ECAEP review is authoritative. Nothing was APPROVED or PUBLISHED by this preparation.

## Review summary

| Subject | Questions | Ready for Review | CMS status |
|---|---:|---:|---|
| Physics | 10 | 10 | DRAFT |
| Chemistry | 10 | 10 | DRAFT |
| Biology | 10 | 10 | DRAFT |
| **TOTAL** | **30** | **30** | **DRAFT** |

## Safety check

- pilot_run_id = `phase-d-30-mcq-authorized-20260825`
- Questions = 30
- DRAFT = 30
- Published = 0
- ECAEP approved = 0
- New questions created this task = 0
- Historical run excluded = `phase-d-30-mcq-v1`

## Provenance completeness

All 30/30 have SourceDocument, IngestionJob, IngestionSection, source_page, KnowledgeUnit, ContentVersion.

## Chemistry rejected-candidate check

- Failed KUs on this pilot Chemistry job: **1**
- FAILED KU `ba4200b6-af55-46db-b2cd-8c1f8fe0c8e1` — status `FAILED` — **not linked to any final pilot question**
  - Facts preview: ["A double bond between carbon atoms consists of one sigma bond and one pi bond, as illustrated in the formation of C2H4.", "A triple bond between carbon atoms consists of one sigma bond and two pi bonds, as illustrated in the formation of C2H2.", "C2H2 (acetylene) contains both ...
- Linked pilot questions for failed KU: []
- All 10 Chemistry final questions use PASSED KnowledgeUnits only.

## AI validation rollup (advisory)

| Check | PASS | FAIL | NEEDS REVIEW |
|---|---:|---:|---:|
| A_source_grounding | 30 | 0 | 0 |
| B_correct_answer | 29 | 0 | 1 |
| C_explanation | 30 | 0 | 0 |
| D_distractors | 30 | 0 | 0 |
| E_academic_mapping | 30 | 0 | 0 |
| F_neet_suitability | 0 | 0 | 30 |
| G_duplicate | 30 | 0 | 0 |
| H_source_page | 30 | 0 | 0 |

### Flags for human attention

- `7b80d6db-9c07-4b42-a92d-df74ab8428b3` (Physics): B_correct_answer=NEEDS REVIEW — Lexical answer overlap low (formula/symbols); stem+explanation grounded — human must verify exact option vs NCERT.
- F_neet_suitability = NEEDS REVIEW for all 30 (human NEET judgment required).

## Duplicate check

Within-pilot stem Jaccard > 0.75: **0 pairs**. G_duplicate = PASS for all 30.

## Jobs

- Job `f5b496d3-399c-4290-8fc2-e9deac412a71` · `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf` · deduped=1 · KU rejected=0
- Job `da6a1664-e169-4e4d-873b-898e5f8c69ed` · `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf` · deduped=2 · KU rejected=1
- Job `a60ef885-2b4e-42ed-bb51-00627ede5747` · `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf` · deduped=8 · KU rejected=0

## Per-question evidence

CMS workflow reminder: keep DRAFT until a human submits via ECAEP (`DRAFT → SUBMITTED → IN_REVIEW → APPROVED/REJECTED → PUBLISHED`). Do not bypass.

## Q1. Biology — `5dc99543-bec7-4dc3-a283-548fdb62ca9c`

### Question identity

- Question ID: `5dc99543-bec7-4dc3-a283-548fdb62ca9c`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `light-reaction` — Light Reaction
- Concept: `photophosphorylation` — Photophosphorylation
- CMS status: **DRAFT**

### Question

**Stem:** Which of the following correctly distinguishes cyclic photophosphorylation from non-cyclic photophosphorylation?

- **A.** Cyclic photophosphorylation produces only ATP, while non-cyclic photophosphorylation produces both ATP and NADPH + H⁺ **[CORRECT]**
- **B.** Cyclic photophosphorylation produces both ATP and NADPH + H⁺, while non-cyclic produces only ATP
- **C.** Cyclic photophosphorylation involves both PS I and PS II, while non-cyclic involves only PS I
- **D.** Non-cyclic photophosphorylation occurs exclusively in stroma lamellae, while cyclic occurs in grana lamellae

**Correct answer:** A

**Explanation:** In cyclic photophosphorylation, only PS I is functional and electrons cycle back through the electron transport chain to PS I, resulting in the synthesis of ATP only — not NADPH + H⁺. In non-cyclic photophosphorylation, both PS II and PS I work in series via the Z scheme, producing both ATP and NADPH + H⁺.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `1a355ba3-6d49-4b75-a9ac-a3f4d71cbb47`
- Section heading: 11.6.2 Cyclic and Non-cyclic Photo-phosphorylation
- source page: **9**
- KnowledgeUnit ID: `55b46cfe-5d4b-49d0-b322-4ff6078c7495` (status `PASSED`)
- ContentVersion ID: `3e9f7b16-a58b-4beb-8da9-2a072321eea8`

### Source evidence (extracted section passage)

> Living organisms have the capability of extracting energy from oxidisable substances and store this in the form of bond energy. Special substances like ATP, carry this energy in their chemical bonds. The process through which Electron transport system - - e acceptor e acceptor Light Photosystem II Photosystem I NADPH NADP+ LHC LHC H O 2e + 2H + [O] 2 - + ADP+iP ATP Figure 11.5 Z scheme of light reaction 2024-25 140 BIOLOGY ATP is synthesised by cells (in mitochondria and chloroplasts) is named phosphorylation. Photo- phosphorylation is the synthesis of ATP from ADP and inorganic phosphate in the presence of light. When the two photosystems work in a series, first PS II and then the PS I, a process called non-cyclic photo-phosphorylation occurs. The two photosystems are connected through an electron transport chain, as seen earlier – in the Z scheme. Both ATP and NADPH + H+ are synthesised by this kind of electron flow (Figure 11.5). When only PS I is functional, the electron is circulated within the photosystem and the phosphorylation occurs due to cyclic flow of electrons (Figure 11.6). A possible location where this could be happening is in the stroma lamellae. While the membrane

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q2. Biology — `8a979c6a-d6af-4a0d-8099-05f5992b7f46`

### Question identity

- Question ID: `8a979c6a-d6af-4a0d-8099-05f5992b7f46`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `light-reaction` — Light Reaction
- Concept: `photophosphorylation` — Photophosphorylation
- CMS status: **DRAFT**

### Question

**Stem:** A researcher illuminates an isolated chloroplast preparation exclusively with light of wavelength 700 nm. Which of the following outcomes is most likely, and what structural feature explains it?

- **A.** Both ATP and NADPH + H⁺ are produced, because PS II is activated by wavelengths beyond 680 nm
- **B.** Only ATP is produced via cyclic photophosphorylation in stroma lamellae, because light beyond 680 nm cannot excite PS II and only PS I remains functional **[CORRECT]**
- **C.** Only NADPH + H⁺ is produced, because NADP reductase is exclusively active at wavelengths above 680 nm
- **D.** Neither ATP nor NADPH + H⁺ is produced, because wavelengths beyond 680 nm are insufficient to drive any photophosphorylation

**Correct answer:** B

**Explanation:** Light of wavelength 700 nm (beyond 680 nm) can only excite PS I, not PS II. When only PS I is functional, electrons cycle back through the electron transport chain to PS I (cyclic photophosphorylation), producing ATP but not NADPH + H⁺. This process is associated with stroma lamellae, whose membranes lack both PS II and NADP reductase enzyme, making cyclic photophosphorylation the only possible route.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `1a355ba3-6d49-4b75-a9ac-a3f4d71cbb47`
- Section heading: 11.6.2 Cyclic and Non-cyclic Photo-phosphorylation
- source page: **9**
- KnowledgeUnit ID: `55b46cfe-5d4b-49d0-b322-4ff6078c7495` (status `PASSED`)
- ContentVersion ID: `9d6392ca-10c5-424a-8e26-5cb41a5a61b0`

### Source evidence (extracted section passage)

> Living organisms have the capability of extracting energy from oxidisable substances and store this in the form of bond energy. Special substances like ATP, carry this energy in their chemical bonds. The process through which Electron transport system - - e acceptor e acceptor Light Photosystem II Photosystem I NADPH NADP+ LHC LHC H O 2e + 2H + [O] 2 - + ADP+iP ATP Figure 11.5 Z scheme of light reaction 2024-25 140 BIOLOGY ATP is synthesised by cells (in mitochondria and chloroplasts) is named phosphorylation. Photo- phosphorylation is the synthesis of ATP from ADP and inorganic phosphate in the presence of light. When the two photosystems work in a series, first PS II and then the PS I, a process called non-cyclic photo-phosphorylation occurs. The two photosystems are connected through an electron transport chain, as seen earlier – in the Z scheme. Both ATP and NADPH + H+ are synthesised by this kind of electron flow (Figure 11.5). When only PS I is functional, the electron is circulated within the photosystem and the phosphorylation occurs due to cyclic flow of electrons (Figure 11.6). A possible location where this could be happening is in the stroma lamellae. While the membrane

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q3. Biology — `2602f9da-13cc-42ba-b164-f02f1d7a040c`

### Question identity

- Question ID: `2602f9da-13cc-42ba-b164-f02f1d7a040c`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `dark-reaction` — Dark Reaction (Calvin Cycle)
- Concept: `c3-c4-pathway` — C3 vs C4 Pathway
- CMS status: **DRAFT**

### Question

**Stem:** In C4 plants, which enzyme is responsible for the primary fixation of CO2 in mesophyll cells, and what is the first stable product formed?

- **A.** PEP carboxylase; oxaloacetic acid (OAA) **[CORRECT]**
- **B.** RuBisCO; 3-phosphoglycerate (3-PGA)
- **C.** PEP carboxylase; 3-phosphoglycerate (3-PGA)
- **D.** RuBisCO; oxaloacetic acid (OAA)

**Correct answer:** A

**Explanation:** In C4 plants, the primary CO2 acceptor in mesophyll cells is the 3-carbon molecule phosphoenol pyruvate (PEP). The enzyme PEP carboxylase (PEPcase) catalyses the fixation of CO2 onto PEP, producing the 4-carbon compound oxaloacetic acid (OAA) as the first stable product. RuBisCO is absent from mesophyll cells in C4 plants and is instead confined to bundle sheath cells.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `61ce6dce-5df8-492f-b038-9aa256c55324`
- Section heading: 11.8 THE C4 PATHWAY
- source page: **15**
- KnowledgeUnit ID: `4eeff605-8330-47fc-bf11-71fcd680395a` (status `PASSED`)
- ContentVersion ID: `88417c2f-8c66-4033-ae18-2406ac3cdc5a`

### Source evidence (extracted section passage)

> Plants that are adapted to dry tropical regions have the C4 pathway mentioned earlier. Though these plants have the C4 oxaloacetic acid as the first CO2 fixation product they use the C3 pathway or the Calvin cycle as the main biosynthetic pathway. Then, in what way are they different from C3 plants? This is a question that you may reasonably ask. C4 plants are special: They have a special type of leaf anatomy, they tolerate higher temperatures, they show a response to high light intensities, they lack a process called photorespiration and have greater productivity of biomass. Let us understand these one by one. Study vertical sections of leaves, one of a C3 plant and the other of a C4 plant. Do you notice the differences? Do both have the same types of mesophylls? Do they have similar cells around the vascular bundle sheath? The particularly large cells around the vascular bundles of the C4 plants are called bundle sheath cells, and the leaves which have such anatomy are said to have ‘Kranz’ anatomy. ‘Kranz’ means ‘wreath’ and is a reflection of the arrangement of cells. The bundle sheath cells may form several layers around the vascular bundles; they are characterised by having a 

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q4. Biology — `f81153c3-b3d6-4a0c-a908-ffb9c032bd8c`

### Question identity

- Question ID: `f81153c3-b3d6-4a0c-a908-ffb9c032bd8c`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `dark-reaction` — Dark Reaction (Calvin Cycle)
- Concept: `c3-c4-pathway` — C3 vs C4 Pathway
- CMS status: **DRAFT**

### Question

**Stem:** A student examining a leaf cross-section observes large cells surrounding the vascular bundles. These cells have numerous chloroplasts, walls impervious to gaseous exchange, and no intercellular spaces. The student also notes that the surrounding mesophyll cells lack RuBisCO. Which of the following combinations correctly describes the enzyme distribution and site of Calvin cycle operation in this leaf?

- **A.** Mesophyll cells contain PEPcase; bundle sheath cells contain RuBisCO; Calvin cycle occurs only in bundle sheath cells **[CORRECT]**
- **B.** Both mesophyll and bundle sheath cells contain RuBisCO; Calvin cycle occurs in all cells
- **C.** Mesophyll cells contain RuBisCO; bundle sheath cells contain PEPcase; Calvin cycle occurs in mesophyll cells
- **D.** Mesophyll cells contain PEPcase; bundle sheath cells contain PEPcase; Calvin cycle does not occur in this leaf

**Correct answer:** A

**Explanation:** The described leaf has Kranz anatomy, characteristic of C4 plants. In C4 plants, mesophyll cells contain PEP carboxylase (PEPcase) but lack RuBisCO; they fix CO2 into 4-carbon acids (OAA, malic acid, or aspartic acid). These acids are transported to bundle sheath cells, which are rich in RuBisCO but lack PEPcase. CO2 is released in bundle sheath cells and enters the Calvin cycle, which in C4 plants operates exclusively in the bundle sheath cells, not in mesophyll cells.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `61ce6dce-5df8-492f-b038-9aa256c55324`
- Section heading: 11.8 THE C4 PATHWAY
- source page: **15**
- KnowledgeUnit ID: `4eeff605-8330-47fc-bf11-71fcd680395a` (status `PASSED`)
- ContentVersion ID: `5d7991f3-4238-4c21-bcc3-0659a14cbfcf`

### Source evidence (extracted section passage)

> Plants that are adapted to dry tropical regions have the C4 pathway mentioned earlier. Though these plants have the C4 oxaloacetic acid as the first CO2 fixation product they use the C3 pathway or the Calvin cycle as the main biosynthetic pathway. Then, in what way are they different from C3 plants? This is a question that you may reasonably ask. C4 plants are special: They have a special type of leaf anatomy, they tolerate higher temperatures, they show a response to high light intensities, they lack a process called photorespiration and have greater productivity of biomass. Let us understand these one by one. Study vertical sections of leaves, one of a C3 plant and the other of a C4 plant. Do you notice the differences? Do both have the same types of mesophylls? Do they have similar cells around the vascular bundle sheath? The particularly large cells around the vascular bundles of the C4 plants are called bundle sheath cells, and the leaves which have such anatomy are said to have ‘Kranz’ anatomy. ‘Kranz’ means ‘wreath’ and is a reflection of the arrangement of cells. The bundle sheath cells may form several layers around the vascular bundles; they are characterised by having a 

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q5. Biology — `f78dbbf2-1b1e-4fe7-87aa-263699cdd30f`

### Question identity

- Question ID: `f78dbbf2-1b1e-4fe7-87aa-263699cdd30f`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `dark-reaction` — Dark Reaction (Calvin Cycle)
- Concept: `c3-c4-pathway` — C3 vs C4 Pathway
- CMS status: **DRAFT**

### Question

**Stem:** Which of the following correctly distinguishes the roles of mesophyll cells and bundle sheath cells in C4 plants?

- **A.** Mesophyll cells fix CO2 using PEP carboxylase to form OAA, while bundle sheath cells receive C4 acids, release CO2, and carry out the Calvin cycle using RuBisCO **[CORRECT]**
- **B.** Mesophyll cells carry out the Calvin cycle using RuBisCO, while bundle sheath cells fix CO2 using PEP carboxylase to form OAA
- **C.** Both mesophyll cells and bundle sheath cells fix CO2 using PEP carboxylase, but only mesophyll cells carry out the Calvin cycle
- **D.** Mesophyll cells fix CO2 using RuBisCO, while bundle sheath cells transport C4 acids back to mesophyll cells for the Calvin cycle

**Correct answer:** A

**Explanation:** In C4 plants, the primary CO2 fixation occurs in mesophyll cells using PEP carboxylase (PEPcase), which is absent in bundle sheath cells. The resulting C4 acids (such as OAA, malic acid, or aspartic acid) are transported to bundle sheath cells, where they are broken down to release CO2. This CO2 then enters the Calvin cycle, which is carried out by RuBisCO present in bundle sheath cells. RuBisCO is absent from mesophyll cells, and the Calvin pathway does not occur there.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `61ce6dce-5df8-492f-b038-9aa256c55324`
- Section heading: 11.8 THE C4 PATHWAY
- source page: **15**
- KnowledgeUnit ID: `4eeff605-8330-47fc-bf11-71fcd680395a` (status `PASSED`)
- ContentVersion ID: `aeeeccaa-7501-43b2-84ea-8dbc29ba5d37`

### Source evidence (extracted section passage)

> Plants that are adapted to dry tropical regions have the C4 pathway mentioned earlier. Though these plants have the C4 oxaloacetic acid as the first CO2 fixation product they use the C3 pathway or the Calvin cycle as the main biosynthetic pathway. Then, in what way are they different from C3 plants? This is a question that you may reasonably ask. C4 plants are special: They have a special type of leaf anatomy, they tolerate higher temperatures, they show a response to high light intensities, they lack a process called photorespiration and have greater productivity of biomass. Let us understand these one by one. Study vertical sections of leaves, one of a C3 plant and the other of a C4 plant. Do you notice the differences? Do both have the same types of mesophylls? Do they have similar cells around the vascular bundle sheath? The particularly large cells around the vascular bundles of the C4 plants are called bundle sheath cells, and the leaves which have such anatomy are said to have ‘Kranz’ anatomy. ‘Kranz’ means ‘wreath’ and is a reflection of the arrangement of cells. The bundle sheath cells may form several layers around the vascular bundles; they are characterised by having a 

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q6. Biology — `10d4d997-cb60-4450-99e8-47ed905c9775`

### Question identity

- Question ID: `10d4d997-cb60-4450-99e8-47ed905c9775`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `factors-affecting-photosynthesis` — Factors Affecting Photosynthesis
- Concept: `photorespiration` — Photorespiration
- CMS status: **DRAFT**

### Question

**Stem:** In C3 plants, when O2 binds to RuBisCO instead of CO2, RuBP combines with O2 to form which of the following products?

- **A.** One molecule of phosphoglycerate and one molecule of phosphoglycolate **[CORRECT]**
- **B.** Two molecules of phosphoglycerate
- **C.** One molecule of oxaloacetate and one molecule of phosphoglycerate
- **D.** Two molecules of phosphoglycolate

**Correct answer:** A

**Explanation:** In the photorespiratory pathway in C3 plants, RuBP reacts with O2 (instead of CO2) at the active site of RuBisCO to produce one molecule of phosphoglycerate and one molecule of phosphoglycolate (a 2-carbon compound). This pathway does not produce sugars, ATP, or NADPH, but instead releases CO2 while consuming ATP.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `96872144-0091-4852-8783-79dd1e049876`
- Section heading: 11.9 PHOTORESPIRATION
- source page: **17**
- KnowledgeUnit ID: `f01e615a-6cba-4611-b0ec-2a0a23a482d8` (status `PASSED`)
- ContentVersion ID: `cc8ff85b-9cbc-48bb-af14-4b68f9fd4cb0`

### Source evidence (extracted section passage)

> Let us try and understand one more process that creates an important difference between C3 and C4 plants – Photorespiration. To understand photorespiration we have to know a little bit more about the first step of the Calvin pathway – the first CO2 fixation step. This is the reaction where RuBP combines with CO2 to form 2 molecules of 3PGA, that is catalysed by RuBisCO. RuBP CO PGA RuBisCo +  →  × 2 2 3 RuBisCO that is the most abundant enzyme in the world (Do you wonder why?) is characterised by the fact that its active site can bind to both CO2 and O2 – hence the name. Can you think how this could be possible? RuBisCO has a much greater affinity for CO2 when the CO2: O2 is nearly equal. Imagine what would happen if this were not so! This binding is competitive. It is the relative concentration of O2 and CO2 that determines which of the two will bind to the enzyme. In C3 plants some O2 does bind to RuBisCO, and hence CO2 fixation is decreased. Here the RuBP instead of being converted to 2 molecules of PGA binds with O2 to form one molecule of phosphoglycerate and phosphoglycolate (2 Carbon) in a pathway called photorespiration. In the photorespiratory pathway, there is neith

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q7. Biology — `fc61e6e7-c1fd-4d2e-b009-283506e841ff`

### Question identity

- Question ID: `fc61e6e7-c1fd-4d2e-b009-283506e841ff`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `factors-affecting-photosynthesis` — Factors Affecting Photosynthesis
- Concept: `photorespiration` — Photorespiration
- CMS status: **DRAFT**

### Question

**Stem:** A researcher compares two crop plants — one a C3 species and one a C4 species — under conditions of high temperature and high light intensity. Which of the following best explains why the C4 plant shows greater productivity under these conditions?

- **A.** C4 plants fix CO2 only in mesophyll cells, completely bypassing RuBisCO and its dual affinity for O2
- **B.** C4 plants break down C4 acids in bundle sheath cells to release CO2, raising the CO2 concentration at the RuBisCO site so that its carboxylase activity dominates over its oxygenase activity, preventing photorespiration **[CORRECT]**
- **C.** C4 plants possess a modified form of RuBisCO that has no affinity for O2, so photorespiration cannot occur regardless of O2 levels
- **D.** C4 plants synthesise additional ATP and NADPH during photorespiration, compensating for the CO2 lost and thus maintaining higher productivity

**Correct answer:** B

**Explanation:** In C4 plants, C4 acids formed in mesophyll cells are transported to bundle sheath cells where they are broken down to release CO2. This raises the intracellular CO2 concentration at the RuBisCO site, ensuring that RuBisCO functions primarily as a carboxylase and minimising its oxygenase activity. As a result, photorespiration is suppressed, and unlike the C3 photorespiratory pathway (which consumes ATP and releases CO2 without producing sugars or NADPH), carbon is efficiently fixed into sugars — contributing to better productivity, higher yields, and tolerance to higher temperatures in C4 plants.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `96872144-0091-4852-8783-79dd1e049876`
- Section heading: 11.9 PHOTORESPIRATION
- source page: **17**
- KnowledgeUnit ID: `f01e615a-6cba-4611-b0ec-2a0a23a482d8` (status `PASSED`)
- ContentVersion ID: `090900c3-0116-4929-b4ee-6d1ed64538e3`

### Source evidence (extracted section passage)

> Let us try and understand one more process that creates an important difference between C3 and C4 plants – Photorespiration. To understand photorespiration we have to know a little bit more about the first step of the Calvin pathway – the first CO2 fixation step. This is the reaction where RuBP combines with CO2 to form 2 molecules of 3PGA, that is catalysed by RuBisCO. RuBP CO PGA RuBisCo +  →  × 2 2 3 RuBisCO that is the most abundant enzyme in the world (Do you wonder why?) is characterised by the fact that its active site can bind to both CO2 and O2 – hence the name. Can you think how this could be possible? RuBisCO has a much greater affinity for CO2 when the CO2: O2 is nearly equal. Imagine what would happen if this were not so! This binding is competitive. It is the relative concentration of O2 and CO2 that determines which of the two will bind to the enzyme. In C3 plants some O2 does bind to RuBisCO, and hence CO2 fixation is decreased. Here the RuBP instead of being converted to 2 molecules of PGA binds with O2 to form one molecule of phosphoglycerate and phosphoglycolate (2 Carbon) in a pathway called photorespiration. In the photorespiratory pathway, there is neith

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q8. Biology — `85fee888-47f6-408d-ab05-39b131233322`

### Question identity

- Question ID: `85fee888-47f6-408d-ab05-39b131233322`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `factors-affecting-photosynthesis` — Factors Affecting Photosynthesis
- Concept: `photorespiration` — Photorespiration
- CMS status: **DRAFT**

### Question

**Stem:** In the photorespiratory pathway of C3 plants, RuBP reacts with O2 at the active site of RuBisCO to produce which of the following products?

- **A.** One molecule of phosphoglycerate and one molecule of phosphoglycolate **[CORRECT]**
- **B.** Two molecules of phosphoglycerate
- **C.** One molecule of phosphoglycerate and one molecule of ATP
- **D.** Two molecules of phosphoglycolate and one molecule of NADPH

**Correct answer:** A

**Explanation:** When O2 binds to RuBisCO in C3 plants, RuBP combines with O2 instead of CO2, producing one molecule of phosphoglycerate and one molecule of phosphoglycolate (a 2-carbon compound). This pathway neither produces sugars, ATP, nor NADPH, but instead consumes ATP and releases CO2.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `96872144-0091-4852-8783-79dd1e049876`
- Section heading: 11.9 PHOTORESPIRATION
- source page: **17**
- KnowledgeUnit ID: `f01e615a-6cba-4611-b0ec-2a0a23a482d8` (status `PASSED`)
- ContentVersion ID: `d4c89a95-b134-4c1b-bfc8-645679d14c74`

### Source evidence (extracted section passage)

> Let us try and understand one more process that creates an important difference between C3 and C4 plants – Photorespiration. To understand photorespiration we have to know a little bit more about the first step of the Calvin pathway – the first CO2 fixation step. This is the reaction where RuBP combines with CO2 to form 2 molecules of 3PGA, that is catalysed by RuBisCO. RuBP CO PGA RuBisCo +  →  × 2 2 3 RuBisCO that is the most abundant enzyme in the world (Do you wonder why?) is characterised by the fact that its active site can bind to both CO2 and O2 – hence the name. Can you think how this could be possible? RuBisCO has a much greater affinity for CO2 when the CO2: O2 is nearly equal. Imagine what would happen if this were not so! This binding is competitive. It is the relative concentration of O2 and CO2 that determines which of the two will bind to the enzyme. In C3 plants some O2 does bind to RuBisCO, and hence CO2 fixation is decreased. Here the RuBP instead of being converted to 2 molecules of PGA binds with O2 to form one molecule of phosphoglycerate and phosphoglycolate (2 Carbon) in a pathway called photorespiration. In the photorespiratory pathway, there is neith

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q9. Biology — `e6b9fb1e-f022-4172-88c5-318213bc511b`

### Question identity

- Question ID: `e6b9fb1e-f022-4172-88c5-318213bc511b`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `factors-affecting-photosynthesis` — Factors Affecting Photosynthesis
- Concept: `photorespiration` — Photorespiration
- CMS status: **DRAFT**

### Question

**Stem:** According to Blackman's Law of Limiting Factors (1905), which of the following correctly defines the 'limiting factor' in a chemical process affected by multiple factors?

- **A.** The factor that is nearest to its minimal value and directly controls the rate of the process **[CORRECT]**
- **B.** The factor present in the highest concentration that accelerates the process
- **C.** The factor that remains constant while all other factors vary
- **D.** The factor that is at its optimal level and sustains the maximum rate of the process

**Correct answer:** A

**Explanation:** Blackman's Law of Limiting Factors (1905) states that if a chemical process is affected by more than one factor, its rate will be determined by the factor nearest to its minimal value. This is the limiting factor — the one that directly affects the process if its quantity is changed.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `fd9aaca0-9064-4ddf-a86e-83c4a1f54d46`
- Section heading: 11.10 FACTORS AFFECTING PHOTOSYNTHESIS
- source page: **19**
- KnowledgeUnit ID: `6f938534-fbdb-4ce0-9ca0-140d717b3876` (status `PASSED`)
- ContentVersion ID: `f89eded3-f96a-4f98-ae81-bb4022353c48`

### Source evidence (extracted section passage)

> An understanding of the factors that affect photosynthesis is necessary. The rate of photosynthesis is very important in determining the yield of plants including crop plants. Photosynthesis is under the influence of several factors, both internal (plant) and external. The plant factors include the number, size, age and orientation of leaves, mesophyll cells and chloroplasts, internal CO2 concentration and the amount of chlorophyll. The plant or internal factors are dependent on the genetic predisposition and the growth of the plant. The external factors would include the availability of sunlight, temperature, CO2 concentration and water. As a plant photosynthesises, all these factors will simultaneously affect its rate. Hence, though several factors interact and simultaneously affect photosynthesis or CO2 fixation, usually one factor is the major cause or is the one that limits the rate. Hence, at any point the rate will be determined by the factor available at sub-optimal levels. When several factors affect any [bio] chemical process, Blackman’s (1905) Law of Limiting Factors comes into effect. This states the following: If a chemical process is affected by more than one factor, 

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q10. Biology — `8d50e829-6540-44bc-882a-6b140a33da17`

### Question identity

- Question ID: `8d50e829-6540-44bc-882a-6b140a33da17`
- Subject: Biology (`BOTANY`)
- Class: 11
- Chapter: `photosynthesis` — Photosynthesis in Higher Plants
- Topic: `factors-affecting-photosynthesis` — Factors Affecting Photosynthesis
- Concept: `photorespiration` — Photorespiration
- CMS status: **DRAFT**

### Question

**Stem:** A plant is provided with optimal light intensity and an abundant supply of CO2, yet its rate of photosynthesis remains very low. Which of the following best explains this observation, and which internal factor could additionally limit photosynthesis even if external conditions were made optimal?

- **A.** Very low temperature is the external limiting factor as per Blackman's Law; internally, reduced amount of chlorophyll could further limit photosynthesis **[CORRECT]**
- **B.** High CO2 concentration is the limiting factor; internally, a large number of leaves would reduce the rate of photosynthesis
- **C.** Excess light is inhibiting photosynthesis; internally, increased mesophyll cell number is the limiting internal factor
- **D.** Water availability is always the primary limiting factor regardless of other conditions; internal CO2 concentration has no role

**Correct answer:** A

**Explanation:** Blackman's Law of Limiting Factors explains that despite optimal light and CO2, a very low temperature can limit photosynthesis because temperature is the factor nearest to its minimal value. Additionally, internal factors such as the amount of chlorophyll are listed as internal determinants of photosynthesis; reduced chlorophyll would limit photosynthesis even if all external factors were made optimal.

### Source provenance

- SourceDocument ID: `5decdc2c-b443-4630-8df7-dc2041693f8c`
- filename: `ncert-books-class-11-biology-chapter-11.pdf`
- relative source path: `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf`
- SHA-256: `e2dbdb1ec7793daa87101e8264dfe039f7d277ad6153b904ec078d65ed1adbc8`
- IngestionJob ID: `f5b496d3-399c-4290-8fc2-e9deac412a71`
- IngestionSection ID: `fd9aaca0-9064-4ddf-a86e-83c4a1f54d46`
- Section heading: 11.10 FACTORS AFFECTING PHOTOSYNTHESIS
- source page: **19**
- KnowledgeUnit ID: `6f938534-fbdb-4ce0-9ca0-140d717b3876` (status `PASSED`)
- ContentVersion ID: `a614bc69-58be-4486-8468-01e40ced2548`

### Source evidence (extracted section passage)

> An understanding of the factors that affect photosynthesis is necessary. The rate of photosynthesis is very important in determining the yield of plants including crop plants. Photosynthesis is under the influence of several factors, both internal (plant) and external. The plant factors include the number, size, age and orientation of leaves, mesophyll cells and chloroplasts, internal CO2 concentration and the amount of chlorophyll. The plant or internal factors are dependent on the genetic predisposition and the growth of the plant. The external factors would include the availability of sunlight, temperature, CO2 concentration and water. As a plant photosynthesises, all these factors will simultaneously affect its rate. Hence, though several factors interact and simultaneously affect photosynthesis or CO2 fixation, usually one factor is the major cause or is the one that limits the rate. Hence, at any point the rate will be determined by the factor available at sub-optimal levels. When several factors affect any [bio] chemical process, Blackman’s (1905) Law of Limiting Factors comes into effect. This states the following: If a chemical process is affected by more than one factor, 

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q11. Chemistry — `c91a89ec-e071-495c-a6e1-3f2888e7233a`

### Question identity

- Question ID: `c91a89ec-e071-495c-a6e1-3f2888e7233a`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `ionic-bonding` — Ionic Bonding
- Concept: `lattice-energy` — Lattice Energy
- CMS status: **DRAFT**

### Question

**Stem:** What is the lattice enthalpy of NaCl, and what does this value represent?

- **A.** 788 kJ mol-1; the energy required to separate one mole of solid NaCl into one mole of Na+(g) and one mole of Cl-(g) at an infinite distance **[CORRECT]**
- **B.** 788 kJ mol-1; the energy released when one mole of Na+(g) and one mole of Cl-(g) combine to form solid NaCl
- **C.** 488 kJ mol-1; the energy required to separate one mole of solid NaCl into its constituent atoms in the gaseous state
- **D.** 788 kJ mol-1; the energy required to melt one mole of solid NaCl into a liquid

**Correct answer:** A

**Explanation:** By definition, lattice enthalpy is the energy required to completely separate one mole of a solid ionic compound into its gaseous constituent ions. For NaCl, this value is 788 kJ mol-1, representing the energy needed to convert one mole of solid NaCl into one mole of Na+(g) and one mole of Cl-(g) separated to an infinite distance.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `75645f16-7221-4630-97ae-ff7d4e80f68b`
- Section heading: 4.2.1 Lattice Enthalpy
- source page: **8**
- KnowledgeUnit ID: `1936007d-feb3-4521-befd-9e503d466739` (status `PASSED`)
- ContentVersion ID: `62817ce5-80e4-404d-a2a3-e69dcf046cf2`

### Source evidence (extracted section passage)

> The Lattice Enthalpy of an ionic solid is defined as the energy required to completely separate one mole of a solid ionic compound into gaseous constituent ions. For example, the lattice enthalpy of NaCl is 788 kJ mol–1. This means that 788 kJ of energy is required to separate one mole of solid NaCl into one mole of Na+ (g) and one mole of Cl– (g) to an infinite distance. This process involves both the attractive forces between ions of opposite charges and the repulsive forces between ions of like charge. The solid crystal being three- dimensional; it is not possible to calculate lattice enthalpy directly from the interaction of forces of attraction and repulsion only. Factors associated with the crystal geometry have to be included.

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q12. Chemistry — `b33b47de-e94c-481b-a298-b64c67b5ec8d`

### Question identity

- Question ID: `b33b47de-e94c-481b-a298-b64c67b5ec8d`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `ionic-bonding` — Ionic Bonding
- Concept: `lattice-energy` — Lattice Energy
- CMS status: **DRAFT**

### Question

**Stem:** A student attempts to calculate the lattice enthalpy of a solid ionic compound by summing only the attractive forces between oppositely charged ions and the repulsive forces between like-charged ions. Which of the following best explains why this approach is insufficient, and what additional consideration is required?

- **A.** This approach is insufficient because it ignores the thermal energy of the ions; the kinetic energy of each ion at room temperature must be added to the calculation.
- **B.** This approach is insufficient because the ionic solid is three-dimensional, so factors associated with crystal geometry must also be included in the calculation. **[CORRECT]**
- **C.** This approach is sufficient for small unit cells but becomes insufficient for large crystals because the number of ion pairs exceeds Avogadro's number.
- **D.** This approach is insufficient because it ignores the covalent character of ionic bonds, which must be separately quantified for each ion pair.

**Correct answer:** B

**Explanation:** According to the textbook, it is not possible to calculate lattice enthalpy directly from the interaction of attractive and repulsive forces alone because the solid crystal is three-dimensional. Factors associated with the crystal geometry must also be included. The student's approach omits this geometric consideration, making it incomplete.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `75645f16-7221-4630-97ae-ff7d4e80f68b`
- Section heading: 4.2.1 Lattice Enthalpy
- source page: **8**
- KnowledgeUnit ID: `1936007d-feb3-4521-befd-9e503d466739` (status `PASSED`)
- ContentVersion ID: `071ef081-5ef5-4c54-8296-170897cfb777`

### Source evidence (extracted section passage)

> The Lattice Enthalpy of an ionic solid is defined as the energy required to completely separate one mole of a solid ionic compound into gaseous constituent ions. For example, the lattice enthalpy of NaCl is 788 kJ mol–1. This means that 788 kJ of energy is required to separate one mole of solid NaCl into one mole of Na+ (g) and one mole of Cl– (g) to an infinite distance. This process involves both the attractive forces between ions of opposite charges and the repulsive forces between ions of like charge. The solid crystal being three- dimensional; it is not possible to calculate lattice enthalpy directly from the interaction of forces of attraction and repulsion only. Factors associated with the crystal geometry have to be included.

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q13. Chemistry — `87f621ab-a1d8-4097-8152-573b6fa46914`

### Question identity

- Question ID: `87f621ab-a1d8-4097-8152-573b6fa46914`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `covalent-bonding-vsepr` — Covalent Bonding and VSEPR Theory
- Concept: `vsepr-theory` — VSEPR Theory
- CMS status: **DRAFT**

### Question

**Stem:** A student argues that VSEPR theory is sufficient for all purposes of studying molecular bonding because it successfully predicts molecular geometry. Which of the following statements BEST refutes this argument using the context of Valence Bond theory?

- **A.** VSEPR theory incorrectly predicts the geometry of H2, whereas VB theory predicts a bond length of 74 pm and bond enthalpy of 435.8 kJ mol⁻¹
- **B.** VSEPR theory has unlimited applications but VB theory is more mathematically elegant
- **C.** VSEPR theory only predicts geometry without theoretical explanation and has limited applications, whereas VB theory explains bond formation in terms of a balance between attractive and repulsive forces leading to minimum potential energy **[CORRECT]**
- **D.** VSEPR theory correctly explains why repulsive forces between nuclei and electrons outweigh attractive forces in H2 formation

**Correct answer:** C

**Explanation:** VSEPR theory is limited because it predicts geometry of simple molecules but does not theoretically explain bond formation and has limited applications. VB theory, introduced by Heitler and London in 1927, provides a theoretical basis by showing that bond formation in H2 results from attractive forces (NA–eB, NB–eA) outweighing repulsive forces, leading to minimum energy at a bond length of 74 pm with a bond enthalpy of 435.8 kJ mol⁻¹. Option A is incorrect as VSEPR does not incorrectly predict H2 geometry; option D is factually inverted; option B is unsupported by the given facts.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `2fc1d70d-78ff-4a7b-a301-3c13c666e5a0`
- Section heading: 4.5 Valence Bond Theory
- source page: **18**
- KnowledgeUnit ID: `e86cfd41-ae62-48f8-8011-6ee21650fa89` (status `PASSED`)
- ContentVersion ID: `012ca4ee-911e-4e0a-aaa3-7fb112685f55`

### Source evidence (extracted section passage)

> As we know that Lewis approach helps in writing the structure of molecules but it fails to explain the formation of chemical bond. It also does not give any reason for the difference in bond dissociation enthalpies and bond lengths in molecules like H2 (435.8 kJ mol-1, 74 pm) and F2 (155 kJ mol-1, 144 pm), although in both the cases a single covalent bond is formed by the sharing of an electron pair between the respective atoms. It also gives no idea about the shapes of polyatomic molecules. Similarly the VSEPR theory gives the geometry of simple molecules but theoretically, it does not explain them and also it has limited applications. To overcome these limitations the two important theories based on quantum mechanical principles are introduced. These are valence bond (VB) theory and molecular orbital (MO) theory. Valence bond theory was introduced by Heitler and London (1927) and developed further by Pauling and others. A discussion of the valence bond theory is based on the knowledge of atomic orbitals, electronic configurations of elements (Units 2), the overlap criteria of atomic orbitals, the hybridization of atomic orbitals and the principles of variation and superposition. 

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q14. Chemistry — `90d13ef4-c0bc-4534-9c7c-2ad725946d2c`

### Question identity

- Question ID: `90d13ef4-c0bc-4534-9c7c-2ad725946d2c`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `hybridization` — Hybridization
- Concept: `sp-sp2-sp3` — sp, sp2, sp3 Hybridization
- CMS status: **DRAFT**

### Question

**Stem:** In a molecule like NH₃, the lone pair on nitrogen participates in sp³ hybridisation along with the three bond pairs. Which of the following statements best justifies why filled orbitals are included in hybridisation, and what consequence does this have on molecular geometry?

- **A.** Filled orbitals participate because only half-filled orbitals can hybridise; the lone pair does not affect geometry.
- **B.** Filled orbitals of the valence shell can participate in hybridisation; including the lone pair in sp³ hybridisation directs all four electron pairs in space to minimise repulsion, giving NH₃ a trigonal pyramidal geometry. **[CORRECT]**
- **C.** Filled orbitals participate only when the molecule is ionic; the resulting hybrid orbitals are unequal in energy.
- **D.** Filled orbitals never participate in hybridisation; the geometry of NH₃ is determined solely by the three bond pairs arranged in a planar triangle.

**Correct answer:** B

**Explanation:** The NCERT text explicitly states that it is not necessary that only half-filled orbitals participate in hybridisation — even filled orbitals of the valence shell can take part. In NH₃, the lone pair on nitrogen is included in sp³ hybridisation. Since hybrid orbitals are directed in space to minimise electron-pair repulsion, all four sp³ orbitals (three bonding + one lone pair) adopt a tetrahedral arrangement of electron pairs, resulting in a trigonal pyramidal molecular geometry. The hybrid orbitals formed are always equivalent in energy and shape.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `deee43b4-9ce4-49fe-bebc-f3ae1ed58dba`
- Section heading: 4.6 Hybridisation
- source page: **21**
- KnowledgeUnit ID: `e5856110-1f8b-44f6-b465-b46af5618286` (status `PASSED`)
- ContentVersion ID: `6fe826f8-cec4-4106-8d3c-b6afedd8d69f`

### Source evidence (extracted section passage)

> In order to explain the characteristic geometrical shapes of polyatomic molecules like CH4, NH3 and H2O etc., Pauling introduced the concept of hybridisation. According to him the atomic orbitals combine to form new set of equivalent orbitals known as hybrid orbitals. Unlike pure orbitals, the hybrid orbitals are used in bond formation. The phenomenon is known as hybridisation which can be defined as the process of intermixing of the orbitals of slightly different energies so as to redistribute their energies, resulting in the formation of new set of orbitals of equivalent energies and shape. For example when one 2s and three 2p-orbitals of carbon hybridise, there is the formation of four new sp3 hybrid orbitals. Salient features of hybridisation: The main features of hybridisation are as under : 1. The number of hybrid orbitals is equal to the number of the atomic orbitals that get hybridised. 2. The hybridised orbitals are always equivalent in energy and shape. 2024-25 121 Chemical Bonding And Molecular Structure 3. The hybrid orbitals are more effective in forming stable bonds than the pure atomic orbitals. 4. These hybrid orbitals are directed in space in some preferred directi

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q15. Chemistry — `acbbdd83-8e13-4b3f-87cc-45cd00985ab4`

### Question identity

- Question ID: `acbbdd83-8e13-4b3f-87cc-45cd00985ab4`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `hybridization` — Hybridization
- Concept: `sp-sp2-sp3` — sp, sp2, sp3 Hybridization
- CMS status: **DRAFT**

### Question

**Stem:** Which type of hybridisation involves the mixing of one s-orbital and two p-orbitals, resulting in a trigonal planar arrangement with bond angles of 120°, as exemplified by BCl3?

- **A.** sp2 hybridisation **[CORRECT]**
- **B.** sp hybridisation
- **C.** sp3 hybridisation
- **D.** sp3d hybridisation

**Correct answer:** A

**Explanation:** sp2 hybridisation involves the mixing of one s and two p-orbitals to form three equivalent sp2 hybrid orbitals oriented in a trigonal planar arrangement with bond angles of 120°. BCl3 is the classic example given in the textbook for this type of hybridisation.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `0d6d4998-9263-428f-8e51-7b914eb4b1d8`
- Section heading: 4.6.1 Types of Hybridisation
- source page: **22**
- KnowledgeUnit ID: `cf56609d-ae8c-4bde-89f9-a1fbe2278b61` (status `PASSED`)
- ContentVersion ID: `62f38d7e-e9c5-4377-8167-fc09c301970b`

### Source evidence (extracted section passage)

> There are various types of hybridisation involving s, p and d orbitals. The different types of hybridisation are as under: (I) sp hybridisation: This type of hybridisation involves the mixing of one s and one p orbital resulting in the formation of two equivalent sp hybrid orbitals. The suitable orbitals for sp hybridisation are s and pz, if the hybrid orbitals are to lie along the z-axis. Each sp hybrid orbitals has 50% s-character and 50% p-character. Such a molecule in which the central atom is sp-hybridised and linked directly to two other central atoms possesses linear geometry. This type of hybridisation is also known as diagonal hybridisation. The two sp hybrids point in the opposite direction along the z-axis with projecting positive lobes and very small negative lobes, which provides more effective overlapping resulting in the formation of stronger bonds. Example of molecule having sp hybridisation BeCl 2: The ground state electronic configuration of Be is 1s22s2. In the exited state one of the 2s-electrons is promoted to vacant 2p orbital to account for its bivalency. One 2s and one 2p-orbital gets hybridised to form two sp hybridised orbitals. These two sp hybrid orbital

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q16. Chemistry — `2f165110-be0b-402e-aa6c-2b92c6593771`

### Question identity

- Question ID: `2f165110-be0b-402e-aa6c-2b92c6593771`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `hybridization` — Hybridization
- Concept: `sp-sp2-sp3` — sp, sp2, sp3 Hybridization
- CMS status: **DRAFT**

### Question

**Stem:** The H–O–H bond angle in water (104.5°) is less than the H–N–H bond angle in ammonia (107°), which in turn is less than the ideal tetrahedral angle (109.5°). The best explanation for this progressive decrease, based on sp3 hybridisation and repulsion principles, is:

- **A.** Water has two lone pairs on oxygen causing greater lone pair–bond pair repulsion than the single lone pair on nitrogen in ammonia, compressing the bond angle further. **[CORRECT]**
- **B.** Oxygen is more electronegative than nitrogen, so O–H bond pairs are held closer to oxygen, reducing repulsion and widening the bond angle.
- **C.** Nitrogen has a smaller atomic radius than oxygen, causing greater bond pair–bond pair repulsion in NH3 and a smaller bond angle.
- **D.** Water has stronger bond pair–bond pair repulsions than ammonia because hydrogen atoms in water are larger than in ammonia.

**Correct answer:** A

**Explanation:** Both NH3 and H2O involve sp3 hybridisation at the central atom. In NH3, one sp3 orbital contains a lone pair, and lone pair–bond pair repulsion reduces the bond angle from 109.5° to 107°. In H2O, two sp3 orbitals contain lone pairs; the greater number of lone pairs leads to stronger lone pair–bond pair repulsions, compressing the bond angle further to 104.5°. This progressive decrease is directly explained by the increasing number of lone pairs increasing repulsion on the bond pairs.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `0d6d4998-9263-428f-8e51-7b914eb4b1d8`
- Section heading: 4.6.1 Types of Hybridisation
- source page: **22**
- KnowledgeUnit ID: `cf56609d-ae8c-4bde-89f9-a1fbe2278b61` (status `PASSED`)
- ContentVersion ID: `bd762a20-94ea-493c-a731-6f8130194bd7`

### Source evidence (extracted section passage)

> There are various types of hybridisation involving s, p and d orbitals. The different types of hybridisation are as under: (I) sp hybridisation: This type of hybridisation involves the mixing of one s and one p orbital resulting in the formation of two equivalent sp hybrid orbitals. The suitable orbitals for sp hybridisation are s and pz, if the hybrid orbitals are to lie along the z-axis. Each sp hybrid orbitals has 50% s-character and 50% p-character. Such a molecule in which the central atom is sp-hybridised and linked directly to two other central atoms possesses linear geometry. This type of hybridisation is also known as diagonal hybridisation. The two sp hybrids point in the opposite direction along the z-axis with projecting positive lobes and very small negative lobes, which provides more effective overlapping resulting in the formation of stronger bonds. Example of molecule having sp hybridisation BeCl 2: The ground state electronic configuration of Be is 1s22s2. In the exited state one of the 2s-electrons is promoted to vacant 2p orbital to account for its bivalency. One 2s and one 2p-orbital gets hybridised to form two sp hybridised orbitals. These two sp hybrid orbital

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q17. Chemistry — `92dec49f-bb99-48bb-9b79-5f7e2ddb1fd2`

### Question identity

- Question ID: `92dec49f-bb99-48bb-9b79-5f7e2ddb1fd2`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `hybridization` — Hybridization
- Concept: `sp-sp2-sp3` — sp, sp2, sp3 Hybridization
- CMS status: **DRAFT**

### Question

**Stem:** In ethane (C₂H₆), the C–C bond is formed by which type of orbital overlap?

- **A.** sp³–sp³ sigma bond overlap **[CORRECT]**
- **B.** sp²–sp² sigma bond overlap
- **C.** sp–sp sigma bond overlap
- **D.** sp³–sp³ pi bond overlap

**Correct answer:** A

**Explanation:** In ethane, both carbon atoms are sp³ hybridised. The C–C bond is formed by the axial (head-on) overlap of sp³ hybrid orbitals from each carbon, producing a sp³–sp³ sigma bond with a bond length of 154 pm.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `04a5741a-398b-4daf-b812-004a1de2b718`
- Section heading: 4.6.2 Other Examples of sp3, sp2 and sp
- source page: **24**
- KnowledgeUnit ID: `ef11d9c0-9212-43b0-b194-aa6d46a538cc` (status `PASSED`)
- ContentVersion ID: `c8caacd5-2f73-4e39-8d9b-6d9b91c2d5bb`

### Source evidence (extracted section passage)

> Hybridisation sp3 Hybridisation in C2H6 molecule: In ethane molecule both the carbon atoms assume sp3 hybrid state. One of the four sp3 hybrid orbitals of carbon atom overlaps axially with similar orbitals of other atom to form sp3-sp3 sigma bond while the other three hybrid orbitals of each carbon atom are used in forming sp3–s sigma bonds with hydrogen atoms as discussed in section 4.6.1(iii). Therefore in ethane C–C bond length is 154 pm and each C–H bond length is 109 pm. sp2 Hybridisation in C2H4: In the formation of ethene molecule, one of the sp2 hybrid orbitals of carbon atom overlaps axially with sp2 hybridised orbital of another carbon atom to form C–C sigma bond. While the other two sp2 hybrid orbitals of each carbon atom are used for making sp2–s sigma bond with two hydrogen atoms. The unhybridised orbital (2px or 2py) of one carbon atom overlaps sidewise with the similar orbital of the other carbon atom to form weak π bond, which consists of two equal electron clouds distributed above and below the plane of carbon and hydrogen atoms. Thus, in ethene molecule, the carbon- carbon bond consists of one sp2–sp2 sigma bond and one pi (π ) bond between p orbitals which are no

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q18. Chemistry — `b55bb380-cc1e-4094-8259-ffbf915134ef`

### Question identity

- Question ID: `b55bb380-cc1e-4094-8259-ffbf915134ef`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `hybridization` — Hybridization
- Concept: `sp-sp2-sp3` — sp, sp2, sp3 Hybridization
- CMS status: **DRAFT**

### Question

**Stem:** In ethyne (C₂H₂), each carbon undergoes sp hybridisation. Which of the following correctly describes the composition of the C≡C triple bond and the role of the unhybridised orbitals?

- **A.** One sigma bond from sp–sp axial overlap and two pi bonds from sidewise overlap of two sets of unhybridised p orbitals (2py and 2px) **[CORRECT]**
- **B.** Two sigma bonds from sp–sp axial overlap and one pi bond from sidewise overlap of one set of unhybridised p orbitals
- **C.** One sigma bond from sp³–sp³ axial overlap and two pi bonds from sidewise overlap of unhybridised p orbitals
- **D.** One sigma bond from sp²–sp² axial overlap and two pi bonds from sidewise overlap of two sets of unhybridised p orbitals

**Correct answer:** A

**Explanation:** In ethyne, each carbon undergoes sp hybridisation, leaving two unhybridised orbitals (2py and 2px) on each carbon. The C≡C triple bond consists of one sigma bond formed by axial overlap of the sp hybrid orbitals and two pi bonds formed by sidewise overlap of the two sets of unhybridised p orbitals. This distinguishes ethyne from ethene, which has only one pi bond formed from one set of unhybridised p orbitals.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `04a5741a-398b-4daf-b812-004a1de2b718`
- Section heading: 4.6.2 Other Examples of sp3, sp2 and sp
- source page: **24**
- KnowledgeUnit ID: `ef11d9c0-9212-43b0-b194-aa6d46a538cc` (status `PASSED`)
- ContentVersion ID: `52e9e9dd-b9bb-4c4a-86ca-5b8d5b97af8c`

### Source evidence (extracted section passage)

> Hybridisation sp3 Hybridisation in C2H6 molecule: In ethane molecule both the carbon atoms assume sp3 hybrid state. One of the four sp3 hybrid orbitals of carbon atom overlaps axially with similar orbitals of other atom to form sp3-sp3 sigma bond while the other three hybrid orbitals of each carbon atom are used in forming sp3–s sigma bonds with hydrogen atoms as discussed in section 4.6.1(iii). Therefore in ethane C–C bond length is 154 pm and each C–H bond length is 109 pm. sp2 Hybridisation in C2H4: In the formation of ethene molecule, one of the sp2 hybrid orbitals of carbon atom overlaps axially with sp2 hybridised orbital of another carbon atom to form C–C sigma bond. While the other two sp2 hybrid orbitals of each carbon atom are used for making sp2–s sigma bond with two hydrogen atoms. The unhybridised orbital (2px or 2py) of one carbon atom overlaps sidewise with the similar orbital of the other carbon atom to form weak π bond, which consists of two equal electron clouds distributed above and below the plane of carbon and hydrogen atoms. Thus, in ethene molecule, the carbon- carbon bond consists of one sp2–sp2 sigma bond and one pi (π ) bond between p orbitals which are no

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q19. Chemistry — `8c577dd2-4932-4676-8c7e-1f3e3b290485`

### Question identity

- Question ID: `8c577dd2-4932-4676-8c7e-1f3e3b290485`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `hybridization` — Hybridization
- Concept: `sp-sp2-sp3` — sp, sp2, sp3 Hybridization
- CMS status: **DRAFT**

### Question

**Stem:** In PCl5, which of the following correctly describes the bond angles and relative bond lengths?

- **A.** Equatorial P–Cl bonds make 120° with each other; axial P–Cl bonds are slightly longer and weaker than equatorial bonds **[CORRECT]**
- **B.** Axial P–Cl bonds make 120° with each other; equatorial P–Cl bonds are slightly longer and weaker than axial bonds
- **C.** All P–Cl bonds are equivalent in length and strength, with bond angles of 90° and 120°
- **D.** Equatorial P–Cl bonds make 90° with each other; axial P–Cl bonds are slightly shorter and stronger than equatorial bonds

**Correct answer:** A

**Explanation:** In PCl5, the three equatorial P–Cl bonds lie in a plane and subtend 120° angles with each other, while the two axial bonds make 90° with this equatorial plane. Axial bonds experience more repulsion from the three equatorial bond pairs, making them slightly longer and slightly weaker than equatorial bonds.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `88add238-c4c4-45a8-a10c-85d97f22bde7`
- Section heading: 4.6.3 Hybridisation of Elements
- source page: **25**
- KnowledgeUnit ID: `fe335b26-62bf-4aee-948c-ff913eb3efaa` (status `PASSED`)
- ContentVersion ID: `4884678b-c57d-4004-989f-00e1fae34f5c`

### Source evidence (extracted section passage)

> involving d Orbitals The elements present in the third period contain d orbitals in addition to s and p orbitals. The energy of the 3d orbitals are comparable to the energy of the 3s and 3p orbitals. The energy of 3d orbitals are also comparable to those of 4s and 4p orbitals. As a consequence the hybridisation involving either 3s, 3p and 3d or 3d, 4s and 4p is possible. However, since the difference in energies of 3p and 4s orbitals is significant, no hybridisation involving 3p, 3d and 4s orbitals is possible. The important hybridisation schemes involving s, p and d orbitals are summarised below: Fig.4.16 Formation of sigma and pi bonds in ethyne (i) Formation of PCl5 (sp3d hybridisation): The ground state and the excited state outer electronic configurations of phosphorus (Z=15) are represented below. sp3d hybrid orbitals filled by electron pairs donated by five Cl atoms. Shape of molecules/ ions Hybridisation type Atomic orbitals Examples Square planar dsp2 d+s+p(2) [Ni(CN)4]2–, [Pt(Cl)4]2– Trigonal bipyramidal sp3d s+p(3)+d PF5, PCl5 Square pyramidal sp3d2 s+p(3)+d(2) BrF5 Octahedral sp3d2 d2sp3 s+p(3)+d(2) d(2)+s+p(3) SF6, [CrF6]3– [Co(NH3)6]3+ 2024-25 125 Chemical Bonding And

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q20. Chemistry — `863f1289-87a0-4253-b996-c0aff8c47988`

### Question identity

- Question ID: `863f1289-87a0-4253-b996-c0aff8c47988`
- Subject: Chemistry (`CHEMISTRY`)
- Class: 11
- Chapter: `chemical-bonding` — Chemical Bonding and Molecular Structure
- Topic: `hybridization` — Hybridization
- Concept: `sp-sp2-sp3` — sp, sp2, sp3 Hybridization
- CMS status: **DRAFT**

### Question

**Stem:** A student argues that hybridisation involving 3p, 3d, and 4s orbitals should be feasible because 3d orbitals have comparable energy to 4s and 4p orbitals. Why is this argument incorrect according to NCERT?

- **A.** Because 3d orbitals can only hybridise with 3s and 3p orbitals, not with any 4th-shell orbitals
- **B.** Because the energy difference between 3p and 4s orbitals is significant, ruling out their co-hybridisation, even though 3d is comparable in energy to both 3s/3p and 4s/4p **[CORRECT]**
- **C.** Because 4s orbitals are always lower in energy than 3d orbitals, so mixing 3p with 4s would produce unstable hybrids
- **D.** Because hybridisation across different principal quantum number shells is never permitted in any element

**Correct answer:** B

**Explanation:** The NCERT text explicitly states that while 3d orbitals have comparable energy to both 3s/3p and 4s/4p orbitals (enabling sp3d or sp3d2 with 3s/3p/3d, and similar with 4s/4p/3d), hybridisation involving 3p, 3d, and 4s together is not possible because the energy difference between 3p and 4s is significant. The student's error is assuming that transitivity of comparable energies applies — just because 3d ≈ 3p and 3d ≈ 4s does not mean 3p ≈ 4s.

### Source provenance

- SourceDocument ID: `ab567276-729e-4d84-b070-a3a260cb5c7a`
- filename: `ncert-books-class-11-chemistry-chapter-4.pdf`
- relative source path: `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf`
- SHA-256: `3c583e5d705be3139fe802eef7867a079cb33f6a77d8330a9acd2100bb3124d2`
- IngestionJob ID: `da6a1664-e169-4e4d-873b-898e5f8c69ed`
- IngestionSection ID: `88add238-c4c4-45a8-a10c-85d97f22bde7`
- Section heading: 4.6.3 Hybridisation of Elements
- source page: **25**
- KnowledgeUnit ID: `fe335b26-62bf-4aee-948c-ff913eb3efaa` (status `PASSED`)
- ContentVersion ID: `e8c46c44-9cb3-48c8-96db-21ec8bcc527a`

### Source evidence (extracted section passage)

> involving d Orbitals The elements present in the third period contain d orbitals in addition to s and p orbitals. The energy of the 3d orbitals are comparable to the energy of the 3s and 3p orbitals. The energy of 3d orbitals are also comparable to those of 4s and 4p orbitals. As a consequence the hybridisation involving either 3s, 3p and 3d or 3d, 4s and 4p is possible. However, since the difference in energies of 3p and 4s orbitals is significant, no hybridisation involving 3p, 3d and 4s orbitals is possible. The important hybridisation schemes involving s, p and d orbitals are summarised below: Fig.4.16 Formation of sigma and pi bonds in ethyne (i) Formation of PCl5 (sp3d hybridisation): The ground state and the excited state outer electronic configurations of phosphorus (Z=15) are represented below. sp3d hybrid orbitals filled by electron pairs donated by five Cl atoms. Shape of molecules/ ions Hybridisation type Atomic orbitals Examples Square planar dsp2 d+s+p(2) [Ni(CN)4]2–, [Pt(Cl)4]2– Trigonal bipyramidal sp3d s+p(3)+d PF5, PCl5 Square pyramidal sp3d2 s+p(3)+d(2) BrF5 Octahedral sp3d2 d2sp3 s+p(3)+d(2) d(2)+s+p(3) SF6, [CrF6]3– [Co(NH3)6]3+ 2024-25 125 Chemical Bonding And

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q21. Physics — `ade9900b-1ab2-4a5d-aa29-a5f4a605366e`

### Question identity

- Question ID: `ade9900b-1ab2-4a5d-aa29-a5f4a605366e`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `kirchhoffs-laws` — Kirchhoff's Laws
- Concept: `kcl-kvl` — Kirchhoff's Current and Voltage Laws
- CMS status: **DRAFT**

### Question

**Stem:** A conductor carries a non-steady current. In a small interval Δt around time t, a net charge ΔQ flows across a cross-section. As Δt → 0, ΔQ → 0 but ΔQ/Δt → 2 A. Simultaneously, in a separate steady scenario, a net negative charge of 6 C flows in the forward direction and a net positive charge of 2 C flows in the forward direction over 2 s. Which of the following correctly compares the two currents and their directions?

- **A.** The non-steady current is 2 A in the forward direction; the steady current is –2 A, implying it flows in the backward direction **[CORRECT]**
- **B.** The non-steady current is 0 A because ΔQ → 0; the steady current is –2 A in the forward direction
- **C.** The non-steady current is 2 A in the forward direction; the steady current is 2 A also in the forward direction
- **D.** The non-steady current is undefined since the current is non-steady; the steady current is –4 A in the backward direction

**Correct answer:** A

**Explanation:** For the non-steady current, I(t) = lim(Δt→0) ΔQ/Δt = 2 A (positive, so forward direction). For the steady case, q = q+ – q– = 2 – 6 = –4 C, and I = q/t = –4/2 = –2 A. A negative value implies the current flows in the backward direction. Hence the non-steady current is 2 A forward and the steady current is –2 A (backward direction).

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `83bb9108-1e67-4ecd-a17e-c43c23d4f520`
- Section heading: 3.2 ELECTRIC CURRENT
- source page: **1**
- KnowledgeUnit ID: `11d6fb7f-13e3-425b-ae37-a0e2aa781f94` (status `PASSED`)
- ContentVersion ID: `32b58f53-daf9-4d68-9cc9-8bc4f766156b`

### Source evidence (extracted section passage)

> Imagine a small area held normal to the direction of flow of charges. Both the positive and the negative charges may flow forward and backward across the area. In a given time interval t, let q+ be the net amount (i.e., forward minus backward) of positive charge that flows in the forward direction across the area. Similarly, let q– be the net amount of negative charge flowing across the area in the forward direction. The net amount of charge flowing across the area in the forward direction in the time interval t, then, is q = q+– q–. This is proportional to t for steady current Chapter Three CURRENT ELECTRICITY 2024-25 Physics 82 and the quotient q I t = (3.1) is defined to be the current across the area in the forward direction. (If it turn out to be a negative number, it implies a current in the backward direction.) Currents are not always steady and hence more generally, we define the current as follows. Let DQ be the net charge flowing across a cross- section of a conductor during the time interval Dt [i.e., between times t and (t + Dt)]. Then, the current at time t across the cross-section of the conductor is defined as the value of the ratio of DQ to Dt in the limit of Dt ten

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q22. Physics — `c7a54ae9-5044-44d3-bfa4-8a5bbc6c5ef2`

### Question identity

- Question ID: `c7a54ae9-5044-44d3-bfa4-8a5bbc6c5ef2`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `ohms-law` — Electric Current and Ohm's Law
- Concept: `ohms-law-concept` — Ohm's Law
- CMS status: **DRAFT**

### Question

**Stem:** According to Ohm's law, the SI unit of resistance is:

- **A.** Ohm (Ω) **[CORRECT]**
- **B.** Siemens (S)
- **C.** Ampere (A)
- **D.** Volt per ampere squared (V/A²)

**Correct answer:** A

**Explanation:** The SI unit of resistance is the ohm, denoted by the symbol Ω. This is a direct fact stated in the textbook section on Ohm's law (V = RI, where R is the resistance measured in ohms).

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `4dda8f9f-7e89-43a5-b5c8-c16addf62247`
- Section heading: 3.4 OHM’S LAW
- source page: **3**
- KnowledgeUnit ID: `fcff25f5-f369-4dde-b700-1a3a44b961eb` (status `PASSED`)
- ContentVersion ID: `4117b472-cea2-469b-9f76-0c3be97c4760`

### Source evidence (extracted section passage)

> A basic law regarding flow of currents was discovered by G.S. Ohm in 1828, long before the physical mechanism responsible for flow of currents was discovered. Imagine a conductor through which a current I is flowing and let V be the potential difference between the ends of the conductor. Then Ohm’s law states that V µ I or, V = R I (3.3) where the constant of proportionality R is called the resistance of the conductor. The SI units of resistance is ohm, and is denoted by the symbol W. The resistance R not only depends on the material of the conductor but also on the dimensions of the conductor. The dependence of R on the dimensions of the conductor can easily be determined as follows. Consider a conductor satisfying Eq. (3.3) to be in the form of a slab of length l and cross sectional area A [Fig. 3.2(a)]. Imagine placing two such identical slabs side by side [Fig. 3.2(b)], so that the length of the combination is 2l. The current flowing through the combination is the same as that flowing through either of the slabs. If V is the potential difference across the ends of the first slab, then V is also the potential difference across the ends of the second slab since the second slab is

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q23. Physics — `3493be87-e3a8-4e7b-a399-94cbdb349d6f`

### Question identity

- Question ID: `3493be87-e3a8-4e7b-a399-94cbdb349d6f`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `ohms-law` — Electric Current and Ohm's Law
- Concept: `ohms-law-concept` — Ohm's Law
- CMS status: **DRAFT**

### Question

**Stem:** A copper wire of length l and cross-sectional area A has a resistance R. If the length of the wire is doubled and its cross-sectional area is halved, the new resistance of the wire will be:

- **A.** 4R **[CORRECT]**
- **B.** 2R
- **C.** R/2
- **D.** R/4

**Correct answer:** A

**Explanation:** Using R = ρl/A, resistance is proportional to length and inversely proportional to cross-sectional area. Doubling the length doubles R (giving 2R), and halving the cross-sectional area again doubles R (giving another factor of 2). Therefore, the new resistance = ρ(2l)/(A/2) = 4ρl/A = 4R.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `4dda8f9f-7e89-43a5-b5c8-c16addf62247`
- Section heading: 3.4 OHM’S LAW
- source page: **3**
- KnowledgeUnit ID: `fcff25f5-f369-4dde-b700-1a3a44b961eb` (status `PASSED`)
- ContentVersion ID: `7b07fe1b-5dd5-4de9-bc7e-1947bf9fe7d5`

### Source evidence (extracted section passage)

> A basic law regarding flow of currents was discovered by G.S. Ohm in 1828, long before the physical mechanism responsible for flow of currents was discovered. Imagine a conductor through which a current I is flowing and let V be the potential difference between the ends of the conductor. Then Ohm’s law states that V µ I or, V = R I (3.3) where the constant of proportionality R is called the resistance of the conductor. The SI units of resistance is ohm, and is denoted by the symbol W. The resistance R not only depends on the material of the conductor but also on the dimensions of the conductor. The dependence of R on the dimensions of the conductor can easily be determined as follows. Consider a conductor satisfying Eq. (3.3) to be in the form of a slab of length l and cross sectional area A [Fig. 3.2(a)]. Imagine placing two such identical slabs side by side [Fig. 3.2(b)], so that the length of the combination is 2l. The current flowing through the combination is the same as that flowing through either of the slabs. If V is the potential difference across the ends of the first slab, then V is also the potential difference across the ends of the second slab since the second slab is

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q24. Physics — `a42a3589-8070-40c2-9181-f76642b33a85`

### Question identity

- Question ID: `a42a3589-8070-40c2-9181-f76642b33a85`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `ohms-law` — Electric Current and Ohm's Law
- Concept: `drift-velocity` — Drift Velocity
- CMS status: **DRAFT**

### Question

**Stem:** In a copper wire of cross-sectional area 1.0 × 10⁻⁷ m² carrying a current of 1.5 A, the drift speed of conduction electrons is approximately 1.1 × 10⁻³ m s⁻¹. This drift speed is approximately how many times smaller than the typical thermal speed of copper atoms at ordinary temperatures?

- **A.** 10⁻⁵ times **[CORRECT]**
- **B.** 10⁻³ times
- **C.** 10⁻⁷ times
- **D.** 10⁻¹ times

**Correct answer:** A

**Explanation:** According to the textbook, the drift speed of conduction electrons in a copper wire carrying 1.5 A through a cross-sectional area of 1.0 × 10⁻⁷ m² is approximately 1.1 × 10⁻³ m s⁻¹, which is about 10⁻⁵ times the typical thermal speed of copper atoms at ordinary temperatures. This illustrates that drift speeds in typical conductors are extremely small compared to thermal speeds.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `f491d79b-093a-445a-be0d-42398680a2db`
- Section heading: 3.5 DRIFT OF ELECTRONS AND THE ORIGIN
- source page: **5**
- KnowledgeUnit ID: `4f40e57b-77ee-460b-a3e1-2719621c2c07` (status `PASSED`)
- ContentVersion ID: `8d39848a-8a60-47c8-8997-09a827fa3e6e`

### Source evidence (extracted section passage)

> E V v i i i e t m (3.16) since starting with its last collision it was accelerated (Fig. 3.3) with an acceleration given by Eq. (3.15) for a time interval ti. The average velocity of the electrons at time t is the average of all the Vi’s. The average of vi’s is zero [Eq. (3.14)] since immediately after any collision, the direction of the velocity of an electron is completely random. The collisions of the electrons do not occur at regular intervals but at random times. Let us denote by t, the average time between successive collisions. Then at a given time, some of the electrons would have spent FIGURE 3.3 A schematic picture of an electron moving from a point A to another point B through repeated collisions, and straight line travel between collisions (full lines). If an electric field is applied as shown, the electron ends up at point B¢ (dotted lines). A slight drift in a direction opposite the electric field is visible. 2024-25 Physics 86 time more than t and some less than t. In other words, the time ti in Eq. (3.16) will be less than t for some and more than t for others as we go through the values of i = 1, 2 ..... N. The average value of ti then is t (known as relaxation tim

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q25. Physics — `23815930-822d-4740-8e2a-b21689307a37`

### Question identity

- Question ID: `23815930-822d-4740-8e2a-b21689307a37`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `ohms-law` — Electric Current and Ohm's Law
- Concept: `ohms-law-concept` — Ohm's Law
- CMS status: **DRAFT**

### Question

**Stem:** A student lists the following statements about limitations of Ohm's law:
(I) In a diode, reversing the polarity of the applied voltage produces a current of equal magnitude but opposite direction.
(II) GaAs exhibits a non-unique V-I relationship, meaning for a single value of current there can be more than one corresponding voltage.
(III) Materials that deviate from Ohm's law have no practical utility and are avoided in circuit design.
(IV) One deviation from Ohm's law is that V ceases to be proportional to I.
Which combination of statements is correct?

- **A.** II and IV only **[CORRECT]**
- **B.** I, II, and IV only
- **C.** I and III only
- **D.** II, III, and IV only

**Correct answer:** A

**Explanation:** Statement I is incorrect: in a diode (a device violating Ohm's law due to sign-dependence), reversing V does NOT produce the same magnitude of current in the opposite direction. Statement II is correct: GaAs is explicitly identified as showing non-unique V-I relationships. Statement III is incorrect: the textbook states that materials not obeying Ohm's law are widely used in electronic circuits. Statement IV is correct: one deviation is that V ceases to be proportional to I. Hence only II and IV are correct.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `b2659f60-8db1-4d79-8567-a4b20b1089b3`
- Section heading: 3.6 LIMITATIONS OF OHM’S LAW
- source page: **9**
- KnowledgeUnit ID: `7c6b55dd-78d3-44de-9771-e8514acfb53e` (status `PASSED`)
- ContentVersion ID: `c8431ec4-43dc-485c-853d-dabcc6f1bddf`

### Source evidence (extracted section passage)

> Although Ohm’s law has been found valid over a large class of materials, there do exist materials and devices used in electric circuits where the proportionality of V and I does not hold. The deviations broadly are one or more of the following types: (a) V ceases to be proportional to I (Fig. 3.5). (b) The relation between V and I depends on the sign of V. In other words, if I is the current for a certain V, then reversing the direction of V keeping its magnitude fixed, does not produce a current of the same magnitude as I in the opposite direction (Fig. 3.6). This happens, for example, in a diode which we will study in Chapter 14. (c) The relation between V and I is not unique, i.e., there is more than one value of V for the same current I (Fig. 3.7). A material exhibiting such behaviour is GaAs. Materials and devices not obeying Ohm’s law in the form of Eq. (3.3) are actually widely used in electronic circuits. In this and a few subsequent chapters, however, we will study the electrical currents in materials that obey Ohm’s law.

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q26. Physics — `5d4ca5da-6f22-44b4-9c9c-2b93f3eb09ca`

### Question identity

- Question ID: `5d4ca5da-6f22-44b4-9c9c-2b93f3eb09ca`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `ohms-law` — Electric Current and Ohm's Law
- Concept: `ohms-law-concept` — Ohm's Law
- CMS status: **DRAFT**

### Question

**Stem:** Which of the following correctly describes the V-I characteristic of a diode, in the context of limitations of Ohm's law?

- **A.** The relation between V and I depends on the sign of V, so reversing V does not produce a current of the same magnitude in the opposite direction. **[CORRECT]**
- **B.** The relation between V and I is non-unique, meaning there is more than one value of V for the same current I.
- **C.** V is strictly proportional to I for all values of applied voltage.
- **D.** The device exhibits a perfectly linear V-I relationship regardless of the direction of applied voltage.

**Correct answer:** A

**Explanation:** A diode is explicitly given as an example of a device where the V-I relationship depends on the sign of V. Reversing the direction of V does not produce a current of the same magnitude in the opposite direction, making it a deviation from Ohm's law based on sign-dependence. Non-unique V-I relationships are instead characteristic of GaAs, not diodes.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `b2659f60-8db1-4d79-8567-a4b20b1089b3`
- Section heading: 3.6 LIMITATIONS OF OHM’S LAW
- source page: **9**
- KnowledgeUnit ID: `7c6b55dd-78d3-44de-9771-e8514acfb53e` (status `PASSED`)
- ContentVersion ID: `1e676dbd-783d-4c11-97ee-9fcc93820b89`

### Source evidence (extracted section passage)

> Although Ohm’s law has been found valid over a large class of materials, there do exist materials and devices used in electric circuits where the proportionality of V and I does not hold. The deviations broadly are one or more of the following types: (a) V ceases to be proportional to I (Fig. 3.5). (b) The relation between V and I depends on the sign of V. In other words, if I is the current for a certain V, then reversing the direction of V keeping its magnitude fixed, does not produce a current of the same magnitude as I in the opposite direction (Fig. 3.6). This happens, for example, in a diode which we will study in Chapter 14. (c) The relation between V and I is not unique, i.e., there is more than one value of V for the same current I (Fig. 3.7). A material exhibiting such behaviour is GaAs. Materials and devices not obeying Ohm’s law in the form of Eq. (3.3) are actually widely used in electronic circuits. In this and a few subsequent chapters, however, we will study the electrical currents in materials that obey Ohm’s law.

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q27. Physics — `62f4b1f1-57f6-4e6f-8188-5bfab13a14ad`

### Question identity

- Question ID: `62f4b1f1-57f6-4e6f-8188-5bfab13a14ad`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `resistance-resistivity` — Resistance and Resistivity
- Concept: `factors-affecting-resistance` — Factors Affecting Resistance
- CMS status: **DRAFT**

### Question

**Stem:** The temperature coefficient of resistivity (α) for metals is positive. Which of the following correctly explains this observation based on the microscopic model of conduction?

- **A.** In metals, the number of free electrons (n) is nearly independent of temperature, so rising temperature decreases the average collision time (τ), thereby increasing resistivity. **[CORRECT]**
- **B.** In metals, both n and τ decrease with rising temperature, and the decrease in n dominates, causing resistivity to increase.
- **C.** In metals, the number of free electrons (n) increases significantly with temperature, increasing the rate of collisions and raising resistivity.
- **D.** In metals, rising temperature increases the average collision time (τ), which according to ρ = m/(ne²τ) increases resistivity.

**Correct answer:** A

**Explanation:** According to ρ = m/(ne²τ), resistivity depends inversely on both n and τ. In metals, n is not appreciably dependent on temperature. As temperature rises, τ decreases (more frequent collisions), which causes ρ to increase. This gives metals a positive temperature coefficient of resistivity. Option B is wrong because n does not decrease appreciably; Option C is wrong because n does not increase significantly in metals; Option D is wrong because τ decreases, not increases, with rising temperature.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `a929e718-a4ec-48bc-9de3-a60839b62dec`
- Section heading: 3.8 TEMPERATURE DEPENDENCE OF RESISTIVITY
- source page: **10**
- KnowledgeUnit ID: `2196173d-59b5-4ae1-8580-37196eade297` (status `PASSED`)
- ContentVersion ID: `d3713403-3527-46c4-b22d-c91d45e9e776`

### Source evidence (extracted section passage)

> The resistivity of a material is found to be dependent on the temperature. Different materials do not exhibit the same dependence on temperatures. Over a limited range of temperatures, that is not too large, the resistivity of a metallic conductor is approximately given by, rT = r0 [1 + a (T–T0)] (3.26) where rT is the resistivity at a temperature T and r0 is the same at a reference temperature T0. a is called the temperature co-efficient of resistivity, and from Eq. (3.26), the dimension of a is (Temperature)–1. For metals, a is positive. The relation of Eq. (3.26) implies that a graph of rT plotted against T would be a straight line. At temperatures much lower than 0°C, the graph, however, deviates considerably from a straight line (Fig. 3.8). Equation (3.26) thus, can be used approximately over a limited range of T around any reference temperature T0, where the graph can be approximated as a straight line. FIGURE 3.8 Resistivity rT of copper as a function of temperature T. FIGURE 3.9 Resistivity rT of nichrome as a function of absolute temperature T. FIGURE 3.10 Temperature dependence of resistivity for a typical semiconductor.  Some materials like Nichrome (which is an alloy o

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q28. Physics — `26ed6b35-b181-4b5d-af5e-15cf0dd00245`

### Question identity

- Question ID: `26ed6b35-b181-4b5d-af5e-15cf0dd00245`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `resistance-resistivity` — Resistance and Resistivity
- Concept: `factors-affecting-resistance` — Factors Affecting Resistance
- CMS status: **DRAFT**

### Question

**Stem:** A student uses the formula ρT = ρ0 [1 + α(T − T0)] to calculate the resistivity of a metallic conductor at a temperature far below 0°C, and separately at a moderate temperature above T0. Based on the verified textbook facts, which of the following statements is most accurate?

- **A.** The formula gives accurate results at both temperatures, as it is derived from fundamental quantum mechanical principles valid at all temperatures.
- **B.** The formula is approximately valid near and moderately above T0, but deviates considerably from actual behaviour at temperatures much lower than 0°C. **[CORRECT]**
- **C.** The formula is more accurate at very low temperatures because α becomes negligible, making the term α(T − T0) vanishingly small.
- **D.** The formula fails at moderate temperatures above T0 but remains accurate at temperatures well below 0°C because resistivity becomes nearly constant there.

**Correct answer:** B

**Explanation:** The textbook explicitly states that the linear relationship ρT = ρ0[1 + α(T − T0)] is valid only over a limited, not too large range of temperatures, and that it deviates considerably from a straight line at temperatures much lower than 0°C. Therefore, while the formula gives a reasonable approximation at moderate temperatures above T0, it cannot be reliably used at very low temperatures. Options A, C, and D contradict this stated limitation.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `a929e718-a4ec-48bc-9de3-a60839b62dec`
- Section heading: 3.8 TEMPERATURE DEPENDENCE OF RESISTIVITY
- source page: **10**
- KnowledgeUnit ID: `2196173d-59b5-4ae1-8580-37196eade297` (status `PASSED`)
- ContentVersion ID: `05337fe3-d550-4b4d-be02-8086b4fcd11b`

### Source evidence (extracted section passage)

> The resistivity of a material is found to be dependent on the temperature. Different materials do not exhibit the same dependence on temperatures. Over a limited range of temperatures, that is not too large, the resistivity of a metallic conductor is approximately given by, rT = r0 [1 + a (T–T0)] (3.26) where rT is the resistivity at a temperature T and r0 is the same at a reference temperature T0. a is called the temperature co-efficient of resistivity, and from Eq. (3.26), the dimension of a is (Temperature)–1. For metals, a is positive. The relation of Eq. (3.26) implies that a graph of rT plotted against T would be a straight line. At temperatures much lower than 0°C, the graph, however, deviates considerably from a straight line (Fig. 3.8). Equation (3.26) thus, can be used approximately over a limited range of T around any reference temperature T0, where the graph can be approximated as a straight line. FIGURE 3.8 Resistivity rT of copper as a function of temperature T. FIGURE 3.9 Resistivity rT of nichrome as a function of absolute temperature T. FIGURE 3.10 Temperature dependence of resistivity for a typical semiconductor.  Some materials like Nichrome (which is an alloy o

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q29. Physics — `9c80cb11-376a-4bfb-95a4-f3bbc5842075`

### Question identity

- Question ID: `9c80cb11-376a-4bfb-95a4-f3bbc5842075`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `resistance-resistivity` — Resistance and Resistivity
- Concept: `factors-affecting-resistance` — Factors Affecting Resistance
- CMS status: **DRAFT**

### Question

**Stem:** The electromotive force (emf) of a cell is defined as the potential difference between its positive and negative electrodes when:

- **A.** No current is flowing through the cell (open circuit) **[CORRECT]**
- **B.** Maximum current is flowing through the cell
- **C.** The external resistance equals the internal resistance
- **D.** The terminal voltage equals zero

**Correct answer:** A

**Explanation:** According to the textbook, the emf (e) is the potential difference between the positive and negative electrodes in an open circuit, i.e., when no current is flowing through the cell. It equals V+ + V–, where V+ and V– are the potential differences at each electrode-electrolyte interface.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `cd3aa731-f646-4508-9b41-06a89513f105`
- Section heading: 3.10 CELLS, EMF, INTERNAL RESISTANCE
- source page: **13**
- KnowledgeUnit ID: `57fc6254-7211-45de-abab-db60e9d82d10` (status `PASSED`)
- ContentVersion ID: `e49deac6-0d3a-460f-8145-f0cd5389a091`

### Source evidence (extracted section passage)

> We have already mentioned that a simple device to maintain a steady current in an electric circuit is the electrolytic cell. Basically a cell has two electrodes, called the positive (P) and the negative (N), as shown in FIGURE 3.11 Heat is produced in the resistor R which is connected across the terminals of a cell. The energy dissipated in the resistor R comes from the chemical energy of the electrolyte. 2024-25 Physics 94 Fig. 3.12. They are immersed in an electrolytic solution. Dipped in the solution, the electrodes exchange charges with the electrolyte. The positive electrode has a potential difference V+ (V+ > 0) between itself and the electrolyte solution immediately adjacent to it marked A in the figure. Similarly, the negative electrode develops a negative potential – (V– ) (V– ≥ 0) relative to the electrolyte adjacent to it, marked as B in the figure. When there is no current, the electrolyte has the same potential throughout, so that the potential difference between P and N is V+ – (–V–) = V+ + V– . This difference is called the electromotive force (emf) of the cell and is denoted by e. Thus e = V++V– > 0 (3.36) Note that e is, actually, a potential difference and not a f

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Q30. Physics — `7b80d6db-9c07-4b42-a92d-df74ab8428b3`

### Question identity

- Question ID: `7b80d6db-9c07-4b42-a92d-df74ab8428b3`
- Subject: Physics (`PHYSICS`)
- Class: 12
- Chapter: `current-electricity` — Current Electricity
- Topic: `kirchhoffs-laws` — Kirchhoff's Laws
- Concept: `kcl-kvl` — Kirchhoff's Current and Voltage Laws
- CMS status: **DRAFT**

### Question

**Stem:** In a circuit loop, a cell of EMF ε and internal resistance r has a current I flowing from its positive terminal P to its negative terminal N (i.e., opposite to the conventional internal current direction). Using Kirchhoff's Loop Rule and the correct expression for terminal potential difference in this scenario, which equation correctly represents the potential change across this cell as current moves from P to N, and what does this imply physically?

- **A.** V(N) – V(P) = –ε – Ir, implying the cell is being charged (acts as a load) and potential drops by more than ε **[CORRECT]**
- **B.** V(N) – V(P) = ε – Ir, implying the cell is discharging and gains potential in the direction of current
- **C.** V(N) – V(P) = –ε + Ir, implying the cell is discharging and the terminal voltage is reduced by internal resistance
- **D.** V(N) – V(P) = ε + Ir, implying the cell always gains potential regardless of current direction

**Correct answer:** A

**Explanation:** When current I flows from P (positive terminal) to N (negative terminal) through the cell, the potential difference is given by V(P) – V(N) = ε + Ir. Therefore, V(N) – V(P) = –ε – Ir. This scenario (current entering the positive terminal) corresponds to the cell being charged — it acts as a load rather than a source. The potential falls by (ε + Ir) in going from P to N, which is consistent with the Loop Rule requiring the algebraic sum of all potential changes around the loop to equal zero.

### Source provenance

- SourceDocument ID: `264c1f82-016c-41f4-8328-bb3d8edc6bb3`
- filename: `ncert-book-class-12-physics-part-1-chapter-3.pdf`
- relative source path: `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
- SHA-256: `76cd7927ef3c6eb40e0a06a5413f618d44bc4a2e93d1cba5408aba3016ff4312`
- IngestionJob ID: `a60ef885-2b4e-42ed-bb51-00627ede5747`
- IngestionSection ID: `71440154-31a0-4bb8-9128-4c5f7664bde3`
- Section heading: 3.12 KIRCHHOFF’S RULES
- source page: **17**
- KnowledgeUnit ID: `e5f8f04d-d353-4d6b-aa3c-c9baa12b488c` (status `PASSED`)
- ContentVersion ID: `fef85035-402e-4c8d-9db4-024745bca160`

### Source evidence (extracted section passage)

> Electric circuits generally consist of a number of resistors and cells interconnected sometimes in a complicated way. The formulae we have derived earlier for series and parallel combinations of resistors are not always sufficient to determine all the currents and potential differences in the circuit. Two rules, called Kirchhoff’s rules, are very useful for analysis of electric circuits. Given a circuit, we start by labelling currents in each resistor by a symbol, say I, and a directed arrow to indicate that a current I flows along the resistor in the direction indicated. If ultimately I is determined to be positive, the actual current in the resistor is in the direction of the arrow. If I turns out to be negative, the current actually flows in a direction opposite to the arrow. Similarly, for each source (i.e., cell or some other source of electrical power) the positive and negative electrodes are labelled, as well as, a directed arrow with a symbol for the current flowing through the cell. This will tell us the potential difference, V = V (P) – V (N) = e – I r [Eq. (3.38) between the positive terminal P and the negative terminal N; I here is the current flowing from N to P throug

### Reviewer checks (AI advisory)

| A Source grounding | B Correct answer | C Explanation | D Distractors | E Academic mapping | F NEET suitability | G Duplicate | H Source page |
|---|---|---|---|---|---|---|---|
| PASS | NEEDS REVIEW | PASS | PASS | PASS | NEEDS REVIEW | PASS | PASS |

**Human decision:** _pending_ (do not auto-APPROVE)

---

## Final status

**PHASE D — ECAEP REVIEW READY**

No questions approved or published. Stop.