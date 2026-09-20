# MCQ-PROVIDER-ABSTRACTION-001

**Status:** `GREEN — ABSTRACTION COMPLETE / HARD FREEZE OK (unmapped_draft soft drift noted)`

Decouples the content factory from any mandatory single LLM vendor. No MCQ generation, no resume of the 271 remaining candidates, no publication.

## Existing provider architecture

- AI Gateway under `apps/backend/app/modules/ai/gateway/`
- Contract: `AIProvider` / `AIResponse` / `ProviderError`
- Adapters already present: Anthropic, Gemini, OpenAI, Mistral (+ fallback stub)
- Routing: explicit `fixed` | `fixed_model` | `fallback_chain` (never silent)

## Abstraction design

- New façade: `apps/backend/app/modules/cms/services/mcq_llm_provider.py`
- Protocol `McqLlmProvider`: `generate_mcq`, `health_check`, `classify_error`, `provider_name`, `model_name`
- Production adapter `GatewayMcqLlmProvider` → `AIGateway` → vendor adapters
- `ContentFactoryGenerationService` calls the façade only (no vendor SDK at factory layer)
- Cursor is **not** a generation provider

## Providers currently supported

| Alias | Registry | Notes |
|---|---|---|
| `anthropic` | anthropic | Primary (pilot used `claude-sonnet-4-6`) |
| `google` / `gemini` | gemini | Existing Gemini adapter preserved |
| `openai` | openai | Cloud OpenAI |
| `local` | openai | Requires `OPENAI_BASE_URL` (OpenAI-compatible) |
| `mistral` | mistral | Gateway adapter present |

## Provider limitations

- `PROVIDER_BLOCKED` stops immediately; operator must explicitly choose another provider to continue
- `FACTORY_PROVIDER_MODE=fallback_chain` rejected for MCQ unless `MCQ_ALLOW_FALLBACK_CHAIN=true`
- Local endpoint not silently enabled without `OPENAI_BASE_URL`

## Configuration

```text
MCQ_PROVIDER=anthropic|google|gemini|openai|local|mistral
MCQ_ALLOW_FALLBACK_CHAIN=false
OPENAI_BASE_URL=   # required when MCQ_PROVIDER=local
```

- Resolved now: `fixed:gemini` model=`gemini-3.6-flash`

## Error classification

| Code | Behavior |
|---|---|
| PROVIDER_BLOCKED | Stop; not retryable; not treated as 429 |
| RATE_LIMIT (PROVIDER_RATE_LIMITED) | Bounded exponential backoff + jitter |
| AUTH_ERROR | Stop |
| NETWORK_ERROR / TIMEOUT | Retryable per gateway rules |
| PROVIDER_INTERNAL_ERROR | Fail attempt |
| PARSE_ERROR / VALIDATION_ERROR / DUPLICATE | Content-layer; no provider switch |

## Resume behavior

- Existing CREATED candidates: **129** (expected 129)
- By subject: `{'CHEMISTRY': 29, 'PHYSICS': 100}`
- Remaining recoverable: **271**
- This task did **not** resume generation
- Stem-hash / CREATED guards prevent regenerating successes

## Reproducibility

Each run/candidate records provider, model, routing policy, blueprint, source, run ID, candidate ID. Metadata mismatch between response provider and selected provider aborts the run.

## Tests

- `apps/backend/tests/test_mcq_provider_abstraction_001.py` (18 cases)

## Database safety verification

- Pilot CREATED unchanged: `True` (129)
- Protected freeze OK: `True`
- Checksum: `354e06e7baaf81bbdfc203fcbfd52e8b`
- Provider/models on CREATED: `[{'provider': 'anthropic', 'model': 'claude-sonnet-4-6', 'count': 129}]`
- No generation / publication / certification in this task

## STOP

Do not resume the 271. Do not generate MCQs. Do not commit/push from this task.
