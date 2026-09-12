# PRODUCTION SEED V1 — PRACTICE ISOLATION REMEDIATION REPORT

**Date:** 2026-09-03  
**Verdict:** GREEN  
**allowlist_sha256:** `c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1`

## Summary

Added server-enforced `scope_type=SEED_V1` that resolves exclusively to the frozen Production Seed V1 UUID allowlist. Hero **Practice now** remains `FULL`. New dashboard CTA **Practice Seed V1** requests the isolated scope.

## Scope contract

- Client sends: `{ "scope_type": "SEED_V1", "question_count": 30 }`
- Server loads membership from `TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json`
- Query: `id IN (exact 30) AND status=PUBLISHED`
- Response meta includes `seed_v1_allowlist_sha256` + `seed_v1_allowlist_count`
- Clients cannot inject UUID lists

## Implementation files

- `apps/backend/app/modules/assessment/seed_v1_allowlist.py`
- `apps/backend/app/modules/assessment/repositories/assessment_repository.py`
- `apps/backend/app/modules/assessment/services/assessment_service.py`
- `apps/backend/app/modules/assessment/schemas/assessment.py`
- `apps/backend/app/modules/assessment/models/assessment.py`
- `apps/web/src/features/assessment/api.ts`
- `apps/web/src/app/student/dashboard/page.tsx`
- `apps/backend/tests/test_seed_v1_practice_isolation.py`
- `apps/backend/scripts/run_seed_v1_live_practice_e2e_audit.py`
- `apps/web/e2e/seed-v1-live-practice-browser-audit.cjs`

## Test results

- Pytest (seed isolation + practice regression): **15 passed**
- Backend live E2E: **GREEN**
- Browser live E2E: **PASS**
  - CTA → `POST /practice` scope_type=`SEED_V1` 201
  - 30/30 allowlist membership (`outside_count=0`)
  - FULL CTA still visible

## Firewall

- Seed session unique IDs match frozen allowlist: **True**
- FULL still broader than Seed: **True**

## Content / protected integrity

- Seed status: `{"PUBLISHED": 30}`
- Fingerprint mismatches vs post-publication: **0**
- T6-D unchanged: **True**
- T6-F2 unchanged: **True**
- Legacy unchanged: **True**
- ECAEP: **0**

## Gate matrix

```json
{
  "implementation": "PASS",
  "seed_scope": "PASS",
  "exact_allowlist": "PASS",
  "seed_firewall": "PASS",
  "hero_seed_cta": "PASS",
  "practice_init": "PASS",
  "answer_submission": "PASS",
  "explanation": "PASS",
  "next_question": "PASS",
  "progress": "PASS",
  "scoring": "PASS",
  "completion": "PASS",
  "full_regression": "PASS",
  "browser_e2e": "PASS",
  "backend_e2e": "PASS",
  "content_integrity": "PASS",
  "t6d_unchanged": "PASS",
  "t6f2_unchanged": "PASS",
  "ecaep_zero": "PASS"
}
```

## Final verdict

**GREEN**
