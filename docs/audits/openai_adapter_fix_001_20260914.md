# OPENAI-ADAPTER-FIX-001

**Status:** `GREEN — OPENAI ADAPTER FIX + SMOKE CREATED`
**Generated:** `2026-09-14T00:32:37.419769+00:00`

## Previous failure

- Benchmark OpenAI `gpt-5-mini` returned HTTP 400:
  `Unsupported parameter: 'max_tokens' … Use 'max_completion_tokens' instead.`

## Inspection

| Item | Finding |
|---|---|
| API endpoint | `POST {base_url}/chat/completions` |
| Transport | `httpx` 0.28.1 (no OpenAI Python SDK installed) |
| API style | Chat Completions (not Responses API) |
| Old incompatible parameter | `max_tokens` |
| Corrected parameter | `max_completion_tokens` (gpt-5 / o1 / o3 / o4 families) |
| Legacy models | `gpt-4o-*` still use `max_tokens` |
| Other incompatibilities | Non-default `temperature` rejected on gpt-5 — omitted |
| Structured output | `response_format: {type: json_object}` preserved |
| Model | `gpt-5-mini` (unchanged; not substituted) |

## Adapter changes (OpenAI only)

File: `apps/backend/app/modules/ai/gateway/openai_provider.py`

1. Model-aware output-token field (`max_completion_tokens` vs `max_tokens`)
2. Reasoning-token headroom for gpt-5 family (`min(max(budget*2, budget+1024), 8192)`) so visible JSON is not truncated to empty (`finish=length`)
3. Lineage model keeps request id (`gpt-5-mini`); dated API snapshot stored in `safe_metadata.api_model` for pricing continuity

Unchanged: McqLlmProvider, Anthropic, Gemini, Mistral, blueprints, NCERT guards, provenance, validation, ECAEP.

## Smoke (1 candidate max)

| Field | Value |
|---|---|
| Blueprint | `bp-create-002-20260913-bp-physics-drift-velocity-mcq` |
| Scope | PHYSICS / Current Electricity / Drift Velocity |
| NCERT path | `NCERT Books\Class 12\Physics\leph1dd\leph103.pdf` |
| Request / model reached | Success / True |
| Created | **1** |
| Parse | SUCCESS |
| Deterministic validation | PASS |
| Candidate ID | `aa41982d-8b25-4dfd-81ce-87c3297d9d49` |
| Content item | DRAFT (`8b295bc4-83a5-48c3-85b1-7bb058fd0450`) |
| Provider metadata | `openai` / `gpt-5-mini` / `fixed:openai` / cost ESTIMATED |
| Published | False |
| NCERT certified | False |
| Editorially approved | False |
| NCERT verification | **NOT PERFORMED** |
| Counted toward 271 | False |
| Part of 400 pilot | False |

## Database safety

- Pilot CREATED: **129 → 129**
- PUBLISHED 1479 / IN_REVIEW 111 / SUPERSEDED 6 / blueprints 445 / KUs 381 unchanged
- Smoke artifact batch prefix: `openai-adapter-fix-001-20260914-*`

## Tests

- `tests/test_openai_adapter_fix_001.py` + blocked/backoff checks: **12 passed**

## STOP

Do not re-run the 20-provider benchmark. Do not resume the 271. Do not generate the 400 pilot. Do not publish/certify/commit/push.
