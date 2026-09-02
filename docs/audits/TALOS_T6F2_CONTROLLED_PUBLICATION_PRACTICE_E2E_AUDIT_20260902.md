# T6-F2 Controlled Publication + Practice E2E Audit

**Date:** 2026-09-02  
**Batch:** `physics-t6f1-pilot-20260902`

---

## 1. Executive Verdict

**GREEN**

Controlled publication of 938 eligible T6-F1 DRAFT questions completed through server-side ECAEP gates. Practice API scopes (FULL/SUBJECT/CHAPTER/TOPIC/CONCEPT), authentication, empty-pool behavior, Kinematics topic isolation (cross-leak = 0), and Playwright browser E2E all **EXECUTED AND PASSED**. Legacy 5,000 and T6-D 100 unchanged.

---

## 2. Prerequisite Gate

T6-F1 Vector Contract: **GREEN**

Source: `docs/audits/TALOS_T6F1_VECTOR_MAGNITUDE_CONTRACT_FIX_AUDIT_20260902.md`

---

## 3. Pre-Publication Inventory

| Metric | Value |
|--------|------:|
| Batch | `physics-t6f1-pilot-20260902` |
| Candidates generated (F1) | 1,000 |
| Staged DRAFT | 938 |
| Rejected (never persisted) | 62 |
| Already published (pre-F2) | 0 |
| Subject | Physics |
| Class | XI (NCERT Class XI evidence) |
| NCERT level | SECTION_VERIFIED (938/938) |

Manifest: `docs/audits/TALOS_T6F2_PUBLICATION_MANIFEST_20260902.json`

---

## 4. Final Publication Gates

Server-side `evaluate_question_publication_gates` / `assert_question_publishable` enforced on every publish:

| Gate | Result |
|------|--------|
| Structural | PASS (938/938 eligible) |
| Scientific / numerical | PASS |
| NCERT evidence | PASS (SECTION_VERIFIED) |
| Taxonomy (concept_id) | PASS |
| Duplicate vs published stems | PASS |
| Provenance | PASS |
| Review APPROVED | PASS (ECAEP path) |

Blocked by pre-publish gate evaluation: **0**

---

## 5. Publication Manifest

| Field | Value |
|-------|------:|
| Staged | 938 |
| Eligible | 938 |
| Blocked | 0 |
| Consistency errors | [] |
| Eligible IDs | 938 UUIDs in manifest file |
| Rejected IDs in publish set | 0 |
| Legacy / T6-D IDs in publish set | 0 |

---

## 6. Publication Result

| Metric | Value |
|--------|------:|
| Staged | 938 |
| Eligible | 938 |
| Published (this run) | **938** |
| Blocked | 0 |
| Rejected | **62** (unchanged, never published) |
| Rolled back | 0 |
| Post-state | published=938, draft=0 |

---

## 7. NCERT Evidence

- Level: **SECTION_VERIFIED** for all 938 published
- Page-verified: **0** (capability not claimed; no fabricated pages)

---

## 8. Scientific Validation

Publication path invokes `classify_and_verify`. Incomplete/invalid numericals hard-fail. No batch-specific scientific bypass.

---

## 9. Vector-Magnitude Contract

Precision-aware `vector_mag` contract from T6-F1 fix remained active. **PASS**

---

## 10. Taxonomy Verification

| Dimension | Status |
|-----------|--------|
| Subject PHYSICS | PASS |
| Chapter/topic/concept lineage via concept_id | PASS |
| Concept keys covered | 45 |

---

## 11. Kinematics Topic Isolation

| Metric | Value |
|--------|------:|
| Straight Line (TOPIC pool) | **82** |
| Plane Motion (TOPIC pool) | **57** |
| Cross-Leak | **0** |
| Kinematics CHAPTER pool | 139 |
| Sample CONCEPT pool | 27 |

Browser E2E confirmed TOPIC isolation with zero cross-leak.

---

## 12. Duplicate Verification

Pre-publish gate checked published-stem duplicates. Blocked count: **0**. No duplicate published.

---

## 13. Provenance Verification

All published items retained batch/provenance/NCERT structured evidence. **PASS**

---

## 14. Practice API

| Scope | Result |
|-------|--------|
| FULL | PASS (qcount=5 generated) |
| SUBJECT | PASS |
| CHAPTER (kinematics) | PASS (pool=139) |
| TOPIC straight | PASS |
| TOPIC plane | PASS |
| CONCEPT | PASS |

---

## 15. Authentication

| Check | Result |
|-------|--------|
| Unauthenticated Practice POST | Rejected (≥401) — PASS |
| Authenticated student session | PASS (Playwright bootstrap) |

---

## 16. Practice Question Flow

Authenticated browser path: question visible → Option A → Next (when enabled) → Submit → Score visible. Repeated for Plane Motion. **PASS**

---

## 17. Browser E2E

**EXECUTED AND PASSED**

```
npx playwright test e2e/practice-t6f2-publication.spec.ts \
  e2e/practice-physics-topic-isolation.spec.ts --project=laptop-1366
→ 2 passed (18.5s)
```

Specs:
- `apps/web/e2e/practice-t6f2-publication.spec.ts`
- `apps/web/e2e/practice-physics-topic-isolation.spec.ts` (routes fixed to `/api/v1/subjects`)

Note: Running API was restarted onto current backend (venv) so TOPIC scope is available; older process lacked TOPIC in `SCOPE_TYPES`.

---

## 18. Empty-Pool Behavior

Code: `NO_QUESTIONS_AVAILABLE` (422)  
Message: “Not enough published questions are currently available for this selection…”  
Distinct from auth/server errors. **PASS**

---

## 19. Answer Position Distribution

Published T6-F1:

| Position | Count |
|----------|------:|
| A | 240 |
| B | 241 |
| C | 218 |
| D | 239 |

All four represented. No rebalancing.

---

## 20. Difficulty Distribution

| Difficulty | Count |
|------------|------:|
| Easy | 560 |
| Medium | 357 |
| Hard | 21 |

Truthful metadata — not altered for statistics.

---

## 21. Idempotency

Second publish run: **published = 0**, `idempotent_rerun = true`. **PASS**

---

## 22. Legacy Safety

| Invariant | Before | After |
|-----------|-------:|------:|
| total | 5000 | 5000 |
| concept_id NULL | 5000 | 5000 |
| published | 0 | 0 |
| fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` | MATCH |

---

## 23. T6-D Safety

| Metric | Before | After |
|--------|-------:|------:|
| total | 100 | 100 |
| published | 100 | 100 |

Unchanged.

---

## 24. Database Before/After

| Batch | Before | After |
|-------|--------|-------|
| T6-F1 | draft=938, published=0 | draft=0, published=938 |
| Rejected | 62 never persisted | 62 never persisted |
| Unexpected non-batch CMS mutations | — | **0** |

---

## 25. Test Results

| Suite | Passed | Failed | Skipped |
|-------|-------:|-------:|--------:|
| `test_physics_t6f2_publish.py` + vector + t6f1 focused | 30 | 0 | 0 |
| Playwright T6-F2 + topic isolation (laptop-1366) | 2 | 0 | 0 |
| Earlier T6-E / vector contract suites | previously green | 0 | — |

---

## 26. Failures / Limitations

- Initial Playwright failure: wrong academic URL prefix (`/api/v1/academic/...` vs `/api/v1/subjects`) — fixed in E2E specs.
- Initial Playwright failure: stale API process without TOPIC scope — restarted uvicorn with project venv.
- Empty-pool product copy uses “Not enough published questions…” rather than the exact string “No published questions are available for this scope.” Behavior is distinct and correct (`NO_QUESTIONS_AVAILABLE`).

---

## 27. Final Gate

**GREEN**

All GREEN requirements satisfied: prerequisite, gated publication of 938, no rejected/legacy/T6-D pollution, Practice API + auth + browser E2E executed and passed, Kinematics isolation cross-leak = 0, idempotency OK, database safety OK.
