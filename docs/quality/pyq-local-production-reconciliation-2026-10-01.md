# NEET PYQ Local vs. Production Reconciliation Audit — 2026-10-01

**Audit timestamp:** 2026-10-01, ~15:07 UTC (session-local clock; see individual query evidence files for exact sub-times).
**Repository:** `ravishori/ai-neet-exam-app`
**Branch:** `feat/whatsapp-m2a-account-linking`
**Commit:** `94e3206ca72dc034b618745159a4edf53899b23f`
**Working tree at audit time:** 6 modified + untracked files, all pre-existing and unrelated to PYQ (an in-progress credential-sanitization fix in `app/core/logging.py` / `app/modules/ai/gateway/*`, plus this audit's own new doc files). None reference `pyq`.

## Executive summary

**Production could not be audited.** Every attempt to establish a read-only connection to the production PostgreSQL database failed — not with a credentials error, but by hanging indefinitely with zero output, consistent with the database being reachable only from Railway's private network and not from this local machine (no `DATABASE_PUBLIC_URL` variable exists on the production service; `railway run` injects environment variables locally but does not proxy network traffic). This was reproduced twice independently (once earlier in this session, once during this audit), with a control test confirming the tooling itself works correctly for non-database commands. Per this audit's own safety instructions, production querying was stopped rather than guessed at.

**Consequently, this report delivers:**
- A fully evidence-backed **local** PYQ snapshot (Phase C), confirmed to have **zero drift** from the 2026-10-01 baseline in `docs/quality/pyq-coverage-audit.md` (same date, no intervening writes).
- **No** schema comparison, production snapshot, record-level reconciliation, or migration-coverage percentage — all of Phases B, D, and E are marked **not available** below, with the specific blocker, not an estimate or inference, as the reason.
- A remediation backlog limited to what is actually known: the production-access blocker itself (now the top finding) plus the local-only findings already on record from the baseline audit.

**No row counts, percentages, or completeness claims about production are made anywhere in this report.** Where a reader might expect a production number, this report says `not available` and states why.

## Scope and explicit non-goals

**In scope:** confirming local/production target identity safely; attempting read-only production access; re-confirming current local PYQ metrics against the existing baseline.

**Explicitly NOT done, and why:**
- Phase B (schema comparison), Phase D (production snapshot), Phase E (record-level reconciliation / migration coverage percentages) — **blocked**, production was never queried. See [Target identity and read-only proof](#target-identity-and-read-only-proof).
- No data, schema, migration, configuration, or secret was modified on either database. No DDL/DML was ever issued against production — the connection itself never succeeded, so there was no opportunity to issue any statement, read or write.
- This report does not infer or estimate what production's state probably is. Every "not available" below is a true gap in this audit's evidence, not a filled-in guess.

## Target identity and read-only proof

### Local target
- **Database:** `trinetra_db`, host `localhost:5432`.
- **Environment marker:** `ENVIRONMENT=development` (from `apps/backend/.env`).
- **Confirmed via safe metadata:** schema inspection (`\dt pyq.*`, `\d pyq.questions`, etc.) succeeded directly against this database in the baseline audit and was spot-checked again in this audit — see [Local target evidence](#local-fresh-snapshot-phase-c).
- **Read-only proof:** every query in this audit (and the baseline it extends) ran inside an explicit `BEGIN TRANSACTION READ ONLY; ... COMMIT;` block via `psql`, confirmed by the literal `BEGIN`/`COMMIT` echoed in query output (see evidence files). **Status: `confirmed`.**
- **Local migration state note (new finding this audit):** the local database's `alembic_version` is `b3f9c299033e`, while the repository's current `alembic` head is `e2f3a4b5c6d7` (confirmed via `alembic heads` in `apps/backend`). The local dev database is **behind** the repo's current migration head by at least one migration (the WhatsApp M2A `whatsapp.link_codes` table, unrelated to PYQ). All PYQ-schema migrations (`a2b3c4d5e6f7` through `a3f7c8d1e2b4`) are confirmed applied locally — the gap is in later, unrelated migrations, not in the PYQ data model itself. Labeled `confirmed` (directly queried), flagged because it means "local" is not perfectly synchronized with "repo head" either, which matters for any future schema-compatibility claim.

### Production target
- **Service:** `ai-neet-exam-app`, Railway project `sincere-happiness`, confirmed via `railway status` to be `Online` at `https://api.neet.trinetralab.net` (same identity confirmed in the separate WhatsApp M2A post-merge audit earlier this session).
- **Database identity: NOT independently confirmed this audit** — every attempt to query it (even `SELECT current_database()`) failed to return before the connection attempt was abandoned. **Status: `not available`.**
- **Read-only session: NOT established.** No connection was ever successfully opened, so there was nothing to prove read-only about. **Status: `not available`, not `confirmed` and not `failed-but-attempted-write`** — no attempt to write was ever possible either, since no connection succeeded at all.
- **Full evidence of what was attempted, exact commands, and the reasoning for the conclusion that this is a private-network-only database:** see `docs/quality/_pyq_reconciliation_2026-10-01/production_access_attempts.txt`.

**Per Phase A's explicit instruction** ("If production target is ambiguous, credentials are unavailable, or read-only guarantees cannot be established, do not guess. Complete only the safe local audit and document why production comparison could not run."), production querying stopped here.

## Methodology and exact safe commands/queries

```bash
# Repo state
git branch --show-current
git rev-parse HEAD
git status --short

# Local target confirmation (no secret values printed)
grep -E "^(ENVIRONMENT|DATABASE_URL)=" apps/backend/.env   # values redacted in this report

# Local migration state
cd apps/backend && .venv/Scripts/python.exe -m alembic heads
PGPASSWORD=*** psql -h localhost -U trinetra_app -d trinetra_db -t -c "SELECT version_num FROM alembic_version;"

# Fresh local Phase C spot-check (read-only transaction)
PGPASSWORD=*** psql -h localhost -U trinetra_app -d trinetra_db -c "
BEGIN TRANSACTION READ ONLY;
SELECT count(*) AS total, count(*) FILTER (WHERE state='ANSWER_VERIFIED') AS verified,
       count(*) FILTER (WHERE state='ANSWER_PENDING') AS pending FROM pyq.questions;
SELECT (SELECT count(*) FROM pyq.answer_assertions) AS assertions,
       (SELECT count(*) FROM pyq.duplicate_candidates) AS dup_candidates,
       (SELECT count(*) FROM pyq.qa_reviews) AS qa_reviews,
       (SELECT count(*) FROM pyq.promotion_log) AS promotions;
COMMIT;
"

# Production target — attempted, did not succeed (see evidence file for full detail)
railway run --service ai-neet-exam-app -- echo "railway-run-test-ok"   # control: succeeded
railway run --service ai-neet-exam-app -- psql "$DATABASE_URL" -c "SELECT current_database(), inet_server_addr()::text, version();"   # hung, no output, eventually exit 1
railway variables --service ai-neet-exam-app --kv | cut -d'=' -f1   # variable NAMES only, confirms no DATABASE_PUBLIC_URL
```

All local queries exited `0`. All production query attempts failed to return a usable result (see evidence directory for full detail including process-level diagnostics).

## Schema comparison (Phase B)

**Status: `not available`.** No production schema was inspected. The local schema (12 tables under `pyq.*`, fully described in the 2026-10-01 baseline) is on record in `docs/quality/pyq-coverage-audit.md`. No comparison with production's schema could be performed. This also means no claim can be made about whether row-level comparison would even be *safe* on production — that determination itself depends on schema access this audit did not get.

## Fresh local coverage snapshot and comparison to historical baseline (Phase C)

| Metric | Baseline (2026-10-01, earlier today) | This audit (2026-10-01, re-check) | Change |
|---|---:|---:|---:|
| Total PYQ questions | 12,396 | 12,396 | 0 |
| `ANSWER_VERIFIED` | 2,452 | 2,452 | 0 |
| `ANSWER_PENDING` | 9,944 | 9,944 | 0 |
| Answer assertions | 2,452 | 2,452 | 0 |
| `duplicate_candidates` rows | 0 | 0 | 0 |
| `qa_reviews` rows | 0 | 0 | 0 |
| `promotion_log` rows | 0 | 0 | 0 |

**Result: `confirmed` zero drift.** No PYQ records were added, removed, or changed between the baseline audit and this one — both ran on the same date with no intervening writes (no migrations, importers, or resolvers were run against `pyq.*` in between, confirmed by `git status` showing no new pyq-related commits/migrations in the working tree). For the complete breakdown (year-wise, subject-wise, NCERT evidence detail, duplicate-cluster analysis, metadata gaps, full gap backlog), this report defers entirely to the baseline — it is not restated here to avoid duplicating a document that is still current and unchanged. See `docs/quality/pyq-coverage-audit.md`.

## Production coverage snapshot (Phase D)

**Status: `not available` for every metric.** No production query succeeded. The table below lists what was required and why none of it could be measured.

| Metric | Status | Reason |
|---|---|---|
| Total PYQ question count | not available | Production connection never succeeded |
| Counts by year/subject/class/paper/chapter | not available | Same |
| Answer populated/missing/verified/unverified/conflict counts | not available | Same |
| NCERT evidence and source provenance coverage | not available | Same |
| Metadata completeness | not available | Same |
| Duplicate classification status | not available | Same |
| QA review and promotion/live-content counts | not available | Same |
| Schema/migration version | not available | Same |

## Local-vs-production reconciliation (Phase E)

**Status: `not available` in full.** Without a production connection, no record identity key, content fingerprint, or match classification could be computed. No local record can be labeled `matched`, `matched identity but content differs`, `present locally but absent in production`, or `ambiguous` — all of these require reading production data, which did not happen. No production record could be labeled `matched`, `production-only`, or `duplicate/ambiguous candidate` for the same reason.

**No migration coverage percentage is reported.** Reporting a percentage without a production denominator would be exactly the kind of unlabeled estimate this audit's own instructions prohibit ("If the production schema does not support a local metric, mark it `not comparable`... do not substitute an estimate without labeling it" — the stronger case here, no production access at all, gets the stronger label: `not available`, not an estimate of any kind).

## Data integrity and provenance findings

No new production-side integrity findings — none could be produced. The local-side findings already on record in the baseline (9,944 unresolved answers, 0 QA/promotion progress, 7,125 rows in unclassified exact-duplicate clusters, 61.3% missing subject classification, 2022 entirely absent from the local corpus, etc.) stand unchanged — see baseline report for the full list with reproducible query references.

## Prioritized remediation backlog

| ID | Severity | Environment(s) | Finding | Evidence | Count/Denominator | Impact | Recommended next action | Requires separate authorization? |
|---|---|---|---|---|---|---|---|---|
| REC-1 | **Critical** | Production (access) | Production PYQ database cannot be reached read-only from this environment via any currently available tooling (`railway run` injects env vars locally but does not proxy to Railway's private network; no public DB endpoint variable exists). | `docs/quality/_pyq_reconciliation_2026-10-01/production_access_attempts.txt` — 2 independent hung attempts, 1 successful control test, variable-name-only confirmation of no public endpoint. | 0/1 production connection attempts succeeded | Blocks all of Phases B/D/E — no schema comparison, no production snapshot, no migration-coverage percentage is currently possible from this environment. | Establish a sanctioned read-only path to production Postgres (e.g. a dedicated read-only role reachable via Railway's proxy/`railway connect`, a bastion, or a scheduled read-only export) before attempting this reconciliation again. | **Yes** — provisioning any new production access path requires separate explicit authorization; this audit only identifies the gap. |
| REC-2 | High (carried over, unchanged) | Local | 9,944 of 12,396 local questions (80.2%) have no answer assertion at all. | `docs/quality/pyq-coverage-audit.md`, Gap 1 | 9,944 / 12,396 | Largest single gap in the local corpus; unchanged since baseline. | See baseline remediation backlog. | No — read-only measurement already complete; closing it requires separately authorized resolver runs. |
| REC-3 | Medium-High (carried over, unchanged) | Local | 7,125 rows (57.5%) sit in an exact-hash duplicate cluster never run through `duplicate_candidates` classification. | `docs/quality/pyq-coverage-audit.md`, Gap 4 | 7,125 / 12,396 | Fastest large-scale gap-closing opportunity (evidence already exists in the data). | See baseline remediation backlog. | No — same as above. |

*(REC-2 and REC-3 are restated here only as pointers with their severity preserved, per the instruction to prioritize findings in this report; full detail intentionally lives in the baseline to avoid duplicate, potentially-diverging copies of the same finding.)*

## Limitations, unavailable metrics, and unresolved questions

- **Every production-side metric in this report is `not available`**, not `0`, not `estimated`, and not inferred from local data. A reader must not treat the absence of a production number as evidence that production is empty, broken, or identical to local.
- Whether production's PYQ schema exists at all, and if so at what migration revision, is genuinely unknown — the local migration-state finding above (`b3f9c299033e` vs. repo head `e2f3a4b5c6d7`) is about *local*, not production, and must not be conflated with it.
- `railway connect` (Railway's interactive DB-proxy command) was not attempted — it was judged out of scope for non-interactive, reproducible audit tooling within the time available. It remains a plausible path to a working production connection and should be the first thing tried in a follow-up.
- No question content, PII, or row-level data was ever read from production, by construction — the connection never succeeded.

## Audit evidence references

- `docs/quality/_pyq_reconciliation_2026-10-01/production_access_attempts.txt` — full detail of both production connection attempts, the control test, and the reasoning for the "private-network-only" conclusion. No credentials or connection strings included.
- `docs/quality/_pyq_reconciliation_2026-10-01/local_fresh_snapshot.sql_and_output.txt` — the exact query and output for this audit's local re-confirmation.
- `docs/quality/pyq-coverage-audit.md` and its own evidence directory `docs/quality/_pyq_audit_2026-10-01_queries/` — the full local baseline this audit confirmed as unchanged.

## Dated audit history

| Date | Type | Summary |
|---|---|---|
| 2026-10-01 (earlier) | Local baseline | First full local PYQ coverage audit. See `docs/quality/pyq-coverage-audit.md`. |
| 2026-10-01 (this report) | Local↔production reconciliation attempt | Local re-confirmed with zero drift from baseline. **Production could not be accessed** — all of schema comparison, production snapshot, and record-level reconciliation are `not available`, blocked on a production read-only access gap (REC-1), not on any data finding. |

*(Future updates: once a working, sanctioned read-only path to production is established and separately authorized, re-run this reconciliation and append a new dated section above, preserving this one unchanged.)*
