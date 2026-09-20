# NEET Content Factory — Implementation Roadmap

**Status:** Planning · 2026-09-01 · FACTORY-P0–**P5** complete; live ~100 gen→QA→review still BLOCKED on Anthropic credits  
Execute **one FACTORY wave per dedicated Cursor prompt**.

Preserves: ECAEP question lifecycle, PUBLISHED-only student boundary, modular monolith, auth model.

---

## Global Definition of Done (factory waves)

| Gate | Requirement |
|------|-------------|
| Safety | No auto-approve / auto-publish |
| Provenance | Honest source_tier; no invented NTA/NCERT |
| Idempotency | Re-running jobs does not duplicate questions |
| Audit | Batch/job/certify/publish audited |
| Tests | Unit + workflow regression; practice PUBLISHED-only |
| Docs | Update this roadmap status + gap register |
| Scale honesty | Do not claim 100k readiness after pilot batches |

---

## FACTORY-P0 — Foundation audit

| Field | Content |
|-------|---------|
| **Status** | **DONE (docs)** — 2026-09-01 |
| **Objective** | Evidence-based architecture & plans |
| **Deliverables** | `CONTENT_FACTORY_*.md` suite |
| **Code/DB** | None |

---

## FACTORY-P1 — Content batch & generation job model

| Field | Content |
|-------|---------|
| **Status** | **DONE** — 2026-09-01 |
| **Priority** | **MUST HAVE** |
| **Complexity** | **HIGH** |
| **Objective** | Persist batches/jobs/runs; stop one-off script-only orchestration |
| **Deliverables** | Alembic `e5f6a7b8c9d0`; models/repos/services/APIs; RBAC `content.factory.*`; audits; tests; `CONTENT_FACTORY_P1_IMPLEMENTATION.md` |
| **Non-goals (held)** | Mass generation; auto-publish; item↔batch link; Celery/Kafka/ES |
| **Acceptance** | Met — see P1 implementation doc; question checksums unchanged (164 Q / 11 PUBLISHED) |
| **Next** | FACTORY-P2 |

---

## FACTORY-P2 — Knowledge & blueprint system

| Field | Content |
|-------|---------|
| **Status** | **DONE** — 2026-09-01 |
| **Priority** | MUST for 10k+ |
| **Complexity** | HIGH |
| **Objective** | Concept → objective → family → blueprint + coverage slices |
| **Deliverables** | Alembic `f6a7b8c9d0e1`; planning models/APIs; hierarchy-gap blocking; `CONTENT_FACTORY_P2_IMPLEMENTATION.md` |
| **Non-goals (held)** | Mass generation; syllabus-wide seed; admin UI |
| **Acceptance** | Met — checksums unchanged; P1 regression green |
| **Next** | FACTORY-P3 (smallest ~100-Q controlled pilot) |

---

## FACTORY-P3 — Controlled AI generation pilot (~100)

| Field | Content |
|-------|---------|
| **Status** | **IMPLEMENTATION DONE** · live ~100 pilot **BLOCKED_PROVIDER** (Anthropic credits) — 2026-09-01 |
| **Priority** | MUST |
| **Complexity** | VERY HIGH |
| **Objective** | Blueprint-driven generate N valid unique **DRAFT** questions via existing AI Gateway |
| **Deliverables** | `generation_candidates` migration `a7b8c9d0e1f2`; generation service; `POST .../generate`; prompt `neet_mcq_factory_v1`; caps; mocked tests; `CONTENT_FACTORY_P3_IMPLEMENTATION.md` + pilot results |
| **Non-goals (held)** | Auto-submit/approve/publish; AI scientific judge; semantic dedupe; Celery; 1k+ scale |
| **Acceptance** | Code/tests met; live count deferred until funded API — see pilot results (no fabricated Q) |
| **Next** | FACTORY-P4 (done) → re-run live pilot when credits available |

---

## FACTORY-P4 — Automated QA + dedupe + sampling prep

| Field | Content |
|-------|---------|
| **Status** | **DONE** — 2026-09-01 |
| **Priority** | MUST |
| **Complexity** | HIGH |
| **Objective** | Gates A–G; GREEN/YELLOW/RED; QAResult; DB fingerprints; ReviewSample eligibility |
| **Deliverables** | Migration `b8c9d0e1f2a3`; QA/sampling services; APIs; editorial `factory_qa` packet; docs; tests |
| **Non-goals (held)** | AI judge; semantic/pgvector dedupe; auto ECAEP transitions; 1k+ generation |
| **Acceptance** | Met in code/tests; live generate→QA deferred with P3 credits block |
| **Next** | FACTORY-P5 (done) → live ~100 pilot when credits available |

---

## FACTORY-P5 — Human sampling & exception review UX

| Field | Content |
|-------|---------|
| **Status** | **DONE** — 2026-09-01 |
| **Priority** | MUST |
| **Complexity** | MEDIUM–HIGH |
| **Objective** | GREEN sample / YELLOW 100% / RED quarantine → human decisions → ECAEP (manual) |
| **Deliverables** | `factory_review_items` migration `c9d0e1f2a3b4`; review APIs; `/admin/factory-review`; docs; tests |
| **Non-goals (held)** | Auto ECAEP transitions; AI judge; regeneration; mass generation |
| **Acceptance** | Met in code/tests; no live pilot executed |
| **Next** | FACTORY-P3.1 (multi-provider gateway) → controlled ~100 pilot |

---

## FACTORY-P3.1 — Multi-provider AI Gateway (**DONE**)

| Field | Content |
|-------|---------|
| **Status** | **IMPLEMENTATION DONE** · 2026-09-01 |
| **Priority** | MUST (unblocks pilot when Anthropic credits exhausted) |
| **Complexity** | MEDIUM |
| **Objective** | Explicit multi-provider abstraction + routing without changing P1–P5 semantics |
| **Deliverables** | Adapters (Anthropic/OpenAI/Gemini/Mistral); registry; router; pricing; capabilities; lineage migration `d0e1f2a3b4c5`; fakes + contract tests; `CONTENT_FACTORY_P3_1_MULTI_PROVIDER.md` |
| **Non-goals (held)** | Live generation; silent fallback; AI judge; ECAEP changes; crowning a “best” model |
| **Acceptance** | Met in code/tests; no live pilot; no silent provider switch |
| **Next** | Controlled cross-provider ~100 pilot when credentials/budgets configured — then P4/P5 review — **not** 1k |

---

## FACTORY-P6 — Certification & release (**NEXT after pilot**)

| Field | Content |
|-------|---------|
| **Priority** | MUST before claiming factory releases |
| **Complexity** | MEDIUM–HIGH |
| **Objective** | BatchCertification + ContentRelease; quarantine/rollback by run |
| **Features** | Certify permission; evidence package; revoke; unpublish helpers |
| **Dependencies** | P5 + successful ~100 pilot review |
| **Acceptance** | Certified ≠ published; rollback identifies run members |

---

## FACTORY-P7 — Coverage optimization

| Field | Content |
|-------|---------|
| **Priority** | SHOULD (needed by 10k–50k) |
| **Complexity** | MEDIUM |
| **Objective** | Demand-driven generation from coverage matrix + quotas |
| **Features** | Coverage planner UI; configurable quotas; anti-monoculture caps |
| **Dependencies** | P2–P3 |

---

## FACTORY-P8 — Scale testing

| Field | Content |
|-------|---------|
| **Priority** | MUST before 50k+ claims |
| **Complexity** | HIGH (ops) |
| **Objective** | Execute Stage 1→5 benchmarks on staging |
| **Features** | Perf fixes for practice sampling & admin lists; version retention |
| **Dependencies** | P1–P7 as needed per stage |
| **Acceptance** | Written SLO report; practice p95 within budget at stage target PUBLISHED size |

---

## Prioritization summary

### MUST HAVE (for trustworthy 10k+)
- ContentBatch / GenerationJob / Run  
- Idempotent generation  
- Structured QA + dedupe at DB  
- Sampling + exception queues  
- Certification ≠ publish  
- Practice pool query fix before large PUBLISHED sets  
- Honest provenance  

### SHOULD HAVE
- LearningObjective / rich blueprints  
- SourceDocument registry  
- ContentRelease snapshots  
- Coverage planner UI  
- pgvector semantic dedupe (if metrics demand)  

### NICE TO HAVE
- QuestionVariant entity (vs parent_id)  
- Judge model routing sophistication  
- Advanced sequential sampling statistics  

### DO NOT BUILD NOW
- Microservices / K8s for factory  
- External Elasticsearch / vector SaaS (default)  
- Multi-tenancy  
- 12-agent / Digital Twin  
- Auto-approve / auto-publish  
- Replacing ECAEP item states for student visibility  

---

## Definition of Done — Content Factory (product-level)

- [ ] Batch generation idempotent  
- [ ] Provenance complete for factory items  
- [ ] Duplicate rate controlled & reported  
- [ ] Invalid questions cannot certify/publish  
- [ ] Human review is sample + exception based  
- [ ] PUBLISHED-only student boundary intact  
- [ ] Batches quarantinable / roll-backable  
- [ ] Coverage measurable  
- [ ] Generation observable (throughput, cost, failures)  
- [ ] No silent AI fallback as scientific authority  

---

## Immediate next implementation wave

**FACTORY-P3 — Smallest controlled AI-generation pilot (~100 questions)**

Single Cursor prompt should: generate candidates from eligible blueprints into DRAFT via existing AI Gateway + ContentItem/ContentVersion; mandatory provenance (`model_used`, cost, prompt_version, blueprint_id/version); budget caps; idempotent job runs — **without** auto-approve/auto-publish or jumping to 1k+/10k scale. See `CONTENT_FACTORY_P2_IMPLEMENTATION.md` P3 contract.

---

## Relationship to WAVE-P0 content work

P0 waves (Batch A, SME Physics pilot, hierarchy gaps, ECAEP submit) remain the **manual/SME path**. Factory waves **automate production around** that governance — they do not obsolete human review of PHY-01–10 or remaining Batch A.
