# MCQ-CONTROLLED-GENERATION-001

**Generated:** 2026-09-14T07:08:41.719505+00:00
**Verdict:** **GREEN**
**Provider:** {'FACTORY_PROVIDER': 'openai', 'MCQ_PROVIDER': 'openai', 'FACTORY_PROVIDER_MODE': 'fixed', 'model_hint': 'gpt-5-mini', 'prior_attempt': {'provider': 'anthropic', 'result': 'PROVIDER_BLOCKED', 'summary': 'Provider billing/credits blocked (20/20)'}}

## Request

- Requested: **20** (5 Physics / 5 Chemistry / 5 Botany / 5 Zoology)
- Created (valid unique DRAFTs): **20**
- Provider attempts: **21**
- Parse failures: **1**
- Validation failures: **0**
- Provider failures: **0**
- Duplicates: **0**
- Syllabus-gate stops: **0**
- NCERT-evidence stops: **0**
- Estimated cost USD: **0.098451**
- Total latency ms (sum of runs): **537854**

## Verification

- Created content items: **20**
- All created DRAFT: **True**
- Canonical NCERT path on every created: **True**
- Syllabus mapping on every created: **True**
- Duplicate stem hashes among created: **False**

## By subject

| Subject | Requested | Created |
|---|---:|---:|
| PHYSICS | 5 | 5 |
| CHEMISTRY | 5 | 5 |
| BOTANY | 5 | 5 |
| ZOOLOGY | 5 | 5 |

## Safety

- Published delta: **0** (expect 0)
- Taxonomy/KU/blueprint count freeze: **True**
- Unmapped DRAFT unchanged: **True**
- Candidates created this run: **21**
- Any candidate published: **False**

## Limitations

- Deterministic validation only; no independent editorial NCERT certification.
- Used live GENERATION_READY pool (IN_SYLLABUS + NCERT_EVIDENCE_READY), not stale coverage-002 alone.
- First attempt anthropic → PROVIDER_BLOCKED (billing); retry fixed to openai.
- Prior anthropic failed candidate/job/run rows remain in DB from the blocked attempt.
