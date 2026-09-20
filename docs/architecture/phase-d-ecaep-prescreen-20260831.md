# Phase D — ECAEP Pre-Screen & Quality Audit

**Date:** 2026-08-31  
**Pilot:** `phase-d-30-mcq-authorized-20260825`  
**Database:** `trinetra_db`  
**Mode:** READ-ONLY (0 database writes)  
**Readiness:** **AMBER**

## Repository relationships (discovered)

```text
cms.content_items
  ├─ current_version_id → cms.content_versions.id  (student/published tip)
  ├─ latest_version_id  → cms.content_versions.id  (editorial tip)
  └─ concept_id → academic.concepts → topics → chapters → subjects
cms.content_versions.body (QuestionBody: stem, options[], correct_option, explanation, difficulty)
cms.content_version_knowledge_units → knowledge.knowledge_units
  → ingestion.ingestion_sections → ingestion.ingestion_jobs.pilot_run_id
  → ingestion.source_documents.relative_source_path
```

## Pilot jobs

| job_id | status | target | source |
|---|---|---:|---|
| `a60ef885-2b4e-42ed-bb51-00627ede5747` | COMPLETED | 10 | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf` |
| `da6a1664-e169-4e4d-873b-898e5f8c69ed` | COMPLETED | 10 | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf` |
| `f5b496d3-399c-4290-8fc2-e9deac412a71` | COMPLETED | 10 | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf` |

## Lineage & pointers

- Unique QUESTIONS via pilot lineage: **30**
- Unique versions: **30** (nver>1: 0)
- Publication: DRAFT×30; pilot PUBLISHED×0
- Pointers: current set 30/30; latest set 30/30; both==intended 30/30
- Global CMS QUESTION status: `{'DRAFT': 78, 'IN_REVIEW': 1, 'PUBLISHED': 11}`

## Pilot summary scorecard

```text
total = 30
structural_pass = 30
structural_fail = 0
answer_pass = 29
answer_warning = 1
answer_fail = 0
ncert_pass = 30
ncert_partial = 0
ncert_fail = 0
ncert_not_verified = 0
explanation_pass = 29
explanation_warning = 1
explanation_fail = 0
difficulty_match = 27
difficulty_mismatch = 3
duplicate_exact = 0
duplicate_near_match = 1
p0 = 0
p1 = 3
p2 = 8
p3 = 2
recommend_approve = 21
recommend_revise = 9
recommend_reject = 0
answer_distribution = {'A': 23, 'B': 6, 'C': 1}
difficulty_distribution = {'easy': 11, 'hard': 14, 'medium': 5}
subject_distribution = {'BOTANY': 10, 'CHEMISTRY': 10, 'PHYSICS': 10}
```

## Subject summary

### BOTANY — 10
```text
APPROVE: 7
REVISE:  3
REJECT:  0
Critical/major findings:
  - 10d4d997-cb60-4450-99e8-47ed905c9775: Correct photorespiration products. Near-duplicate of 85fee888 — keep one, revise/remove the other.
  - 85fee888-47f6-408d-ab05-39b131233322: Near-duplicate of 10d4d997; prefer revise/retire this or the other before ECAEP approval of both.
```

### CHEMISTRY — 10
```text
APPROVE: 8
REVISE:  2
REJECT:  0
Critical findings: none
```

### PHYSICS — 10
```text
APPROVE: 6
REVISE:  4
REJECT:  0
Critical/major findings:
  - 7b80d6db-9c07-4b42-a92d-df74ab8428b3: Sign convention for charging cell (V(P)−V(N)=ε+Ir) appears consistent with NCERT, but dense notation previously flagged for human answer verification.
```

## Question-level scorecard

| # | ID | Subject | Chapter | Topic | Diff | Structural | Answer | Expl | NCERT | Distr | Ambiguity | NEET | Dup | Sev | Rec |
|---:|---|---|---|---|---|---|---|---|---|---:|---|---:|---|---|---|
| 1 | `5dc99543` | BOTANY | photosynthesis | light-reaction | easy/easy | PASS | PASS | 5 | PASS | 5 | CLEAR | 5 | N | — | APPROVE |
| 2 | `8a979c6a` | BOTANY | photosynthesis | light-reaction | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 3 | `2602f9da` | BOTANY | photosynthesis | dark-reaction | easy/easy | PASS | PASS | 5 | PASS | 5 | CLEAR | 5 | N | — | APPROVE |
| 4 | `f81153c3` | BOTANY | photosynthesis | dark-reaction | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 5 | `10d4d997` | BOTANY | photosynthesis | factors-affecting-photosynthesis | easy/easy | PASS | PASS | 5 | PASS | 4 | CLEAR | 4 | Y | P1 | APPROVE |
| 6 | `fc61e6e7` | BOTANY | photosynthesis | factors-affecting-photosynthesis | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 7 | `e6b9fb1e` | BOTANY | photosynthesis | factors-affecting-photosynthesis | easy/easy | PASS | PASS | 4 | PASS | 4 | CLEAR | 4 | N | P2 | REVISE |
| 8 | `8d50e829` | BOTANY | photosynthesis | factors-affecting-photosynthesis | hard/medium | PASS | PASS | 4 | PASS | 3 | MINOR_AMBIGUITY | 4 | N | P2 | REVISE |
| 9 | `f78dbbf2` | BOTANY | photosynthesis | dark-reaction | medium/medium | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 10 | `85fee888` | BOTANY | photosynthesis | factors-affecting-photosynthesis | medium/easy | PASS | PASS | 5 | PASS | 4 | CLEAR | 3 | Y | P1 | REVISE |
| 11 | `c91a89ec` | CHEMISTRY | chemical-bonding | ionic-bonding | easy/easy | PASS | PASS | 5 | PASS | 4 | CLEAR | 4 | N | P3 | APPROVE |
| 12 | `b33b47de` | CHEMISTRY | chemical-bonding | ionic-bonding | hard/hard | PASS | PASS | 4 | PASS | 4 | CLEAR | 4 | N | — | APPROVE |
| 13 | `87f621ab` | CHEMISTRY | chemical-bonding | covalent-bonding-vsepr | hard/hard | PASS | PASS | 4 | PASS | 3 | MINOR_AMBIGUITY | 3 | N | P2 | REVISE |
| 14 | `90d13ef4` | CHEMISTRY | chemical-bonding | hybridization | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 4 | N | — | APPROVE |
| 15 | `acbbdd83` | CHEMISTRY | chemical-bonding | hybridization | easy/easy | PASS | PASS | 5 | PASS | 5 | CLEAR | 4 | N | — | APPROVE |
| 16 | `2f165110` | CHEMISTRY | chemical-bonding | hybridization | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 17 | `92dec49f` | CHEMISTRY | chemical-bonding | hybridization | easy/easy | PASS | PASS | 5 | PASS | 5 | CLEAR | 4 | N | — | APPROVE |
| 18 | `b55bb380` | CHEMISTRY | chemical-bonding | hybridization | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 19 | `8c577dd2` | CHEMISTRY | chemical-bonding | hybridization | easy/easy | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 20 | `863f1289` | CHEMISTRY | chemical-bonding | hybridization | hard/hard | PASS | PASS | 5 | PASS | 3 | MINOR_AMBIGUITY | 4 | N | P2 | REVISE |
| 21 | `ade9900b` | PHYSICS | current-electricity | kirchhoffs-laws | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 4 | N | P2 | REVISE |
| 22 | `c7a54ae9` | PHYSICS | current-electricity | ohms-law | easy/easy | PASS | PASS | 3 | PASS | 3 | CLEAR | 2 | N | P2 | REVISE |
| 23 | `23815930` | PHYSICS | current-electricity | ohms-law | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 24 | `62f4b1f1` | PHYSICS | current-electricity | resistance-resistivity | easy/easy | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 25 | `26ed6b35` | PHYSICS | current-electricity | resistance-resistivity | hard/hard | PASS | PASS | 5 | PASS | 4 | CLEAR | 5 | N | — | APPROVE |
| 26 | `9c80cb11` | PHYSICS | current-electricity | resistance-resistivity | easy/easy | PASS | PASS | 5 | PASS | 5 | CLEAR | 4 | N | — | APPROVE |
| 27 | `7b80d6db` | PHYSICS | current-electricity | kirchhoffs-laws | hard/hard | PASS | WARNING | 4 | PASS | 3 | MINOR_AMBIGUITY | 4 | N | P1 | REVISE |
| 28 | `3493be87` | PHYSICS | current-electricity | ohms-law | medium/medium | PASS | PASS | 5 | PASS | 5 | CLEAR | 5 | N | — | APPROVE |
| 29 | `a42a3589` | PHYSICS | current-electricity | ohms-law | medium/easy | PASS | PASS | 4 | PASS | 3 | CLEAR | 3 | N | P2 | REVISE |
| 30 | `5d4ca5da` | PHYSICS | current-electricity | ohms-law | medium/medium | PASS | PASS | 5 | PASS | 4 | CLEAR | 4 | N | — | APPROVE |

## Top risks

### 1. Near-duplicate photorespiration products item vs 10d4d997
- **Question:** `85fee888-47f6-408d-ab05-39b131233322`
- **Severity:** P1
- **Evidence:** Stem Jaccard≈0.50; identical correct option text; same answer A
- **Recommended action (do not execute):** Revise or retire one of the two before approving both

### 2. Dense Kirchhoff charging-cell sign convention needs human confirmation
- **Question:** `7b80d6db-9c07-4b42-a92d-df74ab8428b3`
- **Severity:** P1
- **Evidence:** Prior Phase-D advisory NEEDS REVIEW; pre-screen provisional PASS on algebra
- **Recommended action (do not execute):** Human ECAEP reviewer verify V(P)−V(N)=ε+Ir wording against NCERT

### 3. Severe answer-position skew (A=23, B=6, C=1, D=0)
- **Question:** `PILOT`
- **Severity:** P2
- **Evidence:** 76.7% keyed to A; no D answers
- **Recommended action (do not execute):** Do not auto-rebalance; flag for future item writing guidelines

### 4. Academic concept metadata mismatch (photorespiration vs Blackman)
- **Question:** `e6b9fb1e-f022-4172-88c5-318213bc511b / 8d50e829-6540-44bc-882a-6b140a33da17`
- **Severity:** P2
- **Evidence:** concept_code=photorespiration; stems test limiting factors
- **Recommended action (do not execute):** Retag concept before publish; content itself is sound

### 5. Topic/concept tags Kirchhoff but content is §3.2 current definition
- **Question:** `ade9900b-1ab2-4a5d-aa29-a5f4a605366e`
- **Severity:** P2
- **Evidence:** section_heading=3.2 ELECTRIC CURRENT; topic=kirchhoffs-laws
- **Recommended action (do not execute):** Retag to ohms-law/current concept path

## Answer distribution audit

Observed: `{'A': 23, 'B': 6, 'C': 1}`

**WARNING — answer-position distribution skew** (A-heavy; D=0). Do not alter answers in this audit.

## NCERT fidelity method

Source PDFs exist on disk via `absolute_source_path_dev`. Alignment scored using stored `ingestion_sections.raw_text` + `knowledge_units.structured_facts` (same pages cited by lineage), not by regenerating content. No question marked NOT_VERIFIED because section text was available for all 30.

## Integrity confirmation

```text
Database writes by this audit = 0
Application data changes = 0
Publication changes = 0
ECAEP submit/approve/publish = not performed
```

---

*AI pre-screen only. Final ECAEP decision remains with the authorized human reviewer.*