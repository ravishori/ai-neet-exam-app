# FACTORY-P3.1 — Multi-Provider AI Gateway

**Status:** IMPLEMENTATION COMPLETE (infrastructure) · **Date:** 2026-09-01  
**Scope:** Provider abstraction + controlled routing for Content Factory generation.  
**Not in scope:** Live 100-question pilot, ECAEP changes, question body mutations, AI judge, microservices.

**Verdict language:** Provider infrastructure is ready for controlled evaluation. Do **not** crown a “best” provider from this wave alone.

---

## Architecture

```
Content Factory → Generation Service → AI Gateway → Provider Router → Adapter
  Anthropic | OpenAI | Gemini | Mistral
       → normalized AIResponse → GenerationCandidate → P4 → P5
```

Content Factory contains **no** provider SDK calls. It uses `AIGateway.generate(...)` only.

### Key modules (`apps/backend/app/modules/ai/gateway/`)

| Module | Role |
|--------|------|
| `base.py` | `AIProvider`, `GenerateRequest`, `AIResponse`, normalized `ProviderError` codes |
| `registry.py` | Enablement + key presence → CONFIGURED/ENABLED/AVAILABLE/BLOCKED/DISABLED |
| `router.py` | `fixed` / `fixed_model` / `fallback_chain` — **never** silent fallback |
| `pricing.py` | Config-driven rates → `ESTIMATED` \| `UNAVAILABLE` |
| `capabilities.py` | Lightweight model capability registry |
| `claude_provider.py` | Anthropic (preserved) |
| `openai_provider.py` | OpenAI Chat Completions (httpx) |
| `gemini_provider.py` | Google generateContent (httpx) |
| `mistral_provider.py` | Mistral chat (httpx) |
| `fallback_provider.py` | Legacy stub when **no** live provider configured — **not** the multi-provider router |
| `fakes.py` | Offline fake providers for tests |
| `ai_gateway.py` | Single gateway; logs cost/latency; optional injected provider for tests |

Dependencies: reused existing `anthropic` + `httpx`. No extra provider SDKs added (OpenAI/Gemini/Mistral via httpx). `requirements.txt` unchanged.

---

## Configuration (environment)

See `apps/backend/.env.example`.

| Variable | Purpose |
|----------|---------|
| `AI_PROVIDER_DEFAULT` | Default preferred provider name |
| `ANTHROPIC_*` / `OPENAI_*` / `GEMINI_*` / `MISTRAL_*` | `API_KEY`, `ENABLED`, `MODEL` |
| `FACTORY_PROVIDER_MODE` | `fixed` \| `fixed_model` \| `fallback_chain` |
| `FACTORY_PROVIDER` | Primary provider for factory |
| `FACTORY_PROVIDER_FALLBACK_CHAIN` | Explicit CSV chain (only when mode=`fallback_chain`) |

A provider is AVAILABLE only if **enabled** and **API key present**. Missing key ⇒ BLOCKED. Disabled ⇒ DISABLED.

Never commit keys. Never return keys in API/logs/audit/admin UI.

---

## Routing policy

- **FIXED** (pilot default): only `FACTORY_PROVIDER` may run. Unavailable ⇒ `PROVIDER_BLOCKED` / provider error. No silent switch.
- **FIXED_MODEL**: fixed provider + configured model override.
- **FALLBACK_CHAIN**: tries explicit chain; **every attempt recorded**.

`FallbackProvider` remains a no-key stub for tutor/legacy paths. Content Factory still rejects `is_fallback=True`.

---

## Lineage

### GenerationRun `execution_metadata`

- `routing_policy`, `provider_attempts[]`, `stats.providers`, prompt/generator versions

### GenerationCandidate (migration `d0e1f2a3b4c5`)

- `provider`, `model_used`, `routing_policy`, `provider_attempt_no`, `cost_status`, `provider_request_id`, `generator_version`, `prompt_version`

---

## Cost & budget

- Pricing table in `pricing.py` (observability-grade, not billing).
- Unknown model ⇒ `cost_status=UNAVAILABLE` (cost not invented).
- Factory **fail-closes** on `UNAVAILABLE` for live routed providers (`PROVIDER_COST_UNKNOWN`).
- Existing caps preserved: count, attempt multiplier, `$` cost, sync cap.

---

## Errors & retries

Normalized codes: `PROVIDER_BLOCKED`, `PROVIDER_AUTH_FAILED`, `PROVIDER_RATE_LIMITED`, `PROVIDER_TIMEOUT`, `PROVIDER_INVALID_RESPONSE`, `PROVIDER_UNAVAILABLE`, `PROVIDER_ERROR`, `PROVIDER_COST_UNKNOWN`.

Auth/billing/blocked stop the run (bounded attempts; no infinite retry). Transient errors may continue within P3 attempt budget.

---

## Health

`AIGateway.provider_health()` — config-only (no live credit burns).

---

## Testing

- `tests/test_ai_gateway_multi_provider.py` — contract, registry, routing, budget
- Fake providers — no network / no keys
- P1–P5 factory regression + existing AI tests

---

## Pilot methodology (do not run in this wave)

Prefer **FIXED_PROVIDER** A/B:

| Pilot | Config |
|-------|--------|
| A | `FACTORY_PROVIDER=openai` `OPENAI_ENABLED=true` |
| B | `FACTORY_PROVIDER=gemini` … |
| C | `FACTORY_PROVIDER=mistral` … |
| D | `FACTORY_PROVIDER=anthropic` … |

Same blueprints / objectives / families / difficulty / `neet_mcq_factory_v1` across providers. Compare via P4/P5 evidence — not raw speed/cost alone.

### Exact commands (when credentials/budgets ready)

```bash
# 1) Configure .env for ONE provider in FIXED mode
# 2) Migrate
cd apps/backend && alembic upgrade head

# 3) Controlled pilot (example OpenAI) — still subject to factory caps
python scripts/run_factory_p3_pilot.py

# 4) Then P4 QA + P5 sample review on that batch
# Do NOT scale to 1,000 until P4/P5 results reviewed
```

Cross-provider 100-Q matrix (25 each) is optional ops design — not auto-executed here.

---

## Safety checklist

- No live generation in this wave
- No ECAEP / question body / PHY-01–10 changes
- No silent Anthropic→OpenAI fallback
- No second Content Factory / Kafka / Celery / pgvector / AI judge
