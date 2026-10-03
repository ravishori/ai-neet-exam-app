# PYQ One-Pass Gemini Answer Resolution — Implementation & Pilot Report

**Date:** 2026-10-01
**Repository:** `ravishori/ai-neet-exam-app`
**Branch:** `feat/whatsapp-m2a-account-linking`
**Commit at start of this work:** `94e3206ca72dc034b618745159a4edf53899b23f`

## Executive summary

Implementation is complete and tested. **The pilot ran safely but resolved zero questions and spent $0**, because the local development database's `knowledge.knowledge_units` table — the NCERT-evidence corpus the existing resolver (both the free deterministic Stage 1 and the paid Gemini Stage 2) retrieves context from — is **completely empty** (0 rows). This is a genuine environment/data blocker discovered by the pilot doing exactly its job, not a bug: the resolver's own safety design correctly refuses to call Gemini when there is no retrieved evidence to reason over, rather than ever guessing. **Phase D (full batch processing) cannot proceed** until this is resolved by the project owner — see [Blocker](#blocker-requires-owner-decision) below. No Gemini API cost was incurred; no PYQ data was modified; production was never touched.

## 1. Repository inspection (Phase A)

| Searched item | Found |
|---|---|
| `apps/backend/scripts/resolve_pyq_answers.py` | **Already implements** a two-stage resolver: Stage 1 (deterministic, free, mechanical word-overlap grounding against `knowledge.knowledge_units`) and Stage 2 (a genuine one-pass Gemini call, via the centralized `AIGateway`/`GeminiProvider`, over whatever Stage 1 leaves pending within the same bounded batch). Stage 2 already matches almost everything the task requested: single call per question, structured JSON output, bounded evidence (`EVIDENCE_UNIT_CAP=8` knowledge units), never retries indefinitely, never guesses (empty/unparseable/fallback responses are always treated as unresolved), idempotent (`ON CONFLICT ... DO NOTHING`), resumable (cursor-paginated by `created_at, id`). |
| `GEMINI_API_KEY` / `GEMINI_MODEL` / `GEMINI_ENABLED` | Present in `apps/backend/.env`: `GEMINI_ENABLED=true`, `GEMINI_MODEL=gemini-3.6-flash` (key value never printed in this report). Code default in `app/core/config.py` is `gemini-2.0-flash`, but the actual configured/active model (and the one Stage 2 already uses via `settings.gemini_model`) is `gemini-3.6-flash`. |
| `AIGateway` | `app/modules/ai/gateway/ai_gateway.py` — the single centralized entrypoint; Stage 2 already uses it correctly (`_stage2_default_gateway()` injects a `GeminiProvider` instance directly, bypassing the multi-provider router by design, so the unrelated `FACTORY_PROVIDER` setting is never touched). |
| `PYQ_ANSWER_RESOLVER` | The `agent_type` tag Stage 2 already logs under — this is how its cost/token usage is distinguishable in `ai.ai_requests` from every other AI feature in the app. |
| `resolve_pyq_answers` | The script itself; see above. |
| `answer_assertion` | `pyq.answer_assertions` — see schema section below. |
| `evidence_note` | Free-text column already used by both stages for provenance (NCERT book/page citations for Stage 1, knowledge-unit IDs + model name + reasoning for Stage 2). |
| `qa_reviews` / `duplicate_candidates` | Both exist, both empty (0 rows) — confirmed in the 2026-10-01 baseline audit; untouched by this task. |

**Existing config/mechanisms reused as-is, not reimplemented:** `AIGateway`, `GeminiProvider`, `app/modules/ai/prompts/pyq_resolver.py` (system prompt + user-prompt builder), `pyq.answer_assertions` table, cost/token logging into `ai.ai_requests` (via `AIGateway._log()`), the existing bounded-retry/error-classification logic in `app/modules/ai/gateway/errors.py`, rate-limit infrastructure already used elsewhere in the app.

**No parallel Gemini client, duplicate configuration, or parallel resolution pipeline was introduced.**

## 2. Database target and safety (Phase A/B)

Freshly re-confirmed (not relying on historical figures) immediately before any change:

```
ENVIRONMENT=development
current_database = trinetra_db, server_addr = ::1 (localhost), pg_version = 18.6
pyq.questions: total=12396, verified=2452, pending=9944
```

Identical to the 2026-10-01 baseline (`docs/quality/pyq-coverage-audit.md`) — zero drift. **Confirmed local development, not production.**

### Environment finding (unrelated to PYQ, fixed as a prerequisite)

The local database's `alembic_version` was stamped `b3f9c299033e` — a revision ID that does not exist in any file under `alembic/versions/` in this repository. Direct schema inspection showed the actual schema matched exactly what migration `a3f7c8d1e2b4` (the last PYQ migration) produces, with no `whatsapp` schema at all. This is a bookkeeping mismatch, not real data drift — likely an orphaned stamp from a deleted/renamed local migration file. Fixed via `alembic stamp --purge a3f7c8d1e2b4` (realigning the recorded version to match the schema's actual, verified state) followed by `alembic upgrade head`, which applied the two already-reviewed, already-merged WhatsApp M1/M2A migrations (PR #81, merged earlier this session) plus the new migration below. **No PYQ table, column, or row was affected by this fix** — confirmed by re-querying the same three counts immediately after (unchanged: 12396/2452/9944).

## 3. Schema change (Phase B) — `AI_RESOLVED` verification status

**Finding:** the existing Stage 2 resolver already writes `verification_status='VERIFIED'` for a single-option Gemini answer — the *same* value Stage 1's independent, deterministic NCERT-grounding check uses. This conflates exactly the distinction the task's policy requires ("must not be represented as independently NCERT-verified"). Nothing in the schema previously allowed telling the two apart except free-text `resolver_version`/`assertion_source` prefixes.

**Migration added:** `alembic/versions/d9c6e1a8f9ed_pyq_ai_resolved_verification_status.py` — additive-only, adds `'AI_RESOLVED'` to the `ck_pyq_answer_assertions_status` CHECK constraint on `pyq.answer_assertions.verification_status` (now `ASSERTED | VERIFIED | DISPUTED | AI_RESOLVED`). Applied to both `trinetra_db` (local dev) and `trinetra_test_db` (test fixtures). **`pyq.questions.state` was deliberately left unchanged** — it still uses the existing `ANSWER_VERIFIED` value to mean "has a final answer, no longer pending" for both deterministic and AI-resolved cases, since that state value drives other parts of the app and the task asked to preserve existing verified-answer statuses, not redefine them. The AI-vs-deterministic distinction lives at the `answer_assertions.verification_status` row level, which is the field that actually carries per-answer provenance.

**Code change:** `scripts/resolve_pyq_answers.py`, `resolve_stage2_batch()` now writes `'AI_RESOLVED'` instead of `'VERIFIED'` for its single-supported-option case. The multi-option (`DISPUTED`) path is unchanged. A `run_id` parameter was added and threaded through to `resolve_up_to()` / the CLI, embedded into `evidence_note` as `run=<id>; ...` for per-run provenance without needing a new column.

**CLI change:** `scripts/resolve_pyq_answers.py main()` gained `--max-total N` (bounds the run and enables Stage 2, for pilot/batch runs) and `--run-id` (defaults to a UTC timestamp). The pre-existing unbounded `--apply` (Stage-1-only, free, no LLM) behavior is unchanged when `--max-total` is omitted.

## 4. Student question-quality feedback (Section 7)

**Existing mechanism found and reused, not reimplemented:** `POST /api/v1/cms/questions/{id}/report` (`app/modules/cms/api/cms_router.py`), backed by `cms.content_reports` (`ContentReport` model) — already supports authenticated + CSRF-protected submission of `{reason, comment}`, records `reported_by`, `content_version_id` (the answer/content version at report time), `created_at`, and `status` (`OPEN`/`RESOLVED`/`DISMISSED` — the model's own docstring already notes "no admin UI exists yet to change this from OPEN," an existing, previously-documented limitation, not introduced here).

**Extension made:** `REPORT_REASONS` in `cms_router.py` extended from `{WRONG_ANSWER, UNCLEAR, TYPO, OFFENSIVE, OTHER}` to also include `WRONG_EXPLANATION`, `BAD_OPTIONS`, `MISSING_INFO` — covering all six categories the task requested, as a plain Python set (the `reason` column is `VARCHAR(30)` with app-level validation only, so **no migration was needed** for this change).

**Important limitation, confirmed not inferred:** this endpoint operates on `cms.content_items` (published, student-facing content), not `pyq.questions` directly. Per the 2026-10-01 baseline audit, **zero PYQ questions have ever been promoted to `cms.content_items`** (`pyq.promotion_log` is empty, `state='PROMOTED'` count is 0) — PYQ-sourced questions are not yet visible to students anywhere in the product. The feedback mechanism is therefore ready and will work correctly the moment any PYQ question is promoted, but there is currently nothing PYQ-specific for a student to report against. Building a separate, PYQ-specific, pre-promotion reporting path was judged out of scope (it would mean exposing unpublished/unreviewed PYQ content to students directly, which this task's instructions never asked for and which would itself need separate product sign-off).

## 5. Small pilot (Phase C)

**Command:**
```
.venv/Scripts/python.exe -m scripts.resolve_pyq_answers --apply --max-total 15 --run-id "pilot-2026-10-01"
```

**Result:**
```json
{
  "total_scanned": 15,
  "answered": 0,
  "unresolved_no_source_match": 15,
  "unresolved_no_option_grounded": 0,
  "conflicts": 0,
  "assertions_inserted": 0,
  "stage2_answered": 0,
  "stage2_conflicts": 0,
  "stage2_unresolved": 15
}
```

**All 15 questions were left `ANSWER_PENDING`, exactly as designed, because of the blocker below — not because of a bug.** Confirmed by direct query immediately after: `pyq.questions` counts unchanged (12396/12396 total, 2452/2452 verified, 9944/9944 pending), `pyq.answer_assertions` count unchanged (2452/2452), and `ai.ai_requests` shows **zero** rows logged for `agent_type='PYQ_ANSWER_RESOLVER'` in the preceding 10 minutes — i.e. **Gemini was never actually called**, confirmed from the cost-tracking table itself, not inferred from the script's own report.

### Blocker (requires owner decision)

`knowledge.knowledge_units` — the table both Stage 1's free matching *and* Stage 2's NCERT-evidence retrieval depend on — has **0 rows** in this local development database (`SELECT count(*) FROM knowledge.knowledge_units` → 0, confirmed with and without the `deleted_at IS NULL` filter). Stage 2's own documented safety invariant ("a question with literally zero shared vocabulary with the corpus never reaches the model at all... there is nothing to synthesize from... never asked to guess") correctly refuses to call Gemini when there is no evidence to retrieve — this is working exactly as designed, but it means **the existing resolver cannot resolve anything at all in this database's current state**, pilot or full batch, regardless of how many pending questions exist.

Per this task's own Section 6 pause conditions ("Pause processing if... database consistency or transaction safety is at risk") and Section 11 ("Do not fabricate... source references... Do not invent answers when Gemini fails"), this was treated as a hard stop rather than something to improvise around. Two real options exist, and **this report does not choose between them** — that is the project owner's decision:

1. **Populate `knowledge.knowledge_units` first** (via whatever existing Content Factory / NCERT-ingestion pipeline normally fills it — not investigated further here, out of this task's scope) and then re-run the pilot.
2. **Explicitly authorize a different one-pass design** that sends the question directly to Gemini with no NCERT-evidence grounding step at all — this would be a genuine, material change to the resolver's safety/quality model (no retrieval-grounding safety rail, relying entirely on Gemini's own knowledge), not a small tweak, and should not be decided unilaterally here.

## 6. Tests run (Phase 9)

All tests mock external Gemini calls (`_FakeAIGateway` — no paid API credits consumed by the test suite).

```
.venv/Scripts/python.exe -m pytest tests/test_pyq_resolver_worker.py tests/test_question_solving.py -v
28 passed, 5 warnings in 74.56s
```

Includes 2 new tests added this task (`test_stage2_run_id_recorded_in_evidence_note`, `test_stage2_conflict_assertions_remain_disputed_not_ai_resolved`), 1 existing test strengthened with a new assertion it previously lacked (`test_stage2_semantic_synthesis_verifies_despite_wording_difference` — now explicitly asserts `verification_status == "AI_RESOLVED"`, which would have caught the VERIFIED/AI_RESOLVED conflation bug immediately if it had existed before), and 3 new parametrized tests for the extended feedback reasons (`test_report_question_accepts_extended_quality_reasons[WRONG_EXPLANATION|BAD_OPTIONS|MISSING_INFO]`).

**Pre-existing failures observed during the broader session (not caused by this task):** `test_prod_5k_run_002_dry_run.py` (2 tests, data/fixture-dependent), `test_identity_state_city.py`/`test_locations_api.py` (seed-data dependent), `test_python_mcq_engine_010.py` (3 tests, NCERT-evidence-matching issue) — all previously bisected and confirmed pre-existing in an earlier task this session; not re-touched here and not part of this task's scope.

Lint: `ruff check` on all 5 modified/added files (`scripts/resolve_pyq_answers.py`, `app/modules/cms/api/cms_router.py`, `tests/test_pyq_resolver_worker.py`, `tests/test_question_solving.py`, the new migration) — **clean**.

Type check (`mypy`): not installed in this environment's `.venv` — reported as not run, consistent with every prior task this session.

## 7. Counts

| Metric | Value |
|---|---:|
| Initial total PYQ | 12,396 |
| Initial verified | 2,452 |
| Initial pending (eligible pool) | 9,944 |
| Excluded by business rule | 0 (none identified beyond "not already verified," which the resolver's own `WHERE state='ANSWER_PENDING'` already enforces) |
| Processed this run (pilot bound) | 15 |
| Finalized as `AI_RESOLVED` | **0** |
| Still pending after pilot | 9,944 (unchanged) |
| Failed technically (malformed/unparseable response) | 0 — Gemini was never invoked |
| Flagged ambiguous/conflict | 0 |
| Gemini tokens used | 0 |
| Gemini cost incurred | **$0.00** (confirmed via `ai.ai_requests`, not estimated) |
| Student feedback reports created during this run | 0 (no PYQ content is promoted/student-visible yet; see Section 4) |

**No cost estimate for the remaining ~9,944 questions is given**, because the pilot could not produce a real per-question token/cost sample — any number here would be an unlabeled guess, which this task's own instructions prohibit ("Produce a cost estimate... using actual model pricing only if verified"). Once the knowledge_units blocker is resolved, a fresh small pilot will produce a real, evidence-based estimate before Phase D proceeds.

## 8. Known limitations

- Cannot estimate full-batch cost or timeline until the `knowledge_units` blocker is resolved (Section 5).
- Student feedback categories are ready but not currently exercisable against any PYQ-derived content, since none is promoted (Section 4).
- `pyq.questions.state` does not distinguish AI-resolved from deterministically-verified at the question level, only `answer_assertions.verification_status` does (a deliberate, documented design choice — Section 3).
- The pre-existing `ContentReport.status` admin-review workflow gap (no admin UI to triage reports) remains open — not newly introduced, not addressed here, already documented in the model's own pre-existing docstring.

## 9. Production confirmation

**Production was never connected to, queried, or modified.** All work in this task — the migration, the code changes, the pilot run — targeted exclusively `trinetra_db` (local dev, port 5432, `localhost`) and `trinetra_test_db` (test fixtures, same host). No Railway deployment, environment variable, secret, or configuration was touched. No commit or push was made.

---

## Related audit update

`docs/quality/pyq-coverage-audit.md` has been updated with a dated pointer to this report (see its Audit History table) — the original baseline and all prior history remain unchanged.
