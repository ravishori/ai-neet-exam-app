# FACTORY-P4 QA — Gemini P3 95 DRAFTs forensic report

**Timestamp:** 2026-09-02T16:47:15.045460+00:00
**Verdict:** `GREEN — P4 QA PASSED`

## A. Execution
```text
target population: P3 Gemini pilot 95 DRAFTs (from CONTENT_FACTORY_P3_PILOT_RESULTS.json)
batch: factory-p3-pilot-2026-09-01-batch (22c5684b-cf86-4137-82bf-be237be1e2ee)
items evaluated: 95
P4 command: scripts/run_factory_p4_gemini_p3_95.py (evaluate_candidate×95, force_new)
provider calls: 0
new content generated: 0
excluded older batch CREATED candidates: 5
```

## B. Gate results
```text
gate_A: pass=95 fail=0
gate_B: pass=95 fail=0
gate_C: pass=95 fail=0
gate_D: pass=95 fail=0
gate_E: pass=95 fail=0
gate_F: pass=95 fail=0
gate_G: pass=95 fail=0
overall GREEN/YELLOW/RED: {'GREEN': 95}
fully passing (all gates + lineage): 95
items with failures: 0
```

## C. Subject results
```text
{
  "Physics": {
    "n": 40,
    "GREEN": 40,
    "YELLOW": 0,
    "RED": 0,
    "gate_fail_counts": {},
    "failure_rate": 0.0
  },
  "Chemistry": {
    "n": 20,
    "GREEN": 20,
    "YELLOW": 0,
    "RED": 0,
    "gate_fail_counts": {},
    "failure_rate": 0.0
  },
  "Botany": {
    "n": 20,
    "GREEN": 20,
    "YELLOW": 0,
    "RED": 0,
    "gate_fail_counts": {},
    "failure_rate": 0.0
  },
  "Zoology": {
    "n": 15,
    "GREEN": 15,
    "YELLOW": 0,
    "RED": 0,
    "gate_fail_counts": {},
    "failure_rate": 0.0
  }
}
```

## D. Failure analysis
Categories: {}
Examples: {}

Semantic dedupe: SEMANTIC_DEDUPE_NOT_AVAILABLE (not treated as semantic uniqueness PASS).

## E. Integrity
```text
legacy changed: False
T6-D changed: False
T6-F2 changed: False
protected published changed: False
P3 drafts body/status changed: False
unexpected mutations: []
approved transitions: 0
published transitions: 0
ECAEP transitions: 0 (ContentItem.status remained DRAFT)
```

## F. Artifacts
- D:\ravishori\AI Neet Exam App\docs\audits\TALOS_FACTORY_P4_95_PRE_BASELINE_20260902.json
- D:\ravishori\AI Neet Exam App\docs\audits\TALOS_FACTORY_P4_95_RESULTS_20260902.json
- D:\ravishori\AI Neet Exam App\docs\audits\TALOS_FACTORY_P4_95_POST_INTEGRITY_20260902.json
- D:\ravishori\AI Neet Exam App\docs\audits\TALOS_FACTORY_P4_95_FORENSIC_REPORT_20260902.md

## G. Final verdict
```text
GREEN — P4 QA PASSED
```

## H. Next gate
```text
NEXT: P5 human sampling/review
```

P5 was **not** executed. No approve/publish/ECAEP.

**Certification limit:** P4 is automated factory QA only — not NCERT verified / scientifically certified / NEET verified.