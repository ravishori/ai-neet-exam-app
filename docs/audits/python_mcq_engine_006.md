# PYTHON-MCQ-ENGINE-006 — Reviewed Multi-Subject Fact Pack

**Verdict:** **GREEN**
**Reviewed corpus:** **100**
**MCQ_ELIGIBLE:** **100**
**Subject counts:** Physics 25 / Chemistry 25 / Botany 25 / Zoology 25
**Shortfalls to 25:** none

## Distribution

- Chapters used across pack: see `metrics.chapter_counts` in JSON
- Topics used: see `metrics.topic_counts` in JSON
- Source PDFs: 15 canonical NCERT paths under `NCERT Books/`
- Question-type eligibility: DEFINITION_IDENTIFICATION 97, CONTROLLED_ASSOCIATION 2, DIRECT_FACT 1

## Curation honesty

- Seeded 5 ENGINE-004 Chemistry/Biomolecules REVIEWED facts unchanged.
- Newly curated facts use literal NCERT “is/are called” / “known as” quotes with same-PDF distractors.
- Every retained fact passed schema validation (`extra=forbid`), NCERT source guard, syllabus gate, taxonomy consistency, and fact-quality gate with typed template → **MCQ_ELIGIBLE**.
- 4 curation candidates rejected for `DUPLICATE_FACT_ID` (fail-closed; not forced into the pack).
- **Internal REVIEWED / MCQ_ELIGIBLE ≠ NCERT certification.** No independent pedagogical certification is claimed.

## Safety

- Provider/API calls: **0**
- Production DB mutations: **0**
- Invariants unchanged: **True**
- Worker observation: **UNKNOWN / UNKNOWN** (continuity not claimed)
- No MCQ generation; non-production fixture only

## Tests

- Focused: **12 passed**
- Regression: **63 passed** (006 + 005 + engine/adapter/loader/gate)
- Ruff: **passed**

## Limitations

- Definition-pattern dominance (high-confidence deterministic recall).
- Chemistry still denser in Biomolecules than ideal; other subjects use multiple chapters.
- Scope review is deterministic gate-backed internal review, not external NCERT certification.
- OpenAI worker was not observable.

**Recommended next task:** PYTHON-MCQ-ENGINE-007: re-run the ENGINE-005 100-fact read-only evaluation using `python_mcq_engine_006_reviewed_100.json` (no persistence, no providers), and report verified yield by subject/chapter/question type.
