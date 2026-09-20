# FACTORY-P2 Implementation — Planning Layer

**Status:** COMPLETE · 2026-09-01  
**Scope:** LearningObjective, QuestionFamily, QuestionBlueprint, CoverageSlice + batch/job wiring.  
**Non-goals:** AI generation, question mutation, auto-approve/publish, mass syllabus seeding, admin UI.

---

## Architecture

```
Academic hierarchy (Subject→Chapter→Topic→Concept)
        ↓
LearningObjective  +  QuestionFamily
        ↓
QuestionBlueprint (versioned generation contract)
        ↓
CoverageSlice (demand targets)     ContentBatch ⇄ blueprint (M2M)
        ↓                                    ↓
   gap reports                    GenerationJob(blueprint_id, version)
                                         ↓
                              FACTORY-P3 (future AI generation)
```

P2 defines **WHAT** to generate. P1 still owns batch/job/run orchestration. ECAEP still owns question lifecycle.

### Batch ↔ Blueprint decision

| Option | Verdict |
|--------|---------|
| Force `batch.blueprint_id` single FK | Too rigid for multi-blueprint batches |
| **`content_batch_blueprints` join** | **Chosen** — Batch → Blueprint(s) → Job(s) |
| Job-only link | Insufficient for planning/attach before job create |

`GenerationJob.blueprint_id` + `blueprint_version` prepare the P3 contract: “generate N of Blueprint X @ version V”.

---

## LearningObjective

| Field | Notes |
|-------|--------|
| `objective_key` | Unique idempotency |
| `concept_id` | Required FK — no orphans |
| `title` | Min length 8 — capability statement |
| `learning_level` | recall/understand/apply/analyze/evaluate |
| `is_active` | Soft disable |

Missing concept → `HIERARCHY_GAP`.

---

## QuestionFamily

Reusable pedagogical pattern (no question text).

| Field | Notes |
|-------|--------|
| `family_key` | Unique |
| `applicable_subject_codes` | e.g. `PHYSICS` — subject-scoped |
| `cognitive_intent` | Short intent string |
| `difficulty_min` / `difficulty_max` | Project enum `easy\|medium\|hard` |
| `question_format` | `MCQ_4` |

Cross-subject misuse blocked at blueprint validation (`FAMILY_SUBJECT_INCOMPATIBLE`).

---

## QuestionBlueprint

Generation contract — **never stores question bodies**.

| Field | Notes |
|-------|--------|
| `blueprint_key` + `blueprint_version` | Unique pair; versioning via `new_version=true` |
| Full hierarchy FKs | subject/chapter/topic/concept all required |
| `learning_objective_id`, `question_family_id` | Required |
| `difficulty` | Must fit family range |
| `target_count` | Planned volume |
| `constraints` JSONB | format, correct_option_count=1, explanation_required, reasoning notes |
| `provenance_tier` | `authoritative\|licensed\|human\|ai\|derived` only |
| `generation_eligible` | Set only when validation GREEN |
| `last_validation` | Deterministic findings |

Creating with `new_version=true` supersedes prior DRAFT/ACTIVE rows for that key.

---

## Coverage model

`CoverageSlice` stores **targets**; counts computed at read time:

| Metric | Definition |
|--------|------------|
| `target` | Slice `target_count` |
| `existing` | QUESTIONS at concept (any status; DRAFT included) |
| `published` | `status == PUBLISHED` only |
| `planned` | Sum of active/draft blueprint `target_count` matching dimensions |
| `generated` | **0 until P3** (factory-produced not yet tracked) |
| `gap_vs_published` | max(0, target − published) |
| `demand_signal` | empty / low / met_or_over / overrepresented |

---

## Hierarchy validation

Hard rules:

- Missing concept → **BLOCK** (`HIERARCHY_GAP`) — never invent UUID
- Subject/chapter/topic/concept mismatch → `INVALID_HIERARCHY`
- Objective must belong to blueprint concept
- Family must list subject code
- Difficulty must be in family range and project enum

---

## Provenance

Reuse P1 tiers. Schema rejects `official_source` / `nta` / `ncert_official`. AI blueprints cannot inherit official NTA/NCERT labels.

---

## Versioning

Historical blueprint versions retained (`SUPERSEDED`). Jobs pin `blueprint_version` for P3 lineage.

---

## API

Under `/api/v1/cms`:

| Method | Path | Permission |
|--------|------|------------|
| POST/GET | `/learning-objectives` | create / view |
| POST/GET | `/question-families` | create / view |
| POST/GET | `/question-blueprints` | create / view |
| GET | `/question-blueprints/{id}` | view |
| POST | `/question-blueprints/{id}/validate` | create |
| POST | `/coverage-slices` | create |
| GET | `/content-coverage` | view |
| POST | `/content-batches/{id}/blueprints` | create |

Job create accepts optional `blueprint_id` (P1 endpoint extended).

---

## RBAC

Reuses FACTORY-P1 permissions. No new roles. Teachers/students denied.

---

## Audit

`factory.objective.created`, `factory.family.created`, `factory.blueprint.created`, `factory.blueprint.validated`, `factory.coverage_slice.created`, `factory.batch.blueprint_attached`.

---

## Migration

`f6a7b8c9d0e1` — reversible; upgrade→downgrade→upgrade verified on `trinetra_db`. Adds planning tables + nullable job blueprint columns. No question row changes.

---

## Testing

`tests/test_content_factory_p2.py` + P1 regression (11 tests combined). Editorial review regression separately.

---

## Database safety (trinetra_db)

BEFORE_P2 / AFTER_P2 checksums identical (see final report). Zero question modifications.

---

## Known limitations

- No admin UI
- No mass syllabus catalogue
- `generated` always 0 until P3
- No KU binding on objectives yet (concept is sufficient for P2)
- Blueprint create rejects RED entirely (no half-saved invalid plans)

---

## P3 interface contract

P3 receives:

```
blueprint_id + blueprint_version + requested_count + batch_id + job_id
```

and must **not** invent academic mapping, family, objective, provenance, or difficulty — those are frozen on the blueprint version.
