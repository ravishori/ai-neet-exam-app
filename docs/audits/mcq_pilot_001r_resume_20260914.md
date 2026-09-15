# MCQ-PILOT-001R — Rate-limit-aware resume

- Generated: `2026-09-13T19:40:08.811981+00:00`
- Final status: **YELLOW — GENERATION PARTIALLY COMPLETE / PROVIDER LIMITED**
- Publication / NCERT certification / editorial approval: **NONE**
- Git: **no commit / no push**

## Previous pilot state
- Previously CREATED: `129`
- Physics was complete and **not regenerated**

## Resume request
- Resume requested: `271` (Chem 71 + Botany 100 + Zoology 100)
- Resume CREATED: `0`
- Final total CREATED: `129`
- Remaining gap: `271`

## Subject final counts

| Subject | Target | Final CREATED | Gap |
|---|---:|---:|---:|
| PHYSICS | 100 | 100 | 0 |
| CHEMISTRY | 100 | 29 | 71 |
| BOTANY | 100 | 0 | 100 |
| ZOOLOGY | 100 | 0 | 100 |

## Telemetry A–L
- A total requested: `400`
- B previously created: `129`
- C resume requested: `271`
- D resume CREATED: `0`
- E provider rate-limit failures: `0`
- F other provider failures: `219`
- G parse failures: `0`
- H validation rejections: `0`
- I duplicate rejections: `0`
- J retries: `0`
- K final total CREATED: `129`
- L remaining gap: `271`

## Yield (rate-limit excluded from content denominator)
- Content processing yield: `0.0%`
- Overall 400-request CREATED rate: `32.25%`

```json
{
  "resume_created": 0,
  "provider_rate_limit_failures": 0,
  "other_provider_failures": 219,
  "failed_parse": 0,
  "rejected_validation": 0,
  "duplicate": 0,
  "retries": 0,
  "attempted": 219,
  "A_total_requested": 400,
  "B_previously_created": 129,
  "C_resume_requested": 271,
  "D_resume_created": 0,
  "E_provider_rate_limit_failures": 0,
  "F_other_provider_failures": 219,
  "G_parse_failures": 0,
  "H_validation_rejections": 0,
  "I_duplicate_rejections": 0,
  "J_retries": 0,
  "K_final_total_created": 129,
  "L_remaining_gap": 271,
  "final_total_created": 129,
  "remaining_gap": 271,
  "content_processing_yield_pct": 0.0,
  "overall_created_rate_pct": 32.25,
  "candidate_status_counts_pilot": {
    "CREATED": 129,
    "REJECTED_VALIDATION": 6,
    "FAILED_PARSE": 1,
    "FAILED_PROVIDER": 437
  },
  "rate_limit_candidate_rows": 0
}
```

## Rate-limit handling
```json
{
  "provider_fixed": "anthropic",
  "no_silent_provider_switch": true,
  "concurrency": 1,
  "max_resume_retries_per_bp": 3,
  "base_backoff_s": 20.0,
  "max_backoff_s": 300.0,
  "retry_after_honored_when_present": true,
  "consecutive_rl_stop": 6,
  "initial_cooldown_s": 45,
  "gateway_note": "AI gateway classifies HTTP 429 as PROVIDER_RATE_LIMITED (retryable) but does not sleep; resume layer adds backoff/jitter."
}
```

## Database / ECAEP freeze
- Protected freeze OK: `True`
- Protected checksum unchanged: `True`
- ECAEP reviews unchanged: `1824 → 1824`
- Blueprints/KUs/taxonomy unchanged
- DRAFT delta this resume: `0`

## Tests
- Passed `37` / Failed `0`

```
.....................................                                    [100%]
============================== warnings summary ===============================
<frozen importlib._bootstrap>:241
<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:241
<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
37 passed, 5 warnings in 75.33s (0:01:15)
```

## Confirmation
```json
{
  "physics_regenerated": false,
  "mcqs_published": false,
  "ncert_certified": false,
  "editorially_approved": false,
  "provider_silently_switched": false,
  "existing_questions_mutated": false,
  "blueprints_modified": false,
  "kus_modified": false,
  "taxonomy_modified": false,
  "ecaep_modified": false,
  "beyond_remaining_271": false,
  "committed": false,
  "pushed": false
}
```

**STOP** — no NCERT certification, no editorial approval, no publish, no commit, no push.
