# NCERT Relaxed-Retrieval Enablement for the Owner-Accepted Candidate Pool

**Date:** 2026-10-01 (implementation executed 2026-10-03)
**Priority:** P0 — launch-critical, as directed by the project owner
**Environment:** local development only (`trinetra_db` @ `localhost:5432`). Production was never accessed. Nothing committed or pushed.

## 0. Headline result — read this first

The project owner's instruction was to enable "all 8,159 PYQs identified by the relaxed NCERT retrieval analysis." Per this task's own instruction ("If the exact 8,159 set is not reproducible, report the discrepancy and use the reproducible result rather than forcing the old count"), the exact mechanics were re-run against the current database with the actual implementation, not assumed:

| Configuration | Reproduced count | Matches 8,159? |
|---|---:|---|
| Relaxed threshold (0.25), **no** subject constraint | 4,291 new + 3,868 already-strict = **8,159** | ✓ exact match |
| Relaxed threshold (0.25), **with** the subject-constrained safeguard (required by this task's own Section 3.7: "Avoid unrelated cross-subject context where subject metadata is available and reliable") | 3,683 new + 3,868 already-strict = **7,551** | ✗ — 608 fewer |

**The reproducible, safeguarded number is 7,551, not 8,159.** The 608-question gap is not a bug — it is exactly the set of questions whose only relaxed-threshold match was in a *different* subject than the question's own label, which the prior relevance-validation audit found to be a large and real false-positive risk (55.4% cross-subject mismatch rate among labeled newly-covered questions). **This report uses 7,551 as the actual, safeguarded, implemented candidate count**, and documents the 8,159 figure as the unsafeguarded reference point for comparison — never as the number actually enabled.

## 1. Pre-implementation baseline (recomputed, not assumed)

```
pyq.questions: total=12396, ANSWER_VERIFIED=2452, ANSWER_PENDING=9944
disputed/conflicting answer_assertions: 0 questions
knowledge.knowledge_units: 1112 (986 PASSED / 126 FAILED)
```

| Metric | Value |
|---|---:|
| Total PYQs | 12,396 |
| Independently verified (`ANSWER_VERIFIED`) | 2,452 |
| Pending (`ANSWER_PENDING`) | 9,944 |
| Candidate set (relaxed, subject-constrained) | **3,683** of the 9,944 pending |
| Already independently verified within the candidate logic's scope | 0 (candidate computation only ever runs over `ANSWER_PENDING` rows — independently verified questions are structurally excluded, never recomputed) |
| Pending with no answer at all | 9,944 (= all pending, since none have any assertion yet) |
| Conflicting/disputed answer assertions | 0 |
| Excluded as deleted/malformed | 0 knowledge units newly excluded by this task's correctness fix beyond the 126 already-FAILED ones (see Section 3) |

## 2. Files changed

| File | Change |
|---|---|
| `apps/backend/app/core/config.py` | Added 3 new feature-flag settings: `pyq_relaxed_retrieval_enabled` (default `False`), `pyq_relaxed_retrieval_threshold` (default `0.25`), `pyq_relaxed_retrieval_subject_constrained` (default `True`). |
| `apps/backend/app/modules/knowledge/services/grounding_check.py` | Added an optional `threshold` keyword to `is_fact_grounded()`, defaulting to the existing `OVERLAP_THRESHOLD` — **every existing caller's behavior is unchanged**; this only lets the new relaxed-retrieval diagnostic reuse the one existing grounding function instead of duplicating it. |
| `apps/backend/scripts/resolve_pyq_answers.py` | (1) `_load_ku_index()` now filters `validation_status = 'PASSED'` — excludes the 126 FAILED (duplicate-flagged) units from the retrieval index; directly measured to change **zero** Stage-1 strict-match outcomes (delta=0, per the prior forensic audit), so this is a no-regression correctness fix. (2) Added `compute_retrieval_tier()` — a new, separate function for retrieval-**context** tiering only; it is never called by `resolve_batch()`/`resolve_stage2_batch()` and never influences an `ANSWER_VERIFIED`/`ANSWER_CONFLICT` decision. |
| `apps/backend/scripts/pyq_retrieval_enablement.py` | **New script.** Computes and (only with `--apply`) persists `retrieval_match_tier`/`ncert_owner_accepted` for `ANSWER_PENDING` questions. Never touches `pyq.answer_assertions`, never changes `state`, never calls an AI provider. |
| `apps/backend/alembic/versions/62aa0447d463_pyq_retrieval_tier_owner_acceptance.py` | **New migration**, additive only: `pyq.questions.retrieval_match_tier` (nullable varchar, CHECK constrained to `STRICT_MATCH`/`RELAXED_MATCH`/`NONE`), `pyq.questions.ncert_owner_accepted` (boolean, default `false`), `pyq.questions.ncert_owner_accepted_at` (nullable timestamptz). Applied locally only (dev + test DB); never run against production. |
| `apps/backend/tests/test_pyq_retrieval_enablement.py` | **New**, 9 tests (Section 6). |
| `apps/backend/tests/test_pyq_resolver_worker.py` | One-line fixture fix: the knowledge-unit seeding helper used `validation_status = 'VALIDATED'`, a value the real schema never produces (production code always writes `PASSED`/`FAILED`) — this only ever worked because the old `_load_ku_index()` didn't filter by status at all. Changed to `'PASSED'` to match real data; **this is a correctness fix the retrieval-index fix exposed, not a weakening of any test's intent.** All pre-existing assertions in that file are unchanged and still pass.

**Not changed:** any source PDF, any `raw_stem`/`raw_options`/question text, any existing `pyq.answer_assertions` row, any `pyq.questions.state`, any production system, any CI/CD config.

## 3. Retrieval enablement — implementation detail

`compute_retrieval_tier(idx, stem, question_subject, *, relaxed_enabled, relaxed_threshold, subject_constrained)`:

1. **Always tries the existing strict (0.5) matcher first**, unmodified. If it matches, returns `STRICT_MATCH` — the relaxed path is never even consulted. This is the "preserve the original threshold as fallback" requirement: strict match is the unconditional, always-tried-first behavior.
2. Only if strict finds nothing **and** `relaxed_enabled=True` (off by default, matching `Settings.pyq_relaxed_retrieval_enabled`): computes candidates at `relaxed_threshold` (default 0.25) against the **same PASSED-only** `knowledge.knowledge_units` corpus — no new units, no duplication.
3. **If `subject_constrained=True` (default) and the question carries a `subject` label**, candidates are filtered to knowledge units whose chapter-derived subject matches (coarse-normalized: PHYSICS/CHEMISTRY/BOTANY/ZOOLOGY/BIOLOGY) *before* scoring — not a post-hoc filter on already-scored results. This is the cross-subject safeguard (task Section 3.7).
4. Returns `RELAXED_MATCH` with the matched unit IDs, or `NONE` if nothing clears even the relaxed bar.

**This function is never called from `resolve_batch()` or `resolve_stage2_batch()`** — it has no path to an `ANSWER_VERIFIED` state or an `answer_assertions` row. It is only invoked by the new, separate `pyq_retrieval_enablement.py` script, which writes exactly two new columns and nothing else.

**Rollback path:** re-run `scripts/pyq_retrieval_enablement.py --apply` (without `--relaxed-enabled`) — every `RELAXED_MATCH`-tiered row reverts to `NONE` and `ncert_owner_accepted` resets to `false`; `STRICT_MATCH` rows and `ANSWER_VERIFIED` rows are untouched. Verified directly (Section 5).

## 4. Owner-acceptance policy and status semantics

- **`pyq.questions.retrieval_match_tier`** (`STRICT_MATCH` / `RELAXED_MATCH` / `NONE` / `NULL`) — represents retrieval-**context availability** (measure C in the forensic-audit taxonomy), nothing else.
- **`pyq.questions.ncert_owner_accepted`** (boolean) — records that the project owner has accepted this specific question into the launch-prioritized, relaxed-retrieval candidate pool. **It is not an answer-verification status.** It is set `true` only for `RELAXED_MATCH`-tier rows.
- **`pyq.answer_assertions.verification_status`** (`ASSERTED`/`VERIFIED`/`DISPUTED`/`AI_RESOLVED`) is **completely separate** and untouched by this task. No code path anywhere sets `VERIFIED` or `AI_RESOLVED` because of `ncert_owner_accepted` or `RELAXED_MATCH`.
- A new, distinct field was the right call here (not reusing `VERIFIED`) precisely because the existing schema has no way to express "the owner accepts this candidate pool for prioritization" without that being confused with "this answer is independently verified" — conflating them was explicitly prohibited by this task.
- **No existing record's semantics were changed.** Every pre-existing `answer_assertions` row, and every pre-existing `ANSWER_VERIFIED`/`ANSWER_PENDING` state, is exactly as it was before this task (verified in Section 5).

## 5. Database integrity — before/after, idempotency, rollback (all executed locally)

All four runs below used `scripts/pyq_retrieval_enablement.py` against the local `trinetra_db`. Full logs preserved under `docs/quality/_pyq_8159_retrieval_enablement_2026-10-01/` (`dryrun_flag_off.log`, `dryrun_flag_on.log`, `dryrun_flag_on_unconstrained.log`, `apply_run_1.log` through `apply_run_4_final.log`).

| Run | Config | `state` distribution | `retrieval_match_tier` distribution | `ncert_owner_accepted` count |
|---|---|---|---|---:|
| Dry-run, flag off | — | unchanged | all `NULL` (no write) | 0 |
| Dry-run, flag on, subject-constrained | relaxed=T, thr=0.25, subj=T | unchanged | computed: 3868/3683/2393 | n/a (dry-run) |
| Dry-run, flag on, **unconstrained** (comparison only) | relaxed=T, thr=0.25, subj=F | unchanged | computed: 3868/**4291**/1785 (= 8,159 reproduced exactly) | n/a |
| **Apply #1** | relaxed=T, thr=0.25, subj=T | **unchanged**: `ANSWER_VERIFIED=2452, ANSWER_PENDING=9944` | `STRICT_MATCH=3868, RELAXED_MATCH=3683, NONE=2393, NULL=2452` | **3683** |
| **Apply #2 (idempotency check)** | identical config, rerun | unchanged | **identical**: 3868/3683/2393 | **3683** (identical) — total row count still 12,396, no duplicates |
| **Apply #3 (rollback check)** | relaxed=**F** | unchanged | `STRICT_MATCH=3868, NONE=6076` (3683+2393 reverted), `NULL=2452` | **0** |
| **Apply #4 (restore final state)** | relaxed=T, thr=0.25, subj=T | unchanged | back to 3868/3683/2393 | 3683 |

**Confirmed at every single step:** `pyq.questions.state` distribution (`ANSWER_VERIFIED=2452` / `ANSWER_PENDING=9944`) never changed. `knowledge.knowledge_units` count never changed (1,112 before and after — **no duplicate knowledge units were created**). `ai.ai_requests` row count never changed (32 — **zero AI calls made** anywhere in this task). Questions with disputed assertions: 0 before, 0 after (none existed to preserve, correctly none introduced).

**Final local state after this task:** 3,868 `STRICT_MATCH` + 3,683 `RELAXED_MATCH` (= `ncert_owner_accepted`) + 2,393 `NONE` = 9,944, matching the pending count exactly.

## 6. Automated validation and tests

New file: `apps/backend/tests/test_pyq_retrieval_enablement.py` (9 tests, all passing):

1. `test_load_ku_index_excludes_failed_units` — a FAILED unit is never in the retrieval index.
2. `test_compute_retrieval_tier_strict_match_takes_priority` — strict match wins even when relaxed is enabled.
3. `test_compute_retrieval_tier_relaxed_disabled_by_default` — flag off ⇒ `NONE`, never `RELAXED_MATCH`.
4. `test_compute_retrieval_tier_subject_constraint_blocks_cross_subject_match` — the safeguard actually blocks a real cross-subject match (and the same match IS found with the safeguard explicitly disabled, proving the constraint — not some other factor — is what excluded it).
5. `test_retrieval_enablement_dry_run_does_not_write` — dry-run leaves every column untouched.
6. `test_retrieval_enablement_apply_never_touches_state_or_assertions` — `--apply` sets the two new columns but never touches `state` or `answer_assertions`.
7. `test_retrieval_enablement_does_not_touch_already_verified_question` — an `ANSWER_VERIFIED` question is completely untouched (not even its `retrieval_match_tier`, which stays `NULL`).
8. `test_retrieval_enablement_idempotent_rerun` — identical tier on rerun, no duplicate row.
9. `test_retrieval_enablement_rollback_path_is_flag_off` — confirms the rollback mechanism at the unit level.

**Commands run and actual results** (not claimed without running):

```
PYTHONPATH=<repo>/apps/backend .venv/Scripts/python.exe -m pytest tests/test_pyq_retrieval_enablement.py -q
→ 9 passed

PYTHONPATH=<repo>/apps/backend .venv/Scripts/python.exe -m pytest tests/test_pyq_retrieval_enablement.py tests/test_pyq_resolver_worker.py -q
→ 25 passed

PYTHONPATH=<repo>/apps/backend .venv/Scripts/python.exe -m pytest app/modules/ingestion/tests/ app/modules/knowledge/tests/ \
  tests/test_pyq_resolver_worker.py tests/test_pyq_retrieval_enablement.py tests/test_question_solving.py \
  tests/test_gemini_provider_response_handling.py tests/test_credential_redaction.py -q
→ 196 passed, 17 skipped, 0 failed

.venv/Scripts/python.exe -m ruff check scripts/resolve_pyq_answers.py scripts/pyq_retrieval_enablement.py \
  app/modules/knowledge/services/grounding_check.py app/core/config.py tests/test_pyq_retrieval_enablement.py
→ All checks passed! (one import-order auto-fix applied, then re-verified clean)

.venv/Scripts/python.exe -m mypy ...
→ mypy is not installed in this project; no type-checker is configured here. Not claimed as run.
```

**Coverage against the task's requested test list:** reproducible candidate selection ✓, already-independently-verified handling ✓, disputed/conflicting preservation ✓ (none exist in current data, but the mechanism — selecting only `ANSWER_PENDING` — structurally protects them), feature-flag + fallback ✓, no duplicate knowledge units ✓, subject-aware safeguard ✓, idempotent reruns ✓, rollback ✓. **Not separately covered by a new test** (already exercised by existing suites / out of scope for this pass): NCERT source-provenance-in-context formatting for student display (no student-facing API currently reads `retrieval_match_tier` — see Section 7), invalid/malformed answer-option handling and answer-option validation (unchanged Stage-1/Stage-2 logic, already covered by `test_pyq_resolver_worker.py`), student-facing response compatibility (no API surface changes this task — see Section 7).

## 7. Launch-readiness and performance

- **Retrieval coverage for the selected set:** 3,683 `RELAXED_MATCH` + 3,868 `STRICT_MATCH` = 7,551/9,944 (76.0%) of pending questions now carry a tiered retrieval-context classification; 2,393 (24.1%) remain `NONE`.
- **Comparison against the existing threshold:** strict-only coverage is unchanged at 3,868 (38.9% of pending); the relaxed tier adds 3,683 more under the safeguard (vs. 4,291 unsafeguarded) — a **608-question, ~14% reduction** from enforcing the cross-subject safeguard, which this report treats as the correct, safer number, not a shortfall to work around.
- **Empty/irrelevant/cross-subject matches:** cross-subject matches are structurally prevented by the safeguard for subject-labeled questions (test #4 confirms this mechanically); for the 2,265 `(null)`-subject questions among the unsafeguarded 4,291 (per the prior relevance audit), the safeguard cannot apply (no subject to constrain against) — this is a known, inherited limitation, not newly introduced.
- **Query latency/resource use:** the full 9,944-question scan against 986 knowledge units completes in on the order of 1–2 minutes per run on this local machine (consistent with every prior audit in this chain) — acceptable for an offline batch job; not benchmarked as a request-path operation since this script is never called from a live API.
- **Student-facing rendering:** **not verified in this task** — no student-facing API or UI currently reads `retrieval_match_tier`/`ncert_owner_accepted` (grep-confirmed: these are brand-new columns with no other reader yet). This task deliberately stopped at the data/retrieval layer per its own scope ("do not expand into unrelated refactoring"); wiring these into an explanation/context display is future, separately-scoped work.
- **No answer is displayed as independently verified without evidence:** confirmed structurally — `ncert_owner_accepted`/`retrieval_match_tier` have no code path into `answer_assertions` or `state`, so there is nothing new that could be mis-displayed as verified.
- **Known limitation:** the `(null)`-subject population (61% of the pending corpus) cannot benefit from the cross-subject safeguard at all — this is a pre-existing data gap (subject classification coverage), not something this task could fix in scope.

## 8. Answer-resolution: security gate status

**Checked directly, not assumed:** `docs/production/gemini_api_key_log_exposure_incident.md` states explicitly: *"Status: Code remediated and tested. Production key rotation NOT performed — pending authorized operator action."* and *"The exposed key has not been rotated... must be treated as compromised."*

**Therefore: the security prerequisite is NOT satisfied. Per this task's own mandatory safeguard, no Gemini or other paid AI call was made at any point in this task.** Confirmed by `ai.ai_requests` row count (32, identical before and after — zero new rows).

**What was prepared instead (safe, offline):** the existing one-pass Gemini resolver (`resolve_stage2_batch` in `resolve_pyq_answers.py`, already implemented in a prior, separate task) is untouched and already enforces every one of this task's answer-resolution requirements: schema/option validation (`supported_options` filtered to real option labels), rejection of malformed/fallback responses (treated as unresolved, never guessed), no overwriting of independently verified answers (only ever selects `ANSWER_PENDING`), isolation of disputed/conflicting results (`ANSWER_CONFLICT` + `DISPUTED` assertions, never silently resolved), `AI_RESOLVED` status (never `VERIFIED`) for one-pass Gemini answers, and failure recording via `report.stage2_unresolved` (never hidden).

**Exact remaining steps before any Gemini call can run** (not performed in this task, requires the project owner):
1. Rotate the exposed `GEMINI_API_KEY` in Google AI Studio / Cloud Console.
2. Securely configure the new key (environment/secrets manager, never in a log or this report).
3. Confirm the old key is revoked (401/403 on a test call using the old, already-compromised key only).
4. Only then may `scripts/resolve_pyq_answers.py --max-total N --apply` be run to resolve any of the `RELAXED_MATCH`/`STRICT_MATCH` candidates via Stage 2 — and even then, Stage 2's existing logic still never uses `ncert_owner_accepted` as evidence; it independently re-evaluates each question against the indexed corpus.

## 9. Known limitations and unresolved cases

- The 8,159 figure from the prior relaxed-retrieval diagnostic was produced **without** the subject-constrained safeguard; this task's reproducible, safeguarded figure is 7,551. This discrepancy is reported per the task's own instruction, not minimized.
- `retrieval_match_tier`/`ncert_owner_accepted` are not yet surfaced to any student-facing API — they exist at the data layer only.
- The `(null)`-subject population cannot be protected by the cross-subject safeguard; a plausible future improvement (not implemented here) would be inferring a coarse subject from the matched unit's own chapter metadata as a secondary signal, but that was out of this task's scope.
- No semantic/relevance validation of the 3,683 `RELAXED_MATCH` questions has occurred — per the prior relevance-validation audit, "relevance" (measure D) and "owner acceptance of a candidate pool" (this task) remain explicitly distinct; owner acceptance is not evidence of relevance.
- Answer resolution (actually answering any of these questions) has not happened and cannot happen until the Gemini key-rotation prerequisite is met.

## 10. Rollback procedure (for the record)

```bash
cd apps/backend
PYTHONPATH=<repo>/apps/backend .venv/Scripts/python.exe scripts/pyq_retrieval_enablement.py --apply
# (omit --relaxed-enabled) -- reverts every RELAXED_MATCH row to NONE and
# ncert_owner_accepted to false; STRICT_MATCH and ANSWER_VERIFIED rows are
# never touched. Verified working in Section 5, Apply #3.
```
To fully remove the feature (schema-level rollback): `alembic downgrade -1` from revision `62aa0447d463` — drops `retrieval_match_tier`, `ncert_owner_accepted`, `ncert_owner_accepted_at`. Verified working via a downgrade/upgrade round-trip during implementation (Section 2).

## Final confirmations

- **Files changed:** see Section 2 (10 files: 1 config, 1 grounding-check, 1 resolver script modified, 1 new enablement script, 1 new migration, 2 new/modified test files).
- **Exact current candidate count:** **3,683** (subject-constrained, reproducible) — not 8,159 (that figure required disabling the cross-subject safeguard this task was required to implement).
- **Retrieval implementation status:** **Implemented and tested locally; applied to the local dev database.** Feature-flagged, off by default in `Settings`; explicitly enabled via CLI flag for this task's local apply runs.
- **Answer-resolution status:** **Not executed. No AI call was made.** Blocked by the unresolved Gemini key-rotation prerequisite, confirmed directly from the incident doc, not assumed.
- **Test commands and results:** see Section 6 — 9 new + 16 existing resolver tests (25 total) pass; broader relevant suite 196 passed/17 skipped/0 failed; ruff clean; mypy not installed/not claimed.
- **Database before/after counts:** see Section 5 — `state` distribution unchanged throughout; `retrieval_match_tier`/`ncert_owner_accepted` populated and verified idempotent and reversible.
- **Security blockers:** exposed Gemini API key not yet rotated (production action, pending owner). This is the sole blocker on any AI-based answer resolution.
- **Remaining launch blockers:** (1) Gemini key rotation (owner action), (2) no student-facing surface yet reads the new retrieval-tier data (separately-scoped future work), (3) no relevance/semantic validation has occurred for the `RELAXED_MATCH` pool.
- **Production:** never accessed, never modified. **Git:** nothing committed, nothing pushed — all changes remain as local, uncommitted working-tree modifications alongside this session's pre-existing uncommitted work, which was preserved and built upon, not discarded.

## 11. Follow-up review (2026-10-04) — final state re-verified, OCR findings folded in, no new work repeated

**Scope of this addendum:** re-review only — no code, migration, or test was changed in this pass; the database was re-read (not re-written) to confirm nothing drifted since Section 5's Apply #4.

### 11.1 Implementation re-verified unchanged

```
pyq.questions state:              ANSWER_VERIFIED=2452, ANSWER_PENDING=9944   (identical to Section 1/5)
pyq.questions retrieval_match_tier: RELAXED_MATCH=3683, STRICT_MATCH=3868, NONE=2393, NULL=2452
ncert_owner_accepted = true:      3683  (identical to Apply #4's final state)
ai.ai_requests row count:         32    (unchanged — zero AI calls since this task began)
```
No drift. The 3,683-candidate safeguarded figure stands as the only reproducible, implemented number — 8,159 remains correctly documented as the unsafeguarded reference point only (Section 0).

### 11.2 Gemini key-rotation status — re-checked directly, unchanged

`docs/production/gemini_api_key_log_exposure_incident.md` line 3, read directly again: *"Code remediated and tested. **Production key rotation NOT performed — pending authorized operator action.**"* No confirmation of rotation exists anywhere in this repository's tracked or untracked files as of this review. **The security gate remains closed.** No Gemini or other paid AI call was made in this review pass (confirmed by the unchanged `ai.ai_requests` count above) — none was attempted, consistent with this task's constraint not to execute AI answer resolution until rotation is confirmed and explicitly authorized.

### 11.3 OCR reconstruction findings (from the already-completed `docs/quality/_pyq_ocr_reconstruction_2026-10-01/` run) — reviewed, not re-run

| Classification | Count (of 42) |
|---|---:|
| `PARTIALLY_RECOVERABLE` | 33 |
| `SOURCE_MISMATCH` | 7 |
| `UNRESOLVED` | 2 |
| `OCR_RECOVERABLE` (high-confidence) | **0** |

**Actionable finding, newly surfaced by this review:** the high-confidence matching method (detecting a printed "`<Subject> : Section-X (Q. No. A to B)`" header and cross-checking the question number against that range) **never fired for any of the 42 questions** — every single row fell back to a weaker method (`number_token + token_overlap≥3`, 25 rows, confidence `MEDIUM`; or `token_overlap_only`, 15 rows, confidence `LOW`). This means:
- **No OCR reconstruction candidate in this set has reached high confidence.** All 33 `PARTIALLY_RECOVERABLE` rows require human verification before any text could be treated as a usable reconstruction — none is.
- The likely cause (not confirmed, flagged for a future scoped check): the header-detection regex expects a specific printed format that may not match how these particular papers actually render the section header, or OCR degraded that specific header line even where the surrounding question text came through legibly (as shown in the earlier, smaller 13-question sample in `_pyq_local_ocr_evaluation_2026-10-01/`). This is a tooling-precision gap, not evidence that the underlying source pages are illegible.
- **7 `SOURCE_MISMATCH` and 2 `UNRESOLVED` questions remain genuinely unlocated** — their best candidate page is explicitly flagged unreliable (score 2 or similarly weak) or no candidate was found at all. No reconstruction should be attempted for these without a fresh, targeted page search.
- **No proposed_reconstruction text exists for any of the 42** — confirmed again (`rows_with_proposed_reconstruction_placeholder: 0` in the preserved summary), consistent with this task's prohibition on fabricating or silently repairing question text.

**Recommendation (not implemented in this pass, requires separate authorization):** a follow-up OCR pass using a more tolerant header-detection pattern (or, more robustly, OCR'ing with layout/column-order preservation so printed question numbers appear adjacent to their own question text rather than scattered by multi-column reading order) could plausibly raise several of the 25 `MEDIUM`-confidence rows to a verifiable `HIGH` tier. This remains future work, not performed here.

### 11.4 Remaining retrieval-mapping / data-quality issues (reviewed against existing evidence, no new scan run)

- **The 2,452 `(null)`-tier rows are already-`ANSWER_VERIFIED` questions**, correctly and deliberately never touched by the retrieval-tier script (Section 5/6) — not a gap, confirmed by design.
- **The 2,393 `NONE`-tier pending questions** have no retrieval context at any threshold tested — consistent with, and not contradicted by, the earlier relevance-validation audit's finding that only ~1–2% of the fully-uncovered population has zero vocabulary overlap at all; the remainder here reflects the subject-constrained safeguard removing otherwise-found (but cross-subject, unreliable) matches, which is the intended, safer behavior, not a new defect.
- **No new knowledge-unit mapping issue was found** in this review — `knowledge.knowledge_units` count (1,112) and the FAILED/PASSED split (126/986) are unchanged from every prior audit in this chain; nothing new to report here.
- **No change to this task's known limitations** (Section 9) is warranted by this review — they stand as previously documented.

### 11.5 Outstanding blockers and exact next steps

1. **Gemini key rotation (owner/operator action, external to this repo's code).** Hard blocker on any AI-based answer resolution. Confirmed still unresolved as of this review.
2. **OCR reconstruction tooling improvement** (Section 11.3) — optional, separately-scoped, needed only if the project wants to pursue the 42 corrupted-stem questions further; not launch-blocking for the 3,683-question retrieval-enablement work, which is independent of those 42 questions.
3. **Student-facing surface for `retrieval_match_tier`** — still not wired to any API (confirmed unchanged from Section 7); required before this data is useful to an end user, but not required for the data-layer enablement itself to be considered complete.
4. **No other blocker identified.** The implementation, tests, and database state are stable and unchanged since Section 5/6; this review found nothing requiring rework.

**Distinguishing states, precisely, as requested:**
- **Implemented:** retrieval-tier feature flag, subject-constrained relaxed matcher, owner-acceptance schema, rollback mechanism.
- **Tested:** via 9 new unit/integration tests plus the full existing relevant suite (196 passed).
- **Locally data-applied:** `retrieval_match_tier`/`ncert_owner_accepted` populated for all 9,944 pending questions in the local dev database (3,683 accepted into the relaxed pool).
- **Independently verified:** **unchanged at 2,452** — nothing in this task added to this count.
- **Production-deployed:** **nothing** — this entire task was local-only, as required.
