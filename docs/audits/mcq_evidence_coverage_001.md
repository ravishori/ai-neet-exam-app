# MCQ-EVIDENCE-COVERAGE-001 — Blueprint dual-gate audit

**Generated:** 2026-09-14T02:14:13.007566+00:00
**Mode:** READ_ONLY (no generation, no question mutation, no publish)
**Syllabus:** `D:\ravishori\AI Neet Exam App\NEETSyllabus.txt` (sha256 `82a616e31ba75d6e…`)
**NCERT root:** `D:\ravishori\AI Neet Exam App\NCERT Books`

## Verdict

- Blueprints audited (latest version per key): **445**
- `GENERATION_READY`: **278**
- `NEEDS_SYLLABUS_REVIEW`: **30**
- `NEEDS_NCERT_SOURCE`: **137**
- `NEEDS_NCERT_EVIDENCE`: **0**
- `NEEDS_TAXONOMY_REVIEW`: **0**

Both gates required: NEET-2026 syllabus mapping **and** canonical NCERT evidence.
StudyMaterial / web / model knowledge were not used as evidence fallbacks.

## Syllabus unit inventory (parsed)

| Subject | Units |
|---|---:|
| PHYSICS | 20 |
| CHEMISTRY | 20 |
| BIOLOGY | 10 |

## Subject readiness

| Subject | Blueprints | GENERATION_READY |
|---|---:|---:|
| BOTANY | 121 | 92 |
| CHEMISTRY | 139 | 90 |
| PHYSICS | 115 | 67 |
| ZOOLOGY | 70 | 29 |

## Gate pass rates (latest blueprints)

| Gate | Pass rate |
|---|---:|
| `syllabus_mapping` | 93.5% |
| `subject` | 100.0% |
| `unit` | 93.5% |
| `topic_subtopic` | 93.0% |
| `ncert_chapter_path` | 69.2% |
| `ncert_concept` | 100.0% |
| `pdf_readable` | 69.2% |
| `evidence_extractable` | 69.2% |
| `evidence_sufficient` | 69.2% |
| `taxonomy` | 100.0% |

## Syllabus units with zero GENERATION_READY blueprints

Count: **13** / 50

- PHYSICS Unit 10: OSCILLATIONS AND WAVES — statuses={}
- PHYSICS Unit 13: MAGNETIC EFFECTS OF CURRENT AND MAGNETISM — statuses={}
- PHYSICS Unit 14: ELECTROMAGNETIC INDUCTION AND ALTERNATING CURRENTS — statuses={}
- PHYSICS Unit 15: ELECTROMAGNETIC WAVES — statuses={}
- PHYSICS Unit 17: DUAL NATURE OF MATTER AND RADIATION — statuses={}
- PHYSICS Unit 18: ATOMS AND NUCLEI — statuses={}
- PHYSICS Unit 19: ELECTRONIC DEVICES — statuses={}
- PHYSICS Unit 20: EXPERIMENTAL SKILLS — statuses={}
- CHEMISTRY Unit 9: CLASSIFICATION OF ELEMENTS AND PERIODICITY IN PROPERTIES — statuses={}
- CHEMISTRY Unit 10: P-BLOCK ELEMENTS — statuses={}
- CHEMISTRY Unit 13: PURIFICATION AND CHARACTERISATION OF ORGANIC COMPOUNDS — statuses={}
- CHEMISTRY Unit 16: ORGANIC COMPOUNDS CONTAINING HALOGENS — statuses={}
- CHEMISTRY Unit 20: PRINCIPLES RELATED TO PRACTICAL CHEMISTRY — statuses={}

## Samples by status

### GENERATION_READY
- `bp-create-001-20260913-bp-botany-loss-of-biodiversity-mcq` | BOTANY/loss-of-biodiversity | syllabus=Ecology and Environment | ncert=Class 12/Biology/lebo1dd/lebo113.pdf | reasons=[]
- `bp-create-001-20260913-bp-botany-patterns-of-biodiversity-mcq` | BOTANY/patterns-of-biodiversity | syllabus=Ecology and Environment | ncert=Class 12/Biology/lebo1dd/lebo113.pdf | reasons=[]
- `bp-create-002-20260913-bp-botany-bc-classification-history-mcq` | BOTANY/bc-classification-history | syllabus=Diversity in Living World | ncert=Class 11/Biology/kebo1dd/kebo102.pdf | reasons=[]
- `bp-create-002-20260913-bp-botany-bc-whittaker-five-kingdom-mcq` | BOTANY/bc-whittaker-five-kingdom | syllabus=Diversity in Living World | ncert=Class 11/Biology/kebo1dd/kebo102.pdf | reasons=[]
- `bp-create-002-20260913-bp-botany-bc-fungi-structure-nutrition-repro-mcq` | BOTANY/bc-fungi-structure-nutrition-repro | syllabus=Diversity in Living World | ncert=Class 11/Biology/kebo1dd/kebo102.pdf | reasons=[]

### NEEDS_SYLLABUS_REVIEW
- `bp-create-001-20260913-bp-botany-why-and-how-conserve-mcq` | BOTANY/why-and-how-conserve | syllabus=Ecology and Environment | ncert=Class 12/Biology/lebo1dd/lebo113.pdf | reasons=['syllabus:no_confident_neet_2026_unit_match']
- `bp-create-002-20260913-bp-botany-pk-pteridophytes-vascular-organisation-mcq` | BOTANY/pk-pteridophytes-vascular-organisation | syllabus=Structural Organisation in Animals and Plants | ncert=Class 11/Biology/kebo1dd/kebo103.pdf | reasons=[]
- `bp-create-001-20260913-bp-botany-law-of-segregation-mcq` | BOTANY/law-of-segregation | syllabus=Genetics and Evolution | ncert=Class 12/Biology/lebo1dd/lebo104.pdf | reasons=['syllabus:no_confident_neet_2026_unit_match']
- `bp-create-001-20260913-bp-chemistry-basicity-of-amines-mcq` | CHEMISTRY/basicity-of-amines | syllabus=ORGANIC COMPOUNDS CONTAINING NITROGEN | ncert=Class 12/Chemistry 2/lech2dd/lech204.pdf | reasons=['syllabus:no_confident_neet_2026_unit_match']
- `bp-create-001-20260913-bp-chemistry-preparation-of-amines-mcq` | CHEMISTRY/preparation-of-amines | syllabus=ORGANIC COMPOUNDS CONTAINING NITROGEN | ncert=Class 12/Chemistry 2/lech2dd/lech204.pdf | reasons=['syllabus:no_confident_neet_2026_unit_match']

### NEEDS_NCERT_SOURCE
- `production-seed-v2-2026-09-03-bp-zoology-06` | BOTANY/biomolecule-classes | syllabus=Cell Structure and Function | ncert=None | reasons=['non_canonical_StudyMaterial_path', 'missing_ncert_source_path']
- `production-seed-v1-2026-09-02-bp-zoology-04` | BOTANY/dna-rna | syllabus=Structural Organisation in Animals and Plants | ncert=None | reasons=['missing_ncert_source_path']
- `production-seed-v2-2026-09-03-bp-zoology-07` | BOTANY/dna-rna | syllabus=Cell Structure and Function | ncert=None | reasons=['non_canonical_StudyMaterial_path', 'missing_ncert_source_path']
- `production-seed-v1-2026-09-02-bp-zoology-03` | BOTANY/enzyme-basics | syllabus=Cell Structure and Function | ncert=None | reasons=['missing_ncert_source_path']
- `production-seed-v2-2026-09-03-bp-zoology-13` | BOTANY/enzyme-basics | syllabus=Cell Structure and Function | ncert=None | reasons=['non_canonical_StudyMaterial_path', 'missing_ncert_source_path']

### NEEDS_NCERT_EVIDENCE
_none_

### NEEDS_TAXONOMY_REVIEW
_none_

## Safety

- No MCQs generated
- No existing questions modified
- No publication
- No commit/push

## Next step

Remediate `NEEDS_NCERT_SOURCE` / `NEEDS_NCERT_EVIDENCE` / `NEEDS_SYLLABUS_REVIEW` before capacity-scale generation. Only `GENERATION_READY` blueprints may enter controlled factory runs under the dual-gate pipeline.
