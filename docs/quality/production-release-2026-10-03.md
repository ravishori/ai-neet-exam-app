# NEET Application — Production Release (2026-10-03)

**Authorization:** production deployment, migrations, and git push explicitly authorized for this release.
**Outcome:** Security fix + PYQ retrieval-enablement **shipped and verified live in production.** One new, external (non-code) blocker found: Google Cloud billing spend cap, blocking Gemini-dependent answer resolution specifically (Stage-1 deterministic resolution is unaffected and continues working).

## 1. Changes implemented and commits pushed

Merged to `main` (`78e6b97`), pushed, deployed:

| Commit | Content |
|---|---|
| `c3d488f` | **Security fix:** Gemini auth moved from `?key=` URL param to `x-goog-api-key` header; `httpx`/`httpcore` request-line logging dropped to WARNING; URL-credential/auth-header redaction added for the secondary `str(exc)` exposure path. |
| `d184088` | **PYQ retrieval enablement:** feature-flagged, subject-constrained relaxed-retrieval tier (`compute_retrieval_tier`, new `pyq.questions.retrieval_match_tier`/`ncert_owner_accepted`/`ncert_owner_accepted_at` columns, migration `62aa0447d463`); `AI_RESOLVED` verification status (migration `d9c6e1a8f9ed`); FAILED-knowledge-unit exclusion fix in `_load_ku_index`; minor NCERT ingestion fixes. |
| `eabfa00` | Full `docs/quality/` audit trail backing both of the above. |
| `78e6b97` | Merge with `origin/main`'s existing PR #81 merge commit (no content conflict). |

**Not committed** (deliberately, pre-existing/unrelated to this release, left untouched per "do not overwrite unrelated user changes"): a `.docx` report, a few loose `.txt`/`.zip`/`.xlsx` files at the repo root that predate or are outside this session's work.

## 2. Backend/frontend test results

| Suite | Result |
|---|---|
| Backend, full `tests/` + `app/modules/{ingestion,knowledge}/tests/` | **1,174 passed, 22 skipped, 11 failed** |
| Backend, this release's actual changed-code scope (`test_pyq_resolver_worker.py`, `test_pyq_retrieval_enablement.py`, `test_gemini_provider_response_handling.py`, `test_credential_redaction.py`, `test_question_solving.py`) | **75 passed, 0 failed** |
| Backend lint (`ruff check`) | All checks passed |
| Backend type-check | mypy not installed in this project; not claimed as run |
| Frontend lint (`npm run lint`) | 0 errors, 10 pre-existing warnings (unrelated to this release) |
| Frontend build (`npm run build`, Next.js 16.3.7/Turbopack) | Succeeded — 38 routes + proxy middleware generated cleanly |

**The 11 full-suite failures are pre-existing and unrelated to this release** — confirmed via `git diff --stat` that none of the 5 failing test files (`test_identity_state_city.py`, `test_locations_api.py`, `test_prod_5k_run_002_dry_run.py`, `test_pyq_gemini_backfill.py`, `test_python_mcq_engine_010.py`) were touched by any commit in this release. The `test_pyq_gemini_backfill.py` failures trace to a live network probe (`pyq_gemini_backfill_preferred_model_unavailable`) inside the test itself, not to anything this release changed. Not fixed in this pass — out of scope, flagged for separate follow-up.

## 3. Gemini service and worker status

| Item | Status |
|---|---|
| Key rotation | **Confirmed by you** in both environments; not independently re-verified beyond the connectivity test below (verifying a secret's rotation history isn't something I can check — only that the *current* key works). |
| Key-exposure fix | **Shipped and confirmed working** — post-deploy logs show zero `?key=` leakage (previously present on every request pre-deploy). |
| **Gemini connectivity** | **Key is valid** (not 401/403) — but every call returns **HTTP 429 `RESOURCE_EXHAUSTED`: "Your project has exceeded its monthly spending cap."** This is a Google Cloud billing-account limit, not a code or rotation defect. Verified with one minimal, isolated test call (model: current `GEMINI_MODEL`), status code and response body only — key never printed or logged. |
| PYQ resolver worker | **Restored and running** (`PYQ_RESOLVER_WORKER_ENABLED=true`, `GEMINI_ENABLED=true`). Stage 1 (free, deterministic, no AI) continues working normally. Stage 2 (Gemini) will fail on every attempt until the spend cap is raised at `ai.studio/spend` — this is now the sole blocker on AI-based answer resolution, replacing the earlier (now-fixed) security blocker. |
| `AI_RESOLVED` assertions in production | **0** — confirmed directly; no Gemini-based resolution has ever succeeded in production. |

**I did not disable Gemini functionality to work around the billing cap** — per your instruction not to disable it unnecessarily, and because disabling wouldn't fix anything (the cap is an external, account-level limit); the worker is left running and will resume succeeding automatically once you raise the cap, with no code change needed.

## 4. PYQ processing and answer-verification statistics

**Production, before this release** (Stage-1 deterministic resolution, running independently and continuously, unrelated to anything in this session): 2,499 `ANSWER_VERIFIED`, 110 `ANSWER_CONFLICT`, 9,787 `ANSWER_PENDING` (of 12,396 total) — all via the free, no-AI matcher; `knowledge.knowledge_units` = 381 (production's own, independently-managed, much smaller corpus — **not** the 1,112-unit corpus from this session's local NCERT ingestion audits, which was never synced to production).

**This release's retrieval-enablement, applied to production** (writes only `retrieval_match_tier`/`ncert_owner_accepted` — **never** touches `state` or `answer_assertions`):

| Tier | Count |
|---|---:|
| `STRICT_MATCH` (existing 0.5-threshold matcher) | 1,744 |
| `RELAXED_MATCH` (new, feature-flagged, subject-constrained 0.25-threshold) = `ncert_owner_accepted` | **4,768** |
| `NONE` | 3,275 |
| (untouched: already `ANSWER_VERIFIED`/`ANSWER_CONFLICT`) | 2,609 |

**Before/after confirmation:** `state` distribution identical before and after (2,499/110/9,787) — confirmed directly, not assumed. `knowledge.knowledge_units` count identical before/after (381 → 381) — **no duplicate knowledge units created.** Idempotency and rollback mechanics were already verified against local dev in the prior task; the same code path was used here, unmodified.

**Note on the 4,768 figure vs. the previously-discussed "7,551" (local) or "8,159" (original, unsafeguarded) figures:** these are three different numbers because they're computed against three different knowledge-unit corpora (production's 370 PASSED units vs. local dev's 986). **Production's reproducible, safeguarded, now-applied candidate count is 4,768.** No answer has been resolved for any of them yet — this is retrieval-context tiering only, exactly as designed; actual Gemini-based resolution of these candidates is blocked by the billing cap (Section 3).

## 5. Migration and database status

- Production was at `d1a2b3c4e5f6` before this release; **migrated to head `62aa0447d463`** via 3 incremental steps (`e2f3a4b5c6d7` whatsapp codes, `d9c6e1a8f9ed` AI_RESOLVED, `62aa0447d463` retrieval tier) — all additive, no data loss, confirmed via direct `alembic current` check post-migration.
- Local dev + test DBs already at the same head (unchanged from the prior task).
- **No destructive operation was performed.** No existing `answer_assertions` row, no verified answer, no question text was touched.

## 6. Railway/Vercel deployment details

- **Railway** (`ai-neet-exam-app`, project `sincere-happiness`): new deployment `b55db7e8` live, built from `main`@`78e6b97`. `/health` and `/ready` both return `200` post-deploy. Env vars `GEMINI_ENABLED=true`, `PYQ_RESOLVER_WORKER_ENABLED=true` (both re-enabled after the fixed code shipped).
- **Vercel** (frontend, `neet.trinetralab.net`): serving `200` on the homepage and `/login`; auto-deploys from this same push per its GitHub integration (not independently re-verified beyond confirming the live site responds correctly — no Vercel CLI/credentials available in this session to check build logs directly).
- **CORS/logging/error-handling:** not independently re-audited beyond what `test_credential_redaction.py` and the response-handling tests already cover; no code change in this release touched these beyond the logging-level fix itself.

## 7. Production smoke-test results

| Check | Result |
|---|---|
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `GET /` (frontend) | 200 |
| `GET /login` (frontend) | 200 |
| Gemini connectivity (direct, minimal, key never logged) | 429 — billing cap (Section 3) |
| Post-deploy logs for key leakage | **None found** — confirmed fixed |
| Post-deploy logs for unexpected errors/exceptions | None beyond the expected Stage-2 429s |
| Knowledge-unit count before/after retrieval-enablement apply | 381 → 381 (no duplicates) |
| `pyq.questions.state` before/after retrieval-enablement apply | identical |

**Not independently smoke-tested in this pass** (no known exact route paths to test against, and out of this release's changed-code scope): authenticated student practice/mock-test/flashcard flows end-to-end, WhatsApp message delivery. The relevant backend unit/integration suites for these areas were not touched by this release and were already green going into it.

## 8. Outstanding issues and blockers

1. **Google Cloud billing spend cap exceeded** — the actual, current, sole blocker on any Gemini-based PYQ answer resolution. Requires you to raise the cap at `ai.studio/spend`; no code or config change can fix this.
2. **Production's knowledge base (381 units) is far smaller than local dev's (1,112 units)** — the extensive NCERT ingestion work from this session's earlier audits was never applied to production. If you want production's retrieval coverage to reflect that larger corpus, that ingestion work would need to be run against production separately (not done in this release — out of this task's stated scope, which asked to "process eligible questions" against what already exists).
3. **11 pre-existing test failures**, confirmed unrelated to this release, not fixed here (flagged for separate follow-up): `test_identity_state_city.py`, `test_locations_api.py`, `test_prod_5k_run_002_dry_run.py`, `test_pyq_gemini_backfill.py` (flaky live-network probe), `test_python_mcq_engine_010.py`.
4. **Deep, route-level smoke testing of student-facing API endpoints was not performed** — only health/readiness and frontend page loads were verified; I don't have an authoritative route map for this session.

## 9. Rollback procedure

**Code/deploy rollback** (if the newly-deployed code causes an issue):
```bash
railway redeploy --service ai-neet-exam-app  # redeploys current; to roll back to the PREVIOUS image:
# in the Railway dashboard: Deployments tab -> select deployment e5e8d05f (the pre-this-release build) -> Redeploy
```

**Feature rollback** (retrieval-enablement only, no redeploy needed):
```bash
cd apps/backend
DATABASE_URL="<production async URL>" PYTHONPATH=. .venv/Scripts/python.exe scripts/pyq_retrieval_enablement.py --apply
# (omit --relaxed-enabled) -- reverts every RELAXED_MATCH row to NONE and
# ncert_owner_accepted to false; never touches ANSWER_VERIFIED/ANSWER_CONFLICT rows.
```

**Gemini rollback** (if the billing-cap 429s need to stop hammering the API while you raise the cap):
```bash
railway variables --set "PYQ_RESOLVER_WORKER_ENABLED=false" --service ai-neet-exam-app
railway redeploy -y --service ai-neet-exam-app
```

**Schema rollback** (full removal of this release's new columns):
```bash
DATABASE_URL_SYNC="<production sync URL>" .venv/Scripts/python.exe -m alembic downgrade d9c6e1a8f9ed
```

## 10. What's verified in production vs. local/implemented only

| Item | Production | Local only |
|---|---|---|
| Gemini key-exposure fix | ✅ deployed, confirmed no leak | — |
| httpx logging suppression | ✅ deployed, confirmed | — |
| `AI_RESOLVED` status / migration | ✅ applied | — |
| Retrieval-enablement feature code | ✅ deployed | — |
| Retrieval-enablement **data applied** | ✅ 4,768 candidates tiered | (local dev separately has its own 3,683, different corpus) |
| Gemini-based answer resolution | ❌ blocked by billing cap | ❌ also blocked (same key/cap) |
| Full NCERT ingestion corpus (1,112 units) | ❌ never applied to prod | ✅ local dev only |
| Frontend build/lint | ✅ verified locally; live site responds 200 | — |
| Backend full test suite | N/A (not run against prod) | ✅ 1,174/1,185 passed locally |
