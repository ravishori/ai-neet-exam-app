# Stop Gemini Spend & Zero-Paid-API PYQ Resolution Design

**Date:** 2026-10-03. Read-only audit except for the two authorized kill-switch variable changes below (explicitly the task's own first objective). No production data, migration, or deployment change was made.

## 1. Confirmation: Gemini calls disabled

```
railway variables: GEMINI_ENABLED=false, PYQ_RESOLVER_WORKER_ENABLED=false
```
**Deployment `4c86fdfa` live, confirmed by direct log read: startup log shows no `pyq_resolver_task` creation** (the line that appears only when `settings.pyq_resolver_worker_enabled` is true at `app/main.py`'s `lifespan()`). `/health` returns 200 throughout.

**This is a partial guard, not a complete one — see Section 2's critical finding.**

## 2. Inventory of all Gemini call sites — including the gap these two flags do NOT close

| File | Gated by `GEMINI_ENABLED`? | Gated by `PYQ_RESOLVER_WORKER_ENABLED`? | Trigger |
|---|---|---|---|
| `app/main.py` → scheduled `pyq_resolver_task` (Stage 2 inside) | — | **Yes** (now off) | App startup, recurring |
| `app/modules/ai/gateway/registry.py` (generic `AIGateway` router's provider selection) | **Yes** (now off) | — | Any feature using the shared router |
| `app/modules/cms/mcq/p2_3/provider_routing.py` | **Yes** (now off) | — | MCQ provider routing |
| `app/modules/cms/acquisition/mmf/config.py`, `embedding_backends.py` | **Yes** (now off) | — | Embedding backend selection |
| **`scripts/resolve_pyq_answers.py` — `_stage2_default_gateway()`** | **❌ No** | **❌ No** | Constructs `GeminiProvider` **directly** from `settings.gemini_api_key`/`gemini_model`, bypassing the router and both flags entirely, "by design" (per the file's own comment, to avoid touching the unrelated `FACTORY_PROVIDER` setting) |
| **`app/modules/cms/pyq/pyq_gemini_backfill.py`** (admin API: `POST /api/v1/admin/pyq-gemini-backfill/start`, `/{job_id}/run`) | **❌ No** | **❌ No** | Same direct-construction pattern, triggerable via an authenticated admin API call |
| `scripts/run_factory_gemini_5q_pilot.py`, `run_factory_gemini_smoke.py`, `run_gemini_jsonl_phy11_ch02_b001.py`, `mcq_provider_benchmark_001.py` | Mixed/not audited in depth — all are manual CLI scripts, not background/scheduled, require a human to invoke with a real key present | | |

**Critical finding:** `GEMINI_ENABLED=false` and `PYQ_RESOLVER_WORKER_ENABLED=false` **do not form a true fail-closed guard.** Two real paths — the PYQ Stage-2 resolver script and the admin Gemini-backfill endpoint — construct `GeminiProvider` directly and would still make real, billed calls if invoked, **regardless of either flag**, as long as `GEMINI_API_KEY` is set (which it still is — only the booleans were changed, not the key). This is exactly how I was able to run the manual bulk-resolution calls in the prior task even while these flags existed.

**Proposed hard guard (not implemented or deployed — requires your approval):** add one check inside `GeminiProvider.__init__` (the single class every one of these paths ultimately instantiates) that reads `settings.gemini_enabled` and raises immediately if false. This centralizes the kill-switch in the one place nothing can bypass, instead of relying on every call site remembering to check it individually. A ~5-line change, one file, fully backward-compatible (today's "disabled" state would then also block the CLI script and admin endpoint, exactly as the task requires). **I have not written or deployed this change** — flagging it as the recommended fix pending your go-ahead.

## 3. Current database checkpoint — no overwrites, confirmed unchanged since the last report

```
state: ANSWER_PENDING=9416, ANSWER_CONFLICT=405, ANSWER_VERIFIED=2575
answer_assertions: VERIFIED=2523, AI_RESOLVED=52, DISPUTED=1374
```
Identical to the checkpoint in `docs/quality/pyq-bulk-resolution-batch-audit-2026-10-03.md` — the scheduled worker's one further tick (12:17 today, before this task's disablement) made zero database changes (100% of its Stage-2 attempts failed on the exhausted spend cap, same as before). No PYQ record, assertion, or production config beyond the two kill-switch variables was touched in this task.

## 4. Coverage report — pending PYQs vs. available NCERT sources (reusing existing audits, not re-derived)

This exact question was already answered in depth by three audits earlier this session — reused here rather than repeated:

| Measure | Local dev corpus (1,112 KUs, never synced to prod) | Production corpus (381 KUs, currently live) |
|---|---|---|
| Strict mechanical-match coverage | 3,868/9,944 (38.9%) | 1,744/9,787 pending at last tier-apply (≈ similar order) |
| Relaxed, subject-safeguarded coverage | 3,683 additional (total 7,551/9,944, 76%) | 4,768 additional (total 6,512/9,787, 67%) |
| Zero-vocabulary-overlap (plausibly missing source) | 113/9,944 (1.1%) | not separately re-run for production's smaller corpus — would require the same diagnostic, not re-run here to respect cost-efficiency |
| Known PDF/ingestion gaps | 2 non-chapter files (appendix, cover page) — everything else mapped | not independently audited (production's corpus predates this session) |

**Full detail:** `ncert-retrieval-coverage-forensic-audit-2026-10-01.md`, `ncert-retrieval-relevance-validation-2026-10-01.md`, `pyq-8159-ncert-retrieval-enablement-2026-10-01.md`. **Key, already-established finding directly relevant here:** relaxed-threshold retrieval context being *available* is not the same as an answer being *resolved* — of 2,897 successful Gemini calls in today's bulk run, only 52 (1.8%) produced a usable single answer; the rest correctly found no clear single supported option. **This means even a perfect zero-cost retrieval system would still leave most of the backlog unresolved without either an official answer key or a stronger reasoning method** — retrieval alone was never going to resolve most of these questions, Gemini or not.

## 5. Zero-paid-API resolution design

**Tier 1 — exact/official answer-key reuse (highest confidence, zero cost, not yet implemented):** check whether any locally-held NCERT PYQ official answer-key PDF/data exists (`NEET_PYQ_OFFICIAL/` holds question papers; **I did not find an official answer-key source in this repository during this session's work** — flagged as unknown, not confirmed absent). If one exists or can be obtained, exact question-hash or question-number matching against it would resolve matched questions with the highest possible confidence, no retrieval or AI needed.

**Tier 2 — deterministic NCERT retrieval (already implemented, zero cost):** Stage 1's existing strict 0.5-threshold matcher. Already running, already free, unaffected by this task's Gemini shutdown — **continues to work normally** and should keep running on its own schedule.

**Tier 3 — numerical/formula verification (not implemented):** for Physics/Chemistry numerical questions, a deterministic calculator that parses the question's given values and checks each option against a computed answer, where the question type is unambiguously numerical (e.g., "find the resistance given..."). Not designed in detail here — would need its own scoped task; flagged as a promising zero-cost avenue the current pipeline doesn't attempt at all.

**Tier 4 — local model only as a last resort, never self-verified:** per your explicit instruction, "do not assume local model output is verified" — any locally-run open-weight model's output would need the exact same evidence-grounding check Stage 1 already uses (`is_fact_grounded`) before being trusted, and should be tagged with its own distinct status (not `VERIFIED`, not `AI_RESOLVED` — a new, clearly-labeled status, mirroring the same discipline already applied to `AI_RESOLVED` vs `VERIFIED`). **No local model is currently installed or evaluated in this repository** — this is a design placeholder, not a working component.

## 6. Small, read-only pilot proposal

**Scope:** 50 pending questions, stratified the same way as the existing relevance-review worksheet (subject × score band), reusing `docs/quality/_retrieval_relevance_2026-10-01/relevance_validation_audit_script.py`'s already-proven sampling method.

**Method:** for each sampled question, attempt Tier 1 (if an answer-key source is located) then Tier 2 (existing deterministic matcher, already free) only. **No Gemini call, no local model call.**

**Expected outcome:** given Tier 2 alone, by direct extrapolation from today's real data (Stage 1 answered 24 of 371 processed = 6.5%), expect roughly 3-4 of the 50 to resolve via Tier 2 alone; the rest would need either Tier 1 (if a source is found) or remain correctly unresolved.

**Validation criteria:** every Tier-1/Tier-2 resolved answer must carry a traceable source citation (page + document for Tier 2, exact key-source reference for Tier 1) — exactly the existing `evidence_note` convention — and must be spot-checked by a human against that source before being trusted at scale, consistent with every other audit in this chain's refusal to self-certify.

**Definition of Done for this pilot:** a CSV of the 50 sampled questions, their Tier-1/Tier-2 outcome (resolved/unresolved, with evidence), and zero Gemini/local-model calls — ready for your review before any decision to scale it.

## Unknowns and blockers, disclosed explicitly

- **Whether an official NEET answer-key source exists locally** — not found in this session's exploration of `NEET_PYQ_OFFICIAL/`, but not exhaustively ruled out either (only the question papers were inventoried in depth; a separate answer-key file may exist under a name not yet searched for).
- **The hard-guard code fix (Section 2) is designed but not implemented or deployed** — needs your explicit approval before I write and ship it.
- **No numerical-verification tier exists today** — would be new work, not a quick fix.
- **Production's smaller (381-unit) corpus has not been separately coverage-audited** the way local dev's was — would require the same diagnostic script run against production's data (cheap, read-only, not yet done in this task to respect the cost-control instruction from the prior turn).
