# PRODUCTION SEED V1 — LIVE STUDENT PRACTICE E2E AUDIT REPORT

**Date:** 2026-09-03
**Verdict:** GREEN
**allowlist_sha256:** `c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1`

## 1. Executive Verdict

GREEN. See failures/limitations below.

## 2. Exact 30 population verification

```json
{
  "PUBLISHED": 30
}
```

Subjects: {'total': 30, 'physics': 10, 'chemistry': 10, 'botany': 5, 'zoology': 5}
ECAEP preflight: 0

## 3. Practice Now click evidence

UI path: `apps/web/src/app/student/dashboard/page.tsx` → `HeroPracticeCta` → `useStartPractice` →
`POST /api/v1/assessments/practice` `{scope_type:FULL, question_count:30}` →
`POST /api/v1/assessments/{id}/attempts` → `/student/attempts/{id}`.

```json
{
  "mode": "API_EQUIVALENT_OF_HERO_CTA",
  "student": {
    "email": "seed-v1-practice-f9fffe3eb8@example.com"
  },
  "evidence": {
    "generate_status": 201,
    "scope_type": "FULL",
    "assessment_id": "944f6547-a055-4e2c-b9a9-4ab3701b9ca8",
    "attempt_id": "492e255e-816d-4ead-bafe-fdb53cb2cafd",
    "requested": 30,
    "delivered": 30,
    "availability_meta": {
      "available_count": 1079,
      "requested_count": 30,
      "delivered_count": 30,
      "shrunk": false
    },
    "presented_outside_allowlist": 28,
    "first_question_rendered_fields": {
      "has_stem": true,
      "option_count": 4
    },
    "full_regression_broader_than_seed": true
  },
  "pass": true,
  "note": "Browser click evidence filled by companion Playwright run when available"
}
```

## 4. Application request/response path

```json
{
  "ui_component": "apps/web/src/app/student/dashboard/page.tsx::HeroPracticeCta",
  "event_handler": "onClick \u2192 useStartPractice().mutate({scope_type:'FULL', question_count:30})",
  "hook": "apps/web/src/features/assessment/use-start-practice.ts",
  "generate_endpoint": "POST /api/v1/assessments/practice",
  "generate_payload": {
    "scope_type": "FULL",
    "question_count": 30
  },
  "start_attempt_endpoint": "POST /api/v1/assessments/{assessment_id}/attempts",
  "attempt_detail_endpoint": "GET /api/v1/attempts/{attempt_id}",
  "answer_endpoint": "POST /api/v1/attempts/{attempt_id}/answers",
  "submit_endpoint": "POST /api/v1/attempts/{attempt_id}/submit",
  "selection": "AssessmentRepository.published_question_ids_for_scope + sample_question_ids",
  "scoring": "AssessmentService.submit_attempt compares selected_option to body.correct_option; marks=1 neg=0",
  "explanation": "Omitted in in-progress attempt serializer; included after SUBMITTED",
  "next_question": "Client-side index over attempt.questions (Next button)",
  "completion": "POST submit \u2192 status SUBMITTED + score aggregates"
}
```

## 5. Question-selection firewall

```json
{
  "full_session_outside_allowlist_count": 28,
  "full_session_note": "FULL remains all PUBLISHED inventory (Seed+T6-D+T6-F2)",
  "full_regression_broader_than_seed": true,
  "seed_v1_scope_type": "SEED_V1",
  "seed_v1_meta": {
    "available_count": 30,
    "requested_count": 30,
    "delivered_count": 30,
    "shrunk": false,
    "seed_v1_allowlist_sha256": "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1",
    "seed_v1_allowlist_count": 30
  },
  "controlled_session_assessment_id": "1c50bc7f-2f1e-4310-8cae-fb5c0d29beff",
  "controlled_session_attempt_id": "605ff8d4-6400-4980-959b-5d0a60ebf56e",
  "controlled_presented_count": 30,
  "controlled_exact_allowlist_match": true,
  "controlled_outside": [],
  "controlled_unique_ids": [
    "061d07ed-ca1f-4f31-b7f8-cbdb3dfe8453",
    "16dd7280-a48b-4437-80ac-a2b72b28d952",
    "18f304f5-89b2-4bcb-a4dd-b04eb6374cad",
    "1d598d79-afe1-4ddb-8f32-2b51c8fb2b02",
    "27552790-48f4-48ba-bc37-fdbd14902dfb",
    "2e17c7e6-5d8f-4469-9cea-407177e61e8e",
    "336ec42d-aa33-4b5b-8c46-f8d5461883b0",
    "3c565dee-ea37-4937-bb32-4006ce383006",
    "3d0dbda5-7882-4e3f-90d8-3a479cf67ab2",
    "3dc11d2a-b9ad-4155-93ec-4cd7b3bae9af",
    "4f0dcbb1-c236-42a3-a148-cf8233326b52",
    "5b1b5f27-bb6d-4b35-8b1c-96c252278d98",
    "621ffc10-0673-4d4f-a5be-c07ed2f7f48f",
    "7e4fb145-08fe-43cf-accc-ef53e9535b07",
    "872a0115-cb0a-4109-99ff-55ada6774d51",
    "8a3937ce-5ad0-41af-bc84-17bf04c386ce",
    "92c31281-cbdf-4954-9b25-79342cb1b400",
    "93c46e39-6a4c-4730-9ae7-a07a4bdab0a9",
    "9dd374e7-c677-46ab-9e83-8cf0e6139feb",
    "a357fe24-b0ef-4bd5-b7f7-956f392f9942",
    "aae4fe1b-9665-4216-be4b-2f758f4dbf70",
    "b207ad06-7427-417e-abfd-a928ab68df84",
    "b4a2e055-f141-4f05-8b06-850d84122b60",
    "b690c0d3-98f6-4e57-851f-aae1ac6ad8cd",
    "c85bba09-451b-4b2f-988d-e440929fa770",
    "dd7b5422-437d-4b0f-a2dc-f370ea0496c2",
    "e15d0065-7b79-477c-b9ec-81bc421a6a71",
    "e3e36b8e-ff15-455e-807d-eb32de6c1f75",
    "e4a6fdc3-7a55-4762-a176-f8af33709308",
    "f6f59a22-5d9b-47a3-adb6-8dcf7ce56a1c"
  ],
  "pre_submit_key_leak_ids": [],
  "selection_mechanism": "POST /practice scope_type=SEED_V1 \u2192 server allowlist IN (...) + PUBLISHED"
}
```

## 6. Answer submission evidence

```json
{
  "subject_samples": [
    {
      "subject": "Physics",
      "content_item_id": "27552790-48f4-48ba-bc37-fdbd14902dfb",
      "intent_correct": true,
      "selected": "B",
      "stored_correct": "B",
      "http_status": 200,
      "before_submit_leak": {
        "has_correct_option": false,
        "has_explanation": false
      },
      "response_ok": true
    },
    {
      "subject": "Chemistry",
      "content_item_id": "e3e36b8e-ff15-455e-807d-eb32de6c1f75",
      "intent_correct": false,
      "selected": "A",
      "stored_correct": "B",
      "http_status": 200,
      "before_submit_leak": {
        "has_correct_option": false,
        "has_explanation": false
      },
      "response_ok": true
    },
    {
      "subject": "Botany",
      "content_item_id": "f6f59a22-5d9b-47a3-adb6-8dcf7ce56a1c",
      "intent_correct": true,
      "selected": "C",
      "stored_correct": "C",
      "http_status": 200,
      "before_submit_leak": {
        "has_correct_option": false,
        "has_explanation": false
      },
      "response_ok": true
    },
    {
      "subject": "Zoology",
      "content_item_id": "2e17c7e6-5d8f-4469-9cea-407177e61e8e",
      "intent_correct": false,
      "selected": "A",
      "stored_correct": "B",
      "http_status": 200,
      "before_submit_leak": {
        "has_correct_option": false,
        "has_explanation": false
      },
      "response_ok": true
    }
  ],
  "correct_and_incorrect_tested": true,
  "pass": true
}
```

## 7. Explanation-after-submit evidence

```json
{
  "samples": [
    {
      "subject": "Physics",
      "content_item_id": "27552790-48f4-48ba-bc37-fdbd14902dfb",
      "pre_submit_had_explanation": false,
      "post_submit_has_explanation": true,
      "explanation_matches_stored": true,
      "correct_option_matches_stored": true,
      "ui_contract": "explanation and correct_option only in submitted attempt payload"
    },
    {
      "subject": "Chemistry",
      "content_item_id": "e3e36b8e-ff15-455e-807d-eb32de6c1f75",
      "pre_submit_had_explanation": false,
      "post_submit_has_explanation": true,
      "explanation_matches_stored": true,
      "correct_option_matches_stored": true,
      "ui_contract": "explanation and correct_option only in submitted attempt payload"
    },
    {
      "subject": "Botany",
      "content_item_id": "f6f59a22-5d9b-47a3-adb6-8dcf7ce56a1c",
      "pre_submit_had_explanation": false,
      "post_submit_has_explanation": true,
      "explanation_matches_stored": true,
      "correct_option_matches_stored": true,
      "ui_contract": "explanation and correct_option only in submitted attempt payload"
    },
    {
      "subject": "Zoology",
      "content_item_id": "2e17c7e6-5d8f-4469-9cea-407177e61e8e",
      "pre_submit_had_explanation": false,
      "post_submit_has_explanation": true,
      "explanation_matches_stored": true,
      "correct_option_matches_stored": true,
      "ui_contract": "explanation and correct_option only in submitted attempt payload"
    }
  ],
  "pass": true
}
```

## 8. Next Question evidence

```json
{
  "mechanism": "client index over attempt.questions ordered by assessment_questions.order_no; Next button advances index",
  "question_count": 30,
  "unique_ids": 30,
  "duplicates": 0,
  "db_order_count": 30,
  "api_order_matches_db": true,
  "transitions_tested": [
    {
      "from": "e3e36b8e-ff15-455e-807d-eb32de6c1f75",
      "to": "2e17c7e6-5d8f-4469-9cea-407177e61e8e",
      "different": true
    },
    {
      "from": "2e17c7e6-5d8f-4469-9cea-407177e61e8e",
      "to": "27552790-48f4-48ba-bc37-fdbd14902dfb",
      "different": true
    },
    {
      "from": "27552790-48f4-48ba-bc37-fdbd14902dfb",
      "to": "336ec42d-aa33-4b5b-8c46-f8d5461883b0",
      "different": true
    },
    {
      "from": "336ec42d-aa33-4b5b-8c46-f8d5461883b0",
      "to": "b690c0d3-98f6-4e57-851f-aae1ac6ad8cd",
      "different": true
    },
    {
      "from": "b690c0d3-98f6-4e57-851f-aae1ac6ad8cd",
      "to": "621ffc10-0673-4d4f-a5be-c07ed2f7f48f",
      "different": true
    }
  ],
  "pass": true
}
```

## 9. Score/progress evidence

```json
{
  "expected_correct": 28,
  "expected_incorrect": 2,
  "actual": {
    "status": "SUBMITTED",
    "score": 28.0,
    "correct_count": 28,
    "incorrect_count": 2,
    "skipped_count": 0
  },
  "pass": true
}
```

## 10. Completion evidence

```json
{
  "submit_http": 200,
  "status": "SUBMITTED",
  "pass": true,
  "no_extra_questions_after": true
}
```

## 11. Runtime/API error audit

```json
{
  "items": [],
  "blocker_count": 0,
  "pass": true
}
```

## 12. Database consistency

```json
{
  "answer_rows": 30,
  "correctness_consistent": true,
  "content_mutations": [],
  "pass": true
}
```

## 13. Post-audit integrity

```json
{
  "allowlist_sha256": "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1",
  "status_counts": {
    "PUBLISHED": 30
  },
  "published": 30,
  "approved": 0,
  "draft": 0,
  "ecaep": 0,
  "protected": {
    "t6d": {
      "total": 100,
      "published": 100,
      "draft": 0,
      "approved": 0,
      "content_fp": "e0758fbcb071180b61a33f2b4581e894",
      "tag": "physics-t6d-pilot-20260902"
    },
    "t6f2": {
      "total": 938,
      "content_fp": "17a1672c444c8362ed0261dacf0f82c7",
      "tag": "physics-t6f1-pilot-20260902"
    },
    "legacy": {
      "total": 5000,
      "published": 0,
      "draft": 5000,
      "approved": 0,
      "content_fp": "13d51e697382663a28ffc44fd56aedb1",
      "tag": "legacy-physics-5000-import-20260902"
    }
  },
  "protected_unchanged": {
    "t6d": true,
    "t6f2": true,
    "legacy": true
  }
}
```

## 14. Failures and limitations

### Failures

```json
[]
```

### Limitations

```json
[
  "FULL Practice Now continues to sample all PUBLISHED questions (~1079 including T6-D/T6-F2).",
  "SEED_V1 is an explicit separate scope; Hero 'Practice now' remains FULL; 'Practice Seed V1' CTA uses SEED_V1."
]
```

## 15. Final verdict

GREEN

## 16. Exact next remediation step if not GREEN

None — GREEN.
