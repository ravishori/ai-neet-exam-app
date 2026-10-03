# Claude Cost & Productivity Audit — NEET PYQ Resolution

**Date:** 2026-10-03. **Read-only audit** — reuses data already gathered this session; no new resolver runs, no new Gemini calls, no production writes.

## A. Executive summary

| Item | Value | Status |
|---|---|---|
| **Claude/Anthropic token cost** | **Unknown to me** | I have no tool access to this session's Anthropic billing/token-usage data. Your "~₹1,000" figure is from your own Claude Code billing view, which I cannot read or verify from inside the session. |
| **Gemini API cost (confirmed)** | **$7.4879** (≈ ₹622 at ~₹83/USD, approximate) | **Verified** — summed directly from `cost_usd` fields logged on every successful call across both bulk-resolution runs today. |
| **Gemini cost, all-time (all features, not just today)** | $28.23 (as of my last DB check) | Verified, but includes pre-existing history unrelated to today's work. |
| **PYQs actually, verifiably resolved today** | **76** | 24 via Stage-1 deterministic (free), 52 via Stage-2 Gemini (`AI_RESOLVED`) |
| **PYQs newly flagged conflicted** | **295** | Correctly isolated, not guessed, not silently resolved |
| **PYQs merely "attempted" (Gemini called, no usable answer)** | ~2,845 of 2,897 successful calls | **Not counted as resolved** — most Stage-2 calls correctly returned "no clear single answer" and were left pending |
| **Cost per genuinely resolved question (Gemini-attributable only)** | **$7.4879 / 76 ≈ $0.0985** (if crediting the whole run's spend against only the 76 outcomes) — or **$7.4879 / 52 ≈ $0.144** counting only the Gemini-resolved subset | Both framings given; neither should be read as "cost per question in the full backlog," since most of the spend went to calls that correctly produced no answer |

## B. Session-wise audit (this session, today, 2026-10-03)

| Task | Claude cost | Gemini cost | Tool calls (approx.) | PYQs updated | Outcome | Evidence |
|---|---|---:|---:|---:|---|---|
| Gemini key-leak emergency mitigation + fix shipped + deploy | unknown | $0 | ~35 | 0 | Leak stopped, code deployed, migrations applied | `docs/quality/production-release-2026-10-03.md` |
| Retrieval-enablement applied to production | unknown | $0 | ~10 | 0 (tiering only, no answers) | 4,768 candidates tiered, `state` unchanged | same report, Section 4 |
| Stage-2 connectivity verification (50-question bounded test) | unknown | $0.1138 | ~8 | 1 | 1 question `AI_RESOLVED`, 44 correctly left pending, 5 Stage-1-unresolved | `docs/quality/production-final-verification-2026-10-03.md` |
| **Bulk resolution, run 1** (crashed on a connection drop after 2,897 Gemini calls) | unknown | **$7.4879** | ~6 | **371** (24 verified + 295 conflicted + 52 AI-resolved) | **Real, productive** — committed, verified, zero duplicates | `docs/quality/pyq-bulk-resolution-batch-audit-2026-10-03.md` |
| **Bulk resolution, run 2** (resumed; hit the monthly spend cap immediately) | unknown | **$0** (267/267 calls failed — Google does not bill failed calls) | ~5 | **0** | **Wasted tool-call/turn overhead, zero Gemini cost, zero DB change** | same report |
| Cost-control protocol response + this audit | unknown | $0 | ~6 (this report) | 0 | — | this file |

**Note on Claude cost column:** every row says "unknown" because I genuinely cannot see it from inside this session — there is no tool here that exposes Anthropic token/billing data. If you need this broken down, it has to come from your Claude Code usage dashboard, correlated against the timestamps in this table.

## C. Before-and-after database comparison

| Metric | Baseline (session start today) | After bulk run 1 | After bulk run 2 (= final, unchanged) |
|---|---:|---:|---:|
| `ANSWER_PENDING` | 9,787 | 9,416 | 9,416 |
| `ANSWER_VERIFIED` | 2,499 | 2,575 | 2,575 |
| `ANSWER_CONFLICT` | 110 | 405 | 405 |
| `answer_assertions.VERIFIED` | 2,499 | 2,523 | 2,523 |
| `answer_assertions.AI_RESOLVED` | 0 | 52 | 52 |
| `answer_assertions.DISPUTED` | 375 | 1,374 | 1,374 |
| Duplicate `(question_id, assertion_source)` rows | — | 0 | 0 |

**No unexplained differences.** 9,787 − 9,416 = 371 = 76 (24 verified + 52 AI-resolved) + 295 (conflicted) — reconciles exactly. Run 2 produced zero change (confirmed identical before/after), consistent with its 0-success outcome.

**Attribution:**
- **24 `VERIFIED`** — Stage-1 deterministic matching (free, no AI, no Claude involvement in the decision logic itself — Claude invoked the existing, unmodified script).
- **52 `AI_RESOLVED`** — Stage-2 Gemini, using NCERT-sourced retrieval context (the existing, unmodified `resolve_stage2_batch` logic).
- **295 conflicted** — Stage-1 and Stage-2 both found multiple plausible options; correctly recorded as `DISPUTED`/`ANSWER_CONFLICT`, not resolved.
- **Nothing here was decided or judged by Claude directly** — Claude invoked existing, previously-tested, deterministic/Gemini-backed code; the actual answer decisions came from that code's own logic, not from Claude's own reasoning about question content.

## D. Waste analysis (quantified where evidence exists)

| Item | Quantified impact |
|---|---|
| Run 2's 267 Stage-2 calls against an already-exhausted spend cap | **$0 wasted in Gemini billing** (failed calls aren't charged) but **~5-10 minutes of wall-clock/tool-call overhead** before I diagnosed and stopped it — should have checked spend-cap headroom before resuming, not after. |
| Earlier in this session: first attempt to disable Gemini used `GEMINI_ENABLED=false`, which doesn't gate the PYQ resolver worker at all | 1 redeploy cycle (~1-2 min) spent before finding the correct variable (`PYQ_RESOLVER_WORKER_ENABLED`) |
| A variable `--set` call silently no-op'd because the Railway CLI's service link had gone stale | 1 extra diagnostic round-trip + 1 extra redeploy before the fix actually applied |
| Full backend test suite (`pytest tests/`, ~1,185 tests) run once this session, taking ~47 minutes wall-clock | Not wasted — needed once to confirm no regression before shipping — but should not be re-run again without a reason; **not re-run in this audit, per your cost-control instruction.** |
| Multiple short `sleep`+status-check polling loops while waiting on slow Railway builds/tunnels | Each individually cheap, but accumulated turns; a longer single wait would have been more efficient. |

**Not quantifiable from here:** Claude token/thinking-token consumption per step — no access to that data (Section A).

## E. Recommendations

1. **Check Gemini spend-cap headroom before every resume**, not after a failure — a single `curl` connectivity probe (as used throughout this session) costs nothing and would have avoided run 2's wasted cycle entirely.
2. **Set a lower, explicit per-session Gemini budget ceiling** (e.g., a `--max-cost-usd` guard in the resolver script) so a long unattended run stops itself before hitting an external cap unexpectedly — not implemented today, flagged as a cheap, high-value future change.
3. **Add connection-retry/resume logic** to `resolve_up_to()` (already identified in `pyq-bulk-resolution-batch-audt-2026-10-03.md` Section 2) so a dropped long-lived DB connection doesn't require a manual restart.
4. **Batch Railway variable changes together** before triggering a redeploy, rather than one redeploy per variable, to cut deploy-cycle overhead.
5. **For future large-batch work:** confirm the exact spend cap value upfront (ask you directly, or check if it's queryable) rather than discovering it empirically via failed calls.

## Disclosed gaps

- **Claude/Anthropic-side cost figures are entirely unverified by me** — no tool in this environment exposes that data. The ₹1,000 figure is yours, not independently confirmed here.
- **"Genuinely supported by NCERT evidence"** was not separately re-validated per-answer in this audit (would require re-reading all 76 answers against source text — an expensive operation not authorized here); the 52 `AI_RESOLVED` answers rely on the Stage-2 prompt's own NCERT-context grounding, as already described in the resolver's own evidence_note field, not independently re-verified question-by-question in this pass.
- Tool-call/turn counts in Section B are approximate, reconstructed from this conversation, not from an exact log export.
