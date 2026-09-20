# NEET Content Factory — Scale Plan

**Status:** Planning only · 2026-09-01  
**Verified baseline:** ~164 QUESTIONS on `trinetra_db` (11 PUBLISHED).

Objective: scale **safely** through 100 → 1k → 10k → 50k → 100k **per subject** without proportional engineering toil — while optimizing quality and coverage, not raw count.

---

## 1. Incremental scale stages

### Stage 1 — 100 questions (pilot factory)

| Dimension | Target |
|-----------|--------|
| Goal | Prove batch + QA + sample + certify loop on one chapter |
| Throughput | Tens/day |
| DB / search | Current indexes sufficient |
| Dedupe | Normalized hash + exact stem |
| Human | Near-100% or high sample rate |
| Cost | Full observability; measure \(g,v\) empirically |
| Exit criteria | Idempotent re-run; zero accidental publishes; audit complete |

### Stage 2 — 1,000

| Dimension | Target |
|-----------|--------|
| Goal | Multi-chapter; stratified sampling |
| Practice selection | Still OK if PUBLISHED ≪ 1k; plan SQL sampling |
| Editorial queue | Replace “load 500” with indexed filters + keyset pagination |
| Exit | Duplicate rate measured; YELLOW queue usable |

### Stage 3 — 10,000 (**MUST-HAVE architecture complete**)

| Dimension | Target |
|-----------|--------|
| ContentBatch + GenerationJob + QAResult live | Required |
| Practice pool | SQL `ORDER BY random()` / tablesample / precomputed pools — **no full ID arrays** |
| Dedupe | DB-backed hash + trigram candidates |
| Admin UX | Factory dashboard + exception queue |
| Exit | Certify batch without reviewing every GREEN |

### Stage 4 — 50,000

| Dimension | Target |
|-----------|--------|
| Coverage engine | Demand-driven quotas |
| Version retention | Policy for old DRAFT versions |
| Optional pgvector | Only if semantic dup FN rate too high |
| Cost | Judge-on-escalation only; budget caps per batch |

### Stage 5 — 100,000 per subject (~400k total)

| Dimension | Target |
|-----------|--------|
| Ops | Job concurrency limits; rate limits to AI provider |
| Analytics | Coverage/fill dashboards |
| Rollback | Quarantine by run/blueprint at volume |
| Exit | Documented SLOs; release playbooks; no monolith split unless measured need |

---

## 2. Performance bottlenecks (evidence-based)

| Area | Current behaviour | Risk at 100k/subject |
|------|-------------------|----------------------|
| Practice ID load | All PUBLISHED IDs in memory | **HIGH** |
| Editorial queue | ≤500 rows + versions in Python | **HIGH** |
| Exact duplicate scan | In-memory stems | **HIGH** |
| FTS GIN | Present on PUBLISHED | **MEDIUM** — keep; maintain reindex |
| ContentVersion growth | Every draft edit appends row | **MEDIUM** |
| AI check on every submit | Live model call | **MEDIUM** cost/latency — cache/skip for GREEN factory path |

---

## 3. Coverage engine

Matrix dimensions:

`subject × chapter × topic × concept × difficulty × question_family × published_count (+ draft/in_review)`

Factory jobs **fill deficits** subject to quotas:

- Max per concept / family / difficulty  
- Min Tier-1 fraction (policy)  
- Zoology / empty-chapter priority (product lesson from Batch A)

Campaign control (≥25/area) remains a **planning overlay**, not a publish quota.

---

## 4. Storage growth (order-of-magnitude)

Per question rough: body JSON ~1–3 KB + versions + indexes.  
At 400k × average 2 versions ≈ hundreds of GB worst case if unconstrained — hence **version retention** and avoid storing full AI traces on every version (link `AIRequestLog` instead).

---

## 5. Cost controls

- Batch budget ceiling (tokens / USD) hard-stop  
- Prefer templates that don’t need judge  
- Deterministic gates before any AI  
- Sample GREEN; don’t AI-revalidate entire certified bank nightly  
- FallbackProvider must not silently “pass” science gates  

Symbolic cost: see `CONTENT_FACTORY_QA_STRATEGY.md`.

---

## 6. Source strategy (tiers)

| Tier | Examples | Factory role |
|------|----------|--------------|
| 1 Authoritative | NCERT, official NTA papers/keys when legally held | Prefer for high-stakes factual; strict provenance |
| 2 Licensed / SME | Licensed pubs, SME authoring (Batch A class) | Core volume with human honesty labels |
| 3 AI-generated | From KU + blueprint | Dominant volume **after** QA + sampling |

Never blur tiers in UI.

---

## 7. Release & rollback

**Release** = `ContentRelease` metadata pointing at certified batch item set + generator versions + sample report.

**Rollback** = quarantine flag + unpublish PUBLISHED members by `generation_run_id` (soft). Retain rows for audit.

---

## 8. Admin UX (minimum)

1. **Content Factory Dashboard** — batches, jobs, failures, QA mix, cost  
2. **Exception Queue** — RED/YELLOW  
3. **Sampling Queue** — drawn sample → existing review packet  
4. **Batch Certification** — evidence + decision  
5. **Coverage Planner** — gap matrix & job creation  

Reuse `/admin/ai-review` for item review; do not fork a second ECAEP.

---

## 9. Migration coexistence

Legacy 164 + Batch A remain first-class. Factory fields nullable. Backfill provenance lazily. No big-bang cutover.

---

## 10. Benchmark checklist (per stage)

For each stage record: throughput, p95 submit/publish, search p95, gen fail %, duplicate %, QA throughput, admin list p95, storage delta, $ / 1k questions (measured).

**Do not run Stage 3+ generation in audit waves.**
