# Production Seed V2 — Practice Isolation Preflight (Read-Only)

**Gate:** V2 Practice Preflight — Phase 0  
**Date:** 2026-09-04  
**Verdict: AMBER**  
**Mode:** READ-ONLY — no mutations, no V1 changes, no publication changes, no generation

This is **not** implementation complete. Publication Authorization remains **CLOSED / GREEN**. V1 Practice remains **CLOSED**.

---

## 1. V1 practice architecture

### Entry points (UI)

| Surface | File | CTA | `scope_type` |
|---------|------|-----|----------------|
| Hero **Practice now** | `apps/web/src/app/student/dashboard/page.tsx` (`HeroPracticeCta`) | Must stay unchanged | `FULL`, `question_count: 30` |
| Hero **Practice Seed V1** | same | Isolated V1 | `SEED_V1`, `question_count: 30` |
| Recommendation **Practice now** | `PracticeNowButton` | Concept-scoped | `CONCEPT` + `scope_id` |
| Practice arena | `apps/web/src/app/student/practice/page.tsx` | Scope picker or open | `SUBJECT`/`CHAPTER`/`TOPIC`/`CONCEPT` or `FULL` |
| Shared starter | `apps/web/src/features/assessment/use-start-practice.ts` | generate → start attempt → `/student/attempts/:id` | any allowed GenerateInput |

Hero **Practice now** is **not** SEED_V1. Isolated V1 is a **separate** outline button.

### Routes / API

| Step | Method | Path | Auth |
|------|--------|------|------|
| Session creation | POST | `/api/v1/assessments/practice` | JWT + CSRF |
| Start attempt | POST | `/api/v1/assessments/{id}/attempts` | JWT + CSRF |
| Load attempt | GET | `/api/v1/attempts/{id}` | JWT |
| Save answer | POST | `/api/v1/attempts/{id}/answers` | JWT + CSRF |
| Submit / score | POST | `/api/v1/attempts/{id}/submit` | JWT + CSRF |
| History | GET | `/api/v1/questions/{id}/history` | JWT |
| Runner UI | — | `/student/attempts/[attemptId]` | student layout |

Router: `apps/backend/app/modules/assessment/api/assessment_router.py`

### Scope constant and allowlist

- Constant: `SEED_V1` (`app/modules/assessment/services/assessment_service.py` `SCOPE_TYPES`)
- Membership: `app/modules/assessment/seed_v1_allowlist.py`
- Artifact: `docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json#exact_uuid_allowlist`
- Frozen SHA-256: `c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1`
- Query: `AssessmentRepository.published_question_ids_for_scope`:
  - always `content_type=QUESTION` AND `status=PUBLISHED` AND `deleted_at IS NULL`
  - **plus** `id IN seed_v1_uuids()` for `SEED_V1`
  - **FULL** adds **no** ID filter (all published questions)

Clients cannot inject UUIDs. They only send `scope_type=SEED_V1`.

### Student flow (reused for any scope)

ENTRY (CTA) → `generatePractice` → persist `assessment` + `assessment_questions` → `startAttempt` (`IN_PROGRESS`) → GET attempt (`_public_question`: **no** `correct_option` / `explanation`) → option click `saveAnswer` (upsert while IN_PROGRESS) → Next/palette → Submit → scoring (`selected_option == body.correct_option`) → GET attempt (`_result_question`: explanation + correctness) → Score badge / topic breakdown.

| Concern | Current behavior |
|---------|------------------|
| Explanation after submit | **Attempt-level** submit, not per-question. In-progress GET strips explanation. |
| Duplicate submit | `submit_attempt` raises `ATTEMPT_EXPIRED`/`already submitted` if not `IN_PROGRESS`. |
| Duplicate answer | `save_answer` **overwrites** existing row while IN_PROGRESS (intentional revisit). |
| Score / progress | Score on submit; UI progress bar = answered count. |
| Refresh | GET `/attempts/{id}` reloads server state. |
| Back/forward | Client `currentIndex` only; URL does not encode question index. |
| Restart | No dedicated restart; start a **new** practice POST. |
| Concurrent sessions | New `Attempt` every start; no uniqueness constraint. |
| Auth | `get_current_user` on router; CSRF on mutating POSTs. |
| Mobile / a11y | Touch targets, progressbar ARIA, axe in `practice-now.spec.ts`. |

### Publication firewall (CMS, not practice)

`ContentWorkflowService.publish` + `publication_gates.py` — already applied. Practice only reads `PUBLISHED`.

### V1 tests (do not change)

- `apps/backend/tests/test_seed_v1_practice_isolation.py` — hash, unknown scope, T6-D/T6-F2/legacy/other-published exclusion, FULL regression, explanation leak, scoring
- `apps/web/e2e/practice-now.spec.ts` — Hero **Practice now** (`FULL`)
- `apps/web/e2e/seed-v1-live-practice-browser-audit.cjs` + `run_seed_v1_live_practice_e2e_audit.py`
- `apps/backend/tests/test_practice_availability.py`, `test_practice_topic_scope.py`

**`SEED_V2` does not exist** in `SCOPE_TYPES`, TS `GenerateInput`, or UI.

---

## 2. V2 published cohort verification (independent DB)

Source artifact: `docs/audits/TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json`

| Check | Result |
|-------|--------|
| Artifact ID count | 100 unique |
| Artifact SHA-256 | `a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978` |
| Recomputed SHA (same order) | **exact match** |
| DB rows for those IDs | 100 |
| DB statuses | **PUBLISHED = 100** |
| Subjects | Physics 35 / Chemistry 35 / Botany 15 / Zoology 15 |
| Exact-set equality (artifact ↔ DB) | **true** |
| IDs in allowlist with superseded tags | **0** |
| Extra V2-tagged PUBLISHED outside allowlist | **0** |
| Historical 8 statuses | all **DRAFT** (not published) |
| Intersection with V1 30 | **empty** |
| T6-D / T6-F2 / legacy IDs in allowlist | **0** |
| V1 published count still 30 | **true** |

Numerical replacements (published):

- physics-10 `2e43ef71-d72a-423a-b9be-2e44c51de8b1`
- physics-11 `5b4f381e-0dee-4118-b237-fbaabbe1d0f5`
- physics-20 `f60e3124-8aa0-4ff6-b3e1-f8ad81eadce9`
- physics-34 `b98e5873-8352-4bb6-9a30-368e2f0ce6f7`

Visual slots published: physics-05, physics-21, zoology-12.

**No mismatch → do not STOP RED on cohort identity.**

---

## 3. Exact V2 fingerprint

```
a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978
```

Definition (same as V1/V2 publication): SHA-256 of artifact `exact_allowlist` joined by `\n` plus trailing newline, **order-preserving**. Independent recomputation matches the publication artifact.

---

## 4. V1 protection findings

Proved in code:

1. Hero **Practice now** still posts `FULL` only (`dashboard/page.tsx` lines 107–127).
2. **Practice Seed V1** is a distinct CTA posting `SEED_V1`.
3. Server membership for `SEED_V1` is frozen artifact + hash pin, not “latest 30”, not batch-only, not `status=PUBLISHED` alone.
4. Isolation tests assert T6-D / T6-F2 / legacy / arbitrary published IDs are excluded from SEED_V1 sessions.
5. This preflight **did not modify** any of the above.

**Risk (not a V1-seed break):** `FULL` (Hero Practice now + arena fallback) now samples **all** published questions, including the new V2 100. That is existing FULL semantics. Isolated V1 remains `SEED_V1`. Do **not** retarget Practice now to V2.

---

## 5. V2 isolation design (recommended; not implemented)

Safest pattern: **clone the V1 allowlist pattern**, do not reuse V1 IDs or FULL.

1. Add `app/modules/assessment/seed_v2_allowlist.py` analogous to `seed_v1_allowlist.py`:
   - Load `TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json` `exact_allowlist`
   - Pin `EXPECTED_ALLOWLIST_SHA256 = a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978`
   - Reject load if count ≠ 100 or hash mismatch
2. Add `SEED_V2` to `SCOPE_TYPES` and `SCOPES_WITHOUT_ID`.
3. In `published_question_ids_for_scope`, `SEED_V2` → `id IN seed_v2_uuids()` **AND** existing PUBLISHED filter (never PUBLISHED alone).
4. `generate_practice`: title `Production Seed V2 practice`, default count **100**, attach `seed_v2_allowlist_sha256` in meta.
5. Raise `GenerateRequest.question_count` max from **90 to ≥100** (or special-case SEED_V2). **Current `le=90` cannot request 100.**
6. TS: extend `GenerateInput.scope_type` with `"SEED_V2"`.
7. **New CTA only**, e.g. dashboard outline **Practice Seed V2**, `aria-label` distinct from V1, `seedStartV2.mutate({ scope_type: "SEED_V2", question_count: 100 })`.
   - Page: `/student/dashboard` (and optionally practice arena extra button)
   - Do **not** change Practice now or Practice Seed V1 handlers
8. Reuse attempt runner, save/submit, scoring, explanation-after-submit, auth.

**Must not:** `ORDER BY created_at LIMIT 100`, batch UUID without allowlist, V1 allowlist, FULL, DRAFT/APPROVED, superseded tags.

---

## 6. Required implementation changes (next phase — not this phase)

| Item | Status now |
|------|------------|
| `SEED_V2` scope + allowlist module | **Missing** |
| Repository branch for SEED_V2 | **Missing** |
| `question_count` Pydantic max ≥ 100 | **Missing** (`le=90`) |
| Frontend type + dedicated CTA | **Missing** |
| Isolation unit tests (V2) | **Missing** |
| Playwright E2E for Seed V2 | **Missing** |
| V1 Practice now | Must remain `FULL` |
| Question content / publication | Must not change |

Existing attempt UI can be reused **if** the assessment is created with `SEED_V2`.

---

## 7. Required E2E test plan (future)

A. Dedicated V2 entry (not Practice now)  
B. First question visible  
C. Every `content_item_id` ∈ exact 100 allowlist  
D. Each ID `status=PUBLISHED` in DB  
E. None carry superseded tags  
F. Correct option save + later submit scores +1  
G. Incorrect option scores incorrect  
H. GET in-progress: no explanation / correct_option; after submit: both present  
I. Next / palette  
J. Progress bar  
K. Score badge  
L. Completion SUBMITTED  
M. Refresh retains attempt  
N. Browser back/forward (document: index is client-only)  
O. Restart = new POST SEED_V2  
P. Second submit → 409  
Q. Logout/login: attempt owned by user  
R. Two concurrent SEED_V2 attempts allowed (current model)  
S. Mobile viewport overflow  
T. axe critical/serious empty  
U. assessment.questions ⊆ allowlist in DB  
V. Firewall negatives (below)  
W. V1 regression: SEED_V1 still 30 + hash; Practice now still FULL  

---

## 8. Negative firewall tests (required)

Reject from a SEED_V2 session:

- Any V1 allowlist ID  
- T6-D tag IDs  
- T6-F2 tag IDs  
- Legacy tag IDs  
- DRAFT / APPROVED even if tagged seed-v2  
- Historical superseded 8 (currently DRAFT)  
- Arbitrary other PUBLISHED IDs  
- Client-supplied UUID lists (must ignore; server allowlist only)  
- `scope_type=SEED_V1` must not return V2 IDs  
- Unknown `SEED_V2` today → `INVALID_SCOPE` (proves not accidentally live)

---

## 9. Risks

1. **FULL pool contamination:** Hero Practice now can now mix V2 into general practice. Isolated V2 must be a **new** CTA, not a rewrite of Practice now.  
2. **`question_count` ≤ 90** blocks an exact-100 session without a schema bump.  
3. **Random sample:** `sample_question_ids` shuffles; if count=100 and pool=100, all IDs are included (order random). If count stays 90, 10 V2 items never appear — avoid.  
4. **Per-question instant explanation** is **not** current product behavior; E2E must not assume it.  
5. **No concurrent-session lock** — two V2 attempts can run; document, don’t invent a lock in this gate.  
6. **Question index not in URL** — refresh stays on Q1 unless local state restored (currentIndex resets). Pre-existing.  
7. Implementing SEED_V2 incorrectly as FULL-with-filter-in-UI would leak. Server must own membership.

---

## 10. Recommendation

- **Do not implement in this phase.**  
- Next authorized gate: **V2 Practice Isolation Implementation** following §5, plus tests in §7–8, plus **V1 regression W**.  
- Keep publication closed. Do not generate. Do not retarget Practice now.

**Verdict AMBER:** exact published V2 100 is verified and the V1 SEED pattern is a safe template, but **SEED_V2 and a dedicated CTA do not exist yet**. Isolation cannot be claimed until those components land. V1 does **not** need modification for that work.

---

**STOP** — V2 Practice Preflight only. No practice rollout, no 1k generation.
