# TALOS T6-F2 Remediation Report — Close AMBER DoD Findings

**Date:** 2026-09-02  
**HEAD (pre-commit):** `d2d69cebcb4dd121311c4e9599194a788f293a50`  
**Branch:** `main`  
**Database:** `trinetra_db` (local)  
**Prior forensic verdict:** 🟡 AMBER — functionally passed, DoD evidence incomplete  

---

## 1. Initial Findings (Phase 1 confirmation)

| Finding | Current status (pre-remediation) | Evidence |
| ------------------------ | -------------- | -------- |
| Explanation assertion | OPEN | Prior E2E had no post-submit `Explanation` heading assert; `question-panel.tsx` renders Explanation only when `isSubmitted && explanation` |
| Practice Now CTA E2E | OPEN | Prior T6-F2 path used `page.evaluate(fetch)` / non-CTA start |
| Git reproducibility | OPEN | Entire `acquisition/`, e2e, audits untracked (`??`) |
| CMS mutation fingerprint | OPEN | “Unexpected mutations = 0” asserted without protected-population before/after content fp |
| T6-D content fingerprint | OPEN | Counts only; no stored deep content fp before original F2 publish |
| Deep idempotency proof | OPEN | Second-run publication count only; no T6-F1 body fingerprint |

---

## 2. Changes Made

| Area | Files | Purpose |
|------|-------|---------|
| Fingerprints | `apps/backend/app/modules/cms/acquisition/physics_integrity_fingerprints.py` | Canonical row + MD5 content fingerprints; row-canon diffs |
| Integrity CLI | `apps/backend/scripts/run_physics_t6f2_integrity_verify.py` | Before → idempotent publish → after; writes evidence JSON |
| Evidence | `docs/audits/TALOS_T6F2_INTEGRITY_IDEMPOTENCY_EVIDENCE_20260902.json` | T6-D / protected CMS / idempotency artifact |
| Playwright | `apps/web/e2e/practice-t6f2-publication.spec.ts` | Real Practice Now CTA + post-submit Explanation |
| Tests | `apps/backend/tests/test_physics_t6f2_publish.py` | Firewall + fingerprint determinism |

No T6-D / legacy / protected CMS content was modified by remediation. Integrity script’s `publish=True` is a no-op on already-published batch (`published_new=0`).

---

## 3. Practice Now E2E Evidence

**Command:**
```text
cd apps/web
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:3001"
$env:PLAYWRIGHT_API_URL="http://127.0.0.1:8000"
npx playwright test --project=laptop-1366 e2e/practice-t6f2-publication.spec.ts e2e/practice-physics-topic-isolation.spec.ts --reporter=list
```

**Result:** exit 0 · **2 passed** · 0 failed · 0 skipped · ~3.6s

**Journey proven (CTA path, not `page.evaluate(fetch)`):**
1. Unauthenticated `POST /assessments/practice` → ≥401  
2. Student bootstrap → dashboard  
3. Click real `Practice now` button in `main`  
4. Wait for POST `/api/v1/assessments/practice` ok  
5. Navigate to `/student/attempts/{uuid}`  
6. Question UI visible; pre-submit: Explanation count = 0, Score absent  
7. Option A select (`aria-pressed=true`); optional Next to Q2  
8. Submit → Score / N correct / N incorrect / Correct|Incorrect|Skipped  
9. Heading `Explanation` visible post-submit  
10. Optional Next in review; Explanation still visible  

Topic isolation spec also passed (SL vs Plane pools).

---

## 4. Explanation-after-submit Evidence

**Asserted (stable UI convention from `question-panel.tsx`):**
- **Before submit:** `getByRole('heading', { name: /^Explanation$/i })` count = 0  
- **After submit:** same heading **visible** (only rendered when `isSubmitted && question.explanation`)  
- Coupled with Score / correctness badges so the panel is in post-submit state  

**Documented assertion:** post-submit Explanation heading visibility, not pre-existing explanation DOM.

---

## 5. T6-D Before/After Integrity

From `TALOS_T6F2_INTEGRITY_IDEMPOTENCY_EVIDENCE_20260902.json` (idempotent rerun window):

```text
T6-D population: physics-t6d-pilot-20260902
Before count: 100
Before fingerprint: e0758fbcb071180b61a33f2b4581e894
After count: 100
After fingerprint: e0758fbcb071180b61a33f2b4581e894
Changed rows: 0
Added rows: 0
Deleted rows: 0
```

**Residual:** Historical fingerprint immediately **before the original 938 publish** was never stored → **NOT RETROACTIVELY VERIFIABLE** for that window. Current evidence proves post-publication stability across a no-op F2 rerun.

---

## 6. Protected CMS Mutation Evidence

Protected population = all CMS `QUESTION` except T6-F1 batch (intentional F2 publications excluded).

```text
Protected population before: 5275
Protected population after:  5275
Before fingerprint: 7fcac5bb0a0e18080cd5932a6a19b2bb
After fingerprint:  7fcac5bb0a0e18080cd5932a6a19b2bb
Unexpected updates: 0
Unexpected inserts: 0
Unexpected deletes: 0
Unexpected status changes: 0
Unexpected content changes: 0
```

**Residual:** Same historical limitation for the original publish window → labeled **NOT RETROACTIVELY VERIFIABLE** in the artifact. Post-publish protected stability across idempotent rerun is proven.

---

## 7. Idempotency Evidence

**FIRST RUN** (from stored manifest `TALOS_T6F2_PUBLICATION_MANIFEST_20260902.json`, not re-executed):
- eligible population: **938**
- already_published before: **0**
- staged: **938**
- consistency_errors: **[]**
- rejected never persisted: **true**
- publish log: **938** `content_published` events

**SECOND RUN** (`run_physics_t6f2_integrity_verify.py`):
- eligible: **0**
- newly published: **0**
- already_published: **938**
- errors: **[]**
- T6-F1 published content_fp before = after: `17a1672c444c8362ed0261dacf0f82c7`
- T6-D / legacy / protected fps unchanged

Deep idempotency for already-published content: **proven for second run**. First-run deep “no collateral mutation” remains historically **NOT RETROACTIVELY VERIFIABLE**.

---

## 8. Test Execution Results

| Command | Exit | Tests | Notes |
|---------|------|-------|-------|
| `pytest tests/test_physics_t6f2_publish.py tests/test_vector_mag_contract.py -q` | 0 | **21 passed** (~0.61s) | Includes fingerprint determinism |
| `python scripts/run_physics_t6f2_integrity_verify.py` | 0 | n/a | `all_required_stable: true` |
| Playwright T6-F2 + topic isolation (laptop-1366) | 0 | **2 passed** (~3.6s) | CTA + explanation |

No destructive DB operations beyond the safe no-op publish path were executed.

---

## 9. Git / Reproducibility Status

```text
branch: main
HEAD:   d2d69cebcb4dd121311c4e9599194a788f293a50
```

Artifacts remain **uncommitted** (human approval required). Do **not** commit automatically.

### Proposed staging set (T6-F2 remediation + required F1/F2 lineage)

```text
Files to commit:
apps/backend/app/modules/cms/acquisition/physics_t6f2_constants.py
apps/backend/app/modules/cms/acquisition/physics_t6f2_service.py
apps/backend/app/modules/cms/acquisition/physics_integrity_fingerprints.py
apps/backend/app/modules/cms/acquisition/physics_acquisition_common.py
apps/backend/app/modules/cms/acquisition/physics_t6f1_*.py   # F1 lineage as needed for import graph
apps/backend/app/modules/cms/services/numerical_validation.py
apps/backend/scripts/run_physics_t6f2_publish.py
apps/backend/scripts/run_physics_t6f2_integrity_verify.py
apps/backend/tests/test_physics_t6f2_publish.py
apps/backend/tests/test_vector_mag_contract.py
apps/web/e2e/practice-t6f2-publication.spec.ts
apps/web/e2e/practice-physics-topic-isolation.spec.ts
apps/web/e2e/helpers.ts   # if required by specs
docs/audits/TALOS_T6F2_PUBLICATION_MANIFEST_20260902.json
docs/audits/TALOS_T6F2_INTEGRITY_IDEMPOTENCY_EVIDENCE_20260902.json
docs/audits/TALOS_T6F2_CONTROLLED_PUBLICATION_PRACTICE_E2E_AUDIT_20260902.md
docs/audits/TALOS_T6F2_REMEDIATION_REPORT_20260902.md
```

**Exclude:**
- `docs/audits/_t6f2_publish_run.log` (verbose operational log)
- `.env`, credentials, DB dumps, temporary logs
- Unrelated dirty tree / other factory scripts unless intentionally scoped

### Safe commit command (human approval)

```powershell
cd "D:\ravishori\AI Neet Exam App"
# Stage only the approved paths above, then:
git commit -m "$(cat <<'EOF'
Close T6-F2 DoD evidence gaps: CTA/explanation E2E and integrity fingerprints.

Add Practice Now CTA Playwright coverage with post-submit Explanation asserts,
plus deterministic T6-D/protected-CMS fingerprints and idempotent rerun evidence.
EOF
)"
```

(On Windows PowerShell, use an equivalent here-string commit message.)

**Status:** commit-level reproducibility = **AWAITING HUMAN COMMIT** (still incomplete until staged + committed).

---

## 10. Updated DoD Matrix

| Gate | Previous | Current | Evidence |
| ---- | -------- | ------- | -------- |
| 938/938 publication | PASS | PASS | DB f1_pub=938; manifest eligible=938 |
| Zero failed publications | PASS | PASS | manifest consistency_errors=[]; log content_published×938 |
| Rejected 62 isolation | PASS | PASS | rejected_never_persisted; no F1 drafts |
| Legacy 5,000 integrity | PARTIAL (count) | PASS (post-rerun deep fp) / historical NOT RETRO | legacy total=5000, pub=0, fp stable on rerun |
| T6-D 100 integrity | PARTIAL (count) | PASS (post-rerun deep fp) / historical NOT RETRO | count=100, fp equal, changed=0 |
| Idempotency (deep) | PARTIAL | PASS (2nd run) | published_new=0 + T6-F1 content_fp unchanged |
| Protected CMS mutations | FAIL/unsupported | PASS (post-rerun) / historical NOT RETRO | unexpected *=0; fp stable |
| Practice Now CTA | FAIL | PASS | Playwright click CTA + practice POST |
| Answer submission | PARTIAL | PASS | Submit → Score / correct / incorrect |
| Correctness state | PARTIAL | PASS | Correct\|Incorrect\|Skipped badge |
| Explanation | FAIL | PASS | Explanation heading post-submit only |
| Next-question | PARTIAL | PASS | Next pre/post submit where enabled |
| Auth gate | PASS | PASS | unauth ≥401 |
| Empty / topic isolation | PASS | PASS | topic isolation E2E passed |
| A–D options | PASS | PASS | Option A button exercised |
| Unit/integration tests | PARTIAL | PASS | 21 pytest passed |
| Git reproducibility | FAIL | BLOCKED (awaiting commit) | proposed staging set only |

---

## 11. Remaining Limitations

| Item | Classification |
|------|----------------|
| Practice Now CTA + explanation E2E | **proven** |
| Post-publish T6-D / protected CMS / T6-F1 content fps across idempotent rerun | **proven** |
| Second-run deep idempotency (0 new pubs + content fp unchanged) | **proven** |
| First-run eligible/published counts | **proven** (manifest + log) |
| Deep immutability of T6-D/protected CMS **during original 938 publish** | **not retroactively verifiable** |
| Commit-level reproducibility at a git SHA | **not verified** until human commit |
| NCERT/NEET pedagogical certification of 938 stems | **not tested** / out of scope |
| Production deploy | **not tested** |

---

## 12. Final Verdict

🟡 AMBER — T6-F2 FUNCTIONALLY PASSED BUT DoD EVIDENCE INCOMPLETE

Mandatory residual gaps that block GREEN under the stated decision rule:
1. Historical pre-original-publish deep fingerprints for T6-D and protected CMS are **NOT RETROACTIVELY VERIFIABLE**.
2. T6-F2 artifacts remain **uncommitted**, so commit-level reproducibility is not yet objective.

Does T6-F2 now genuinely satisfy the project's Definition of Done?

**NO.**
