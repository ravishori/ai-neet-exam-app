# FACTORY-P1 Implementation — ContentBatch / GenerationJob / GenerationRun

**Status:** COMPLETE · 2026-09-01  
**Scope:** Orchestration foundation only. No AI generation, no question body/status mutation, no auto-approve/publish.

---

## Architecture

Content Factory is an **orchestration layer around existing CMS/ECAEP**, not a second question lifecycle.

```
ContentBatch  →  GenerationJob  →  GenerationRun
     │                                    │
     │ (future waves)                     │ (future: AI / import)
     ▼                                    ▼
 existing ContentItem / ContentVersion → ECAEP DRAFT→…→PUBLISHED
```

**Invariant:** Batch `CERTIFIED` / `RELEASED` ≠ question `APPROVED` / `PUBLISHED`. Student visibility remains `ContentItem.status == PUBLISHED` only.

PostgreSQL schema: `cms` (modular monolith). No Celery/Kafka/ES/vector DB/microservices.

---

## Entities

### ContentBatch (`cms.content_batches`)

| Field | Notes |
|-------|--------|
| `batch_key` | Global unique idempotency key |
| `name`, `description` | Human labels |
| `subject_id` | Required FK → `academic.subjects` |
| `chapter_id` / `topic_id` / `concept_id` | Optional; hierarchy validated |
| `source_type` / `source_tier` | Provenance class (not NTA claims) |
| `target_count`, `created_count`, `failed_count`, `qa_pass_count` | Progress counters (created_* unused until P3+) |
| `status` | Batch orchestration state machine |
| AuditedBase | `id`, timestamps, `created_by`, soft delete, `version` |

**Deviation from audit sketch:** No `quota_json` / `stats_json` yet — counters are explicit columns; JSON quotas deferred to P2/P3. No `content_items.batch_id` FK in P1 (prefer join table later; avoids touching question rows).

### GenerationJob (`cms.generation_jobs`)

| Field | Notes |
|-------|--------|
| `batch_id` | FK CASCADE |
| `job_key` | Unique **within batch** |
| `job_type` | `GENERATE` \| `VALIDATE` \| `DEDUPE` \| `SAMPLE` \| `IMPORT` |
| `status` | `PENDING` → `RUNNING` → `SUCCEEDED`/`FAILED`/`CANCELLED` |
| counts | `requested` / `processed` / `success` / `failure` |
| `retry_count` / `max_retries` | Bounded retries (default max 3) |
| `error_code`, `started_at`, `completed_at` | Failure / timing |

### GenerationRun (`cms.generation_runs`)

| Field | Notes |
|-------|--------|
| `job_id` | FK CASCADE |
| `attempt_number` | Unique per job |
| `status` | `PENDING` → `RUNNING` → `SUCCEEDED`/`FAILED` |
| counts + `error_summary` | Bookkeeping |
| `execution_metadata` | JSONB — secrets/prompts stripped |

---

## State machine (batch)

```
CREATED → GENERATING → QA → SAMPLING → CERTIFIED → RELEASE_CANDIDATE → RELEASED
Any active → FAILED | QUARANTINED
FAILED → GENERATING | QUARANTINED
QUARANTINED → QA | FAILED
RELEASED → QUARANTINED
```

Enforced via `BATCH_TRANSITIONS` + `POST .../status` only (no generic PATCH).

Job/run transitions similarly explicit. Completing a run is **bookkeeping only** — does not create questions.

---

## API endpoints

All under `/api/v1/cms`:

| Method | Path | Permission |
|--------|------|------------|
| POST | `/content-batches` | `content.factory.create` |
| GET | `/content-batches` | `content.factory.view` |
| GET | `/content-batches/{id}` | `content.factory.view` |
| POST | `/content-batches/{id}/status` | `content.factory.create` |
| POST | `/content-batches/{id}/jobs` | `content.factory.create` |
| GET | `/content-batches/{id}/jobs` | `content.factory.view` |
| GET | `/generation-jobs/{id}` | `content.factory.view` |
| POST | `/generation-jobs/{id}/status` | `content.factory.execute` |
| POST | `/generation-jobs/{id}/runs` | `content.factory.execute` |
| POST | `/generation-runs/{id}/complete` | `content.factory.execute` |
| GET | `/generation-runs/{id}` | `content.factory.view` |

**Not implemented:** generate, approve, publish, certify (permission seeded for later).

---

## RBAC

New permissions (seeded; granted to `SUPER_ADMIN`, `ADMIN`, `CONTENT_MANAGER` only):

| Code | Purpose |
|------|---------|
| `content.factory.view` | Read batches/jobs/runs |
| `content.factory.create` | Create batch/job; batch status transitions |
| `content.factory.execute` | Runs/retries; job status; run complete |
| `content.factory.certify` | Reserved for FACTORY-P6 |

**Not granted** to `TEACHER`, `STUDENT`, `SUPPORT`.

---

## Idempotency & concurrency

- Unique `batch_key` (DB constraint).
- Unique `(batch_id, job_key)`.
- Unique `(job_id, attempt_number)`.
- Duplicate create returns existing row (`meta.idempotent=true`, HTTP 200).
- Concurrent creates race on unique constraint → loser returns winner (IntegrityError path).

---

## Retry model

- Failed job may request another `GenerationRun` until `retry_count >= max_retries`.
- Succeeded jobs cannot create further runs (`JOB_ALREADY_SUCCEEDED`).
- No automatic infinite retry; no AI execution in P1.

---

## Audit

Events via `system.audit_logs` (same session as mutations):

- `factory.batch.created` / `factory.batch.status_changed`
- `factory.job.created` / `factory.job.status_changed`
- `factory.run.created` / `factory.run.retry_requested` / `factory.run.completed` / `factory.run.failed`

Metadata includes actor, previous/new status, correlation `trace_id`. No secrets/prompts/student PII.

---

## Indexes

- batches: `batch_key` (unique), `status`, `subject_id`, `created_at`
- jobs: `(batch_id, job_key)` unique, `batch_id`, `status`
- runs: `(job_id, attempt_number)` unique, `job_id`, `status`

---

## Migration

- Revision: `e5f6a7b8c9d0` (revises `d4e5f6a7b8c9`)
- Reversible; creates only new `cms` tables
- Verified: upgrade → downgrade → upgrade on `trinetra_test_db`
- Applied on development `trinetra_db` (not production)

---

## Testing

`tests/test_content_factory_p1.py`:

- RBAC deny student/teacher
- Create batch+job+run lifecycle
- Idempotency batch/job
- State machine valid/invalid
- Retry limit
- Concurrent unique `batch_key`
- Audit actions present
- No factory-created questions

---

## Database safety (trinetra_db)

| Metric | BEFORE | AFTER |
|--------|--------|-------|
| Questions | 164 | 164 |
| PUBLISHED | 11 | 11 |
| DRAFT | 142 | 142 |
| IN_REVIEW | 11 | 11 |
| item checksum | `ce682b03848bf9b3a5b4058308ac6d62` | same |
| version body checksum | `6e1e7062fe5b94e9b83516750ff6bb1e` | same |
| review_count | 11 | 11 |

---

## Known limitations

- No link from batch → ContentItem yet (intentionally deferred).
- No worker / AI generation.
- Batch progress counters not auto-updated from question creation (no creation yet).
- Certify permission seeded but unused.
- No admin UI dashboard (API-only).

---

## Recommended FACTORY-P2

Knowledge & blueprint system: QuestionFamily, LearningObjective / concept metadata, QuestionBlueprint, coverage slice selector — so P3 jobs target blueprints instead of ad-hoc chapter counts. Hierarchy gap blocking (Optics lesson) remains a hard gate before mass generation.
