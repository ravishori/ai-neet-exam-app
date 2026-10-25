# Study Planner — provider-independent AI personalization

## Design

`StudyPlannerService.generate()` always computes a deterministic, rule-based
plan first (`study_plan_deterministic.build_deterministic_plan`) — no network
calls, no randomness. AI personalization is layered on top as an **optional
improvement**, never a dependency: on any failure (no provider configured/
available, response fails strict schema validation, or the daily spend cap
is reached) the service silently uses the deterministic plan and marks the
result `is_fallback: true`, surfaced all the way to the frontend (a
"Standard plan" badge, vs. "AI-personalized" when the AI call succeeded).

```
deterministic plan (always)
        │
        ▼
   cache lookup (Redis, 1h TTL, keyed on user_id + inputs) ── hit ──▶ use cached AI plan
        │ miss
        ▼
   spend-cap reservation (ai.ai_requests-backed, see spend_guard.py) ── over cap ──▶ use deterministic
        │ reserved
        ▼
   AI call (independent routing policy; require_json=True)
        │
        ▼
   strict schema validation (StudyPlanShape) ── fails ──▶ use deterministic
        │ passes
        ▼
   cache the result, is_fallback=False
```

## Provider choice: still Anthropic by default, nothing forced

The AI gateway (`app/modules/ai/gateway/`) already has fully-built adapters
for OpenAI, Gemini, Mistral, OpenRouter, Groq, Krutrim, DeepSeek, and Sarvam,
each with fail-closed "is it actually configured" checks and its own
registered `PriceRate`. "Anthropic-only" was a **default-settings** fact
(`anthropic_enabled=True`, everything else `False`), not an architectural
limitation — so this change is mostly new settings and a validation/
caching/spend-cap layer around the existing gateway, not new provider code.

**`STUDY_PLANNER_PROVIDER` / `STUDY_PLANNER_PROVIDER_FALLBACK_CHAIN` are new,
independent settings** (`app/core/config.py`), read only by
`StudyPlannerService._build_routing_policy()` — they never touch
`factory_provider`/`factory_provider_mode` (Content Factory's own routing)
or `ai_provider_default` (the gateway's generic default for untouched
callers). Both are empty by default, which makes Study Planner **inherit
`ai_provider_default`** (today: `"anthropic"`) exactly as before this
feature existed — shipping this is a zero-behavior-change by default. An
operator sets these two independently to change Study Planner's provider
without affecting anything else, and vice versa.

## Provider comparison (evaluated against this feature's registered rates)

| Provider (model) | $/1M tokens, in · out | Adapter | JSON-mode | Notes |
|---|---|---|---|---|
| **Gemini 2.0 Flash** | $0.10 · $0.40 | Live, registered | Native (`responseMimeType: application/json`) | **Recommended primary** — cheapest registered rate |
| **OpenAI GPT-4o mini** | $0.15 · $0.60 | Live, registered | Native (`response_format: json_object`) | **Recommended fallback** — most consistently documented pricing across public sources |
| Mistral Small | $0.10–0.20 · $0.30–0.60 (sources disagree) | Live, registered | Decent, less consistently reliable historically | Not recommended for this feature — pricing/reliability less certain than the other two |
| OpenRouter | Same as the underlying routed model, usually no markup | Live, but **fails closed by design** (`OPENROUTER_MODEL` empty until an operator confirms a real model id) | Depends on routed model | No cost advantage over calling the same model directly; adds a third-party dependency. Not used for this feature |

**At this feature's volume** (rate-limited to 5 requests/hour/user, ~1,200
max completion tokens, ~150–300 prompt tokens), the dollar difference
between all of these is trivial — on the order of **$0.0003–0.0006 per plan
generation**, i.e. well under $1/month even at hundreds of generations/day.
Reliability and JSON-mode support, not price, are what should drive the
choice here.

**⚠️ Unresolved risk — verify before enabling in production:** the table
above reflects this codebase's own already-registered rates
(`app/modules/ai/gateway/pricing.py`) plus a quick public-pricing
cross-check done 2026-10-25. Provider pricing and model availability change
over time and can move past this assistant's knowledge cutoff (January
2026) — **re-confirm the exact model id and current price on each
provider's own pricing page immediately before setting
`GEMINI_ENABLED=true` / `OPENAI_ENABLED=true` in any real environment.**
Registry status `AVAILABLE` means "enabled + looks configured" (a non-empty
API key and model string) — it is **not** a live-verified "this key
actually works and this model id actually exists" check; the first real
call is still where that gets proven, which is exactly why the
deterministic baseline exists.

## Configuration reference

| Setting | Default | Purpose |
|---|---|---|
| `STUDY_PLANNER_PROVIDER` | `""` (inherits `AI_PROVIDER_DEFAULT`) | Primary provider for this feature only |
| `STUDY_PLANNER_PROVIDER_FALLBACK_CHAIN` | `""` (fixed mode, no fallback) | Comma-separated fallback chain, e.g. `openai` |
| `STUDY_PLANNER_CACHE_TTL_SECONDS` | `3600` | How long an identical-input AI-personalized plan is reused from cache |
| `STUDY_PLANNER_DAILY_SPEND_CAP_USD` | `1.0` | Daily USD ceiling for `agent_type=STUDY_PLANNER`'s AI calls (`ai.ai_requests`-backed, concurrency-safe — see `spend_guard.py`). `<= 0` means no AI spend allowed (always falls back to the deterministic plan), never "unlimited" |

**Recommended production values** (once the pricing/availability caveat
above has been re-checked):
```
STUDY_PLANNER_PROVIDER=gemini
STUDY_PLANNER_PROVIDER_FALLBACK_CHAIN=openai
GEMINI_ENABLED=true
GEMINI_API_KEY=<redacted>
OPENAI_ENABLED=true
OPENAI_API_KEY=<redacted>
```
No change is needed to `anthropic_enabled`, `ai_provider_default`,
`factory_provider`, or `factory_provider_mode` — none of them are read by
this feature's routing policy.

## Spend-cap concurrency safety

A plain `SELECT SUM(estimated_cost_usd) ... WHERE created_at >= today`
followed by "if under the cap, proceed" is racy: two concurrent requests can
both read the same still-under-cap sum before either one's real cost is
logged. `spend_guard.reserve_spend` closes this with a Postgres advisory
transaction lock (`pg_advisory_xact_lock`, keyed per `agent_type`) held only
for the brief check, plus an immediately-committed reservation row (an
`ai.ai_requests` row tagged with the call's worst-case cost) so a second
concurrent caller's own check sees it before the first call's real cost is
known. See the module's own docstring for the full reasoning and the one
accepted edge case (a reservation that outlives a process crash inflates
that day's total until the window resets at midnight UTC).

## Known limitations / unresolved risks

- **Concurrency verification is manual, not automated.** The spend cap's
  atomicity mechanism (`pg_advisory_xact_lock` + an immediately-committed
  reservation row — see `spend_guard.py`) was verified by hand against a
  real Postgres instance: a standalone script constructing its own fresh
  engine/connection/session (not through the test fixtures) called
  `reserve_spend` and received a valid, committed reservation back,
  confirming the mechanism works exactly as a real request would exercise
  it. An automated pytest-based two-connection race test hit a SQLAlchemy
  "MissingGreenlet" error specific to constructing a second ad-hoc async
  engine inside this suite's session-scoped event loop — a test-harness/
  event-loop-scoping interaction, not a defect in `reserve_spend` itself
  (its behavior does not depend on how the caller's session was
  constructed). **Recommendation before relying on this cap at
  meaningful scale: a quick manual check in a real running environment**
  (two concurrent requests to `/api/v1/ai/study-plan` with a very low
  `STUDY_PLANNER_DAILY_SPEND_CAP_USD`) to directly confirm cross-request
  behavior once, outside the test suite.
- Mistral/OpenRouter pricing in the table above has lower confidence than
  Gemini/OpenAI's — re-verify before choosing either.
- The spend cap is a soft, best-effort guard (not billing-grade), consistent
  with every other cost estimate already in this codebase.
- Caching is keyed on exact input equality (including the weak-concepts
  list) — a student whose weak concepts change between requests will not
  get a cache hit, by design (the plan should reflect that change).
- The deterministic plan always spans a representative 7-day week template,
  not the full `days_remaining` span — matches the existing schema/frontend
  rendering ("Day 1..N"), not calendar dates.
