# TALOS T6-A/B/C — Safe Practice Integration Implementation

**Date:** 2026-09-02  
**Source audits:** T5 live Practice + taxonomy integration; P0 taxonomy implementation (GREEN)

---

## 1. Executive Verdict

```text
GREEN — T6-A/B/C IMPLEMENTED AND VERIFIED
```

TOPIC practice scope is end-to-end (API + ScopePicker + types). Kinematics topic-tree separation is verified in `trinetra_test_db` with rollback-scoped fixtures (no live question inventory changes). Empty-pool UX is explicit. Authenticated practice path verified via existing `register_user` ASGI tests. Legacy 5,000 fingerprint unchanged.

---

## 2. Scope

```text
T6-A authenticated Practice path
T6-B UX behavior
T6-C TOPIC scope
```

**Not in scope:** publication, legacy classification, P1/P2, Gravitation, AI prompts, ECAEP, MCQ generation.

---

## 3. Files Changed

| File | Change |
|------|--------|
| `apps/backend/app/modules/assessment/services/assessment_service.py` | `TOPIC` in `SCOPE_TYPES` |
| `apps/backend/app/modules/assessment/repositories/assessment_repository.py` | TOPIC join filter |
| `apps/backend/app/modules/assessment/schemas/assessment.py` | Comment / contract |
| `apps/backend/app/modules/assessment/models/assessment.py` | Comment |
| `apps/backend/tests/test_practice_topic_scope.py` | **New** — auth, TOPIC, Kinematics, empty pool |
| `apps/web/src/features/assessment/api.ts` | `TOPIC` in Assessment + GenerateInput |
| `apps/web/src/components/scope-picker.tsx` | Subject→Chapter→Topic→Concept |
| `apps/web/src/app/student/practice/page.tsx` | Empty-pool status UI |
| `apps/web/src/app/student/dashboard/page.tsx` | Disabled CTA copy; hero empty-pool |
| `apps/web/src/components/ds/quick-launch-hub.tsx` | Navigation-only clarity |
| `apps/web/src/features/assessment/use-start-practice.ts` | Auth / empty / 5xx messages |
| `apps/web/src/features/assessment/use-start-practice.test.ts` | Message unit tests |
| `apps/web/src/features/assessment/thin-content.ts` | Aligned student copy |
| `docs/audits/TALOS_T6_SAFE_PRACTICE_INTEGRATION_IMPLEMENTATION_20260902.md` | This report |

---

## 4. API Contract Before/After

**Before:** `scope_type ∈ {CONCEPT, CHAPTER, SUBJECT, FULL}` with optional `scope_id` (required unless FULL).

**After:** `scope_type ∈ {CONCEPT, TOPIC, CHAPTER, SUBJECT, FULL}` — same request shape `{ scope_type, scope_id?, question_count? }`.

| Scope | Semantics (unchanged unless noted) |
|-------|-------------------------------------|
| FULL | All PUBLISHED questions (`deleted_at IS NULL`) |
| SUBJECT | Published questions under concepts in subject |
| CHAPTER | Published questions under **all topics** of chapter |
| **TOPIC** | **NEW** — published questions whose concept has `topic_id = scope_id` only |
| CONCEPT | Published questions with `concept_id = scope_id` |

Empty published set → `422 NO_QUESTIONS_AVAILABLE` (not a silent empty 201).  
Missing `scope_id` for TOPIC → `400 MISSING_SCOPE_ID`.  
Unknown `scope_type` → `400 INVALID_SCOPE`.

---

## 5. Frontend Changes

- ScopePicker emits `TOPIC` when a topic is selected without a concept.
- Concepts load **per selected topic** (no longer flatten all chapter concepts).
- Practice arena: distinct **status** Alert for empty pool vs destructive API failures.
- Dashboard concept CTA: remains **disabled** at `publishedCount === 0` with explicit copy.
- Quick Launch: **“Practice arena”** / “Configure scope, then start drills” (navigation-only).
- Hero secondary CTA: **“Open practice arena”**.

---

## 6. Backend Changes

- `SCOPE_TYPES` includes `TOPIC`.
- Repository: `ContentItem ⋈ Concept WHERE Concept.topic_id = scope_id`.
- Mock generation reuses the same `_generate` path → TOPIC also works for mocks via shared ScopePicker.

---

## 7. Database Query Changes

Application SQL only (no migrations, no indexes added). Filter uses FK `concepts.topic_id` — no name matching.

---

## 8. Kinematics Verification

```text
one chapter = kinematics
two topic trees = motion-in-a-straight-line | motion-in-a-plane
topic-level separation = VERIFIED (test DB fixtures)
```

Test `test_kinematics_topic_scopes_do_not_cross_leak`:

- TOPIC straight → includes straight Q, excludes plane Q  
- TOPIC plane → includes plane Q, excludes straight Q  
- CHAPTER kinematics → includes both  
- CONCEPT / SUBJECT preserved  

Live DB still has 0 published under those topics (expected; content not published in T6).

---

## 9. Empty Pool Behavior

| Layer | Behavior |
|-------|----------|
| API | `422` + `NO_QUESTIONS_AVAILABLE` |
| Practice page | Non-destructive status Alert: “Practice is not available… No published questions…” |
| Dashboard concept CTA | Disabled + explanation (not clickable empty) |
| Hero FULL empty | Status Alert when mutation returns empty-pool code |

Distinguished from auth redirect and generic API failure copy.

---

## 10. Authentication Behavior

| Check | Result |
|-------|--------|
| Unauthenticated `POST /assessments/practice` | Rejected (`401`/`403`) — `test_practice_unauthenticated_rejected` |
| Authenticated via `register_user` | Can call practice — `test_practice_full_scope_authenticated` |
| Browser middleware | Unchanged: `/student/*` requires `access_token` |
| Live Playwright session | Not re-run against live DB (would create attempts); existing e2e harness (`e2e/global-setup.ts` + `practice-now.spec.ts`) remains the browser path |

Auth was **not** weakened.

---

## 11. Legacy 5,000 Protection

| Metric | Before | After | Expected |
|--------|-------:|------:|---------:|
| Legacy rows | 5000 | 5000 | unchanged |
| `concept_id IS NULL` | 5000 | 5000 | unchanged |
| Published legacy rows | 0 | 0 | unchanged |
| Fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` | `937c60a9aaa5dcbedfa9b5bc569d45a0` | MATCH |

---

## 12. Test Matrix

| Case | Covered |
|------|---------|
| Unauthenticated practice | YES |
| FULL authenticated | YES |
| SUBJECT / CHAPTER / CONCEPT | YES (Kinematics fixture test) |
| TOPIC filter | YES |
| Kinematics straight ≠ plane | YES |
| Empty TOPIC pool | YES |
| Missing TOPIC scope_id | YES |
| Invalid scope_type | YES |
| Nonexistent topic UUID | YES → empty → 422 |
| Legacy protection | Read-only live verify |
| Frontend message copy | Vitest |

---

## 13. Test Results

```text
pytest tests/test_practice_topic_scope.py tests/test_practice_availability.py
11 passed

vitest use-start-practice.test.ts
5 passed
```

---

## 14. Performance Observations

TOPIC filter is a single join on `concept_id` / `topic_id` FKs — same class as CONCEPT. No new speculative indexes. 1M-scale sampling concern from T5 remains a follow-up (T6-F), not blocking TOPIC correctness.

---

## 15. Known Limitations

- Live published Physics under Kinematics/P0 remains **0** — students still see empty-pool UX for those scopes until content is published (T6-D).
- Malformed non-UUID `scope_id` may surface as framework validation error (pre-existing UUID parse), not a dedicated code — same as other scopes.
- Browser Playwright CTA not re-executed in this task against live inventory (write avoidance).

---

## 16. Out-of-Scope Work

```text
Question publication
Legacy classification
Legacy remediation
MCQ generation
P1 taxonomy
P2 taxonomy
Gravitation
ECAEP
AI prompt implementation
```

---

## 17. Recommended T6-D Next Step

**T6-D — Content readiness (publish + careful taxonomy assignment):**

- Use ECAEP to publish eligible Physics inventory into P0 concepts/topics.  
- Do **not** bulk-map the 5,000 legacy DRAFT rows without a verified classification gate.  
- After publish, re-verify Practice FULL / TOPIC counts and Kinematics separation on live `trinetra_db`.  
- Keep legacy fingerprint discipline.

Do **not** implement T6-D in this change set.

---

## Taxonomy report

| Metric | Expected | Actual |
|--------|---------:|-------:|
| P0 nodes | 74 | 74 |
| Gravitation nodes | 0 | 0 |
| Kinematics chapters | 1 | 1 |
| Kinematics topic trees | 2 | 2 |

---

## Final verdict

```text
GREEN — T6-A/B/C IMPLEMENTED AND VERIFIED
```

## Machine-readable safety summary

```text
Application code changes = 13 files (+1 new test module + this audit)
Database taxonomy writes = 0
Question writes = 0
Questions modified = 0
concept_id assignments = 0
Publication changes = 0
Legacy 5000 rows modified = 0
Legacy fingerprint changed = NO
P0 taxonomy nodes modified = 0
Gravitation nodes added = 0
P1 taxonomy implemented = 0
P2 taxonomy implemented = 0
TOPIC scope implemented = YES
Kinematics topic separation verified = YES
Empty pool handling verified = YES
Authentication behavior verified = YES
Final verdict = GREEN
```
