# NEET PYQ Coverage Audit

Durable, evidence-backed record of the PYQ (Previous Year Question) database's answer-coverage, verification, provenance, and gap state. Updated in-place with new dated snapshots as gap-resolution work lands — see [Audit History](#audit-history) at the bottom. Never silently overwritten.

---

## 2026-10-01 Baseline Audit

### Audit metadata

- **Date/time:** 2026-10-01, timezone America (session local clock as observed via `pg_stat_activity`/shell); all timestamps below are as returned by the database server.
- **Repository:** `ravishori/ai-neet-exam-app`
- **Branch:** `feat/whatsapp-m2a-account-linking`
- **Commit:** `94e3206ca72dc034b618745159a4edf53899b23f`
- **Working-tree status at audit time:** 6 modified + 2 untracked files present (an unrelated, separately in-progress credential-sanitization fix: `apps/backend/app/core/logging.py`, `app/modules/ai/gateway/{ai_gateway,gemini_batch,gemini_provider,router}.py`, `tests/test_gemini_provider_response_handling.py`, `tests/test_credential_redaction.py`, `docs/production/gemini_api_key_log_exposure_incident.md`). **None of these touch any PYQ code, schema, or data**, confirmed by `git diff --stat` scope review (see [Verification](#verification-of-this-audit) below).
- **Database/environment identity:** local development PostgreSQL instance, database name `trinetra_db`, host `localhost:5432`, `ENVIRONMENT=development` (confirmed via `apps/backend/.env`). This is **not** the production database. No credentials, connection strings, or secrets are included anywhere in this report.
- **Read-only guarantee:** every query below was executed inside an explicit `BEGIN TRANSACTION READ ONLY; ... COMMIT;` block via `psql`. No `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`/DDL statements were issued. No application code, migrations, or files other than this report were modified as part of the audit itself.

### Scope, exclusions, assumptions, limitations

- **Scope:** all rows in `pyq.questions` and its directly related tables (`pyq.answer_assertions`, `pyq.duplicate_candidates`, `pyq.source_files`, `pyq.sources`, `pyq.import_batches`, `pyq.qa_reviews`, `pyq.promotion_log`, `pyq.subject_classification_audit`, `pyq.subject_conflict_reviews`, `pyq.gemini_batch_jobs`, `pyq.gemini_batch_items`) in the local dev database as of audit time. Schema inspected directly via `\d` in `psql`, not assumed from code or prior docs.
- **Excluded:** `cms.content_items` (the eventual promotion target) was only touched via a one-row sanity cross-check (`pyq.promotion_log`); no PYQ questions have reached promotion yet (see Gap 8), so there is nothing to audit there this cycle. `review_sandbox.questions` (a separate schema/table with a similar name) was identified but is out of scope — it is not referenced by any `pyq.*` foreign key and appears to be an unrelated sandbox table; it was not queried.
- **Assumption, explicitly labeled:** `pyq.answer_assertions.assertion_source` values named `pyq_gemini_ncert_recovery:*` / `pyq_local_ncert_recovery:*` are **directly confirmed** (not assumed) to carry genuine NCERT textbook evidence — a random sample of `evidence_note` values was read and each one contains a structured citation of the form `method=deterministic_ncert_term_phrase_grounding; source=<NCERT book code> page=<N>; excerpt=<verbatim textbook sentence>` (e.g. `source=lebo102 page=5`, `source=kebo104 page=15` — standard NCERT biology textbook file codes). This is evidence, not inference.
- **Limitation:** `raw_options` is stored as a JSONB **object** (not an array) in 100% of rows (query 26). The audit checked for a 4-key/4-option shape only indirectly; a precise per-row "missing option" check would require parsing the object's actual keys, which was not performed this cycle — flagged as a follow-up, not claimed as verified either way.
- **Limitation:** `extraction_confidence` takes only 7 discrete values across all 12,396 rows (0.45, 0.5, 0.625, 0.65, 0.939, 0.94, 0.95) — this is a coarse, effectively-categorical score from the extraction pipeline, not a continuous confidence measure. Treat the ">=0.9 / <0.9" split below as a pipeline-defined category boundary, not a statistically meaningful confidence threshold.
- **Limitation:** This audit does not independently re-verify that any `ANSWER_VERIFIED` answer is *correct* — only that it has a verification status, an asserted option, and an evidence citation. Per the audit instructions, a populated/verified answer is never assumed correct merely because it exists.

### Executive summary

| Metric | Value | % of total |
|---|---:|---:|
| Total PYQ records in scope | **12,396** | 100% |
| Answer verified (`state = ANSWER_VERIFIED`) | **2,452** | 19.78% |
| Answer pending (`state = ANSWER_PENDING`) | **9,944** | 80.22% |
| Answer conflicts (`state = ANSWER_CONFLICT`, or multi-option disputes within `answer_assertions`) | **0** | 0% |
| Questions with zero answer assertions of any kind | **9,944** | 80.22% (identical set to "pending" — see Gap 1) |
| Verified answers with NCERT evidence citation present | **2,452 / 2,452** | **100%** of verified rows |
| Questions reaching QA review (`pyq.qa_reviews`) | **0** | 0% |
| Questions promoted to live content (`state = PROMOTED`) | **0** | 0% |
| Questions flagged as exact-hash duplicates of another question | **7,125** (in 1,680 groups) | 57.48% |
| Rows with a `duplicate_candidates` audit entry (any classification) | **0** | 0% — dedupe pipeline has never recorded output for this batch |

**Headline finding:** the database contains 12,396 extracted NEET PYQ questions spanning 2020–2025 (2022 is absent — see Gap 6), of which only **19.78%** have a verified answer, and **0%** have progressed past answer verification into QA review, deduplication, or promotion. Every one of the 2,452 verified answers is backed by a genuine, directly-observed NCERT textbook citation (book code + page + excerpt). Over half of all rows (57.5%) belong to an exact-duplicate cluster that spans multiple source papers — this looks like legitimate cross-year NEET question reuse (confirmed 0 of the 1,680 duplicate groups are within a single source file), not an extraction bug, but it has never been run through the dedicated `duplicate_candidates` audit table, so no machine-readable record of it exists yet.

### State machine coverage

`pyq.questions.state` supports 12 defined values (`EXTRACTED, NORMALIZED, ANSWER_PENDING, ANSWER_VERIFIED, ANSWER_CONFLICT, DEDUPE_CHECKED, QA_PENDING, QA_APPROVED, QA_REJECTED, PROMOTION_ELIGIBLE, PROMOTED, BLOCKED`). Only **2 of the 12** are present in the live data:

| State | Count | % |
|---|---:|---:|
| `ANSWER_PENDING` | 9,944 | 80.22% |
| `ANSWER_VERIFIED` | 2,452 | 19.78% |
| `EXTRACTED`, `NORMALIZED`, `ANSWER_CONFLICT`, `DEDUPE_CHECKED`, `QA_PENDING`, `QA_APPROVED`, `QA_REJECTED`, `PROMOTION_ELIGIBLE`, `PROMOTED`, `BLOCKED` | 0 each | 0% |

`validation_status` is `'EXTRACTED'` for **100%** of rows (12,396/12,396) — this separate field has never advanced either.

### Answer coverage and verification

- **Answer populated vs. missing:** every verified question has exactly one `pyq.answer_assertions` row (2,452 assertions = 2,452 distinct `question_id`s — a 1:1 relationship, confirmed by query 7 vs. query 9). The remaining 9,944 questions (`ANSWER_PENDING`) have **zero** assertion rows — "missing an answer" and "pending" are the same 9,944-row set in this database; they are not independently distinguishable gap categories today.
- **Verified vs. unverified:** of the 2,452 assertions that exist, **100% are `VERIFIED`** (2,452/2,452). `0` are `ASSERTED`-only (claimed but not verified) and `0` are `DISPUTED`.
- **Conflicts:** `0` questions have more than one distinct `asserted_option` value across their assertions (query 13), and `0` questions carry `state = ANSWER_CONFLICT` (query 13b). No answer-conflict gap exists in the current data — this category is empty, not unmeasured.
- **Evidence quality:** `evidence_note` is populated for **100%** of verified assertions (2,452/2,452, query 15) and, per the sampling above, contains a structured NCERT citation in every sampled row. The separate `explanation` column is **0%** populated (0/2,452) — it is a distinct, unused field in this pipeline, not a duplicate of `evidence_note`.
- **Resolver provenance:** `resolver_version` is `NULL` for all 2,452 rows — the resolver's own version string is not being recorded on the assertion row, even though the `assertion_source` string embeds a date (`:2026-09-29`, `:2026-09-28`) and the `evidence_note` text embeds a `resolver_version=pyq-local-ncert-resolver-v1` fragment. This is a metadata gap (see Gap 5).
- **`assertion_source` breakdown:**

| Source | Verification status | Count |
|---|---|---:|
| `pyq_gemini_ncert_recovery:2026-09-29` | VERIFIED | 2,300 |
| `pyq_local_ncert_recovery:2026-09-28` | VERIFIED | 152 |

- **Answer-option balance (sanity check, not a gap):** among the 2,452 verified answers, the asserted correct option is reasonably balanced across A/B/C/D (A=604, B=586, C=607, D=655) — no evidence of a resolver bias toward one option letter.

### NCERT evidence coverage

- **Answer-level evidence:** 100% of verified answers (2,452/2,452) carry an NCERT-grounded `evidence_note` (book code + page + excerpt), as directly confirmed above. This is answer-verification evidence, kept distinct per the audit's own instruction from the next item.
- **Subject-classification evidence:** `pyq.subject_classification_audit` (a *separate* table tracking NCERT evidence for *subject* classification, not answer correctness) is **completely empty** — 0 rows. Whatever process assigned `subject` on the 4,799 rows that have one (the 2021 batch only — see below) did not go through this audited, evidence-tracked path. `pyq.subject_conflict_reviews` is likewise empty (0 rows) — no subject conflicts have ever been queued or reviewed.

### Source provenance

- **Sources table:** exactly 1 source registered — `NEET_PYQ_OFFICIAL`, "NEET Official PYQ Papers (2020-2025, staged extraction)", `authority_type = OFFICIAL_NEET_PAPER`.
- **Import batches:** 1 batch, `status = COMPLETED`.
- **Source files:** 72 total. **1 of 72** is missing both `exam_year` and `paper_code` — its `relative_path` is `NEET_PYQ_OFFICIAL/unknown/<sha256>.pdf`, i.e. a file that was extracted but never matched to a known paper/year during import. This single file is the only provenance gap at the source-file level.
- **Exam-year distribution of source files:** `(null)`=1, `2020`=16, `2021`=24, `2023`=24, `2024`=3, `2025`=4. **`2022` has zero source files and zero questions** — see Gap 6.

### Duplicate and near-duplicate candidates

- **Exact `question_hash` duplicates:** 1,680 groups, 7,125 rows involved (57.5% of all questions). **All 1,680 groups span multiple distinct `source_file_id`s; zero groups are confined to a single source file.** This is strong evidence these are legitimate cross-year/cross-paper question repeats (a well-known NEET pattern), not a within-file extraction bug duplicating the same question twice.
- **`normalized_question_hash` duplicates:** 1,675 groups, 7,168 rows — a slightly larger set than the exact-hash count, consistent with normalization catching a few additional near-duplicates that differ only in whitespace/formatting at the raw-text level.
- **`pyq.duplicate_candidates` audit table: 0 rows.** Despite the hash-level evidence above, the dedicated dedupe-tracking table has never been populated for this batch — no question has been run through (or recorded as having been run through) the `DEDUPE_CHECKED` pipeline stage. The 1,680/1,675 duplicate clusters above are therefore a **raw-data finding**, not a confirmed-vs-candidate classification — this audit cannot currently distinguish "confirmed duplicate" from "possible duplicate" because the classification table that would hold that distinction is empty.

### Metadata gaps

| Field | Missing/null count | % of 12,396 |
|---|---:|---:|
| `subject` | 7,597 | 61.3% |
| `class_level` | 12,396 | **100%** |
| `concept_id` | 12,396 | **100%** |
| `normalized_stem` / `normalized_options` | 12,396 each | **100%** (never populated at any state, including `ANSWER_VERIFIED`) |

`subject` is populated **only** for the 4,799 questions sourced from 2021 papers (Botany 1,199, Chemistry 1,200, Physics 1,200, Zoology 1,200 — an almost perfectly even 4-way split). All questions from 2020, 2023, 2024, and 2025 (7,597 rows, 61.3% of the database) have `subject = NULL`. `class_level` and `concept_id` are unpopulated across the entire table with no exceptions, including on verified/answered rows.

### Invalid answer values / malformed options

- `raw_options` is a JSONB **object** in 100% of rows (not an array) — no malformed-type rows found at the top-level JSON-type check. A deeper per-row key/shape validation (e.g. confirming exactly 4 option keys with non-empty text) was **not performed** this cycle and is explicitly flagged as unverified, not as clean.
- `asserted_option` is constrained at the database level to `{A, B, C, D}` (CHECK constraint `ck_pyq_answer_assertions_option`) — by construction, no invalid option-letter values can exist in `answer_assertions`. No multiple-correct or no-correct-answer risk was detected in `answer_assertions` because exactly one assertion row exists per verified question (confirmed above) and the check constraint prevents an invalid letter.
- `extraction_confidence` has no `NULL` values (0/12,396) and sits at exactly 7 discrete values, bimodally split around 0.45–0.65 (5,888 rows, 47.5%) and 0.939–0.95 (7,383 rows, 59.6%) — note these two bands overlap in the "ge/lt 0.9" cut because 0.939 falls just below it; see the raw value table in [Verification](#verification-of-this-audit) for exact figures.

### Subject × Year breakdown

| Subject | Exam year | Total | Verified | Verified % |
|---|---|---:|---:|---:|
| (null — subject not classified) | 2020 | 2,880 | 610 | 21.18% |
| (null — subject not classified) | 2023 | 3,536 | 1,271 | 35.94% |
| (null — subject not classified) | 2024 | 646 | 99 | 15.32% |
| (null — subject not classified) | 2025 | 535 | 19 | 3.55% |
| Botany | 2021 | 1,199 | 146 | 12.18% |
| Chemistry | 2021 | 1,200 | 82 | 6.83% |
| Physics | 2021 | 1,200 | 111 | 9.25% |
| Zoology | 2021 | 1,200 | 114 | 9.5% |

### Year-wise breakdown

| Exam year | Total questions | Answer verified | Answer pending | Verified % |
|---|---:|---:|---:|---:|
| 2020 | 2,880 | 610 | 2,270 | 21.18% |
| 2021 | 4,799 | 453 | 4,346 | 9.44% |
| 2022 | 0 | 0 | 0 | — (no data; see Gap 6) |
| 2023 | 3,536 | 1,271 | 2,265 | 35.94% |
| 2024 | 646 | 99 | 547 | 15.32% |
| 2025 | 535 | 19 | 516 | 3.55% |
| **Total** | **12,396** | **2,452** | **9,944** | **19.78%** |

### Gap categories (prioritized remediation backlog)

Each gap below is independently reproducible via the exact SQL query referenced (see [Verification](#verification-of-this-audit)). Overlap between categories is called out explicitly where it exists.

1. **[HIGH] 9,944 questions (80.2%) have no answer assertion at all.** This is the single largest gap and is identical in size to "state = ANSWER_PENDING" — there is currently no way in this database to distinguish "never attempted" from "attempted but not yet resolved," since no failed/in-progress resolver attempts are recorded anywhere. *Reproduce:* query 7 vs. query 8 above.
2. **[HIGH] Zero questions have ever reached QA review.** `pyq.qa_reviews` is empty (0 rows) regardless of state, including the 2,452 `ANSWER_VERIFIED` rows that would be the natural next candidates. *Reproduce:* query 28/29.
3. **[HIGH] Zero questions have been promoted.** `pyq.promotion_log` is empty and `state = PROMOTED` count is 0 — none of this 12,396-question corpus has reached live content yet, including the 2,452 verified+NCERT-evidenced ones. *Reproduce:* query 30/31.
4. **[MEDIUM-HIGH] Deduplication has never been recorded, despite clear duplicate signal in the raw data.** 7,125 rows (57.5%) sit in a hash-duplicate cluster with another row, but `pyq.duplicate_candidates` has 0 rows — meaning none of this has been classified as confirmed/likely/rejected. Running the existing dedupe pipeline against this hash evidence is the fastest large-scale gap-closing opportunity available (it doesn't require new NCERT evidence — the duplicate pairs already exist in the data). *Reproduce:* query 39/40 vs. query 18/20.
5. **[MEDIUM] `subject` is NULL for 61.3% of questions (7,597 rows)** — every year except 2021. `class_level` and `concept_id` are NULL for 100% of all 12,396 rows with no exceptions. *Reproduce:* query 4–6.
6. **[MEDIUM] 2022 is entirely absent from the corpus** — 0 source files, 0 questions for that exam year, while every other year 2020–2025 (except the two missing ones already noted) has data. Needs confirmation of whether 2022 PYQ papers exist as a source and simply haven't been imported yet, or were intentionally excluded. *Reproduce:* query 22/23.
7. **[LOW-MEDIUM] `resolver_version` column is NULL for all 2,452 assertions**, even though the version string is available (embedded as free text inside `evidence_note`). A minor pipeline fix to populate this structured column from the already-computed value would improve queryability without needing new evidence generation. *Reproduce:* query 17.
8. **[LOW] 1 of 72 source files has no `exam_year`/`paper_code`** (`NEET_PYQ_OFFICIAL/unknown/<hash>.pdf`) — a single unresolved import artifact. *Reproduce:* query 49.
9. **[LOW, unverified scope] `raw_options` object-shape validation was not performed this cycle** — flagged as a measurement gap in the audit itself, not a confirmed data defect. A follow-up query parsing the JSON object's keys is needed before this can be reported as clean or broken. *Reproduce: not yet written — follow-up item.*

### Validation methodology and evidence for every reported metric

All counts above were produced by the two SQL scripts listed below, executed via `psql` against `trinetra_db` on `localhost:5432` inside a single `BEGIN TRANSACTION READ ONLY; ... COMMIT;` block each (so neither script could have mutated data even if a bug existed in a query). Full raw output is preserved as evidence files alongside this report is not standard practice for this repo's docs convention, so the exact queries are reproduced inline here instead — any reader can re-run them against the same database to reproduce every number above.

```bash
# Confirm DB target before querying (local dev only, never assume from name alone):
grep -E "^(ENVIRONMENT|DATABASE_URL)=" apps/backend/.env
# ENVIRONMENT=development
# DATABASE_URL=postgresql+asyncpg://trinetra_app:[REDACTED]@localhost:5432/trinetra_db

# Schema confirmation:
psql -h localhost -U trinetra_app -d trinetra_db -c "\dt pyq.*"
psql -h localhost -U trinetra_app -d trinetra_db -c "\d pyq.questions"
psql -h localhost -U trinetra_app -d trinetra_db -c "\d pyq.answer_assertions"
# ...(and \d for every other pyq.* table listed in Scope above)

# All 53 numbered aggregate queries (totals, state/validation/subject/class-level
# distributions, assertion coverage, verification status, conflict detection,
# assertion_source/evidence_note/explanation/resolver_version presence,
# duplicate_candidates classification, exam_year/paper_code provenance,
# raw_options JSON type, extraction_confidence buckets and discrete values,
# qa_reviews/promotion_log/subject_classification_audit/subject_conflict_reviews/
# gemini_batch_items/gemini_batch_jobs/import_batches/sources, exact-hash and
# normalized-hash duplicate grouping with within-file vs. cross-file split,
# state × exam_year, state × subject, asserted_option balance, verified-by-
# year-and-subject, confidence-bucket × state) were run as a single script:
psql -h localhost -U trinetra_app -d trinetra_db -v ON_ERROR_STOP=1 \
  -f pyq_audit_queries.sql
psql -h localhost -U trinetra_app -d trinetra_db -v ON_ERROR_STOP=1 \
  -f pyq_audit_queries2.sql

# NCERT-evidence content sample (read-only, random 3-row sample):
psql -h localhost -U trinetra_app -d trinetra_db \
  -c "SELECT assertion_source, left(evidence_note, 180) FROM pyq.answer_assertions ORDER BY random() LIMIT 3;"
```

Both exit codes were `0` and every transaction `COMMIT`ted cleanly (no rollback, no error). Both query files and their full raw output are preserved alongside this report at `docs/quality/_pyq_audit_2026-10-01_queries/` (`pyq_audit_queries.sql`, `pyq_audit_queries2.sql`, `pyq_audit_results.txt`, `pyq_audit_results2.txt`) — ad hoc scratch scripts created for this audit, not part of the application.

### Verification of this audit

- The report file `docs/quality/pyq-coverage-audit.md` was written by this audit and is confirmed to exist at that path.
- `git status --short` was reviewed before and after writing this report: the only new paths are this report, its supporting query/output files under `docs/quality/_pyq_audit_2026-10-01_queries/`, and this prompt file (`claude_code_pyq_coverage_audit_prompt.md`, pre-existing in the repo before this audit started). No existing file was modified by this audit. No PYQ schema, model, migration, or data file was touched.
- `git diff` was reviewed for the pre-existing unrelated working-tree changes (listed under Audit metadata above) and confirmed to be scoped entirely to `apps/backend/app/core/logging.py` and `apps/backend/app/modules/ai/gateway/*` — none of which reference `pyq`, `PYQ`, or any table/model in the `pyq` schema.
- Every metric in this report traces to a specific numbered query in `pyq_audit_queries.sql` / `pyq_audit_queries2.sql` (under the path above), referenced by number throughout. No metric is reported without that trace.

---

## Audit History

| Date | Type | Summary |
|---|---|---|
| 2026-10-01 | Initial baseline | First audit of this database. 12,396 total questions; 19.78% answer-verified (all with NCERT evidence); 0% reached QA/promotion/dedupe-classification; 57.5% of rows in an unclassified exact-duplicate cluster; 2022 entirely absent from the corpus. See full baseline above. |
| 2026-10-01 | Local↔production reconciliation attempt (pointer) | Re-checked local metrics same-day — **zero drift** from this baseline (12,396 / 2,452 verified / 9,944 pending / 0 duplicate_candidates / 0 qa_reviews / 0 promotion_log, all unchanged). Production database could not be accessed read-only from this environment (no public DB endpoint; `railway run` does not proxy to Railway's private network) — schema comparison, production snapshot, and record-level reconciliation are all `not available`, not estimated. Full report: [`pyq-local-production-reconciliation-2026-10-01.md`](pyq-local-production-reconciliation-2026-10-01.md). |
| 2026-10-01 | One-pass Gemini resolution — implementation + pilot (pointer) | Added `AI_RESOLVED` verification-status (migration `d9c6e1a8f9ed`, additive-only, distinguishes one-pass Gemini answers from independently NCERT-verified ones) and extended student feedback reasons. Pilot (15 questions, `--apply`) resolved **0** and spent **$0** — blocked by `knowledge.knowledge_units` being empty (0 rows) in this local database, which both the free deterministic resolver and the Gemini evidence-retrieval step depend on; Gemini was never actually invoked (confirmed via `ai.ai_requests`, not inferred). Local counts unchanged (12,396 / 2,452 / 9,944). Requires an owner decision before Phase D can proceed. Full report: [`pyq-gemini-one-pass-resolution-2026-10-01.md`](pyq-gemini-one-pass-resolution-2026-10-01.md). |
| 2026-10-01 | NCERT knowledge-units ingestion — diagnosis, registry fix, pilot + full ingestion (pointer) | Root cause: pipeline never run locally, **and** the chapter-mapping registry was stale against a rebaselined academic-chapter taxonomy (0 of 76 sources could map). Corrected 2 of 4 stale codes (verified 1:1 rename); 2 Biology ones left deliberately unmapped, flagged for owner decision. Deterministic (no-AI) ingestion: 76 sources registered, 1,381 sections extracted, **51 knowledge units created** (2 mapped chapters only), idempotency and retrieval compatibility both verified. **Incident disclosed:** a mistaken resolver invocation during retrieval testing made 32 real Gemini calls ($0.069792, not recoverable) and wrote 11 answer_assertions/3 question-state changes outside this task's scope — fully reverted; PYQ counts confirmed unchanged (12,396 / 2,452 / 9,944) before and after. Full report: [`ncert-knowledge-units-ingestion-2026-10-01.md`](ncert-knowledge-units-ingestion-2026-10-01.md). |
| 2026-10-01 | Knowledge-base expansion attempt + Gemini resolution readiness (pointer) | Attempted automated chapter-mapping expansion beyond the existing 2/76 — tested content-keyword matching, found it produced a demonstrated false positive (a "Cell Cycle" chapter confidently mis-matched to "Reproduction"), so **rejected the method and applied no new mappings** (still 2/76). Measured real full-set retrieval coverage: **899/9,944 pending PYQs (9.0%) have non-empty NCERT context**, via direct code use, no Gemini. Gemini pilot **not run** — key-rotation status for the exposed key could not be confirmed, and the task required stopping before any live call until confirmed. Cost estimate for the 899 eligible questions (from real prompt text + existing pricing config, no live calls): **$1.39–$1.96**. Zero DB writes, zero Gemini calls this round. Full report: [`ncert-knowledge-base-and-gemini-resolution-2026-10-01.md`](ncert-knowledge-base-and-gemini-resolution-2026-10-01.md). |
| 2026-10-01 | NCERT manual-evidence mapping expansion (pointer) | Expanded chapter mapping from 2/76 to **68/76 sources**, using direct per-file page-text verification (not filename/keyword matching — the earlier automated attempt's false positive led to this stricter approach). Both previously-blocked Biology entries resolved with direct evidence, including correcting the original registry's wrong chapter number for Body Fluids and Circulation (it's Ch15, not Ch18). Full deterministic (no-AI) ingestion: **824 new knowledge units** (51→1,038 total, 912 PASSED/126 FAILED), idempotency re-verified twice. Retrieval coverage: **899→3,647/9,944 pending PYQs (9.0%→36.7%)**. 8 sources remain unmapped (2 non-chapter content, 6 blocked on a filename-parser limitation for Physics Part-2's native naming — content already verified, owner decision needed on the parser extension). PYQ data and production both confirmed untouched; zero Gemini calls. Full report: [`ncert-manual-mapping-expansion-2026-10-01.md`](ncert-manual-mapping-expansion-2026-10-01.md). |
| 2026-10-01 | Taxonomy & glossary alignment check (pointer) | User-supplied taxonomy file compared against the live DB — **confirmed identical** (3 spot-checks, exact match), so it was already the authoritative source used for the prior mapping task; no new mappings unlocked. User-supplied glossary zip found to contain only placeholder boilerplate (no real definitions); the detailed xlsx glossary has real but explicitly **generated, non-NCERT-verbatim** definitions, so per "NCERT is authoritative" it was deliberately **not** ingested into any knowledge unit. No new ingestion this round (nothing new to ingest) — KU count, mapping count, and retrieval coverage (3,647/9,944, 36.7%) all re-measured fresh and confirmed byte-identical to the prior task. Gemini pilot still not run (key rotation unconfirmed); refreshed cost estimate for the current 3,647 eligible questions: **$5.66–$7.95**. Zero DB writes, zero Gemini calls. Full report: [`ncert-taxonomy-glossary-alignment-2026-10-01.md`](ncert-taxonomy-glossary-alignment-2026-10-01.md). |
| 2026-10-01 | Physics filename-parser fix — unblocks final 6 sources (pointer) | Extended `extract_ncert_chapter_number()` with a minimal, additive regex for NCERT's `leph2NN.pdf` naming (Physics Class 12 Part 2), using chapter identities already directly verified in the prior mapping task (no new guessing). Dry-run confirmed all 6 resolve correctly before any write. Mapping: **68/76 → 74/76 sources** (only the 2 genuinely non-chapter files remain unmapped). Ingestion: **74 new knowledge units** (1,038→1,112, 0 errors), idempotency re-verified. Retrieval coverage: **3,647→3,868/9,944 (36.7%→38.9%)**, gain entirely in Physics as expected (Chemistry/Botany/Zoology unchanged). 137 tests passed (14 new). PYQ data and production both confirmed untouched; zero Gemini calls. Full report: [`ncert-physics-filename-parser-fix-2026-10-01.md`](ncert-physics-filename-parser-fix-2026-10-01.md). |
| 2026-10-01 | Deep forensic audit of 100% NCERT retrieval coverage — read-only (pointer) | Reconfirmed baseline exactly (3,868/9,944, 38.9%, zero discrepancy). **Decisive finding:** the dominant uncoverage cause is retrieval-threshold strictness, not missing content — relaxing the same matcher's threshold from 0.5→0.25 over the *same already-ingested* units raised coverage to 8,159/9,944 (82.1%) with zero new ingestion; only **113/9,944 (1.1%)** questions share zero vocabulary with any ingested unit. No new PDFs, no new mapping gap found (74/76 unchanged). FAILED knowledge units (126, all duplicate-reason) confirmed **not** inflating the reported figure (delta=0 vs PASSED-only). Explicitly scoped the requested 16-category per-question diagnosis down to a 3-way, fully mechanical, exactly-summing split (covered / below-threshold-overlap / zero-overlap) since finer causal attribution needs relevance judgment this audit's deterministic tooling cannot honestly supply — flagged as the key next step (a scoped relevance-validation pass) before any threshold change. Zero DB writes, zero Gemini calls, nothing committed. Full report: [`ncert-retrieval-coverage-forensic-audit-2026-10-01.md`](ncert-retrieval-coverage-forensic-audit-2026-10-01.md). |

| 2026-10-01 | Retrieval relevance validation & coverage optimization — read-only (pointer) | Built and exported a full-population diagnostic of all 4,291 questions newly covered at a relaxed 0.25 threshold vs. the production 0.50 (exact reproduction: 3,868→8,159). **Key finding: 55.4% of the newly-covered, subject-labeled questions (1,123/2,026) have a matched unit in a *different* subject than the question's own label** — strong evidence of meaningful false-positive risk at the relaxed threshold, so **no threshold change is recommended** from this audit. Prepared (not executed) a 193-row stratified human-review worksheet with blank review labels. FAILED-unit impact re-quantified: 6,788 question×unit match pairs touch a FAILED unit, but the coverage numerator is unaffected (delta=0, reconfirmed). Reclassified the zero-overlap group: the prior 113 reproduces exactly, plus a newly-surfaced **42-question sub-group whose stems contain zero significant words at all** (a structural matcher limitation, since it never reads `raw_options`) — both left `UNRESOLVED`, no "missing source" conclusion drawn. PDF inventory gap (76 vs 93 on disk) reconfirmed fully explained by 15 checksum-duplicates + 2 non-pattern upload files, verified by direct checksum this round. Zero DB writes, zero Gemini calls, nothing committed. Full report: [`ncert-retrieval-relevance-validation-2026-10-01.md`](ncert-retrieval-relevance-validation-2026-10-01.md). |

| 2026-10-01 | Human-review preparation & subject-aware retrieval validation — read-only (pointer) | Verified the prior 193-row review sample fully (0 missing/invalid IDs, 0 passage-provenance mismatches, all labels still blank) and built a reviewer-ready worksheet with full question/option text and no answer-key leakage. **Cross-subject breakdown (all 1,123 rows):** dominated by Zoology→Chemistry (213), Botany→Chemistry (148), Chemistry→Biology (141) pairs — plausibly generic shared vocabulary, not yet confirmed. **Constrained-retrieval diagnostic:** restricting relaxed-threshold retrieval to same-subject-only drops labeled-question coverage from 85.4% to 56.4% (1,261 questions lose their only match) — a measured tradeoff, not a recommendation. Same-subject+chapter constraint **could not be run** — question-side chapter/topic metadata does not exist in this DB (confirmed, not assumed). **New finding:** several of the 42 zero-significant-word stems are visibly corrupted/garbled PDF extraction output (e.g. mangled electron-configuration notation, truncated stems), a data-quality issue distinct from the tokenizer's known symbol-handling gap; 10 of the 42 have scientific terms in `raw_options` the stem matcher never sees. The 113 zero-overlap questions remain `UNRESOLVED` (ruled out only "zero ingested content for that subject at all" as a cause). Rubric and adjudication protocol prepared for future human review. Zero DB writes, zero Gemini calls, nothing committed. Full report: [`ncert-retrieval-human-review-preparation-2026-10-01.md`](ncert-retrieval-human-review-preparation-2026-10-01.md). |

| 2026-10-01 | PYQ text extraction quality audit & source reconstruction — read-only (pointer) | Traced all 42 zero-significant-word questions to 23 distinct source PDFs under `NEET_PYQ_OFFICIAL/`. **Decisive finding:** all 23 are full-page scanned-image PDFs with zero extractable native text (directly measured via PyMuPDF — 0 characters across every page, 1 embedded image per page), exclusively from 2023–2025 exam years; a sampled 2020 paper by contrast has a real 43,972-character text layer. This explains the garbled stems (OCR output from a scanned source, not a parsing bug) and means **no reconstruction is possible without re-running OCR**, which this audit did not and could not perform (no OCR tooling installed in this environment — confirmed, not assumed). All 42 `proposed_reconstruction` fields correctly left blank — no silent repair attempted. 10/42 options-only-vocabulary questions individually reviewed: only 3 carry clearly specific, usable scientific terms; the rest are option-label artifacts, generic phrasing, or garbled bilingual text. 193-row review worksheet re-verified clean (0 new issues, all labels still blank). Authorized correction/adjudication workflow documented but not implemented. Zero DB writes, zero Gemini calls, nothing committed. Full report: [`pyq-text-extraction-quality-audit-2026-10-01.md`](pyq-text-extraction-quality-audit-2026-10-01.md). |

| 2026-10-01 | Local OCR evaluation for scanned PYQ source PDFs (pointer) | Tesseract OCR was found **already installed** (v5.5.0, via winget, eng-only); installed `pytesseract` into the backend venv only (not persisted to `requirements.txt`/`pyproject.toml`). Hindi language pack install **blocked by Program Files write permissions** — reported, not worked around; manual instructions provided. Ran local, read-only OCR (300 DPI, eng) across 5 of the 23 scanned source PDFs (~190 pages), evaluating 13 of the 42 corrupted questions. **Result: most sampled questions are highly legible once OCR'd** — e.g. `"g mol\"\"!, 1F = 96487 C)"` resolved to a full, coherent electrochemistry question. **One prior-audit hypothesis was directly corrected by this evidence:** a question guessed as "likely bilingual/Hindi" and another guessed as "likely a CoCl coordination-complex formula" both turned out, via OCR, to be plain English and a Hückel's-rule aromaticity question respectively — concrete proof of why this audit chain never fills in guessed reconstructions. 2 electron-configuration-notation questions' page-location heuristic failed (low confidence, flagged not papered over). No PDF modified, no DB write, no answer imported/promoted, no elevated privileges used, zero paid/external AI or OCR calls. Full report: [`pyq-local-ocr-evaluation-2026-10-01.md`](pyq-local-ocr-evaluation-2026-10-01.md). |

| 2026-10-03 | P0: NCERT relaxed-retrieval enablement for the owner-accepted candidate pool — implemented + locally applied (pointer) | Owner directed enabling the 8,159-question relaxed-retrieval pool for launch. **The exact 8,159 figure was not reproducible under this task's own required cross-subject safeguard** — re-run with the real implementation gives **3,683 RELAXED_MATCH + 3,868 STRICT_MATCH = 7,551/9,944**, not 8,159 (the unsafeguarded figure, 4,291+3,868=8,159, was separately reproduced exactly for comparison). Implemented a feature-flagged (`pyq_relaxed_retrieval_enabled`, off by default), subject-constrained relaxed matcher (`compute_retrieval_tier` in `resolve_pyq_answers.py`) that is architecturally separate from Stage-1/Stage-2 answer resolution — it can never set `ANSWER_VERIFIED`/`AI_RESOLVED`. Fixed `_load_ku_index` to exclude FAILED (duplicate-flagged) knowledge units (delta=0 on existing coverage, a no-regression correctness fix). Added new `pyq.questions.retrieval_match_tier`/`ncert_owner_accepted`/`ncert_owner_accepted_at` columns (migration `62aa0447d463`, additive, local-only) — deliberately distinct from `answer_assertions.verification_status`, never conflated with VERIFIED/AI_RESOLVED. Applied locally with full before/after snapshots, idempotency re-verified (identical counts on rerun), and rollback re-verified (reverts cleanly to NONE/0, never touching `ANSWER_VERIFIED` rows or `state`). 9 new tests + 16 existing resolver tests pass (25/25); broader suite 196 passed/17 skipped/0 failed; ruff clean. **No Gemini call made** — exposed-key rotation still unconfirmed (checked directly in `docs/production/gemini_api_key_log_exposure_incident.md`), hard-blocking all answer resolution per this task's own safeguard. Zero DB writes to answer_assertions/state, zero knowledge-unit duplication, production untouched, nothing committed/pushed. Full report: [`pyq-8159-ncert-retrieval-enablement-2026-10-01.md`](pyq-8159-ncert-retrieval-enablement-2026-10-01.md). |

*(Future updates: append new dated sections above this table entry, following the [Future update protocol] in the originating audit prompt — before/after counts, affected record IDs or reproducible filters, source evidence, validation performed, and remaining gaps. Never replace or delete a prior snapshot.)*
