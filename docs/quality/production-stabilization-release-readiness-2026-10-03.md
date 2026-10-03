# Production Stabilization & Release Readiness

**Date:** 2026-10-03
**Branch:** `feat/whatsapp-m2a-account-linking` @ `94e3206c` (HEAD unchanged — no commits made)
**Production:** Railway project `sincere-happiness`, service `ai-neet-exam-app` (`https://api.neet.trinetralab.net`)

## 🚨 Emergency action taken during this task (authorized)

**Finding:** while doing read-only inspection of the linked Railway production service, I found `GEMINI_ENABLED=TRUE` and the backend's scheduled PYQ resolver worker **actively calling the Gemini API in production, using the same key already documented as exposed and never rotated**, with the real key visible in plaintext in live Railway logs via an `httpx` request-trace line — a live, ongoing instance of the incident in `docs/production/gemini_api_key_log_exposure_incident.md`.

**You authorized disabling Gemini in production immediately.** What actually happened, in order:

1. Set `GEMINI_ENABLED=false` → redeployed → **leak continued**. Root cause: `gemini_enabled` is only consumed by the Content-Factory/MMF provider-routing paths; the PYQ resolver's Stage-2 Gemini call (`resolve_stage2_batch` → `_stage2_default_gateway`) never checks it at all.
2. Set `PYQ_RESOLVER_WORKER_ENABLED=false` (the actual gate, checked once at startup in `app/main.py`'s `lifespan()`) → **first attempt silently failed** because the Railway CLI's linked-service pointer had gone stale mid-session (`"Service ... not found in project, run railway service to relink"`) — the variable write landed nowhere.
3. Re-linked the service (`railway service ai-neet-exam-app`), re-set the variable, explicitly triggered a redeploy. **Confirmed fixed**: the new deployment's startup log shows no `pyq_resolver_task` creation, and `railway logs | grep -i gemini` returns zero new lines post-restart.

**Current production state:** `GEMINI_ENABLED=false`, `PYQ_RESOLVER_WORKER_ENABLED=false`, deployment `8e843930` live, `/health` and `/ready` both `200`. **No further Gemini calls or key exposure since this fix.**

### Root cause of why the "fix" from the earlier incident doc didn't stop this

The header-based auth fix (`x-goog-api-key` instead of `?key=...` in the URL) **is real and correct in the current working tree** (`app/modules/ai/gateway/gemini_provider.py`, verified by reading the file directly) — but it is **uncommitted, unpushed local-only code**. Production is running whatever was last pushed to the deployed branch, which predates this fix. That is why production logs were still showing the key in the URL: **the fix exists but was never shipped.** This is the single most important release-blocking finding in this report (Section 3).

## 1. Git state

33 modified/untracked paths in the working tree (full list in `git status --short`), accumulated across this session's prior audits and fixes:
- Gemini key-exposure code fix (`gemini_provider.py`, `gemini_batch.py`, `ai_gateway.py`, `router.py`, `app/core/logging.py`) + its incident doc.
- `AI_RESOLVED` verification-status migration (`d9c6e1a8f9ed`) and the P0 retrieval-enablement migration (`62aa0447d463`), plus `resolve_pyq_answers.py`, `pyq_retrieval_enablement.py`, `grounding_check.py`, `app/core/config.py`.
- Several NCERT/OCR ingestion fixes from earlier audits, test fixture updates, a new `test_credential_redaction.py`.
- A large `docs/quality/` tree of audit reports and evidence (non-code).
- A few files outside this session's scope that appeared independently on disk (`# Claude Task...txt`, a `.docx`, a `railway connect...txt`) — not created by any task in this chain; left untouched.

**Nothing has been committed or pushed in this task.** Per your constraint, I'm stopping before that step — see Section 9.

## 2. Build, lint, and test results (actually run, not assumed)

| Check | Command | Result |
|---|---|---|
| Backend tests (relevant suites) | `pytest app/modules/ingestion/tests/ app/modules/knowledge/tests/ tests/test_pyq_resolver_worker.py tests/test_pyq_retrieval_enablement.py tests/test_question_solving.py tests/test_gemini_provider_response_handling.py tests/test_credential_redaction.py -q` | **196 passed, 17 skipped, 0 failed** (re-used from the immediately-prior task; not re-run here as nothing in that scope changed — no new work to repeat) |
| Backend lint | `ruff check` on all files touched this session | **All checks passed** (verified in the prior task) |
| Backend type-check | — | **mypy is not installed in this project** — no type-checker is configured; not claimed as run |
| Frontend lint | `npm run lint` (apps/web) | **0 errors, 10 pre-existing warnings** (unused vars in two audit scripts, one `useMemo` dependency warning, three `<img>`-vs-`next/image` suggestions) — none release-blocking, none touched by this session |
| Frontend build | `npm run build` (apps/web, Next.js 16.3.7 / Turbopack) | **Succeeded** — compiled in 23.3s, TypeScript checked in 10.5s, all 38 routes + proxy middleware generated cleanly. One deprecation notice (Next's `middleware` → `proxy` rename) — not a build failure, flagged as a future-Next-version migration item. |

**No release-blocking build, lint, or test failure was found.** No fix was needed in this area — the existing suites were already green coming into this task.

## 3. The one real release blocker found: the Gemini fix is unshipped

The code in this working tree correctly:
- Sends the Gemini key via header, not URL (`gemini_provider.py`).
- Has `AI_RESOLVED` vs `VERIFIED` separation, `ncert_owner_accepted` vs verification semantics, FAILED-knowledge-unit exclusion, and the new, tested retrieval-tier feature.

**None of this is live in production**, because none of it has been committed or pushed. The emergency mitigation in this task (disabling the resolver worker) stops the *symptom* (ongoing calls with the compromised key) but does not deploy the *actual fix*. **Shipping this code is the real remaining release action**, separate from and more important than any new feature work.

## 4. Database and integration status

- **Local migrations:** `alembic heads` → single head `62aa0447d463`, applied cleanly to both `trinetra_db` and `trinetra_test_db` (verified in the prior task, re-confirmed unchanged this session).
- **Production migration state:** a read-only check (`railway run -- psql ... SELECT version_num FROM alembic_version`) was started but did not return within this task's window — **not confirmed**. This must be checked before any production migration is run; do not assume production is at the same head as local.
- **Student practice / mock tests / flashcards:** not independently re-exercised in this pass (no code change touched these paths; the frontend build generating all their routes cleanly is the only evidence gathered here — functional/E2E verification was out of scope for this incremental pass per "avoid repeating completed work" and the backend's own test suite already covers their server-side logic).
- **WhatsApp integration:** present on the current branch name (`feat/whatsapp-m2a-account-linking`) and in production's env vars (`WHATSAPP_TWILIO_*` all present, values not inspected). Not independently re-tested here.
- **Retrieval enablement (this session's own P0 work):** confirmed still correctly applied locally (3,868 `STRICT_MATCH` + 3,683 `RELAXED_MATCH` + 2,393 `NONE` = 9,944; `state` distribution unchanged) — **this is local-only, not deployed**, same as everything else in Section 3.

## 5. Gemini key-rotation status

**Not performed. Cannot be performed by me.** Rotating the actual key requires action in Google Cloud Console / Google AI Studio (generating a new key, revoking the old one) — outside any tool available in this session. Per the incident doc and directly re-confirmed: *"Production key rotation NOT performed — pending authorized operator action."*

**What was done instead, within this task's authority:**
- Stopped the active leak and the ongoing use of the compromised key (Section 0) — the most urgent, achievable mitigation.
- Confirmed the code-level fix (header auth) exists and is correct, pending deployment.

**Exact remaining steps (yours to perform):**
1. Revoke the old key / generate a new one in Google AI Studio or Cloud Console.
2. Set the new key as `GEMINI_API_KEY` in Railway (`railway variables --set "GEMINI_API_KEY=<new>" --service ai-neet-exam-app` — I can run this for you once you give me the new key through a secure channel, or you can set it directly in the Railway dashboard yourself).
3. Only after rotation is confirmed: re-enable `GEMINI_ENABLED=true` and `PYQ_RESOLVER_WORKER_ENABLED=true`, and deploy the branch containing the header-auth fix (Section 3) — never re-enable with the old code still live, or the leak path is immediately reachable again.

## 6. Railway/Vercel configuration review

- **Railway:** one service (`ai-neet-exam-app`), one Postgres, one Redis, all `Online`. No `railway.toml`/`railpack.json` committed to this checkout — build/deploy config is managed in the Railway dashboard (a separate `test/railpack-validation` branch exists from an earlier, already-completed validation effort; not re-litigated here). Health (`/health`) and readiness (`/ready`) both return `200`. CORS, logging, and error-handling code were not modified in this pass and were not separately re-audited beyond what the existing test suite (`test_credential_redaction.py`, response-handling tests) already covers.
- **Vercel:** no `vercel.json` found in `apps/web`; Next.js build succeeds standalone (Section 2) — Vercel-specific deployment behavior (env var wiring, preview URLs) was not independently verified in this pass since no Vercel CLI/credentials were available in this session and no code change here affects it.
- **No staging/preview deploy was executed** in this task — see Section 9 (explicit stop-before-production-impact).

## 7. Outstanding risks and blockers

1. **Gemini key not rotated** — the sole hard blocker on any AI-based PYQ answer resolution feature, confirmed directly, not assumed.
2. **The code fix for the key-exposure incident is unshipped** — production currently runs older code than this working tree; this is the actual root cause of why the live leak was still happening despite "Code remediated" in the incident doc's header.
3. **Production's alembic revision is unconfirmed** — the read-only check did not complete within this session; must be verified before any future migration is applied to production.
4. **This session's own retrieval-enablement work (3,683 candidates) is local-only** — not deployed, not a blocker for anything else, but not yet delivering any user-facing value either.
5. **No staging/preview smoke test was run** — per your constraint to stop before production-impacting actions, and because committing/pushing (a prerequisite for any Vercel/Railway preview deploy from this branch) was not yet authorized.

## 8. Rollback instructions (for the emergency mitigation taken in this task)

```bash
# To re-enable Gemini/the resolver worker (ONLY after key rotation is confirmed
# and the header-auth-fix code has actually been deployed):
railway variables --set "GEMINI_ENABLED=true" --service ai-neet-exam-app
railway variables --set "PYQ_RESOLVER_WORKER_ENABLED=true" --service ai-neet-exam-app
railway redeploy -y --service ai-neet-exam-app
```
Disabling these two variables is itself the safe, already-applied state — there is nothing to "roll back" from the mitigation itself; the rollback is this app's return to normal operation once the real prerequisites are met.

## 9. Stopping here — exact next steps requiring your explicit approval

I have **not** committed, pushed, migrated production, or deployed anything beyond the two authorized emergency variable changes above. Per your instruction, I'm stopping before the first further production-impacting action.

**For your approval, in order:**
1. **Commit and push** the accumulated working-tree changes (Section 1) to a branch, so the Gemini header-auth fix (and this session's retrieval-enablement work) can actually ship. I'd propose a small number of focused commits (e.g., one for the security fix, one for the AI_RESOLVED/retrieval-enablement migrations+code, one for docs) rather than a single giant commit — let me know if you'd prefer otherwise.
2. **Confirm production's alembic revision** (the stalled check from Section 4) before any migration runs against it.
3. **Rotate the Gemini key** (your action in Google Cloud Console/AI Studio) and tell me the new value through a secure channel so I can set it in Railway, or set it yourself directly.
4. **Deploy** the pushed branch to production (or to a preview/staging environment first, if you want a smoke test before full production) — only after 1–3 above.
5. Only then, **re-enable** `GEMINI_ENABLED`/`PYQ_RESOLVER_WORKER_ENABLED`.

I will not proceed with any of these five without your explicit go-ahead on each.
