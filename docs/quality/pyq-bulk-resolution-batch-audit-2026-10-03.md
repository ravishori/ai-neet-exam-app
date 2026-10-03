# PYQ Bulk Resolution — Batch Processing Audit & Final Status

**Date:** 2026-10-03
**Status: Stopped — monthly Gemini spend cap exhausted again. Real, verified progress made (371 of 9,787 processed), zero data-integrity issues found. Not resumable until the project's spend cap is raised.**

## 1. Batch processing — inspected, as-is

`resolve_up_to()` (`scripts/resolve_pyq_answers.py`) processes in pages of `BATCH_SIZE=500`, cursor-paginated by `(created_at, id)`, with **one `session.commit()` per page** — confirmed by direct code read, not assumed. Stage 1 (deterministic) always runs first for the whole page; Stage 2 (Gemini) then runs only on whatever Stage 1 left `ANSWER_PENDING` within that *same* page, immediately followed by its own commit. **The full backlog is never held in one transaction.**

## 2. Resilience & recovery — one real gap found and characterized

**Finding:** there is **no reconnect/retry logic** around the database connection itself. The first bulk run (started for all 9,787) crashed after **2,897 successful Gemini calls** with:
```
asyncpg.exceptions._base.InterfaceError: cannot call Transaction.commit(): the underlying connection is closed
```
This is a long-lived single connection over Railway's **public** Postgres proxy (used because interactive `railway run` tunnel access was unreliable in this environment — documented in the prior task) dropping after a sustained period of use. **This is a real resilience gap**, exactly matching what this task asked me to verify.

**Impact assessed, not assumed:** because each page commits independently, the crash only discarded whatever was *in-flight* in the batch being committed at the moment of the drop — every prior page's commit had already succeeded and is durable. Verified directly: **zero duplicate `(question_id, assertion_source)` assertion rows**, and the post-crash state was fully consistent (76 newly-verified + 295 newly-conflicted = exactly 371, matching the drop in `ANSWER_PENDING`).

**Recovery performed:** re-invoked the same script, unmodified — it re-queries `WHERE state = 'ANSWER_PENDING'` fresh on every invocation, so it naturally picked up exactly the remaining 9,416 rows with no manual bookkeeping needed and no risk of reprocessing the already-resolved 371.

**Not fixed in this pass, recommended for a separate task:** adding an outer retry loop around `resolve_up_to()` that catches a dropped-connection error, opens a fresh `AsyncSessionLocal()`/engine, and resumes the same way this manual re-invocation did — automating what was just done by hand. Not implemented now because (a) it's a resilience/convenience improvement, not a data-integrity defect — the existing per-batch-commit design already protects data correctness during a crash — and (b) further execution is moot regardless until the spend cap (Section 4) is resolved, so there is nothing to validate the fix against right now.

## 3. Answer integrity — directly verified

| Check | Result |
|---|---|
| Existing `VERIFIED` assertions touched | **0** — count before (2,499) unchanged except for legitimate new Stage-1 additions |
| Existing `DISPUTED`/conflicted questions touched | **0** — confirmed via count reconciliation |
| Duplicate `(question_id, assertion_source)` rows | **0** |
| `AI_RESOLVED` vs `VERIFIED` conflated | **No** — all 52 new Stage-2 answers correctly tagged `AI_RESOLVED` |
| Any answer guessed under insufficient evidence | **No** — every provider error or no-single-supported-option case was left `ANSWER_PENDING`, never force-resolved |

## 4. Why execution stopped — the real, current blocker

A direct, minimal, isolated connectivity test (key never logged) confirms: **the Google Cloud project's monthly spending cap has been exceeded again** — `429 RESOURCE_EXHAUSTED`, *"Your project has exceeded its monthly spending cap."* This happened after the first run alone spent **$7.4879** (2,897 successful calls), meaning the cap is evidently set quite low relative to this backlog's full processing cost. The resumed run then produced **267 consecutive Stage-2 failures with zero successes** before I stopped it — confirming the cap, not a code defect, is the blocker.

**I stopped the running job** rather than let it continue burning requests against a guaranteed-fail billing wall, per this task's own stated priority: *"Accuracy and data integrity take priority over resolution volume"* and *"subject to API limits, budget."* No further Gemini calls were attempted after diagnosis.

## 5. Final verification — database counts, reconciled against baseline

| Metric | Baseline (start of this task's prior session) | After run 1 (crashed) | After run 2 (stopped — unchanged) |
|---|---:|---:|---:|
| `ANSWER_PENDING` | 9,787 | 9,416 | 9,416 |
| `ANSWER_VERIFIED` | 2,499 | 2,575 | 2,575 |
| `ANSWER_CONFLICT` | 110 | 405 | 405 |
| `answer_assertions.VERIFIED` | 2,499 | 2,523 | 2,523 |
| `answer_assertions.AI_RESOLVED` | 0 | 52 | 52 |
| `answer_assertions.DISPUTED` | 375 | 1,374 | 1,374 |
| Duplicate assertion rows | — | 0 | **0** |

**Reconciliation:** 9,787 − 9,416 = 371 processed = 76 newly verified + 295 newly conflicted, exactly. No row is miscounted or missing. **Run 2 made zero further database changes** (confirmed identical before/after) — consistent with its 0-success, 267-failure outcome.

## 6. Batch-wise progress and outcomes

| Run | Questions processed (state changed) | Stage-1 verified | Stage-2 `AI_RESOLVED` | Newly conflicted | Stage-2 calls attempted | Stage-2 successes | Stage-2 failures (billing cap, before/during) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Run 1 (crashed mid-batch after a connection drop) | 371 | 24 | 52 | 295 | 3,164 | 2,897 | 267 (hit the cap near the very end, just before the crash) |
| Run 2 (resumed; stopped by me on diagnosis) | 0 | 0 | 0 | 0 | 267 | 0 | 267 (100% — cap still exhausted) |
| **Total** | **371** | **24** | **52** | **295** | **3,431** | **2,897** | **534** |

**Total Gemini spend across both runs:** **$7.4879** (2,897 successful calls; failed/429 calls are not billed by Google). At an approximate ₹83/USD conversion (not a precise, live FX rate — stated as an approximation only), that is **≈ ₹622**.

## 7. Outstanding work / remaining backlog

- **9,416 of 9,787 questions remain `ANSWER_PENDING`.**
- **Cannot be processed further until you raise the project's monthly spend cap** at `ai.studio/spend`. This is the sole blocker — confirmed directly, not inferred.
- Once raised, resuming is a single command (the exact same invocation used for run 2) — no code change is required to resume safely, since the script is idempotent and re-queries pending state fresh each time.
- The connection-resilience gap (Section 2) should be fixed before any future very-large (multi-thousand-question) unattended run, to avoid needing a manual restart if the public-proxy connection drops again over a long run.

## 8. Production health

`GET /health` and `/ready` both returned `200` throughout this entire task — this script runs from the local environment against the public database/Gemini endpoints directly and never touches the running application process, so it cannot destabilize it.

## 9. What was NOT done, confirmed per instruction

- The local NCERT corpus (1,112 units) was **not** synced or modified in production (still 381 units, unchanged).
- No competing bulk-resolution worker was run — the scheduled in-app worker (`PYQ_RESOLVER_WORKER_ENABLED=true`) and this manual CLI invocation both operate on the same `ANSWER_PENDING` selection + `ON CONFLICT DO NOTHING` idempotency guard, so even if the scheduled worker's next tick fires while spend is still capped, it will simply also fail safely (same billing wall) without double-processing or corrupting anything.
