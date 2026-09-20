# TALOS T5 — Live Practice + Taxonomy Integration Audit

**Date:** 2026-09-02  
**Mode:** READ-ONLY diagnostic (no code/DB/question writes)  
**Product:** Trinetra AI Learning OS (TALOS)

---

## 1. Executive Verdict

| Dimension | Verdict |
|-----------|---------|
| **Practice flow** | **AMBER — PRACTICE FLOW HAS IDENTIFIED FIXES** |
| **TALOS taxonomy integration** | **AMBER — TALOS INTEGRATION GAP** |

**Summary:** The Practice Now click path exists end-to-end in code (`useStartPractice` → `POST /api/v1/assessments/practice` → start attempt → `/student/attempts/{id}`). It requires authentication. Live browser this session reached only the login gate (no session cookie). The 74 P0 Physics taxonomy nodes are present in `trinetra_db`, but Practice does **not** expose a `TOPIC` scope and CHAPTER-scoped Kinematics cannot distinguish NCERT Ch 2 vs Ch 3. Eligible practice inventory is **11 PUBLISHED** questions globally (**6 Physics**, all under Current Electricity — **0** under Kinematics / new P0 chapters). The 5,000 legacy Physics imports remain DRAFT with `concept_id IS NULL` and are correctly excluded from the practice pool. The P0 taxonomy implementation did not break Practice; it also did not make new Physics chapters practiceable.

---

## 2. Scope and Read-Only Safety

**Allowed and performed:** source inspection, read-only SQL, port/health probes, browser navigation to login (no credentials submitted), review of prior Practice audits/e2e specs.

**Not performed:** taxonomy seed/`--apply`, migrations, question/`concept_id` changes, publish, practice-session creation, user registration, answer/attempt writes, frontend/backend code changes.

---

## 3. Application Architecture Inspected

```text
apps/web (Next.js)
  /student/dashboard     Hero "Practice now" + concept-row "Practice now"
  /student/practice      ScopePicker + "Enter practice arena"
  /student/attempts/[id] Runner + submit + score
  features/assessment/use-start-practice.ts
  features/assessment/api.ts → apiClient (cookies + CSRF)
  middleware.ts → /student/* requires access_token cookie

apps/backend (FastAPI)
  POST /api/v1/assessments/practice          (+ CSRF, auth)
  POST /api/v1/assessments/{id}/attempts
  GET  /api/v1/attempts/{id}
  POST /api/v1/attempts/{id}/answers
  POST /api/v1/attempts/{id}/submit
  AssessmentService.generate_practice
  AssessmentRepository.published_question_ids_for_scope

DB
  cms.content_items (+ versions)     questions
  academic.{subjects,chapters,topics,concepts}  taxonomy
  assessment.{assessments,assessment_questions,attempts,attempt_answers}
```

Quick Launch hub item **"Practice"** is a **Link** to `/student/practice` only — it does not start a session.

---

## 4. Practice Now Button Trace

| Stage | Status | Notes |
|-------|--------|-------|
| User clicks Practice Now | **UNKNOWN** (live) / **PASS** (code) | Live: not authenticated; cannot reach dashboard |
| DOM/UI event | **PASS** | `onClick` on `HeroPracticeCta` / `PracticeNowButton` |
| click handler | **PASS** | `start.mutate(...)` via `useStartPractice` |
| frontend state | **PASS** | React Query mutation: pending / error / success |
| navigation OR API | **PASS** (code) | API then `router.push(/student/attempts/{id})` |
| HTTP request | **PASS** (code/e2e) | `POST /api/v1/assessments/practice` then attempts |
| backend route | **PASS** | `assessment_router.generate_practice` |
| controller/service | **PASS** | `AssessmentService.generate_practice` → `_generate` |
| repository/query | **PASS** | `published_question_ids_for_scope` |
| database | **PASS** | PUBLISHED + `deleted_at IS NULL` (+ scope joins) |
| response | **PASS** (when pool > 0) | 201 + assessment; else 422 `NO_QUESTIONS_AVAILABLE` |
| frontend render | **PASS** (code) | attempt page; loading/error alerts present |
| answer submission | **PASS** (prior e2e / tests) | Not re-run this session (would write) |
| scoring | **PASS** (prior scripts/tests) | Not re-run this session |

**Exact failure point for the reported “does nothing” symptom (most likely product path):**

1. **Unauthenticated access** → redirect to `/login?next=…` (Practice Now never mounts).  
2. **Mis-identified control:** Quick Launch “Practice” only navigates to configure page.  
3. **Concept-row CTA disabled** when `published_question_count === 0` (looks inert).  
4. **Scoped empty pool:** CHAPTER/CONCEPT under P0 Physics (incl. Kinematics) → 422; UI should show Alert — if user dismisses/misses it, feels like “nothing.”  
5. **Historical:** weak loading feedback on small buttons (documented in prior mobile Practice audit) — less true for hero CTA after that fix.

This is **not** “missing handler / missing route / taxonomy seed deleted the pool.”

---

## 5. Browser/Frontend Findings

| Check | Result |
|-------|--------|
| Frontend listen | `:3001` Listen (PID observed) |
| Backend listen | `:8000` Listen; `/docs` → 200 |
| `/student/dashboard` | Redirect → `/login?next=%2Fstudent%2Fdashboard` |
| Console JS errors on login | None observed in snapshot path |
| Authenticated Practice Now click | **NOT EXECUTED** (would create assessment/attempt rows) |

Prior documented live reproduction (same day, earlier audit): hero Practice Now → attempt with 11 Q (requested 30, shrunk); concept Practice Now → Ohm’s Law attempt. Playwright e2e expects CTA to fire `POST …/practice` (with fetch fallback if CTA flakes).

---

## 6. Routing Findings

| Item | Value |
|------|-------|
| Hero button target | Mutation (not Link) |
| Expected route after success | `/student/attempts/{attemptId}` |
| Configure path | `/student/practice` |
| Quick Launch “Practice” | `/student/practice` (navigate only) |
| Auth gate | `middleware.ts` — `access_token` cookie required for `/student/*` |
| Route exists / renders | Yes (attempt + practice pages present) |

---

## 7. API Findings

| Field | Value |
|-------|-------|
| Method / path | `POST /api/v1/assessments/practice` |
| Auth | Current user (cookie JWT) |
| CSRF | Required (`verify_csrf` + `X-CSRF-Token`) |
| Body | `{ scope_type, scope_id?, question_count? }` |
| Allowed `scope_type` | `CONCEPT` \| `CHAPTER` \| `SUBJECT` \| `FULL` — **no `TOPIC`** |
| Success | 201 assessment + optional availability `meta` |
| Empty pool | 422 `NO_QUESTIONS_AVAILABLE` |
| Next call | `POST /api/v1/assessments/{id}/attempts` → navigate |

Frontend `GenerateInput` matches backend schema. Hero uses `{ scope_type: "FULL", question_count: 30 }`.

---

## 8. Backend Findings

| Layer | Reached | Expected | Actual | Status |
|-------|---------|----------|--------|--------|
| Route | YES | Auth + CSRF | Implemented | PASS |
| Service | YES | Sample published IDs | `generate_practice` | PASS |
| Repository | YES | Scope filter | CONCEPT / CHAPTER / SUBJECT / FULL | PASS |
| SQL | YES | PUBLISHED only | Also requires `concept_id` join for CHAPTER/SUBJECT | PASS (by design) |
| Empty scope | YES | 422 | `NO_QUESTIONS_AVAILABLE` | PASS |

**CHAPTER filter SQL (critical):** joins `ContentItem → Concept → Topic` where `Topic.chapter_id = scope_id`. There is **no** topic-level filter. Questions with `concept_id IS NULL` never appear in CHAPTER/SUBJECT/CONCEPT scopes.

---

## 9. Database Findings (read-only)

| Fact | Value |
|------|------:|
| DB | `trinetra_db` |
| P0 approved present | 74 / 74 missing 0 |
| Gravitation fill codes | 0 |
| Kinematics topics | `motion-in-a-straight-line` (3 concepts), `motion-in-a-plane` (3 concepts) |
| Solids naming | Topic **Stress and Strain**; Concept **Definitions of Stress and Strain** |
| All questions | 5175 (published 11, draft 5153) |
| With `concept_id` | 175; null 5000 |
| Physics-ish pool (concept PHYSICS ∪ legacy tags/slugs) | 5073 (published **6**, draft 5056, null concept 5000) |
| Legacy batch | 5000; null concept 5000; draft 5000; unresolved tag 2500 |
| Legacy fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` (unchanged) |
| Eligible Practice (FULL) | **11** |
| Published Physics via concept | **6** (all `current-electricity`) |
| Published under Kinematics chapter | **0** |
| Published null-concept | **0** (all 11 published have concept_id) |

---

## 10. 74-Node TALOS Integration

| Check | Result |
|-------|--------|
| 74 nodes exist & related | **YES** (`verify_present`: approved_present=74) |
| Gravitation absent | **YES** |
| Visible to academic APIs / ScopePicker | **YES** (chapters → topics loaded to flatten concepts) |
| Consumed by Practice as first-class TOPIC scope | **NO** |
| Practice fields used | `subject` (SUBJECT), `chapter` (CHAPTER), `concept` (CONCEPT), or none (FULL). **Not topic. Not microcompetency.** |
| New P0 nodes practiceable today | **NO** — zero published questions under those concepts/chapters |

---

## 11. Kinematics Contract Audit

**Approved structure:** one chapter `kinematics` + two topic trees (Ch 2 / Ch 3).

**Practice behavior:**

- ScopePicker can select Chapter = Kinematics → emits `scope_type=CHAPTER` → backend filters **all concepts under all topics of that chapter**.
- There is **no** UI control that emits topic-only scope.
- Concept dropdown lists concepts from **both** topic trees under the chapter (flattened).

**Contract:** “Chapter alone is insufficient to distinguish Ch 2 vs Ch 3.”

**Assessment:** **AMBER — TAXONOMY INTEGRATION GAP**  
Not a DB taxonomy failure (hierarchy is correct). Practice/AI generation filters do not enforce chapter + topic for Kinematics NCERT separation.

---

## 12. Legacy 5,000 Classification Boundary

| Question | Answer |
|----------|--------|
| Legacy `concept_id` | All **NULL** (5000) |
| Can Practice retrieve NULL `concept_id`? | **FULL:** yes if PUBLISHED. **CONCEPT/CHAPTER/SUBJECT:** no (join requires concept). |
| Require concept_id? | For scoped practice: **yes**. For FULL: **no**. |
| Legacy in practice pool? | **No** — all DRAFT. |
| Silent zero because unclassified? | For FULL: no (11 other published). For P0 Physics chapter/concept: empty because **unpublished + unclassified**, not because taxonomy nodes missing. |

---

## 13. Practice Question Availability

| Metric | Count |
|--------|------:|
| Physics questions (concept PHYSICS ∪ legacy) | 5073 |
| Published Physics | 6 |
| Draft Physics (incl. legacy) | 5056 |
| With chapter (via concept) | = with concept in Physics tree |
| With topic (via concept) | = with concept |
| With concept (Physics pool) | 73 |
| Legacy 5,000 | 5000 |
| Legacy `concept_id IS NULL` | 5000 |
| Eligible for Practice (global FULL) | **11** |
| Eligible under Kinematics / new P0 chapters | **0** |

---

## 14. End-to-End Practice Test

**Not completed in T5** beyond login wall.

Reason: starting practice creates persistent `assessment` / `attempt` (and optional answer) rows; registering a user also writes. No documented disposable test DB / dry-run mode was used. Prior same-day evidence (API script + Playwright + earlier browser audit) shows the authenticated path can deliver questions and score when the published pool is non-empty.

---

## 15. Practice State Machine

```text
IDLE
  → (click) START_REQUEST (mutation pending / aria-busy)
  → LOADING (“Preparing…” / “Starting…”)
  → API generate → API start attempt
  → NAVIGATE attempt page
  → QUESTION_READY
  → ANSWER_SELECTED (option aria-pressed)
  → ANSWER_SUBMITTED (save answer API)
  → (optional) NEXT / FEEDBACK after submit
  → COMPLETED (score UI)

Error branch:
  → START_REQUEST → ERROR Alert (practiceStartMessage) + Retry
  → empty pool → NO_QUESTIONS_AVAILABLE copy
```

**Missing transition that can look like “does nothing”:** no start mutation when button `disabled` (`publishedCount === 0`); Quick Launch never enters START_REQUEST.

---

## 16. Error Handling

| Case | Handling |
|------|----------|
| API / validation / empty pool | Alert + Retry; NO_QUESTIONS links | **VISIBLE** |
| Network | Explicit NETWORK_ERROR message | **VISIBLE** |
| Auth on protected routes | Redirect login | **VISIBLE** (not Practice error) |
| Mutation exception | Caught by React Query → Alert | **VISIBLE** |
| Silent `catch {}` on Practice CTA | Not found | — |

Disabled concept buttons show helper text “No published questions yet.”

---

## 17. Authentication/Session

| Requirement | Required? |
|-------------|-----------|
| Login / access_token | **YES** (`middleware` + API `get_current_user`) |
| CSRF on POST | **YES** |
| Role / subscription / onboarding | Student routes; no separate Practice subscription gate found |
| Session user ID | Bound to attempt |

Unauthenticated users never see Practice Now on the dashboard.

---

## 18. Taxonomy Filter Contract

**Current Practice contract:**

```text
FULL     → all PUBLISHED questions
SUBJECT  → published with concept under subject
CHAPTER  → published with concept under chapter (all topics)
CONCEPT  → published with concept_id = scope
TOPIC    → NOT SUPPORTED
MICRO    → NOT SUPPORTED
```

**vs approved TALOS (esp. Kinematics):** needs chapter + topic (+ concept). **Gap.**

Affected P0 areas with empty published inventory today: Units & Measurement, Kinematics topic trees, Laws of Motion trees, Work-Energy, Systems/Rotational, Solids, Fluids, Thermodynamics topics, Kinetic Theory — all **0** published for practice via those scopes.

---

## 19. AI Context Integration

Question Generator (`question_generator.py` / service):

```text
Concept: {name}
Concept summary: …
NCERT reference: …
```

Does **not** pass explicit subject / chapter / topic names. Tutor `get_knowledge_context` returns concept + knowledge units + visuals — not a structured chapter+topic path for Kinematics Ch 2 vs Ch 3.

**Status:** **AMBER** for Gate-4 Kinematics AI context contract (report-only; not fixed in T5).

---

## 20. Performance / 1M-MCQ Assessment

| Observation | Assessment |
|-------------|------------|
| `published_question_ids_for_scope` loads all matching IDs then `random.sample` in Python | Does not scale to 1M without streaming/SQL `TABLESAMPLE` / reservoir |
| Scope joins are indexed-friendly FKs but unbounded result set | Risk grows with inventory |
| Frontend does not load full bank into browser for Practice start | Good |

**1M-MCQ classification:** **AMBER** (works for current ~11–5k published/draft; not proven for 1M).

---

## 21. Root Cause

**Primary classification (multi-cause):**

| Code | Applies? |
|------|----------|
| AUTHENTICATION_FAILURE | YES — live session blocked at login |
| EMPTY_QUESTION_SET | YES — for P0/Kinematics scoped practice |
| TAXONOMY_FILTER_FAILURE | PARTIAL — missing TOPIC scope / chapter-only Kinematics |
| UI_EVENT_FAILURE | NO — handlers exist |
| API_ROUTE_FAILURE | NO |
| NAVIGATION_FAILURE | NO for CTA; Quick Launch is intentional navigate-only |
| ERROR_HANDLING_FAILURE | LOW — errors visible when mutation runs; disabled button looks dead |

**Exact failure path (scoped Physics P0 / Kinematics expectation):**

```text
User selects Physics → Kinematics (CHAPTER) → start
  → POST /assessments/practice {CHAPTER, kinematics_id}
  → published_question_ids_for_scope → []
  → 422 NO_QUESTIONS_AVAILABLE
```

**Exact path (hero FULL, authenticated, healthy):**

```text
Practice now → FULL → 11 published IDs → shrink from 30 → attempt → runner
```

---

## 22. Functional vs Taxonomy Failure

| Cause | Role |
|-------|------|
| A. New 74-node taxonomy broke Practice | **NO** — FULL pool still 11; legacy fingerprint unchanged |
| B. Existing Practice implementation | **YES** — no TOPIC scope; chapter mixes Kinematics trees |
| C. Legacy unassigned / unpublished | **YES** — 5000 DRAFT null concept → not in pool |
| D. Auth / UX / inventory thinness | **YES** — login required; only 6 Physics published (old chapter) |
| E. Multiple interacting | **YES** |

Do **not** blame P0 insert for “Practice Now does nothing.” Blame **auth + thin published inventory + missing topic filter + UX of disabled/nav-only controls**, with taxonomy **integration gap** separate from taxonomy **data** correctness.

---

## 23. Required Fixes (do not implement in T5)

See T6 plan below. Smallest safe functional fix for “button does nothing” when logged out: ensure marketing/landing CTA routes to login with clear next. When logged in with empty scope: keep visible errors (already mostly present). Taxonomy: add TOPIC scope for Kinematics contract.

---

## 24. Recommended T6 Implementation Plan

### T6-A — Confirm authenticated Practice Now live (no taxonomy change)
- **Files:** ops / e2e only (`e2e/practice-now.spec.ts`, optional `verify_practice_now_e2e.py`)
- **Problem:** T5 could not re-verify CTA without writing; prior evidence exists
- **Change:** Run existing e2e against local stack with test user
- **Risk:** Creates attempt rows (acceptable in local)
- **DB question changes:** none
- **Validation:** Playwright CTA fires POST; attempt renders

### T6-B — Clarify dead controls (frontend UX only)
- **Files:** `dashboard/page.tsx`, `quick-launch-hub.tsx`
- **Problem:** Quick Launch “Practice” ≠ Practice Now; disabled concept buttons look inert
- **Change:** Copy/tooltips distinguishing “Configure” vs “Start”; ensure disabled state always shows reason
- **Risk:** Low
- **DB:** none
- **Validation:** Vitest + visual check

### T6-C — Add Practice `TOPIC` scope (taxonomy contract)
- **Files:** `assessment_service.py` SCOPE_TYPES, `assessment_repository.py`, schemas, `scope-picker.tsx`, `api.ts` GenerateInput
- **Problem:** Kinematics chapter-only mixes Ch 2 / Ch 3 trees
- **Change:** Support `scope_type=TOPIC`; ScopePicker middle control selects topic before concept
- **Risk:** Medium (API contract + UI)
- **DB schema:** none required if topic_id already on concepts
- **Questions affected:** none
- **Validation:** unit tests for kinematics topic isolation; empty pool still 422

### T6-D — Content readiness (separate from Practice bugs)
- **Problem:** 0 published under P0 Physics; 5000 legacy DRAFT/null concept
- **Change:** ECAEP publish path + careful concept assignment (NOT silent bulk map)
- **Risk:** High if rushed
- **Validation:** published counts per topic; legacy fingerprint discipline

### T6-E — AI prompt context (Kinematics)
- **Files:** `question_generator.py`, optional knowledge context enrichment
- **Problem:** concept-only prompt lacks chapter+topic names
- **Change:** Include subject/chapter/topic in generator prompt when available
- **Risk:** Low–medium (prompt quality)
- **Questions:** none until regenerate

### T6-F — 1M sampling strategy (later)
- **Files:** `assessment_repository.py`
- **Problem:** load-all-IDs sampling
- **Change:** SQL-side limited random selection
- **Risk:** Medium
- **Validation:** load tests with synthetic large IDs

**Priority:** T6-A → T6-B → T6-C → T6-D (content) → T6-E → T6-F.

---

## 25. Safety Proof

```text
Database writes = 0
Database rows modified = 0
Questions modified = 0
concept_id assignments = 0
Publication changes = 0
Taxonomy nodes modified = 0
Migrations executed = 0
Seed scripts executed = 0
Application code modified = 0
Final Practice verdict = AMBER
Final TALOS integration verdict = AMBER
```

Legacy post-check: total=5000, `concept_id` NULL=5000, fingerprint=`937c60a9aaa5dcbedfa9b5bc569d45a0`.

---

## Root-cause table

| Layer | Expected | Actual | Status | Evidence |
|-------|----------|--------|--------|----------|
| UI click | Handler fires | Handler present; live unauthenticated | PASS (code) / NOT REACHED (live) | `HeroPracticeCta` onClick |
| Handler | `useStartPractice` | Implemented | PASS | `use-start-practice.ts` |
| State | pending/error/success | Mutation + Alert | PASS | dashboard/practice pages |
| Navigation | `/student/attempts/{id}` | On success | PASS | `router.push` |
| API request | POST practice | Implemented; CSRF+cookies | PASS | `assessmentApi.generatePractice` |
| API route | Exists | Exists | PASS | `assessment_router.py` |
| Backend | Sample published | Works; empty → 422 | PASS | `AssessmentService` |
| Database | Eligible rows | 11 FULL; 0 Kinematics | PASS query / FAIL inventory for P0 | read-only SQL |
| Response | 201 or 422 | Contract confirmed | PASS | service + docs |
| Rendering | Attempt UI | Present; not retested live | PASS (code) / UNKNOWN (live) | attempt page |
| Answer submission | Save answers | Prior e2e | PASS (prior) / NOT REACHED | verify script |
| Scoring | Score on submit | Prior e2e | PASS (prior) / NOT REACHED | verify script |

---

## Taxonomy table

| Area | Expected | Actual | Status |
|------|----------|--------|--------|
| P0 nodes | 74 | 74 | PASS |
| Gravitation nodes | 0 | 0 | PASS |
| Kinematics chapters | 1 | 1 (`kinematics`) | PASS |
| Kinematics topic trees | 2 | 2 | PASS |
| Solids concept name | Definitions of Stress and Strain | Match | PASS |
| Legacy concept assignments | 0 | 0 | PASS |
| Practice taxonomy filter | chapter + topic (+ concept) where required | CONCEPT/CHAPTER/SUBJECT/FULL only | **FAIL (gap)** |
| AI taxonomy context | subject + chapter + topic + concept | concept (+ ncert/summary) | **FAIL (gap)** |

---

## Practice availability table

| Metric | Count |
|--------|------:|
| Physics questions | 5073 |
| Published Physics | 6 |
| Draft Physics | 5056 |
| With chapter (via concept, Physics) | 73 |
| With topic (via concept, Physics) | 73 |
| With concept (Physics) | 73 |
| Legacy 5,000 | 5000 |
| Legacy `concept_id IS NULL` | 5000 |
| Eligible for Practice (FULL) | 11 |

---

## Final verdicts

```text
AMBER — PRACTICE FLOW HAS IDENTIFIED FIXES
AMBER — TALOS INTEGRATION GAP
```
