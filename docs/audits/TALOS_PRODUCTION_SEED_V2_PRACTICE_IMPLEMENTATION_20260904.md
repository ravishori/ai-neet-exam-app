# TALOS Production Seed V2 — Practice Implementation Verification

**Date:** 2026-09-04  
**Gate:** SEED_V2 practice isolation (implementation verification only)  
**Complete V2 Practice E2E gate:** **not claimed** — STOP after this audit.

## Verdict: GREEN (implementation)

SEED_V2 is implemented, pinned to the exact published V2 allowlist, `question_count` 91–100 is isolated to SEED_V2, negative firewall tests pass, V1 practice paths are unchanged, and no question/publication content was mutated.

This is **not** a student live E2E GREEN.

## V2 allowlist

| Field | Value |
| --- | --- |
| Count | 100 |
| SHA-256 | `a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978` |
| Source | `docs/audits/TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json` field `exact_allowlist` |
| Subject mix (artifact) | Physics 35 / Chemistry 35 / Botany 15 / Zoology 15 |

Membership is **EXACT_V2_ALLOWLIST** ∩ `content_type=QUESTION` ∩ `status=PUBLISHED` ∩ `deleted_at IS NULL` ∩ tags do not overlap superseded rematerialization/numerical tags. IDs absent from the frozen list cannot enter SEED_V2. Latest-100 / created_at / batch-only / subject-only / status-alone are not used.

## SEED_V2 query / firewall

```text
id IN seed_v2_uuids()  -- frozen artifact, server-owned
AND content_type = QUESTION
AND status = PUBLISHED
AND deleted_at IS NULL
AND NOT (tags && ARRAY[visual-superseded, numerical-superseded])
```

Client `question_ids` / forged allowlist / forged SHA are ignored. Scope is only `scope_type=SEED_V2` on `POST /api/v1/assessments/practice`.

## Question-count change

- Generic scopes (FULL, SEED_V1, taxonomy): still `question_count <= 90`.
- SEED_V2 only: `91–100` accepted; `101` rejected for all scopes.
- Default SEED_V2 count: 100.

FULL cannot request 100 through the shared generate schema.

## UI entry point

Dashboard **Practice Seed V2** → `{ scope_type: "SEED_V2", question_count: 100 }`.

Unchanged:

- Hero **Practice now** → `FULL`, 30
- **Practice Seed V1** → `SEED_V1`, 30
- Practice arena default FULL/taxonomy behavior

## Implementation files

- `apps/backend/app/modules/assessment/seed_v2_allowlist.py` (new)
- `apps/backend/app/modules/assessment/repositories/assessment_repository.py`
- `apps/backend/app/modules/assessment/services/assessment_service.py`
- `apps/backend/app/modules/assessment/schemas/assessment.py`
- `apps/backend/app/modules/assessment/models/assessment.py` (comment)
- `apps/web/src/features/assessment/api.ts`
- `apps/web/src/app/student/dashboard/page.tsx`
- `apps/backend/tests/test_seed_v2_practice_isolation.py` (new)

## Tests

### Positive

- Allowlist count 100 + SHA match + subject_distribution on artifact
- SEED_V2 session create; request 100; delivered IDs ⊆ patched/exact allowlist; all PUBLISHED; superseded/draft/approved/ghost excluded
- Answers, progress, submit, score, explanations after submit, restart attempt
- Subject mix of the **cohort** is the frozen 35/35/15/15 (selection samples that allowlist; pytest uses a 3-ID fixture pool)

### Negative

1. V1-stand-in published ID  
2. T6-D tagged ID  
3. T6-F2 tagged ID  
4. Legacy tagged ID  
5. Arbitrary published outsider  
6. Historical superseded (allowlisted + superseded tags)  
7. DRAFT on allowlist  
8. APPROVED on allowlist  
9. Nonexistent allowlist ID  
10. Forged/modified client scope (`SEED_V1`, `FULL`, spaced `SEED_V2 `)  
11. Forged allowlist / SHA / `question_ids` in body  
12. FULL `question_count=100` on the same practice endpoint  

### Count

- 90 works (FULL)
- 91–100 accepted for SEED_V2
- 101 rejected

### V1 regression (unmodified `test_seed_v1_practice_isolation.py` + extra V2-file check)

- Hero Practice now remains FULL
- Practice Seed V1 / SEED_V1 / 30-ID SHA `c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1` unchanged
- V1 ∩ V2 allowlists disjoint

**Pytest:** 22 passed (`test_seed_v2_practice_isolation` + `test_seed_v1_practice_isolation` + `test_practice_availability` + `test_practice_topic_scope`)

## Protected-population checks

- V1 allowlist module and SHA not edited
- No CMS publish/approve/generate scripts run
- No Gemini calls
- Publication authorization artifact not rewritten

## Limitations

- Live student browser E2E against production 100 is **out of scope** (next gate).
- Pytest firewall uses a patched 3-UUID pool; SHA/count/subject mix of the real 100 is asserted from the frozen artifact.
- Hero FULL practice can still include V2 published items in the **general** pool (pre-existing FULL semantics; button not retargeted).
- `CERTIFIED_WITH_LIMITATION` / `page_verified=false` from NCERT re-run are unchanged content limitations.

## Explicit non-claims

- Complete V2 Practice gate is **not GREEN**.
- 1,000-question generation was **not** started.
