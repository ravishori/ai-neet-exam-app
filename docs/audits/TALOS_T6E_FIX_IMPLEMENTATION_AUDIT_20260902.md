# TALOS T6-E-FIX — Implementation Audit — 2026-09-02

## Summary

Pipeline remediations for T6-E AMBER findings are implemented and tested. **No mass edit** of the 100 published pilot questions. **No legacy mutations.**

```text
DB writes performed by this remediation: 0 (code/tests/docs only)
Question rows modified: 0
Legacy rows modified: 0
Publication changes: 0
Taxonomy changes: 0
```

Legacy invariant (verified read-only after implementation):

```text
5000 rows
5000 concept_id NULL
0 published
fingerprint 937c60a9aaa5dcbedfa9b5bc569d45a0
```

Pilot batch `physics-t6d-pilot-20260902` remains **100 PUBLISHED** (unchanged).

---

## Files changed (primary)

| Area | Path |
|------|------|
| Numerical contract | `app/modules/cms/services/numerical_validation.py` |
| Publication gates | `app/modules/cms/services/publication_gates.py` |
| Evidence schemas | `app/modules/cms/schemas/question_evidence.py` |
| QuestionBody extensions | `app/modules/cms/schemas/content_bodies.py` |
| Workflow wire-up | `app/modules/cms/services/content_workflow_service.py` |
| T6-D gates | `app/modules/cms/acquisition/physics_t6d_gates.py` |
| T6-D bank | `app/modules/cms/acquisition/physics_t6d_bank.py` |
| Throughput | `app/modules/cms/acquisition/physics_t6d_throughput.py` |
| Pilot service | `app/modules/cms/acquisition/physics_t6d_service.py` |
| Constants | `app/modules/cms/acquisition/physics_t6d_constants.py` |
| Seed publishability | `app/modules/cms/seed.py` |
| Tests | `tests/test_t6e_fix_gates.py`, updated publish helpers, `helpers_publishable_question.py` |
| Practice E2E | `apps/web/e2e/practice-physics-topic-isolation.spec.ts` |

---

## Finding → fix map

### HIGH 1 — Scientific incomplete calc soft-pass
- Soft paths (`unchecked-keys-ok`, `work numeric present`, …) **removed**.
- `classify_and_verify()` returns `NUMERICAL_COMPLETE|INCOMPLETE|INVALID|NOT_NUMERICAL`.
- Incomplete/invalid → scientific FAIL → REJECT.
- Bank calc payloads completed with explicit `formula` + required keys (generation source only; DB rows not rewritten).

### HIGH 2 — CMS publish bypass
- `ContentWorkflowService.publish` calls `assert_question_publishable` **server-side**.
- Requires: structural, taxonomy (`concept_id`), NCERT evidence, scientific/numerical contract, provenance, duplicate-vs-published, APPROVED state.
- Regression tests: missing NCERT → 422; incomplete calc → 422; duplicate stem → 422; full → 200.

### HIGH 3 — NCERT evidence precision
- Structured `ncert_evidence` with levels: `NOT_VERIFIED`, `SOURCE_TEXT_VERIFIED`, `SECTION_VERIFIED`, `PAGE_VERIFIED`.
- `PAGE_VERIFIED` **rejected** without `page_number` (no fabrication).
- Policy recorded: `page-level evidence capability = NOT AVAILABLE`.
- Distinguishes aligned / section-verified / page-verified explicitly in gate audit output.

### HIGH 4 — Option D never correct
- Generation uses deterministic per-seq option shuffle; correct answer tracked by **text**.
- Batch audit fails generation quality if any of A–D is missing for batches ≥20.
- **Existing published 100 not rebalanced** (FIX PIPELINE NOT DATA).

### MEDIUM 5 — Difficulty skew
- Difficulty remains metadata (not reject gate).
- Batch `difficulty_audit` reports distribution + `collapse_toward_easy` warning.
- Two truthful hard items retained/labeled in bank; no fake Hard quota.

### MEDIUM 6 — Near-duplicate padding
- Pad loop **removed** (`quality > quantity`).
- Digit-folded template near-dup → REJECT.
- Bank size now ≤89 candidates; accepted unique templates ~59 under gates.

### MEDIUM 7 — Practice E2E
- Added Playwright spec `practice-physics-topic-isolation.spec.ts` (TOPIC isolation + submit/score path).
- Skips cleanly if pools/API unavailable (does not claim green from code inspection alone).

### MEDIUM 8 — Throughput
- `ThroughputMeter` on `PhysicsT6DPilotService.run` records stage durations + candidates/hour style rates.

---

## Tests

```text
tests/test_t6e_fix_gates.py
tests/test_physics_t6d_pilot.py
tests/test_cms_publish_quality.py
+ publish-path suites (browser, practice, admin, editorial, solving)
```

Observed in this session:

```text
test_t6e_fix_gates + test_physics_t6d_pilot + test_cms_publish_quality: 30 passed
test_question_browser + practice_* + question_solving + admin + editorial: 54 passed
```

---

## T6-E-FIX RE-AUDIT (existing pilot — read-only)

| Gate | Status | Notes |
|------|--------|-------|
| Content correctness (historical 100) | AMBER | Unchanged published set; prior T6-E spot-checks stand |
| Numerical (pipeline) | GREEN | Soft-pass removed; bank contracts complete |
| Numerical (stored 100 bodies) | AMBER | DB bodies not rewritten; historical incomplete metadata may remain |
| NCERT fidelity | AMBER→honest | Section-verified capability; page-level **NOT AVAILABLE** |
| Taxonomy | GREEN | Unchanged; no taxonomy writes |
| Duplicates (pipeline) | GREEN | Exact + near-template |
| Answer-position (historical DB) | RED/AMBER | Still D=0 in published 100 |
| Answer-position (new generation) | GREEN | A/B/C/D all used in bank |
| Provenance (pipeline) | GREEN | Required at publish |
| Publication gates | GREEN | Server-enforced |
| Practice | AMBER | API/SQL verified historically; new browser E2E depends on live stack |
| Performance | NOT MEASURED (no change claimed) | |
| Throughput | GREEN (instrumented) | Metrics available on next pilot run |
| Idempotency | GREEN (code path) | Stable slug/batch; no mutate retest executed |
| Legacy safety | GREEN | Fingerprint unchanged |

**RE-AUDIT OVERALL: AMBER** — pipeline ready; historical pilot dataset still carries T6-E content biases because we intentionally did not rewrite published rows.

---

## Scale decision

```text
READY FOR T6-E RE-AUDIT: YES (this document + inventory)
READY FOR T6-F 1,000: NO — until a future controlled batch under the new gates is itself GREEN
```

Do not start T6-F until a new generation batch demonstrates:

1. Non-zero A/B/C/D correct positions  
2. No incomplete numerical soft-pass  
3. No near-duplicate padding  
4. Publication path cannot bypass gates  
5. Legacy fingerprint still `937c60a9aaa5dcbedfa9b5bc569d45a0`
