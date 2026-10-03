# NCERT Knowledge Base Expansion & Gemini PYQ Resolution — Readiness Report

**Date:** 2026-10-01
**Repository:** `ravishori/ai-neet-exam-app`
**Branch:** `feat/whatsapp-m2a-account-linking`
**Local database:** `trinetra_db` @ `localhost:5432`, `ENVIRONMENT=development` — reconfirmed fresh before any action.

## Executive summary

**Workstream A** (NCERT knowledge base): no new knowledge units were added this round. I attempted to extend chapter-mapping coverage beyond the 2 chapters mapped in this morning's prior task, using automated content-keyword matching against `academic.chapters` names — **this method was tested, proven unreliable (a demonstrated false positive), and deliberately not applied.** Instead, I measured real retrieval coverage across the full pending PYQ set using the existing, unmodified retrieval code: **899 of 9,944 pending PYQs (9.0%) now have non-empty NCERT retrieval context**, entirely from the 2 chapters already mapped this morning.

**Workstream B** (Gemini resolution): **blocked before any pilot call.** Key-rotation status for the Gemini API key (flagged as exposed and requiring rotation in an earlier session today) **could not be confirmed** — I have no mechanism to verify it without either asking the project owner directly or making a live API call, and the task explicitly prohibits the latter until rotation is confirmed. Per that explicit instruction, I stopped before Stage/Section B6 (the Gemini pilot) and completed only the safe, no-API-call preparation: resolver validation (already covered by existing tests), overwrite-protection confirmation, and a cost/batch-plan estimate computed from real prompt text and the existing pricing configuration (no live calls).

**No PYQ answer was generated or finalized. No Gemini API call was made. No database write occurred this round** beyond the read-only measurement queries and schema inspection already covered by this morning's work.

## 1. Mandatory safety checks (Section 2 of the task)

| Check | Result |
|---|---|
| Repository/branch/working tree | `feat/whatsapp-m2a-account-linking`, all prior uncommitted work preserved exactly — confirmed via `git status --short` before and after this round, identical file list, no changes lost or reverted. |
| Local database identity | `trinetra_db` @ `localhost:5432`, `ENVIRONMENT=development` — re-confirmed, not assumed from name alone (direct `current_database()`/`inet_server_addr()` query). |
| **Gemini key rotation** | **NOT CONFIRMED.** No evidence either way was available to me — I cannot read or compare key values (prohibited), and I have no external channel (e.g. Google Cloud Console access) to check rotation status. The only way to confirm would be the project owner stating it directly, which has not happened in this conversation. **Treated as unconfirmed per the task's own instruction: stopped before any Gemini API call.** |
| Secrets in output | None printed, logged, or committed this round — confirmed by not re-reading `.env`'s `GEMINI_API_KEY` value at all this round (unlike an earlier mistake in a prior task today, not repeated here). |
| Resolver not run in apply mode for testing | Confirmed — all retrieval/coverage measurement this round used `_load_ku_index`/`_match_units` directly (read-only, in-memory), never `scripts/resolve_pyq_answers.py --apply`. This explicitly avoids repeating the earlier-today incident where running the actual resolver script for a "quick test" caused real Gemini spend. |

## 2. Workstream A — Knowledge base expansion attempt

### A2 — Source inventory reconciliation (91 discovered vs. 76 registered)

Re-confirmed, not re-derived: `discover --dry-run` finds 91 NEET-pattern PDFs on disk; `discover` (apply) registers only 76 distinct ones, because 15 are exact-checksum duplicates of already-registered files (confirmed this morning — the `leph2dd/` subfolder contains duplicate copies of already-counted Physics chapters). This is the same 91→76 reconciliation already documented in this morning's `ncert-knowledge-units-ingestion-2026-10-01.md`; re-verified unchanged (`SELECT count(*) FROM ingestion.source_documents` → 76, identical).

### A3 — Chapter mapping expansion (attempted, rejected)

Current state (unchanged from this morning): 2 of 76 sources `MAPPED` (Chemistry Ch.4→`CHEMISTRY-U03`, Physics Ch.3→`PHYSICS-U12`), 74 `UNMAPPED`.

**Attempted method:** for each of the 74 unmapped sources, extract the first 3 pages of real PDF text and search for an exact (case-insensitive, prefix-stripped) match against every `academic.chapters.name` in the same subject. Candidates with exactly one match were treated as "high-confidence."

**Result:** 28 single-candidate matches, 7 multi-candidate (ambiguous), 39 no-candidate.

**This method was then verification-tested and found unsound.** `Biology/Class 11-Biology/.../chapter-10.pdf`'s single candidate was `BIOLOGY-U06: Reproduction` — but direct inspection of that PDF's actual page-1 text shows it is about **"Cell Cycle"** (verbatim: *"10.1 CELL CYCLE... Cell division is a very important process..."*), not Reproduction at all. The false match is almost certainly caused by running headers/footers or other repeated text shared across a bound unit's pages, not genuine chapter content. Given this directly-proven failure on the very first manually-checked case, **none of the 35 proposed candidates (28 single + 7 multi) were applied, and none are presented as even tentative proposals** — the method itself is not trustworthy enough to produce evidence-based candidates, let alone auto-apply them. This is a materially different (and more cautious) conclusion than simply "ambiguous, needs owner review": the single-candidate matches looked confident and were still wrong.

**What this means:** mapping coverage remains exactly 2/76 sources. Expanding it safely requires genuine per-file manual verification (reading each PDF's actual title page / chapter heading, not automated keyword search against page-preview text) — a legitimate, bounded curation task, but one this session's automated approach could not safely shortcut. This is reported as a limitation, not resolved.

### A6 — Coverage measurement (real, full-set, no Gemini)

Using `_load_ku_index()` + `_match_units()` directly against **all 9,944 currently-pending PYQs** (not a sample):

| Subject | Pending | With retrieval context | % |
|---|---:|---:|---:|
| (null — unclassified, 2020/2023/2024/2025 batches) | 5,598 | 511 | 9.13% |
| Chemistry | 1,118 | 190 | 17.0% |
| Botany | 1,053 | 129 | 12.25% |
| Physics | 1,089 | 45 | 4.13% |
| Zoology | 1,086 | 24 | 2.21% |
| **Total** | **9,944** | **899** | **9.04%** |

Elapsed: 17.7 seconds for the full set (in-process, no network calls). **This is retrieval coverage, not answer correctness** — a non-empty match means the mechanical grounding check found shared, source-overlapping vocabulary between the question and at least one of the 51 knowledge units; it is not evidence that the retrieved material actually supports the correct answer option. No claim of correctness is made here.

The non-trivial coverage outside the "obviously related" subjects (e.g. 511 unclassified-subject questions matching) is expected: those 2 mapped chapters (Current Electricity, Chemical Bonding) share general scientific vocabulary with some questions from other topics, and the unclassified-subject PYQs (61% of the corpus, per this morning's baseline audit) include unlabeled Physics/Chemistry questions from 2020/2023/2024/2025 that could legitimately touch these 2 topics.

## 3. Workstream B — Gemini resolution readiness (no live calls made)

### B1 — Resolver behavior (validated by reading code + existing passing tests, not re-derived)

- **Pending definition:** `pyq.questions.state = 'ANSWER_PENDING'` — unchanged.
- **Answer assertion schema:** `pyq.answer_assertions.verification_status` now supports `ASSERTED | VERIFIED | DISPUTED | AI_RESOLVED` (migration `d9c6e1a8f9ed`, applied this morning, re-confirmed still at head: `alembic current` → `d9c6e1a8f9ed`).
- **Verified-answer protection:** `resolve_up_to()`'s cursor query (`WHERE state = 'ANSWER_PENDING'`) structurally never selects an already-verified or already-AI_resolved question — confirmed by the existing, currently-passing test `test_resolve_up_to_never_touches_already_verified_question` and `test_stage2_never_invoked_for_already_verified_question` (both in today's 143-passed run, Section 5).
- **Retrieval selection:** `_load_ku_index()` + `_match_units()` (mechanical word-overlap against `knowledge.knowledge_units`), confirmed via this round's own direct use of that exact code.
- **Gateway/model:** `AIGateway` + `GeminiProvider`, model `gemini-3.6-flash` (from `settings.gemini_model`, confirmed via `.env` variable name only — value never re-read this round).
- **Retry/rate-limit/timeout:** existing `app/modules/ai/gateway/errors.py` classification (`PROVIDER_TIMEOUT`, `PROVIDER_RATE_LIMITED`, etc.) and the phone/agent-level throttling already in the gateway — unchanged, not modified this task.
- **Run ID / provenance:** `run_id` parameter (added this morning) threads into `evidence_note` as `run=<id>; ...`; `resolver_version='pyq-resolver-v1-stage2'`; `assertion_source` embeds a content-hash digest of the evidence units used.
- **Batch limits/resume:** `resolve_up_to(max_total=N)` with cursor-based pagination (`created_at, id`) — resumable by construction, already tested (`test_resolve_up_to_respects_max_total_and_oldest_first_order`).

### B2 — One-pass policy (already implemented this morning, re-confirmed unchanged)

`AI_RESOLVED` (not `VERIFIED`) is written for single-clean-answer Stage 2 outcomes; `DISPUTED` for multi-option conflicts; nothing is ever promoted to `VERIFIED` automatically. No second AI pass exists in the code path. Confirmed by re-reading `resolve_stage2_batch()` — unchanged since this morning.

### B3/B4 — Context use and technical validation (code-level, confirmed unchanged)

Evidence is capped (`EVIDENCE_UNIT_CAP=8` knowledge units per question — bounded, not whole-textbook), the system prompt instructs the model to use only the given excerpts and return an empty list rather than guess, and `parse_json_response` + explicit option-membership filtering (`label in option_texts`) reject malformed/invalid responses — all unchanged from this morning's implementation and still covered by the existing passing test suite (Section 5).

### B5 — Cost and batch plan (estimated from real prompt text + existing pricing config; **no live Gemini calls made**)

Eligible population (pending AND has retrieval context): **899** questions.

Two independent estimation methods, both using the actual `build_user_prompt()` function and the real, already-configured pricing table (`app/modules/ai/gateway/pricing.py`, `gemini-3.6-flash`: $0.75/1M input tokens, $3.75/1M output tokens):

| Method | Basis | Avg input tokens/request | Avg output tokens/request | Estimated total cost (899 requests) |
|---|---|---:|---:|---:|
| A — character-count heuristic | 30-question sample, real prompt text, `chars/4` approximation | ~1,468 | 120 (assumed upper bound) | **$1.39** |
| B — real observed ratio | Ground truth from this morning's accidental 32-call incident (83,987 input / 1,814 output tokens actually measured) | ~2,625 | ~57 | **$1.96** |

**Estimated range: $1.39–$1.96 for all 899 currently-eligible questions**, clearly labeled as an estimate (char-based approximation, not exact tokenization; actual per-request token counts vary with evidence-unit size). This is **not** a promised final cost — actual spend depends on real tokenization and response length at call time.

**Batch plan (not yet executed):**
- Batch size: existing `BATCH_SIZE=500` (Stage 1 page size); Stage 2 only processes whatever Stage 1 leaves pending within that page — no separate batch parameter needed, already bounded by `max_total`.
- Rate-limit strategy: existing gateway-level handling (unchanged).
- Retry/backoff: existing `ProviderError` classification with `retryable` flag (unchanged) — Stage 2 does not retry a failed/fallback response, it marks the question unresolved (by design, "never guess").
- Budget: no hard dollar-cap exists in code today — would need to be enforced externally (e.g. running in small `--max-total` increments and checking `ai.ai_requests` cost between runs) unless the owner wants a code-level budget guard added (not built this round — out of scope without explicit request).
- Resume/checkpoint: `resolve_up_to`'s cursor pagination is inherently resumable; re-running with the same or larger `max_total` never reprocesses an already-resolved question (state no longer `ANSWER_PENDING`).

### B6 — Gemini pilot — **NOT RUN**

**Blocked.** Per Section 2's safety-check table: Gemini key rotation status is unconfirmed, and the task explicitly states *"If key rotation cannot be confirmed, stop before making any Gemini API calls."* No pilot request was made. This is the single, precise, actionable blocker standing between this report and Section B6.

## 4. Student feedback (Section 6) — gap re-confirmed, unchanged

Re-verified by direct code inspection: `cms.content_reports.content_item_id` is a foreign key to `cms.content_items.id` **only** — there is no relationship anywhere in the schema from `ContentReport` to `pyq.questions`. A `pyq_year` field can appear in a `content_item`'s body **after** a PYQ is promoted into CMS content (`cms_router.py` line ~181), but since 0 PYQ questions have ever been promoted (confirmed this morning, re-confirmed unchanged: `pyq.promotion_log` still empty), there is currently no PYQ-origin content a student could report against. This is the identical gap already documented this morning — not re-designed or re-built this round, since nothing about it has changed and building new frontend/DB workflow was explicitly out of scope without separate authorization.

## 5. Tests, lint, type-check

```
.venv/Scripts/python.exe -m pytest app/modules/ingestion/tests/ tests/test_pyq_resolver_worker.py tests/test_question_solving.py tests/test_credential_redaction.py -q
143 passed, 17 skipped, 7 warnings in 86.55s
```
No code was changed this round (pure read-only investigation and measurement), so no new lint/test targets exist beyond what this morning's two reports already covered and verified clean. `ruff check` was not re-run on unchanged files. `mypy`: still not installed in this `.venv` — not run, consistent with every prior task today.

**Pre-existing, unrelated failures** (from the full-suite run earlier today, bisected and confirmed pre-existing, not regressions): `test_prod_5k_run_002_dry_run.py` (2), `test_identity_state_city.py`/`test_locations_api.py` (2), `test_python_mcq_engine_010.py` (3) — unchanged, not re-touched this round.

## 6. Data integrity

Baseline re-confirmed at the start and end of this round, identical both times:
```
pyq.questions: total=12,396, verified=2,452, pending=9,944, conflict=0
pyq.answer_assertions: 2,452
knowledge.knowledge_units: 51 (unchanged — no new ingestion this round)
ingestion.source_documents: 76 (unchanged)
```
**Zero database writes occurred this round** beyond read-only `SELECT` queries. No rollback was needed because no write was attempted.

## 7. Production, secrets, and scope confirmation

- Production was never accessed, queried, or modified.
- No Gemini API call was made (confirmed both by design — all retrieval tests used direct in-process matching, never the resolver script in apply mode — and by evidence: no new `ai.ai_requests` rows this round).
- No secret value was printed, logged, or committed. The exposed key from the earlier-today incident was not re-read.
- Nothing was committed, pushed, or merged.

---

## Next actions requiring owner approval

1. **Confirm Gemini key rotation status directly** (the precise, single blocker for Workstream B). Once confirmed, the B6 pilot (small sample, estimated $1.39–$1.96 range for the full 899-eligible set, pilot itself would be a small fraction of that) can proceed.
2. **Chapter-mapping expansion decision**: automated content-matching was tried and rejected as unsafe (Section 2). Expanding beyond the current 2/76 mapped sources requires either (a) manual, per-file chapter-title verification by a human reviewer, or (b) a more rigorous automated method than page-preview keyword search (e.g., requiring the match to appear specifically within a detected title/heading section rather than anywhere in the first 3 pages) — not attempted this round, flagged as a possible follow-up.
3. **The 2 previously-blocked Biology mappings** (Photosynthesis, Body Fluids & Circulation → candidate `BIOLOGY-U04`/`BIOLOGY-U05`) remain unresolved, unchanged from this morning — still awaiting an owner curriculum decision.
4. **No code-level Gemini spend budget guard exists** — if the owner wants a hard-stop dollar/request cap enforced in code (rather than manually checking `ai.ai_requests` between runs), that would need to be built as a separate, scoped change before B7 (full-scale processing).

## Related audit update

`docs/quality/pyq-coverage-audit.md` updated with a dated pointer to this report (Audit History table) — prior baseline and all history preserved, unchanged.
