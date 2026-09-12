# NEET Content Factory — Data Model Proposal

**Status:** Proposal only · **No migrations in this wave** · 2026-09-01

Maps proposed entities to what exists in TALOS today and what is minimally required for factory scale.

---

## 1. Existing entities (keep)

| Entity | Schema | Role |
|--------|--------|------|
| `ContentItem` | `cms` | Question (and other types) identity, status, tags, concept_id, slug |
| `ContentVersion` | `cms` | Body JSONB, workflow_state, `model_used`, `prompt_version`, cost, confidence, singular KU convenience columns |
| `ContentVersionKnowledgeUnit` | `cms` | Multi-KU lineage |
| `ContentReview` | `cms` | Human approve / request_changes |
| `ContentReport` | `cms` | Student/staff reports |
| `KnowledgeUnit` | `knowledge` | Structured facts from ingestion |
| `IngestionJob` | `ingestion` | PDF pipeline (not general Q-gen) |
| Academic hierarchy | `academic` | Subject→Chapter→Topic→Concept→MicroCompetency |
| `AuditLog` | `system` | Cross-cutting actions |
| `AIRequestLog` | `ai` | Per-call AI observability |

**Question body (JSONB):** stem, options[A–D], correct_option, explanation, difficulty — validated by `QuestionBody` / `assert_body_publishable`.

---

## 2. Entity decision matrix

| Proposed entity | Status | Verdict | Why |
|-----------------|--------|---------|-----|
| **ContentBatch** | Missing | **MUST (P1)** | Group production, quotas, certification, rollback scope |
| **ContentSource** | Partial (tags / model_used strings) | **MUST (P1)** | Explicit source tier + claim level; prevent false “official” labels |
| **SourceDocument** | Partial (ingestion sections) | **SHOULD** | Tier-1/2 document registry; reuse ingestion where possible |
| **SourceLocation** | Partial | **SHOULD** | Page/section anchors for audit |
| **KnowledgeUnit** | Present | **Reuse** | Grounding for AI-gen; expand coverage |
| **LearningObjective** | Missing | **SHOULD (P2)** | Finer than Concept for blueprints without exploding Concept table |
| **QuestionFamily** | Missing | **MUST (P2)** | Taxonomy of cognitive/item types (code + name) |
| **QuestionBlueprint / Template** | Missing | **MUST (P2)** | Parameterized generation unit; idempotency anchor |
| **QuestionVariant** | Missing as entity | **NICE** | Prefer blueprint params + parent_question_id FK over separate table initially |
| **GenerationJob** | Missing | **MUST (P1)** | Async work unit with state machine |
| **GenerationRun** | Missing | **MUST (P1)** | Attempt under a job (model, tokens, cost, error) |
| **QAResult** | Partial (`ai_check_report` JSON) | **MUST (P4)** | Structured gate outcomes queryable by batch |
| **QualityScore / tier** | Missing | **MUST (P4)** | GREEN/YELLOW/RED (+ optional numeric) |
| **ReviewSample** | Missing | **MUST (P5)** | Drawn sample membership + SME outcome |
| **BatchCertification** | Missing | **MUST (P6)** | Evidence package + certifier decision |
| **ContentRelease** | Missing | **SHOULD (P6)** | Immutable release snapshot metadata |

**Unnecessary now:** separate microservice DBs, per-tenant content schemas, full knowledge-graph nodes beyond Concept/KU.

---

## 3. Minimal ContentBatch (implemented P1)

See `CONTENT_FACTORY_P1_IMPLEMENTATION.md`. Batch ↔ blueprint join added in P2 (`content_batch_blueprints`).

## 3b. Planning entities (implemented P2)

See `CONTENT_FACTORY_P2_IMPLEMENTATION.md` for LearningObjective, QuestionFamily, QuestionBlueprint, CoverageSlice.

---

## 3-legacy sketch (superseded by P1/P2)

Suggested columns (illustrative — historical):

- `id`, audited columns  
- `code` (unique human key, e.g. `physics-electrostatics-2026-001`)  
- `subject_id` / optional `chapter_id`  
- `source_tier` (`authoritative|licensed|human|ai|derived`)  
- `status` (`CREATED|GENERATING|QA|SAMPLING|CERTIFIED|RELEASE_CANDIDATE|RELEASED|QUARANTINED|FAILED`)  
- `quota_json` (targets by difficulty/family)  
- `generator_policy_version`  
- `stats_json` (counts by QA tier)  
- `idempotency_namespace`

Link questions via `content_items.batch_id` (nullable FK) **or** join table `content_batch_items` (preferred to avoid polluting non-factory content).

---

## 4. GenerationJob / GenerationRun (sketch)

**Job:** batch_id, blueprint_id (nullable until P2), requested_count, status, coverage_slice_json, created_by  

**Run:** job_id, attempt_no, model, prompt_version, input_hash, output_item_ids[], token/cost fields, error_code, started_at, finished_at  

Idempotency key example:  
`hash(batch_id + blueprint_id + normalized_params + content_schema_version)`

---

## 5. Provenance metadata (minimum on every factory question)

| Field | Purpose |
|-------|---------|
| `source_tier` | Authority class |
| `source_id` / document version | Traceability |
| `batch_id` + `job_id` + `run_id` | Rollback / quarantine |
| `blueprint_id` / `family_code` | Diversity & dedupe class |
| `concept_id` | Academic mapping (existing) |
| `knowledge_unit_id(s)` | Grounding when AI |
| `model_used` + `prompt_version` | Model lineage (existing columns; must be populated) |
| `generation_cost_usd` | Cost observability (existing) |
| `qa_tier` + latest `QAResult` ids | Release eligibility |

Existing Batch A pattern (`model_used=human-authored-batch-a`, tags) is a **proto-provenance** — formalize, don’t invent official claims.

---

## 6. Question family taxonomy (codes, not content)

### Physics (examples)
`direct_concept`, `formula_application`, `numerical`, `ratio_scaling`, `graph`, `vector`, `multi_step`, `experimental`, `misconception`

### Chemistry
`conceptual`, `numerical`, `reaction_product`, `periodic_trend`, `organic_mechanism`, `assertion_reason`, `structure`

### Biology (Botany/Zoology)
`ncert_factual`, `conceptual`, `statement`, `matching_style`, `diagram`, `process_sequence`, `assertion_reason`, `application`

Families are **configuration rows**, not hardcoded product logic.

---

## 7. Variant model (without synonym spam)

Prefer:

- Blueprint parameters (values, scenarios) → new instance  
- Optional `parent_item_id` + `variant_class` on ContentItem  

**Do not count as new educational value:** synonym-only paraphrase of stem with same options/answer.

Duplicate classes (see QA strategy): exact, normalized, semantic, answer-equivalent, family over-concentration.

---

## 8. Indexes & storage notes (planning)

Likely needed when implementing (not now):

- `(status, concept_id)` on content_items for practice pools  
- Unique `(batch_id, idempotency_key)` on generated drafts  
- Hash index/column on normalized stem for exact/normalized dedupe  
- Partial indexes for `qa_tier` / factory flags  
- Version retention policy (keep latest N + published snapshots)

Existing FTS/trigram indexes remain for PUBLISHED search.

---

## 9. Coexistence with current ~164 questions

- Nullable `batch_id` / no batch → legacy CMS / Batch A / SME path continues  
- Preserve all IDs, versions, reviews, publication states  
- Backfill `source_tier=human` or `ai` from tags/`model_used` in a later migration wave  
- No destructive rewrite of ECAEP statuses

---

## 10. Batch vs question lifecycle

| Level | States | Controls |
|-------|--------|----------|
| Batch | CREATED…RELEASED / QUARANTINED | Production eligibility, sampling, certify |
| Question | Existing ECAEP | Student visibility only via PUBLISHED |

Certification must **not** flip questions to PUBLISHED.
