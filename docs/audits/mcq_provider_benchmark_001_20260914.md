# MCQ-PROVIDER-BENCHMARK-001

**Status:** `YELLOW — BENCHMARK COMPLETE / ZERO CREATED (providers blocked, throttled, or adapter-incompatible)`
**Generated:** `2026-09-13T20:08:37.096018+00:00`

Controlled multi-provider benchmark (max 20 candidates). **Not** part of the 400-question pilot. Existing 129 CREATED untouched. 271 remaining **not** resumed.

## Executive findings

| Provider | Model | Outcome |
|---|---|---|
| anthropic | `claude-sonnet-4-6` | **SKIPPED** — prior billing `PROVIDER_BLOCKED`; not spent against |
| gemini | `gemini-3.6-flash` | **PROVIDER_BLOCKED** (billing/credits) on first call — hard stop |
| openai | `gpt-5-mini` | **0/5 CREATED** — API rejects `max_tokens` (needs `max_completion_tokens`); adapter gap |
| mistral | `mistral-small-2603` | **0/5 CREATED** — sustained `PROVIDER_RATE_LIMITED` after bounded backoff |
| local | (openai-compatible) | **PROVIDER_UNAVAILABLE** — `OPENAI_BASE_URL` not configured |

**CREATED total: 0 / 20.** No content-quality ranking is valid until at least one provider produces CREATED candidates. Cost recorded for CREATED: `$0` (no successful completions).

OpenAI diagnostic (non-MCQ probe): HTTP 400 `unsupported_parameter` — `'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.`

## Provider availability

| Provider | Model | Availability | Reason |
|---|---|---|---|
| anthropic | `claude-sonnet-4-6` | SKIPPED | Prior MCQ-PILOT-001R observed PROVIDER_BLOCKED (billing/credits); do not spend to benchmark |
| gemini | `gemini-3.6-flash` | AVAILABLE (preflight) → BLOCKED at call | Billing/credits blocked on generate |
| openai | `gpt-5-mini` | AVAILABLE (preflight) → INVALID_RESPONSE | Model/adapter parameter mismatch |
| mistral | `mistral-small-2603` | AVAILABLE (preflight) → RATE_LIMITED | Sustained rate limit |
| local | `gpt-5-mini` | PROVIDER_UNAVAILABLE | OPENAI_BASE_URL not configured |

## Shared blueprint sample (fair comparison)

| # | Subject | Class | Chapter | Concept | Blueprint key |
|---|---|---|---|---|---|
| 1 | PHYSICS | 11 | Kinetic Theory | Behaviour of Gases | `bp-create-002-20260913-bp-physics-behaviour-of-gases-mcq` |
| 2 | CHEMISTRY | 12 | Biomolecules | Primary, Secondary, Tertiary and Quaternary Structure of Proteins | `bp-create-001-20260913-bp-chemistry-protein-structure-levels-mcq` |
| 3 | BOTANY | 12 | Microbes in Human Welfare | Fermented Beverages and Antibiotics | `bp-create-001-20260913-bp-botany-fermented-beverages-antibiotics-mcq` |
| 4 | ZOOLOGY | 11 | Animal Kingdom | Levels of Organisation | `bp-create-002-20260913-bp-zoology-ak-levels-of-organisation-mcq` |
| 5 | PHYSICS | 11 | Work, Energy and Power | Work–Energy Theorem | `bp-create-002-20260913-bp-physics-work-energy-theorem-mcq` |

Canonical eligible BPs loaded: **307** (1 of 308 excluded by taxonomy/digestion guards — same rules as pilot).

## Comparison table

| Provider | Model | Req | Created | Parse fail | Valid fail | Dup | Prov fail | RL | Blocked | Avg latency ms | Struct OK % | Cost USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini | `gemini-3.6-flash` | 5 | 0 | 0 | 0 | 0 | 1 | 0 | ≥1 | 1025.0 | 0.0 | 0.0 |
| openai | `gpt-5-mini` | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 1575.8 | 0.0 | 0.0 |
| mistral | `mistral-small-2603` | 5 | 0 | 0 | 0 | 0 | 10 | 10 | 0 | 34326.0 | 0.0 | 0.0 |
| local | — | 0 | 0 | — | — | — | — | — | — | — | — | — |
| anthropic | — | 0 | 0 | — | — | — | — | — | — | — | — | — |

## NCERT verification

**NCERT verification status = NOT PERFORMED**

No CREATED candidates reached schema/validation gates with publishable content. Independent NCERT editorial verification remains a later gate.

## Quality sample (attempted candidates)

All rows below are **FAILED_PROVIDER** (no CREATED content). Full table with candidate IDs is in the JSON report under `provider_results.*.candidates`.

| Provider | Failure class | Observation |
|---|---|---|
| gemini | PROVIDER_BLOCKED | Billing/credits blocked |
| openai | PROVIDER_INVALID_RESPONSE | `max_tokens` unsupported for `gpt-5-mini` |
| mistral | RATE_LIMIT | Exhausted bounded retries |

## Recommendation for next 271 (operator decision)

- Auto-selected: **False** (must remain false)
- Suggested next provider: **None** — do **not** resume the 271 until a provider smoke produces ≥1 CREATED MCQ

Do not resume until one of:

1. OpenAI adapter updated for `max_completion_tokens` + re-run **this benchmark only**, or
2. Gemini/Anthropic billing restored + smoke pass, or
3. Mistral rate limits clear + smoke pass, or
4. Local `OPENAI_BASE_URL` configured/reachable + smoke pass

Shortest path for a fair quality/cost comparison: fix OpenAIProvider for `gpt-5-mini`, then re-run MCQ-PROVIDER-BENCHMARK-001 (not the pilot resume).

### Caveats

- NCERT verification NOT PERFORMED
- Zero CREATED ⇒ no valid content-quality ranking
- Anthropic not benchmarked (billing skip policy)
- Local unavailable
- Benchmark is NOT part of the 400 pilot

## Database safety

- Pilot CREATED unchanged: `True` (**129**)
- Hard protected freeze OK: `True` (PUBLISHED 1479 / IN_REVIEW 111 / SUPERSEDED 6 / BPs 445 / KUs 381)
- Benchmark CREATED: **0** (only FAILED_PROVIDER candidate rows in separate `mcq-provider-benchmark-001-20260914-*` batches)
- Publication/certification: none
- 271 not resumed

## Tests

- `tests/test_mcq_provider_abstraction_001.py` + factory blocked + gateway contract: **23 passed / 0 failed**

## STOP

Do not resume the 271. Do not generate beyond this benchmark. Do not publish/certify/commit/push.
