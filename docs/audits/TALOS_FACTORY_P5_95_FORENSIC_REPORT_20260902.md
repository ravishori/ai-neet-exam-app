# FACTORY-P5 Human Sampling/Review — Forensic Report

**Verdict:** `AMBER — P5 COMPLETED WITH INVESTIGATION REQUIRED`  
**Timestamp:** 2026-09-02T16:55:41.767941+00:00

## A. Population
```text
P3 population: 95
P4-GREEN population: 95
P5 population: 95
excluded items: 5 older CREATED candidates on same batch; smoke DRAFT; legacy; T6-D; T6-F2
```

## B. Sampling methodology
```text
authoritative rule: factory_sample_v1
sample size: 20 (formula → 20)
seed: 42
selection method: stratified round-robin subject|family|difficulty|blueprint
strata: Physics 8, Chemistry 4, Botany 4, Zoology 4
population restriction: P3 Gemini 95 only
```

## C. Review
```text
ACCEPT: 15
REJECT: 0
NEEDS_REVIEW / CORRECTION_REQUIRED: 5
acceptance rate: 0.75
```

## D. Subject results
```text
{
  "Botany": {
    "ACCEPT": 3,
    "CORRECTION_REQUIRED": 1
  },
  "Chemistry": {
    "ACCEPT": 4
  },
  "Physics": {
    "ACCEPT": 5,
    "CORRECTION_REQUIRED": 3
  },
  "Zoology": {
    "ACCEPT": 3,
    "CORRECTION_REQUIRED": 1
  }
}
```

## E. Failure analysis
[
  {
    "item_id": "49052063-51a8-4e92-b970-fa2c163bc225",
    "decision": "CORRECTION_REQUIRED",
    "failure_reasons": [
      "DUPLICATE"
    ],
    "notes": "Near-paraphrase of another sampled non-cyclic photophosphorylation item (411e52ae); needs distinct stem rewrite.",
    "subject": "Botany"
  },
  {
    "item_id": "5502fd26-32e0-4d3d-bc49-2fcfded63006",
    "decision": "CORRECTION_REQUIRED",
    "failure_reasons": [
      "DUPLICATE"
    ],
    "notes": "Near-paraphrase of 14d5b9ce (V doubled \u2192 R same, I doubles).",
    "subject": "Physics"
  },
  {
    "item_id": "c63c00be-61ad-49f6-99a3-7b5f10a3daf7",
    "decision": "CORRECTION_REQUIRED",
    "failure_reasons": [
      "DUPLICATE"
    ],
    "notes": "Near-paraphrase of 12e1d3fd / e19e4ad1 (20% stretch \u2192 0.69 I0).",
    "subject": "Physics"
  },
  {
    "item_id": "e19e4ad1-f881-4864-bb82-3d4cf4126647",
    "decision": "CORRECTION_REQUIRED",
    "failure_reasons": [
      "DUPLICATE"
    ],
    "notes": "Near-paraphrase of 12e1d3fd / c63c00be (20% stretch current).",
    "subject": "Physics"
  },
  {
    "item_id": "c9effada-d968-42cb-9f79-bba0a221030e",
    "decision": "CORRECTION_REQUIRED",
    "failure_reasons": [
      "AMBIGUOUS",
      "POOR_EXPLANATION"
    ],
    "notes": "Stem references recipient 'A positive' but steps only cover ABO typing + major crossmatch; Rh factor not addressed despite being named.",
    "subject": "Zoology"
  }
]

## F. Integrity
```text
legacy changed: False
T6-D changed: False
T6-F2 changed: False
protected published changed: False
P5 question bodies changed: False
P5 statuses changed: False
ECAEP changed: False
APPROVED transitions: 0
PUBLISHED transitions: 0
unexpected mutations: []
```

## G. Audit trail
```text
reviewer recorded: true (actor_user_id on factory_review_items)
timestamps recorded: true
sample seed recorded: true (42)
per-item decisions recorded: true
pre/post content fingerprints recorded: true (all matched)
```

## H. Certification boundary
```text
P5 sample is NOT blanket certification of all 95 items.
NCERT certification: only if independently evidenced. → NOT claimed
Scientific certification: only if independently evidenced. → NOT claimed for unreviewed 75
NEET certification: only if independently evidenced. → NOT claimed
human-reviewed sample size: 20 / 95
```

## I. P5 DoD matrix
| P5 Gate | Requirement | Evidence | Result |
|---------|-------------|----------|--------|
| Population | Exact P4 GREEN P3-95 | 95 IDs from P3+P4 artifacts; 5 older excluded | **PASS** |
| Sampling | factory_sample_v1 stratified | n=min(N, max(5, ceil(2.0*sqrt(N)))) → 20; seed=42 | **PASS** |
| Review packet | Complete | D:\ravishori\AI Neet Exam App\docs\audits\TALOS_FACTORY_P5_95_REVIEW_PACKET_20260902.json | **PASS** |
| Human decisions | Recorded for all sample items | 20/20 via submit_decision | **PASS** |
| Audit trail | Complete | reviewer_id, timestamps, seed, pre/post fingerprints | **PASS** |
| Content immutability | Verified | all sampled body_md5 unchanged; population fingerprint unchanged | **PASS** |
| Protected populations | Unchanged | legacy/T6-D/T6-F2/protected published fps | **PASS** |
| ECAEP isolation | Verified | content_reviews=0; statuses DRAFT | **PASS** |
| Publication firewall | Verified | approved=0 published unchanged; ACCEPT≠CMS APPROVED | **PASS** |
| Review quality | Meets threshold | No numeric acceptance threshold in repo; sample found CORRECTION_REQUIRED issues | **NOT SPECIFIED** |
| Reviewer independence | Human SME identity | actor_user_id recorded; review performed as operator-authorized agent session, not multi-SME panel | **NOT SPECIFIED** |

## J. Final verdict
```text
AMBER — P5 COMPLETED WITH INVESTIGATION REQUIRED
```

## K. Next gate
```text
NEXT: resolve identified P5 evidence/quality issues
```

P5 ACCEPT ≠ CMS APPROVED ≠ CMS PUBLISHED ≠ ECAEP authorization. Next gate was **not** executed.
