# TALOS T6-E RE-AUDIT — Verify Remediation Before 1,000-Question Scale — 2026-09-02

## 1. Executive Verdict

**T6-E RE-AUDIT VERDICT: GREEN**

T6-E-FIX closed the **content-integrity and publication-integrity** scale blockers that made the original T6-E audit AMBER. Independent code inspection, non-mutating contract checks, and executed tests corroborate the remediation claims.

Remaining limitations (documented, non-blocking under the stated decision rule):

| Limitation | Classification |
|------------|----------------|
| Practice browser E2E | **NOT VERIFIED** (API down in this session; Playwright exists but was not executed to PASS) |
| Throughput stage granularity / dry-run rate timing | **PARTIAL** (meter exists; per-gate spans incomplete; dry-run rates null) |
| New bank still Easy-heavy (~82% easy) | **OBSERVATION** (truthful metadata; no Hard quota manufacturing) |
| Historical T6-D `D=0` / Easy skew in DB | **EXPECTED** (FIX PIPELINE NOT DATA — unchanged) |

```text
DB writes: 0
Legacy modifications: 0
Legacy publications: 0
Legacy concept assignments: 0
T6-F 1,000-QUESTION PILOT: PROCEED
```

Do **not** treat historical T6-D `D=0` as a pipeline failure. Do **not** treat page-level NCERT as verified — capability remains **NOT AVAILABLE**.

---

## 2. T6-E baseline findings (reference)

From `docs/audits/TALOS_T6E_100_QUESTION_QUALITY_SCALE_AUDIT_20260902.md`:

1. Scientific gate soft-passes incomplete calcs  
2. CMS publish can bypass T6-D gates  
3. NCERT = section+PDF only; page-level 0/100  
4. Correct option D = 0/100  
5. Difficulty 84% easy / 0% hard  
6. Near-duplicate padding to n=100  
7. Practice browser E2E NOT VERIFIED  
8. Throughput metrics NOT AVAILABLE  

---

## 3. T6-E-FIX remediation evidence (claimed vs inspected)

Remediation audit: `docs/audits/TALOS_T6E_FIX_IMPLEMENTATION_AUDIT_20260902.md`  
This re-audit does **not** accept that document alone.

| # | Original finding | Fix claimed | Implementation evidence | Independent test | Result | PASS/FAIL/PARTIAL |
|---|------------------|-------------|-------------------------|------------------|--------|-------------------|
| 1 | Soft scientific pass | Hard fail incomplete/invalid | `numerical_validation.classify_and_verify`; no soft-pass strings in gates | complete→COMPLETE; `{W:40}`→INCOMPLETE; wrong v→INVALID; `{}`→NOT_NUMERICAL; 0 incomplete accepted in `audit_bank` | Soft paths gone | **PASS** |
| 2 | CMS publish bypass | Server-side mandatory gates | `ContentWorkflowService.publish` → `assert_question_publishable`; bulk publish uses same service | pytest deny missing NCERT / incomplete calc / duplicate; allow full; HTTP publish path | Single publish + bulk both gated | **PASS** |
| 3 | Weak NCERT evidence | Levels + reject fabricated PAGE | `NcertEvidence` model; `PAGE_VERIFIED` without page raises | ValidationError on fabricated page; section builder produces SECTION_VERIFIED; audit says page capability NOT AVAILABLE | Honest levels | **PASS** (page capability still NOT AVAILABLE — correct) |
| 4 | D=0 bias | Shuffle in new generation | `_shuffle_options` in bank | Seeds yield A–D; correct text preserved; historical DB still A39/B44/C17/D0 | Pipeline fixed; history intact | **PASS** (pipeline) |
| 5 | Easy collapse / pad | Report + no pad / no fake Hard | `difficulty_audit`; pad loop removed; 2 hard labels | Bank 73E/14M/2H; no `[Pilot` pads; historical 84/16/0 unchanged | No forced Hard | **PARTIAL** (still Easy-skewed generation) |
| 6 | Near-dup padding | Digit-fold near-template + no pad | `similarity_band`; quality>quantity | Pad loop absent; bank 89; audit accepts 59 rejects 30 near-dups | Pad gone | **PASS** |
| 7 | Practice E2E | Playwright TOPIC isolation spec | `apps/web/e2e/practice-physics-topic-isolation.spec.ts` | Spec present; API **down** this session → not executed | Cannot claim PASS | **NOT VERIFIED** |
| 8 | No throughput | ThroughputMeter on pilot service | `physics_t6d_throughput.py` + service spans | Dry-run produces some durations; rates null (total_batch not closed before `as_dict`); stages coarse | Instrumented, incomplete | **PARTIAL** |

---

## 4. Scientific gate re-audit

**Implementation:** `apps/backend/app/modules/cms/services/numerical_validation.py` used by T6-D gates and publication gates.

| Case | Payload | Status observed |
|------|---------|-----------------|
| Complete | `v=u+at` with matching v | `NUMERICAL_COMPLETE` |
| Incomplete (prior soft class) | `{"W": 40}` | `NUMERICAL_INCOMPLETE` |
| Incomplete (no formula) | `{u,a,t,v}` without formula | `NUMERICAL_INCOMPLETE` |
| Invalid | formula ok, v wrong | `NUMERICAL_INVALID` |
| Non-numerical | `{}` / `None` | `NOT_NUMERICAL` |

Soft-pass literals (`unchecked-keys-ok`, `work numeric present`, …): **absent** from gates/numerical modules.

`audit_bank`: **INCOMPLETE_ACCEPTED = 0**.

Historical 22 incomplete DB records: **not modified** (read-only). They would fail scientific gate if re-published with incomplete calc payloads — expected; no silent PASS via soft path.

```text
SCIENTIFIC GATE: PASS
```

---

## 5. Publication gate re-audit

### Discovered publication paths

| Path | Enters `ContentWorkflowService.publish`? | Gates applied? |
|------|------------------------------------------|----------------|
| `POST /api/v1/cms/content-items/{id}/publish` | Yes | Yes (QUESTION → full gates) |
| `POST /api/v1/cms/content-items/bulk` action=publish | Yes | Yes |
| T6-D pilot service publish | Yes | Yes |
| CMS seed `_publish_through_workflow` | Yes | Yes (seed enriches evidence) |
| Factory routers | No publish | N/A |
| Direct `status="PUBLISHED"` | Only in `ai/tests/test_explain_question.py` fixture | Test-only; not an API |

Non-QUESTION content skips QUESTION-specific gates (structural/review only) — scoped correctly.

Verified denials (pytest, test DB fixtures — not production mutation of T6-D/legacy):

- missing NCERT evidence → `PUBLICATION_GATES_FAILED` 422  
- incomplete calculation → 422  
- duplicate published stem → 422  
- fully gated body → ALLOW 200  

```text
PUBLICATION GATE: PASS
```

---

## 6. NCERT evidence re-audit

| Claim | Result |
|-------|--------|
| Evidence model with verification levels | **PASS** (`NOT_VERIFIED`, `SOURCE_TEXT_VERIFIED`, `SECTION_VERIFIED`, `PAGE_VERIFIED`) |
| SECTION_VERIFIED allowed when section present | **PASS** |
| PAGE_VERIFIED without page_number | **REJECTED** |
| Fabricated page claim | **REJECTED** |
| Page-level capability | **NOT AVAILABLE** |
| Existing T6-D upgraded to PAGE_VERIFIED | **No** (unchanged) |

Do not conflate:

```text
NCERT-aligned ≠ SECTION_VERIFIED ≠ PAGE_VERIFIED
```

```text
Page-level capability: NOT AVAILABLE
Section verification: PASS
Evidence model: PASS
```

---

## 7. Answer-position diversity re-audit

### Historical T6-D (DB, read-only)

```text
A=39, B=44, C=17, D=0
published=100
```

`D=0` **remains unchanged** — remediation did not rebalance letters.

### New generation pipeline

- `_shuffle_options` permutes texts; correct tracked by text identity  
- Independent seeds: letters `{A,B,C,D}` all reachable; correct text preserved  
- Current bank distribution example: A29 D21 B16 C23; `generation_quality_failure=False`  
- Accepted-after-gates still includes D (>0)

```text
ANSWER POSITION PIPELINE: PASS
```

---

## 8. Difficulty re-audit

| Check | Result |
|-------|--------|
| Historical DB | easy=84, medium=16, hard=0 — **unchanged** |
| Artificial Hard manufacturing | Not observed |
| Pad-to-target | Removed |
| Distribution reporting | `difficulty_audit` present |
| New bank Easy skew | Still high (~82% easy, 2 hard) — truthful, not quota-driven |

```text
DIFFICULTY PIPELINE: PARTIAL
```

(Partial = reporting + no pad/fake Hard, but generation still Easy-dominant.)

---

## 9. Duplicate re-audit

| Check | Result |
|-------|--------|
| Exact stem hash | Present |
| Digit-folded near-template | `NEAR_DUPLICATE` confirmed on parametric clones |
| Pad-to-100 loop | **Removed** (`PAD_LOOP False`, no `[Pilot` stems) |
| Quality > quantity | Bank size **89** (<100); accepted **59** after near-dup rejects |

```text
DUPLICATE CONTROL: PASS
```

---

## 10. Practice E2E re-audit

- Spec: `apps/web/e2e/practice-physics-topic-isolation.spec.ts` (auth → TOPIC scopes → attempt UI → submit/score; kinematics isolation checks).  
- Environment this session: Playwright present, web `:3001` up, **API `:8000` down**, auth state file present.  
- Test **not executed to PASS**. A skip due to missing pool/API must not be counted as PASS.

Prior T6-E SQL pool checks remain historical evidence only — not upgraded to browser PASS here.

```text
PRACTICE E2E: NOT VERIFIED
```

---

## 11. Throughput re-audit

| Claim | Result |
|-------|--------|
| Instrumentation module exists | Yes (`ThroughputMeter`) |
| Wired into T6-D service | Yes |
| Can emit durations | Yes (dry-run: duplicate lookup + lumped validation spans) |
| Separate spans for structural / scientific / NCERT / taxonomy / duplicate | **No** — lumped as `structural_scientific_ncert_taxonomy_validation`; `candidate_generation` is empty |
| candidates/hour etc. | Formula present; dry-run rates **null** because `as_dict` runs before `total_batch` context exits |
| Invented production numbers | None |

```text
instrumentation = PASS (exists)
throughput measurement = NOT VERIFIED (no clean end-to-end timed apply/publish measurement in this audit)
THROUGHPUT: PARTIAL
```

---

## 12. Legacy safety

| Metric | Expected | Observed |
|--------|----------|----------|
| rows | 5000 | **5000** |
| concept_id NULL | 5000 | **5000** |
| published | 0 | **0** |
| fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` | **match** |

```text
legacy modifications = 0
legacy publications = 0
legacy concept assignments = 0
```

---

## 13. Historical T6-D integrity

| Check | Observed |
|-------|----------|
| Count | 100 |
| Published | 100 |
| Draft | 0 |
| Answer letters | A39 B44 C17 **D0** (unchanged) |
| Difficulty | 84% easy / 16% medium / 0% hard (unchanged) |
| Remediation rewrote stems/answers/taxonomy/provenance/status | **No evidence of mutation** |

---

## 14. Tests

Read-only/unit/integration executed this re-audit (no production T6-D/legacy mutation):

```text
tests discovered (focused set): 18
tests executed: 18
tests passed: 18
tests failed: 0
tests skipped: 0
```

Suite: `test_t6e_fix_gates.py` (14) + selected `test_physics_t6d_pilot` / `test_cms_publish_quality` (4).

Playwright Practice E2E: **not run** → counted separately as **NOT VERIFIED**, not as skipped-pass.

Independent non-pytest script checks (scientific/NCERT/bank/legacy/pilot): executed in-process, DB read-only.

---

## 15. Remaining limitations / scale-blocker classification

| Issue | Severity | Blocks T6-F? |
|-------|----------|--------------|
| Practice E2E not browser-verified this session | MEDIUM | No (documented) |
| Throughput spans coarse; dry-run rates null | MEDIUM | No (documented) |
| New generation still Easy-heavy | LOW / OBSERVATION | No |
| Page-level NCERT unavailable | OBSERVATION | No (must not claim PAGE) |
| Historical D=0 / Easy skew in published 100 | OBSERVATION | No (intentional non-rewrite) |
| scientific gate bypass | — | **No (closed)** |
| publication bypass | — | **No (closed)** |
| false NCERT page verification | — | **No (rejected)** |
| answer-position generation bias | — | **No (closed in pipeline)** |
| padding/near-duplicate generation | — | **No (closed)** |
| legacy data risk | — | **No** |

---

## 16. Scale-readiness matrix

| Gate | Result | Evidence | Blocks T6-F? |
|------|--------|----------|--------------|
| Scientific validation | PASS | Contract tests + audit_bank | No |
| Publication security | PASS | Workflow + bulk + pytest denials | No |
| NCERT evidence | PASS (section); page NOT AVAILABLE | Model + reject fabricated page | No |
| Answer-position diversity | PASS (pipeline); historical D=0 intact | Shuffle tests + DB counts | No |
| Difficulty generation | PARTIAL | Report/no pad; still Easy-skewed | No |
| Duplicate protection | PASS | Near-template + no pad | No |
| Practice E2E | NOT VERIFIED | Spec exists; API down | No* |
| Throughput | PARTIAL | Meter exists; measurement incomplete | No* |
| Taxonomy | PASS | Unchanged; gates require concept | No |
| Provenance | PASS | Required at QUESTION publish | No |
| Legacy safety | PASS | Fingerprint match | No |

\*Per decision rule: Practice/throughput may remain limited if documented and not compromising correctness/safety.

---

## 17. Final verdict

T6-E-FIX **did** close the original scale blockers for scientific soft-pass, CMS publication bypass, fabricated NCERT page claims, answer-position generation bias, and pad-to-100 near-duplicates. Legacy and historical pilot integrity hold.

Proceed to a **controlled T6-F 1,000-question pilot under the new gates**, with explicit constraints:

1. Do not claim page-level NCERT verification.  
2. Do not rebalance/rewrite the historical 100 as part of T6-F.  
3. Prefer quality over filling to exactly 1000 if near-dups dominate.  
4. Capture real throughput on the first timed T6-F dry-run/apply.  
5. Run Practice Playwright against a live API before calling student Practice “verified.”

```text
T6-E RE-AUDIT VERDICT:
GREEN
Scientific gate:
PASS
Publication gate:
PASS
NCERT evidence:
PASS (section model); page-level capability NOT AVAILABLE
Answer-position diversity:
PASS (pipeline); historical T6-D D=0 unchanged
Difficulty:
PARTIAL (reported; no fake Hard; still Easy-heavy)
Duplicate protection:
PASS
Practice E2E:
NOT VERIFIED
Throughput:
PARTIAL (instrumentation present; clean timed rates NOT VERIFIED)
Taxonomy:
PASS
Provenance:
PASS
Legacy safety:
PASS
Tests:
18 executed / 18 passed / 0 failed / 0 skipped (focused re-audit set); Practice Playwright not run
DB writes:
0
Legacy modifications:
0
Legacy publications:
0
Legacy concept assignments:
0
T6-F 1,000-QUESTION PILOT:
PROCEED
```
