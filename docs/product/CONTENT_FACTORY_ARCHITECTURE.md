# NEET Content Factory — Architecture

**Status:** Architecture audit (documentation only) · **Date:** 2026-09-01  
**Environment verified:** development `trinetra_db` (read-only) + repository inspection  
**Principle:** Optimize **QUALITY × COVERAGE × TRACEABILITY × COST × SCALE** — not raw question count.

This document is the strategic north star for evolving TALOS from a manually managed CMS bank into a scalable, traceable NEET Content Factory. **No application code, schema, or question data was changed in this wave.**

---

## 1. Executive framing

**Business target (long-term):** ~100,000 high-quality questions per subject (Physics, Chemistry, Botany, Zoology) → ~400,000 total.

**Not the goal:** Unbounded AI generation that floods DRAFT and calls itself “content ready.”

**First principle:** Keep **question-level ECAEP** (`DRAFT → IN_REVIEW → APPROVED → PUBLISHED`) as the governance mechanism for student-visible content. Add **batch-level production & QA** so humans review *exceptions and samples*, not every obviously valid row.

Separate:

| Layer | Responsibility |
|-------|----------------|
| **Content production** | Coverage-driven generation / acquisition jobs |
| **Content quality control** | Deterministic + AI-assisted gates |
| **Human exception / sample review** | SME capacity on high-risk / sample items |
| **Publication** | Explicit APPROVED → PUBLISHED (student boundary) |

---

## 2. Verified current baseline (`trinetra_db`, 2026-09-01)

| Metric | Count |
|--------|------:|
| QUESTIONS (non-deleted) | **164** |
| PUBLISHED | **11** |
| DRAFT | **142** |
| IN_REVIEW | **11** (includes 10 Physics SME pilot + 1 other) |
| APPROVED | **0** |
| Batch A (`human-authored-batch-a` / batch tags) | **74** (64 DRAFT + 10 IN_REVIEW) |
| Physics SME pilot PHY-01–10 | **10 IN_REVIEW** |
| Subjects / chapters / topics / concepts | **4 / 30 / 36 / 41** |

CMS indexes present: PK + `ix_content_items_search_vector` (FTS) + `ix_content_items_search_text_trgm`.

**Implication:** Inventory is still pilot-scale. Factory architecture must coexist with this corpus without destructive migration.

---

## 3. Architecture map (as built today)

```
┌─────────────────────────────────────────────────────────────────┐
│ Admin UI: /admin/ai-review, /admin/content, /admin/coverage,    │
│           /admin/knowledge-units, /admin/ingestion, /admin/search│
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ CMS (modular monolith)                                          │
│  ContentItem + ContentVersion (+ KU refs)                       │
│  ContentWorkflowService (ECAEP)                                 │
│  EditorialReviewService (queue, packet, campaign, exact dupes)  │
│  assert_body_publishable (structural QUESTION gates)            │
│  Acquisition scripts (Batch A) — no ContentBatch entity         │
│  SearchService — FTS + pg_trgm (PUBLISHED QUESTION)              │
└───────┬─────────────────────┬─────────────────────┬─────────────┘
        │                     │                     │
┌───────▼───────┐   ┌─────────▼────────┐   ┌───────▼────────────────────────────┐
│ Academic      │   │ Knowledge        │   │ AI Gateway (FACTORY-P3.1)          │
│ Exam→…Concept │   │ KnowledgeUnit    │   │ Registry + explicit Router         │
│ MicroCompetency│  │ IngestionJob PDF │   │ Anthropic|OpenAI|Gemini|Mistral    │
└───────────────┘   └──────────────────┘   │ (no silent fallback)              │
                                           └────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│ Assessment / Learning — PUBLISHED-only pools & recommendations  │
└─────────────────────────────────────────────────────────────────┘
```

See `CONTENT_FACTORY_P3_1_MULTI_PROVIDER.md` for provider routing, lineage, and cost fail-closed rules.

### Reusable foundations

- Modular monolith + PostgreSQL + Alembic (ADR stack)
- ECAEP question lifecycle + RBAC permissions
- Structural QUESTION schema validation
- Versioned bodies + ADR-0025 KU linkage fields
- Editorial review packet / campaign / coverage guidance
- Knowledge units + ingestion pipeline (authoritative extraction path)
- FTS/trigram search for PUBLISHED questions
- Audit log pattern (`content.submit` / `review` / `publish` / `sme_edit`)

### Must evolve for factory scale

| Component | Why it does not scale as-is |
|-----------|----------------------------|
| No `ContentBatch` / `GenerationJob` | Orchestration lives in one-off scripts (Batch A runners) |
| Duplicate detection | Exact stem in Python over small windows (≤200–5000) |
| Editorial queue | Loads ≤500 items + versions; in-memory scoring |
| Practice pool selection | Loads all published IDs into memory then `random.sample` |
| AI QuestionGenerator provenance | Often missing `model_used` / cost / prompt version |
| Evaluator “similarity” | Placeholder empty matches |
| Human review model | Implicit 100% review; no sampling/certification entity |
| Coverage | Campaign targets (≥25/area) are planning aids, not demand engine |

---

## 4. Recommended target architecture

Keep the **modular monolith**. Add factory **domain objects and background jobs inside** existing apps (`cms` + `knowledge` + `ai`), not microservices.

```
Coverage Planner
      │
      ▼
ContentBatch (metadata + quotas + certification state)
      │
      ▼
GenerationJob(s)  ──► AI Gateway / SME import / licensed ingest
      │
      ▼
Question instances (ContentItem DRAFT) + provenance chain
      │
      ▼
Automated QA pipeline (Gates A–G) → GREEN / YELLOW / RED
      │
      ├── GREEN → eligible for sample / batch certification
      ├── YELLOW → exception queue
      └── RED → quarantine (no publish path)
      │
      ▼
Human Sampling + Exception Review (existing ECAEP on sampled/flagged items)
      │
      ▼
BatchCertification evidence → ReleaseCandidate
      │
      ▼
Per-question APPROVED → PUBLISH (existing gates) → PUBLISHED student pool
```

**Batch states control eligibility; question ECAEP controls student visibility.** A certified batch does **not** auto-publish.

---

## 5. Content production vs quality vs human vs publish

| Stage | Automation | Human |
|-------|------------|-------|
| Coverage gap selection | High | Configures quotas / priorities |
| Generation / acquisition | High | Authors Tier-1/2 sources; prompt/policy owners |
| Structural + mapping + duplicate gates | Deterministic first | Only on failures |
| Consistency / science assist | AI validator/judge | Exceptions + samples |
| Approve / request changes | Never automatic | Reviewers |
| Publish | Never automatic | Publishers |

---

## 6. Knowledge-first generation model

**Do not** scale with “Generate 100 Physics questions.”

Recommended chain:

```
Subject → Chapter → Topic → Concept (KU)
  → LearningObjective (new or lightweight on Concept)
  → QuestionFamily (type taxonomy)
  → QuestionBlueprint / Template (parameters + constraints)
  → GenerationRun (model, prompt_version, cost)
  → Question instance (ContentItem)
```

Generation is **demand-driven** by empty/underfilled cells in the coverage matrix (concept × difficulty × family).

---

## 7. Provenance chain (target)

```
SourceTier (authoritative | licensed | human | AI | derived)
  → SourceDocument / version (where applicable)
  → Academic node (chapter/topic/concept)
  → KnowledgeUnit (when grounded)
  → LearningObjective / Blueprint
  → GenerationJob / Run (model, prompt, cost, idempotency key)
  → ContentVersion (body + model_used + KU refs)
  → QAResult set (gate outcomes, scores)
  → ContentReview / sample decision
  → BatchCertification / ContentRelease
  → PUBLISHED ContentItem
```

**Today:** Partial (tags, `model_used`, KU id/version, audits, version history). **Missing:** batch/job entities, source document registry, blueprint IDs, structured QA results, certification.

**Never** invent official NTA/NCERT labels. Official vs practice content must remain distinguishable in metadata.

---

## 8. Vector / RAG decision (Content Factory)

| Need | Recommendation |
|------|----------------|
| Admin/student lexical search of PUBLISHED questions | **Keep PostgreSQL FTS + pg_trgm** (already present) |
| Near-duplicate / semantic duplicate at 100k | Start with **normalized hash + FTS/trigram**; add **pgvector later** only if measured false-negative rate requires it |
| Grounded tutoring / KU retrieval | Separate concern (ADR-0007 / G-015); **not required** to stand up the factory |

**Do not** introduce Elasticsearch or external vector DB for factory MVP without evidence that Postgres cannot meet SLAs.

---

## 9. Generation job shape

Request: *“Generate 500 Physics questions for Electrostatics”*

1. Authorize (`content.create` + factory job permission)
2. Create `ContentBatch` with quotas & coverage slice
3. Resolve concepts/KUs under chapter with deficit
4. Enqueue `GenerationJob`s (async worker / Redis queue — already Redis in stack)
5. Generate → validate → dedupe → score → attach QAResult
6. Quarantine RED; enqueue YELLOW to exception queue
7. Draw stratified sample for SME
8. Certification decision (human)
9. Eligible questions still require per-item APPROVED→PUBLISH

**Synchronous HTTP generation of hundreds is not acceptable** (latency, timeouts, partial writes). Use **queued jobs** with idempotency keys.

---

## 10. Failure & idempotency

- Model timeout / malformed JSON → retry with backoff; mark job attempt failed; no silent success
- Partial batch → durable job state; resume without duplicating via idempotency key  
  `(batch_id, blueprint_id, param_hash, attempt_policy)`
- Mapping failure → RED quarantine
- Never auto-publish on job completion
- Prefer soft quarantine / unpublish over hard delete for rollback

---

## 11. Publication safety

Unchanged product rule: **students see PUBLISHED only** (practice, mock, recommendations, published CMS browse).

Batch `RELEASED` means “allowed to enter human publish workflow,” not “visible to students.”

---

## 12. Security (factory)

- RBAC: separate `content.factory.run`, `content.certify`, existing `content.review` / `content.publish`
- Treat source documents as untrusted (prompt-injection hygiene)
- Model output never trusted for provenance claims
- Audit all batch/job/certify/publish actions
- No multi-tenancy for scale theatre (ADR: reserve `organizations`, don’t thread yet)
- Secrets stay in env; never in prompts logs body dumps

---

## 13. Observability

Metrics: generation throughput, job failure rate, duplicate rate, gate fail rates by type, model latency/cost, reviewer throughput, sample approval rate, publish rate, coverage fill %.

Traces: `traceId` on jobs; link to `AIRequestLog`.

Do not log student PII or full prompt secrets.

---

## 14. Legal / provenance safeguards

Architecture must store **source tier** and **claim level** explicitly. UI must show “not official NTA/NCERT” unless a verified Tier-1 record exists. Legal licensing of Tier-2 corpora is a **human/legal** decision outside engineering claims.

---

## 15. Anti-scope (do not build for 400k vanity)

- Microservices / Kubernetes for content factory alone
- External vector DB / Elasticsearch as day-one requirements
- Event-driven distributed choreography
- Multi-tenancy
- 12-agent orchestrator / Digital Twin / Diagram Agent
- Auto-approve or auto-publish
- Replacing ECAEP with batch-only governance for student visibility

---

## 16. Related documents

| Doc | Focus |
|-----|--------|
| [CONTENT_FACTORY_DATA_MODEL.md](./CONTENT_FACTORY_DATA_MODEL.md) | Entities & fields |
| [CONTENT_FACTORY_QA_STRATEGY.md](./CONTENT_FACTORY_QA_STRATEGY.md) | Gates, sampling, certification |
| [CONTENT_FACTORY_SCALE_PLAN.md](./CONTENT_FACTORY_SCALE_PLAN.md) | Stages 100→100k, performance |
| [CONTENT_FACTORY_ROADMAP.md](./CONTENT_FACTORY_ROADMAP.md) | FACTORY-P0…P8 waves |

Existing operational docs remain authoritative for current ECAEP: `ECAEP_HUMAN_REVIEW.md`, `CONTENT_ACQUISITION_BATCH_A.md`, `NEET_CONTENT_COVERAGE_PLAN.md`, `PRACTICE_AVAILABILITY.md`.
