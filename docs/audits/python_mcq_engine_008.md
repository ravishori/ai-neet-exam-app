# PYTHON-MCQ-ENGINE-008 — Chemical Kinetics Grounding Failure Disposition

**Verdict:** **GREEN**
**Fact ID:** `ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99`
**Failure:** `NCERT_GROUNDING_FAILED` / `NCERT_AMBIGUOUS`
**Disposition:** **RETIRED_REJECTED**

## Root cause

Not an engine defect. Generation correctly fail-closed. Keyed option 'rate law or rate expression' and distractor 'rate law' are both independently NCERT-defensible, so claim grounding returns NCERT_AMBIGUOUS → NCERT_GROUNDING_FAILED. Secondary defect: concept misbinding to Integrated Rate Equations.

## Evidence / mapping

- NCERT PDF: `Class 12/Chemistry 1/lech1dd/lech103.pdf`
- Evidence: `The equation like (3.4), which relates the rate of a reaction to concentration of reactants is called rate law or rate expression`
- Syllabus: Unit 8 CHEMICAL KINETICS (`CHEMISTRY:U08:T01`)
- Taxonomy: Chemical Kinetics / Rate Law and Order of Reaction / **Integrated Rate Equations** (misaligned)

## Decision

- Engine logic: **not modified** (fail-closed behavior is correct).
- ENGINE-006 fixture: **not modified**.
- Remediation fixture: `python_mcq_engine_008_kinetics_rate_law_retired.json` with `review_status=REJECTED`.

## Safety

- Provider/API calls: **0**
- Production DB mutations: **0**
- Invariants unchanged: **True**
- ENGINE-007 99/99 verified-yield record: **preserved**
- Focused tests: **5 passed**
- Regression: **29 passed**
- Ruff: **passed**

**Next:** Do not auto-start ENGINE-009. When ready, optionally rebuild a reviewed eligible pack that excludes this rejected fact ID, then re-measure read-only yield if desired.
