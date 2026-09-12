# FACTORY-P3 Implementation — Controlled AI Generation Pilot

**Status:** IMPLEMENTATION COMPLETE · Live ~100-Q pilot **BLOCKED** (Anthropic credit balance) · 2026-09-01  
**Scope:** Blueprint-driven AI → deterministic validation → DRAFT ContentItem/ContentVersion only.  
**Non-goals:** Auto-submit / auto-approve / auto-publish · AI scientific judge · semantic/vector dedupe · Celery/Kafka · mass 1k+ generation · Content Factory UI.

---

## Architecture

```
QuestionBlueprint (GREEN / generation_eligible)
        ↓ pin blueprint_id + blueprint_version
GenerationJob (GENERATE) → GenerationRun
        ↓
AIGateway (Claude provider only; FallbackProvider rejected)
        ↓ prompt_version = neet_mcq_factory_v1
parse JSON → QuestionBody schema
        ↓
deterministic validation + stem-hash dedupe
        ↓
ContentItem + ContentVersion (status/workflow = DRAFT)
        + GenerationCandidate lineage row
```

P1 owns batch/job/run. P2 owns blueprints. P3 only *creates new DRAFT questions*. ECAEP remains the only path to PUBLISHED.

---

## Generation flow

1. `POST /api/v1/cms/content-batches/{batch_id}/generate` (`content.factory.execute`)
2. Eligibility: active GREEN blueprint, hierarchy, objective, family, difficulty, provenance policy, target within pilot caps
3. Attach blueprint to batch; create/idempotent job with **pinned** `blueprint_id` + `blueprint_version`
4. Create run; mark RUNNING
5. Loop until **target_count valid unique DRAFTs** or bounds hit:
   - AI Gateway generate
   - parse / validate / dedupe
   - create DRAFT or record candidate failure
6. Complete run with accurate counters; never submit/approve/publish

### Target-count semantics (chosen)

**`target_count` = desired valid unique DRAFT questions** (not raw attempts).  
Max attempts = `ceil(target × factory_max_pilot_attempt_multiplier)` (default 2.0).  
Shortfall → stop with `ATTEMPT_LIMIT` / `BUDGET_EXCEEDED` / `PROVIDER_BLOCKED` — no endless retry.

---

## AI Gateway integration

- Reuses existing `AIGateway` + `ClaudeProvider` / `FallbackProvider`
- Agent type: `CONTENT_FACTORY_MCQ`
- Fallback output is **rejected** (`FALLBACK_NOT_ALLOWED`) — never labeled as Claude
- Usage/cost logged via gateway `AIRequestLog` (no secrets stored on questions)
- Provider/model recorded on candidate + `ContentVersion.model_used`

**ORM note:** Gateway commits per call. Generation snapshots IDs before commits and re-loads batch for counters. Scripts/services must import `app.modules.knowledge.models` so `content_versions.knowledge_unit_id` FK metadata resolves.

---

## Prompt versioning

| Constant | Value |
|----------|--------|
| `PROMPT_VERSION` | `neet_mcq_factory_v1` |
| `GENERATOR_VERSION` | `factory_p3_v1` |
| Source | `app/modules/cms/prompts/factory_mcq.py` |

Stored on versions/candidates — full prompt body is **not** duplicated onto every question.

---

## Provenance

- Blueprint / batch source tier: `ai`
- Tags include `provenance:ai`
- Never claims NTA / NCERT / official / authoritative merely because the concept is NCERT-aligned

---

## Validation (deterministic only — no AI judge)

| Check | Behavior |
|-------|----------|
| Structure | 4 unique options, one correct, explanation |
| Schema | Existing `QuestionBody` |
| Difficulty | Forced to blueprint difficulty |
| Answer ↔ explanation | Letter contradiction → reject |
| Academic | Blueprint hierarchy must resolve |
| Malformed JSON / markdown fences | `FAILED_PARSE` — no silent repair |

---

## Duplicate detection

| Layer | Mechanism |
|-------|-----------|
| In-batch | In-memory stem hash set |
| Cross-item (concept) | Normalized stem SHA-256 vs existing question bodies |
| DB | Partial unique `(concept_id, stem_hash)` where candidate `CREATED` |

**Not implemented:** semantic / embedding similarity (documented limitation; planned for P4).

---

## Idempotency & concurrency

- Batch/job keys remain idempotent (P1)
- Candidate unique constraint prevents double CREATED same stem/concept
- IntegrityError on create → counted as duplicate, no orphan (rollback)

---

## Retry & budget

| Control | Default |
|---------|---------|
| `factory_max_pilot_generation_count` | 100 |
| `factory_max_sync_generation_count` | 25 (HTTP sync cap) |
| `factory_max_pilot_attempt_multiplier` | 2.0 |
| `factory_max_pilot_cost_usd` | 30.0 |

Permanent provider failures (credit/auth) → `PROVIDER_BLOCKED` (stop immediately).  
Transient errors → continue within attempt budget.  
CLI pilot uses `sync_cap=False` (up to 100).

---

## Sync vs background

**Decision:** Synchronous generation for the pilot.

- HTTP: capped at 25 questions per request (timeout-safe)
- CLI script: up to 100 for diversified pilot
- No Celery/Kafka introduced

---

## Content creation safety

- `ContentWorkflowService.create_item(..., commit=False)` then single commit with candidate
- Status forced DRAFT; safety error if not
- Titles derived from stem — never “official NTA/NCERT”
- Does not mutate existing items / versions / reviews

---

## RBAC / Security

- Permission: `content.factory.execute`
- Students: 403
- Untrusted blueprint text cannot override system prompt safety rules
- Errors redacted via existing AppError patterns; no API keys in payloads

---

## Tests

`tests/test_content_factory_p3.py` (mocked `ScriptedProvider`):

- Valid generation → DRAFT + lineage metadata
- Malformed JSON / duplicate stems
- Fallback stop
- Transient then success
- Credit → `PROVIDER_BLOCKED`
- Ineligible blueprint blocked
- Student RBAC 403

P1 + P2 regression included in factory test suite.

---

## Pilot execution

See `CONTENT_FACTORY_P3_PILOT_RESULTS.md`.

Live ~100-Q run is **BLOCKED** until Anthropic credits are available. Do **not** fabricate DRAFT questions to satisfy the count.

Re-run when unblocked:

```bash
cd apps/backend
# smoke (5 Q):
$env:FACTORY_P3_SMOKE="1"; .\.venv\Scripts\python.exe scripts\run_factory_p3_pilot.py
# full ~100:
Remove-Item Env:FACTORY_P3_SMOKE -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe scripts\run_factory_p3_pilot.py
```

---

## Known limitations

1. No semantic dedupe
2. No AI scientific certification (P4)
3. Sync HTTP capped at 25
4. Gateway mid-loop commits require ID snapshots
5. Live pilot blocked on provider billing in this environment
6. CoverageSlice `generated` counters may need P4 reconciliation pass

---

## Recommended FACTORY-P4

Automated QA gates + GREEN/YELLOW/RED · database-backed / stronger dedupe · sampling prep — **not** 1k/10k/100k scale generation yet.
