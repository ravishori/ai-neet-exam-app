# PYTHON-MCQ-ENGINE-002

**Verdict:** **YELLOW**
**Independent candidate verification:** PASS=5, FAIL=4, AMBIGUOUS=0

## Candidate verification

- **home-sugar — FAIL**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [1, 2]
  - Reason: NCERT supports the fact and keyed answer, but domestic use of sucrose is introductory trivia and is not validly bound to the cited Classification of Carbohydrates syllabus topic. Failed checks: taxonomy_mapping_valid, syllabus_binding_valid.
- **monosaccharide-definition — PASS**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [2]
  - Reason: Independent PDF review supports the stem/key and all options. Monosaccharide, oligosaccharide, polysaccharide, and disaccharide are all explicitly introduced in the classification passage on PDF page 2. Exact/normalized duplicate checks found no match.
- **oligosaccharide-definition — FAIL**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [2]
  - Reason: The intended answer is oligosaccharide, but disaccharide is also defensible: NCERT states that disaccharides yield two monosaccharide units, which is inside the stem's two-to-ten range. Failed checks: exactly_one_defensible.
- **polysaccharide-definition — PASS**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [2]
  - Reason: Independent PDF review supports the stem/key and all options. All four class names are explicit in the PDF-page-2 classification passage; only polysaccharide matches a large number of units. Exact/normalized duplicate checks found no match.
- **non-reducing-sugar — PASS**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [2, 7]
  - Reason: Independent PDF review supports the stem/key and all options. PDF page 7 explicitly keys sucrose; PDF page 2 identifies glucose, fructose, and ribose as monosaccharides and states all monosaccharides are reducing sugars. Exact/normalized duplicate checks found no match.
- **sucrose-hydrolysis — PASS**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [2, 7, 8]
  - Reason: Independent PDF review supports the stem/key and all options. Every association is explicit: sucrose and maltose on PDF page 2, sucrose/maltose on page 7, and lactose/starch on page 8. Exact/normalized duplicate checks found no match.
- **maltose-hydrolysis — PASS**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [2, 7, 8]
  - Reason: Independent PDF review supports the stem/key and all options. Every association is explicit in the cited chapter; only the maltose association answers the target named in the stem. Exact/normalized duplicate checks found no match.
- **maltose-linkage — FAIL**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [7, 8]
  - Reason: NCERT supports the C1-to-C4 linkage, but exact glycosidic linkage positions are not authorized by the cited syllabus wording and are misbound to the Classification of Carbohydrates concept. Failed checks: taxonomy_mapping_valid, syllabus_binding_valid.
- **glycosidic-linkage-definition — FAIL**
  - NCERT: `Class 12/Chemistry 2/lech2dd/lech205.pdf`, PDF pages [7]
  - Reason: NCERT supports the definition, but glycosidic-linkage terminology is outside the cited classification/constituent-monosaccharide syllabus wording and is misbound to the selected concept. Failed checks: taxonomy_mapping_valid, syllabus_binding_valid.

## Structured fact schema and loader

- Schema version: `ncert_fact_pack_v1`
- Review states are explicit and non-equivalent: EXTRACTED, REVIEWED, VERIFIED.
- The loader validates the canonical PDF, exact syllabus binding, schema, stable ID, source evidence, duplicate facts, and review floor.
- Loading is deterministic and read-only; it performs no DB, web, API, or provider operation.

## Verification

- Focused tests: **19 passed (12 loader + 7 engine)**
- Regression tests: **108 passed**
- Ruff: **passed**
- Provider/API calls: **0**
- Production DB mutations: **0**
- OpenAI worker continuity: **NOT_ALIVE_AT_FINAL_CHECK: original PIDs were absent; this task did not signal, stop, restart, or modify the worker**

## Limitations

- The nine pilot candidates cite page sets rather than a single persisted page number; this audit records the independently located PDF pages.
- Duplicate verification covers normalized stem and option-stem hashes supported by current indexed infrastructure; semantic embedding dedupe is unavailable.
- The loader consumes reviewed JSON facts but intentionally does not adapt them into question templates or persist them.
- VERIFIED denotes independent source-text and syllabus verification only; it is not ECAEP approval, NCERT certification, or publication.
- The separately running OpenAI worker exited during this task; its existing audit reports 88 created and 12 remaining. This task did not restart or alter it.
- Four pilot candidates failed independent review: three for semantic syllabus/concept misbinding and one for a non-unique answer.

**Recommended next task:** PYTHON-MCQ-ENGINE-003: create one reviewed, non-production JSON fact-pack fixture for Biomolecules, load it read-only, and add an explicit adapter from loaded facts to existing deterministic question specs; generate no more than 10 in-memory DRAFT candidates and independently verify them.
