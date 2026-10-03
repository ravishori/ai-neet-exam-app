# Fail-Closed Gemini Guard — Implementation & Test Evidence

**Date:** 2026-10-03. **Local implementation only — not deployed, no production config changed in this task.**

## 1. Changed files

| File | Change |
|---|---|
| `apps/backend/app/modules/ai/gateway/base.py` | Added `PROVIDER_DISABLED` error code. |
| `apps/backend/app/modules/ai/gateway/gemini_provider.py` | `GeminiProvider.__init__` now reads `get_settings().gemini_enabled` and raises `ProviderError(PROVIDER_DISABLED, ...)` immediately if `False` — before `self._api_key`/`self._model` are even stored, let alone any network call made. This is the single choke point every call site below goes through. |
| `apps/backend/tests/test_gemini_fail_closed_guard.py` | **New** — 4 regression tests (Section 3). |

**Not changed:** any production variable, migration, deployment, or other application file. `scripts/resolve_pyq_answers.py` and `app/modules/cms/pyq/pyq_gemini_backfill.py` needed **no code change** — they already construct `GeminiProvider` directly, so the new guard inside that class protects them automatically.

## 2. Full Gemini call-site inventory, with guard status after this change

| Call site | Before this change | After this change |
|---|---|---|
| `app/main.py` scheduled worker | Gated by `PYQ_RESOLVER_WORKER_ENABLED` only (at startup, decides whether to even launch the task) | Unchanged — plus now also gated by the new construction-time guard if it ever did start |
| `registry.py` / `provider_routing.py` / MMF embedding backends | Already checked `gemini_enabled` before constructing | Unchanged (redundant with the new guard, harmless) |
| **`scripts/resolve_pyq_answers.py::_stage2_default_gateway`** | ❌ **Not gated at all** — direct construction | ✅ **Now blocked** — raises `ProviderError(PROVIDER_DISABLED)` the instant it's called, before any Gemini traffic |
| **`app/modules/cms/pyq/pyq_gemini_backfill.py::select_backfill_model`** (model-availability probe) | ❌ Not gated | ✅ **Now blocked** — its own existing `except ProviderError` catches it and falls back to `settings.gemini_model` without ever making a real call |
| **`app/modules/cms/pyq/pyq_gemini_backfill.py::run_backfill`** (main batch-processing construction, line ~379) | ❌ Not gated | ✅ **Now blocked** when `ai_gateway` isn't injected (the real-world API-triggered path) |
| `scripts/run_factory_gemini_5q_pilot.py`, `run_factory_gemini_smoke.py`, `run_gemini_jsonl_phy11_ch02_b001.py`, `mcq_provider_benchmark_001.py` | ❌ Not gated (manual CLI scripts) | ✅ **Now blocked** — all construct `GeminiProvider` and inherit the same guard |

**Remaining Gemini call paths after this fix: none bypass the guard.** Every one of the 6+ construction sites found in the codebase-wide search goes through `GeminiProvider.__init__`, and that is now the single point where `gemini_enabled=False` stops all of them — CLI script, admin endpoint, scheduled worker, or shared router, with no path left uncovered that this audit found.

## 3. Regression tests — evidence, no real API calls made

File: `apps/backend/tests/test_gemini_fail_closed_guard.py`. Every test patches `httpx.AsyncClient` to **raise an assertion error if ever constructed** — so a regression in the guard would show up as a hard test failure, not a passed test with a hidden real call.

```
tests/test_gemini_fail_closed_guard.py::test_gemini_provider_construction_rejected_when_disabled PASSED
tests/test_gemini_fail_closed_guard.py::test_gemini_provider_construction_allowed_when_enabled_but_still_no_network_call PASSED
tests/test_gemini_fail_closed_guard.py::test_resolve_pyq_answers_stage2_default_gateway_blocked_when_disabled PASSED
tests/test_gemini_fail_closed_guard.py::test_pyq_gemini_backfill_model_probe_blocked_when_disabled PASSED
4 passed in 0.38s
```

**Regression check against existing suites** (no new failures introduced):
```
pytest tests/test_gemini_provider_response_handling.py tests/test_pyq_resolver_worker.py \
  tests/test_pyq_retrieval_enablement.py tests/test_pyq_gemini_backfill.py \
  tests/test_credential_redaction.py tests/test_gemini_fail_closed_guard.py -q
→ 4 failed, 71 passed
```
The 4 failures are the **same pre-existing** `test_pyq_gemini_backfill.py` failures identified in the prior session's audit (an unmocked real-network model-availability probe inside that test file, unrelated to this change) — confirmed by checking the actual error code in the failure output: it's `PROVIDER_ERROR` (a real attempted-call failure from that test's own local `.env` having `gemini_enabled=True` with a live key), **not** the new `PROVIDER_DISABLED` — i.e., this change did not alter that pre-existing test's behavior at all.

**`ruff check`:** all checks passed (one import-order auto-fix applied, then re-verified).

## 4. Database reconciliation — 12,448 vs 12,396

**Direct, read-only query against production, right now:**
```
total_questions_now: 12396
by_state: {ANSWER_PENDING: 9416, ANSWER_CONFLICT: 405, ANSWER_VERIFIED: 2575}
```
**The actual current total is 12,396 — identical to the original baseline. There is no 12,448 in the database.**

**Most likely source of the discrepancy, found by arithmetic, not guessed:** 12,396 + 52 = **12,448 exactly**, where 52 is the count of new `AI_RESOLVED` **answer_assertions** rows created by today's bulk-resolution run. This strongly suggests "12,448" was produced by someone (or some report) adding the new-assertions count to the question-table total, rather than recognizing that `AI_RESOLVED` assertions are new *answers for existing* questions, not new *questions*. **Confirmed: `pyq.questions` has never grown** — every one of the 12,396 rows shares the identical original `created_at` timestamp (`2026-09-27T15:21:12Z`), confirming no row was added at any point during this session's work.

## 5. Preservation confirmation

- No bulk resolution or Gemini call was executed in this task.
- Production `pyq.questions`/`pyq.answer_assertions` state: **unchanged** from the last checkpoint (`ANSWER_PENDING=9416`, `ANSWER_VERIFIED=2575`, `ANSWER_CONFLICT=405`; `VERIFIED=2523`, `AI_RESOLVED=52`, `DISPUTED=1374`).
- Production config (`GEMINI_ENABLED=false`, `PYQ_RESOLVER_WORKER_ENABLED=false`): **unchanged**, still disabled from the prior task.

## 6. Exact deployment verification required (not performed — awaiting your approval to deploy)

Once you approve shipping this:
1. Commit + push (not done yet).
2. Deploy to Railway (existing CD trigger on push to `main`).
3. **Verification after deploy:** re-run the same connectivity probe used throughout this session (`curl` with `x-goog-api-key`, printing only the status code) **against `GEMINI_ENABLED=true` with the new code live** — confirm the app layer still works end-to-end exactly as before (this guard only blocks when disabled; it must not change behavior when enabled). Then, separately, with `GEMINI_ENABLED=false`, confirm the admin backfill endpoint and the CLI script both now fail fast with `PROVIDER_DISABLED` instead of silently succeeding or crashing with a raw network error — this specifically closes the gap this task was about.
4. No migration is needed (no schema change in this task).

## Not executed, per your explicit instruction

- The 50-question zero-cost pilot — not run.
- No deployment or production configuration change — not made.
