# PYTHON-MCQ-ENGINE-003 — Fact Quality Gate

**Verdict:** **GREEN**
**Fact quality:** approved=5, rejected=4, review-required=0

## Gate

- Canonical NCERT source and exact evidence
- Authoritative NEET-UG-2026 binding
- Authoritative project taxonomy ownership
- Explicit semantic scope review
- Fact type and transformation allow-list
- Exactly one evidence-supported answer
- Evidence-supported, non-answer distractors

## Original pilot re-evaluation

- **home-sugar — FACT_REJECTED**: CONCEPT_MISBOUND
- **monosaccharide-definition — FACT_APPROVED**: all gates passed
- **oligosaccharide-definition — FACT_REJECTED**: FACT_AMBIGUOUS, DISTRACTOR_UNSAFE
- **polysaccharide-definition — FACT_APPROVED**: all gates passed
- **non-reducing-sugar — FACT_APPROVED**: all gates passed
- **sucrose-hydrolysis — FACT_APPROVED**: all gates passed
- **maltose-hydrolysis — FACT_APPROVED**: all gates passed
- **maltose-linkage — FACT_REJECTED**: CONCEPT_MISBOUND
- **glycosidic-linkage-definition — FACT_REJECTED**: CONCEPT_MISBOUND

## Validation boundary

- FACT_APPROVED/MCQ_ELIGIBLE is engine validation only.
- It does not mean independently NCERT verified, ECAEP approved, certified, or published.
- Independent ENGINE-002 result remains PASS=5, FAIL=4, AMBIGUOUS=0.

## Tests and safety

- Focused: **33 passed**
- Regression: **108 passed**
- Ruff: **passed**
- Provider/API calls: **0**
- Production DB mutations: **0**
- Worker continuity: **NOT_RUNNING_AT_TASK_START; no process was stopped or restarted**

## Limitations

- Semantic syllabus/concept fit cannot be safely inferred from IDs or keyword overlap; the gate therefore requires an explicit reviewed scope record.
- Option defensibility relationships are curated deterministic inputs and must be independently reviewed before use.
- The original pilot had only nine created candidates; its previously skipped milk-sugar input was not regenerated.
- Production semantic embedding dedupe remains unavailable; existing normalized hash dedupe is unchanged.
- The OpenAI worker was already absent at task start, so alive continuity could not be established.

**Recommended next task:** PYTHON-MCQ-ENGINE-004: define and review one non-production Biomolecules fact-pack containing only the five ENGINE-003-approved facts, add a typed fact-pack-to-question adapter, and run a maximum five-candidate in-memory round trip with independent verification; do not persist.
