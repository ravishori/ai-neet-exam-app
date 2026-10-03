# Zero-Cost PYQ Resolution: Pilot Results & 80–90% Feasibility Verdict

**Date:** 2026-10-03. Zero Gemini/paid-API calls made. Reused existing code and audits; no new infrastructure added.

## 1. Database reconciliation (reused from last checkpoint — unchanged)
`ANSWER_PENDING=9,416`, `ANSWER_VERIFIED=2,575`, `ANSWER_CONFLICT=405` (total 12,396). No change since the prior task.

## 2. Source audit — new materials provided this turn

You attached 4 new NCERT zip archives (`NCERT Books/Class {11,12}/{Biology,Chemistry 1&2,Physics}.zip`), using NCERT's own official short-filename convention (`kebo1*`, `keph1*`, etc. — the same family as the already-parsed `leph2*` pattern from an earlier audit). **These are not yet ingested** — `knowledge.knowledge_units` is unchanged (production: 381; local dev: 1,112). Checksumming these against the already-ingested `StudyMaterial/` corpus to determine overlap-vs-new-content was **not done** in this pass (would need per-file comparison — a cheap but non-trivial step, skipped here per the cost-discipline instruction; flagged as the natural next step, not completed).

## 3. Pilot: Stage-1-only (zero-cost, zero-Gemini) resolution, 50 questions

Reused `resolve_batch()` unmodified (the existing, already-tested strict-matcher) via a minimal new wrapper that **never constructs a Gemini provider at all** — avoiding the new fail-closed guard entirely rather than needing to catch it. Ran against the next 50 oldest `ANSWER_PENDING` questions in production (read-write, but zero paid cost).

**Result: 0 of 50 resolved.** (`unresolved_no_source_match=45`, `unresolved_no_option_grounded=5`.)

## 4. Verdict: 80–90% zero-cost completion is NOT achievable with the current ingested corpus

This is a **small, honest, negative pilot result**, consistent with — not contradicting — this session's own prior bulk-run data: of the 371 questions already processed earlier today (with Gemini on), only **24 (6.5%)** were resolved by Stage-1 alone; the other 347 needed Gemini (52 succeeded, 295 conflicted/ambiguous). This pilot's 0/50 is within that same low-single-digit-percent range for Stage-1-only, not an anomaly.

**Extrapolating honestly, not optimistically:** at a ~6.5% Stage-1-only hit rate, running Stage 1 across the remaining ~9,366 pending questions would add roughly **~600 more verified answers (≈6.4%)** — nowhere near 80–90%. **I am not claiming this number as validated** (it is an extrapolation from a 50-question sample and a different 371-question batch, not a completed full run) — stated as an estimate, not a result.

**Root cause, already established in this session's earlier audits, not re-derived:** the dominant bottleneck is retrieval-threshold strictness and corpus size, not purely missing source — `ncert-retrieval-relevance-validation-2026-10-01.md` already showed only ~1–2% of the uncovered population has zero vocabulary overlap at all; most have *some* overlap but fail the strict 0.5 threshold, and relaxing it was already shown (same audit) to introduce a 55% cross-subject false-positive rate without human review. **Zero-cost retrieval alone cannot close this gap defensibly** — it would require either (a) human-reviewed relaxed-threshold acceptance (labor, not API cost, but not "zero-cost" in effort), or (b) a genuinely larger/better-matched source corpus, or (c) an official answer key (not located in this repository).

## 5. What would actually move the needle (not done, requires authorization)

1. **Ingest the newly-provided NCERT Books zips** — if they add chapters beyond what's already in `StudyMaterial/`, this directly grows Stage-1's strict-match denominator. Cheapest, highest-leverage next step; not done here (new ingestion work, out of this task's "reuse, don't add infrastructure" scope without your go-ahead).
2. **Numerical/formula verification tier** (proposed, not built, in the prior audit) — could resolve a subset of Physics/Chemistry numericals deterministically, no retrieval needed.
3. **Official answer key** — not found in this repository; if one exists elsewhere, exact-match resolution would be the highest-confidence, truly zero-cost method of all. Status: **unknown, unlocated**.

## 6. Cost incurred
**$0.** No Gemini or other paid API call was made in this task.

## Definition-of-Done check — honest, not inflated

- Before/after counts: unchanged (0 new verified from this pilot).
- Genuinely resolved: **0 of 50 piloted**; **76 of 9,787** cumulative across this entire session (from the earlier Gemini-assisted run, not from zero-cost methods).
- Independently validated accuracy: not applicable — 0 new answers to sample.
- 80–90% zero-cost target: **not achievable with current ingested corpus** — stated plainly, per your own instruction, rather than claimed.
- Blockers: corpus size/coverage (addressable, needs authorization to ingest), no answer-key source located, retrieval-threshold precision gap (needs human review effort, not API cost).

**I am not scaling this to the full 9,416** given the 0/50 pilot result — running it further at zero cost would not meaningfully change the outcome without first growing the corpus or adding a new deterministic tier. Awaiting your direction on whether to proceed with ingesting the new NCERT zips.
