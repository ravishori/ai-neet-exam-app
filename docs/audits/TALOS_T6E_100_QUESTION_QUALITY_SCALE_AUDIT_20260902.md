# TALOS T6-E — 100-Question Physics Pilot Quality & Scale-Readiness Audit — 2026-09-02

## 1. Executive Verdict

**T6-E VERDICT: AMBER**

**1,000-question scale recommendation: FIX FIRST**

The T6-D batch `physics-t6d-pilot-20260902` is real in the database (100 PUBLISHED, legacy 5,000 untouched), structurally clean, taxonomically consistent for Kinematics TOPIC isolation, and free of exact stem-hash duplicates. It is **not** yet evidence-complete enough to justify a 1,000-question controlled pilot without remediation.

Primary blockers to GREEN:

1. **NCERT gate = section reference + PDF on disk only** (0/100 page-level verified). Do not equate with page-level NCERT verification.
2. **Scientific gate soft-accepts incomplete calculation payloads** (`unchecked-keys-ok` / “present” paths) — 22/57 numerical items lack a strict independent recompute path in the gate design (answers spot-checked correct; **process** is insufficient for scale).
3. **Difficulty skew** — 84% easy, 16% medium, **0% hard**; option **D never correct** (0/100).
4. **Practice browser E2E / answer scoring** — **NOT VERIFIED** in this audit (SQL pool membership only).
5. **Throughput instrumentation** — **NOT AVAILABLE** from T6-D.
6. **General CMS publish path** can still publish content that never passed T6-D gates (pilot CLI enforces gates; Admin UI does not reuse that gate suite).

```text
DB writes performed: 0
Question modifications: 0
Legacy modifications: 0
Publication changes: 0
Taxonomy changes: 0
Schema changes: 0
Source changes: 0
```

Machine inventory (read-only): `apps/backend/pilot-t6e-audit-inventory.json`  
Prior T6-D claim set: `docs/audits/TALOS_T6D_PHYSICS_CONTENT_PILOT_AUDIT_20260902.md`

---

## 2. Scope

| Item | Value |
|------|-------|
| Batch | `physics-t6d-pilot-20260902` |
| Questions audited | **100** (all; not sampled) |
| Legacy dataset | `legacy-physics-5000-import-20260902` — invariant only |
| Audit mode | READ-ONLY |
| Code inspected | `physics_t6d_bank.py`, `physics_t6d_gates.py`, `physics_t6d_service.py`, CMS workflow |

---

## 3. Database baseline

| Metric | Expected | Observed | Match |
|--------|---------:|---------:|:-----:|
| T6-D pilot rows | 100 | **100** | YES |
| T6-D published | 100 | **100** | YES |
| T6-D draft | 0 | **0** | YES |
| Legacy rows | 5000 | **5000** | YES |
| Legacy `concept_id` NULL | 5000 | **5000** | YES |
| Legacy published | 0 | **0** | YES |
| Legacy fingerprint | `937c60a9…` | **`937c60a9aaa5dcbedfa9b5bc569d45a0`** | YES |
| Bank slugs missing in DB | 0 | **0** | YES |
| Extra pilot slugs in DB | 0 | **0** | YES |

Physics-ish QUESTION inventory (pilot + legacy + Physics-tagged): **5100** (approx. total with related Physics rows).

---

## 4. 100-question structural audit

Independent checks on all bank candidates (aligned 1:1 with DB published items):

| Check | Result |
|-------|--------|
| Exactly 4 options A–D | **100/100 PASS** |
| Exactly one correct label | **100/100 PASS** |
| Duplicate option texts | **0** |
| Empty stem/explanation | **0** |
| Structural gate re-run | **100 ACCEPT** (with correct repo root / PDFs) |

**Finding (HIGH):** Correct-option position bias — **A=39, B=44, C=17, D=0**. Option D is never the answer. Unacceptable as a scaled NEET bank pattern without randomization.

**Finding (MEDIUM):** 11 pad items (`[Pilot N] …`) exist solely to reach n=100; they are valid but formulaic.

---

## 5. Scientific audit

| Area | Result |
|------|--------|
| Gate scientific re-run | 100 ACCEPT |
| Spot-check of soft-gated items (momentum, work, pad kinematics) | Answers **correct** |
| Gate design | Soft paths accept calc dicts without verifying equations |

**Gate weakness (HIGH for scale):** `verify_calculation()` returns success for:

- `unchecked-keys-ok`
- `work numeric present` / `delta-K present` / `power present` / `scalar check present`

without recomputing from inputs. At 100 this is mitigated by curated authorship; at 1,000 it will not be.

---

## 6. Numerical verification

Independent recompute (T6-E auditor, not trusting stored gate soft-pass):

| Metric | Count |
|--------|------:|
| Numerical questions (calc payload present) | **57** |
| Independently verified (`match=True`) | **35** |
| Independent recompute failures (`match=False`) | **0** |
| Independent recompute unavailable (incomplete calc metadata) | **22** |
| Verification rate among checkable | **1.0** (35/35) |

The 22 unavailable items include:

- Pad kinematics (`t6d-090`…`t6d-100`) — calc has `u,a,t,v` but **no** `formula: v=u+at` key (gate soft-passes).
- Work/power/momentum/CM/torque/inertia — calc stores only result keys (`W`, `P`, `p`, …).

**Manual recomputation of samples** (t6d-044, t6d-048, t6d-090, t6d-100): **MATCH**.

**HOLD recommendation for scale:** strengthen calc payloads + forbid soft-pass before 1,000.

---

## 7. NCERT fidelity audit

### Explicit distinction (mandatory)

| Claim level | Count / status |
|-------------|----------------|
| **NCERT-aligned** (curated templates citing XI sections) | **100/100** |
| **NCERT source-verified** (Gate-4 section string + Class XI PDF file present on disk) | **100/100** |
| **Page-level NCERT verified** (OCR / page extract supporting stem) | **0/100** |

T6-D documented this limitation; T6-E **does not upgrade** the claim.

### Classification of all 100 (honest, without page OCR)

| Class | Count |
|-------|------:|
| DIRECTLY_SUPPORTED (definitional / statement style) | **5** |
| SUPPORTED_WITH_INFERENCE (parametric / applied using section topic) | **95** |
| NOT_SUPPORTED | **0** |
| SOURCE_REFERENCE_INVALID | **0** |

| Evidence precision | Count |
|--------------------|------:|
| Page-level verified | **0** |
| Section-level verified (ref + PDF present) | **100** |
| No sufficiently precise evidence for page fidelity | **100** |

**Scale implication:** AMBER until page-level or stronger excerpt grounding exists for a defined % of the 1,000 pilot (or an accepted product ADR that section+PDF is enough).

---

## 8. Taxonomy audit

Against TALOS Physics P0 manifest + live DB tree:

| Check | Result |
|-------|--------|
| Chapter/topic/concept codes match P0 lineage | **100/100** |
| Kinematics topics in DB | `motion-in-a-straight-line`, `motion-in-a-plane` only |
| Straight-line pilot count | **27** |
| Plane pilot count | **16** |
| Kinematics chapter pilot count | **43** |
| Topic ID overlap (straight ∩ plane) | **0** |
| Misclassification flags (stem vs topic) | **0** |

Chapter accuracy / topic accuracy / concept accuracy (vs P0): **PASS** for this batch.

---

## 9. Duplicate audit

| Comparison | Exact stem-hash collisions |
|------------|---------------------------:|
| Intra-pilot | **0** |
| vs non-pilot existing inventory | **0** |
| vs legacy 5,000 | **0** |

| Risk | Assessment |
|------|------------|
| Near / semantic duplicates | **Present by design** among kinematic pad variants and repeated `v=u+at` templates (different numbers → different hashes). Not caught by current hash gate. |
| False-positive hash matches | **0** observed |

---

## 10. Difficulty distribution

### Observed

| Difficulty | Count | % |
|------------|------:|--:|
| easy | 84 | 84% |
| medium | 16 | 16% |
| hard | **0** | 0% |

### Recommended (project has no frozen target — advisory only)

For a NEET-oriented Physics pilot, a more balanced mix (e.g. ~40/40/20 easy/medium/hard) is typical industry practice. **This is not a TALOS ADR requirement.** Observed distribution is **too easy-heavy** for claiming NEET-representative scale readiness.

---

## 11. Question-type distribution

| Type (auditor classification from metadata/stem) | Count |
|--------------------------------------------------|------:|
| Numerical | 57 |
| Conceptual | 41 |
| Graph/diagram | 2 |
| Assertion/reasoning | 0 |
| Application (separate) | 0 (folded into numerical/conceptual) |

**Concentration:** Kinematics-heavy by design (TOPIC proof). Missing assertion-reason and graph-rich items for a full NEET shape.

---

## 12. Taxonomy coverage

| Level | Represented in pilot |
|-------|---------------------:|
| Chapters | **9 / 9** P0 (unused P0 chapters: none) |
| Topics | **24** |
| Concepts | **45** |
| Unused P0 concepts | **0** among PDF-mapped lineage set used by bank builder |

Note: coverage is breadth-with-skew (43/100 Kinematics), not uniform depth.

---

## 13. Provenance audit

For all 100 DB rows:

| Field | Status |
|-------|--------|
| Batch tag `physics-t6d-pilot-20260902` | **100/100** |
| `subject:physics`, chapter/topic/concept tags | **100/100** |
| `ncert:…`, `source_pdf:…`, `validation:t6d-gates` | **100/100** |
| `concept_id` assigned | **100/100** |
| `model_used` / `prompt_version` on versions | Present via T6-D create path |
| Placeholder / fabricated refs | **Not observed** (refs match Gate-4 P0 strings) |
| Provenance failures | **0** |

---

## 14. Publication-gate audit

### T6-D CLI path (`PhysicsT6DPilotService`)

Enforced before create/publish:

```text
Structural + Scientific + NCERT(section+PDF) + Taxonomy + Duplicate
 → ACCEPT only → DRAFT → submit → approve → publish
```

Re-run of gates: **100 ACCEPT / 0 REJECT / 0 HOLD**.

### General CMS Admin path

`ContentWorkflowService` publish does **not** require T6-D gate suite. An author can still create/publish a QUESTION that never passed NCERT/duplicate/scientific gates.

| Gate enforcement | Verdict |
|------------------|---------|
| T6-D pilot pipeline | **PASS** (for this batch) |
| Platform-wide “cannot publish unverified Physics MCQ” | **FAIL** (bypass exists outside pilot CLI) |

---

## 15. Practice E2E audit

### Verified (read-only SQL)

| Scope | Result |
|-------|--------|
| Pilot in Practice pool (PUBLISHED + batch) | **100** |
| SUBJECT Physics pilot | **100** |
| CHAPTER kinematics | **43** |
| TOPIC Motion in a Straight Line | **27** |
| TOPIC Motion in a Plane | **16** |
| TOPIC ID overlap | **0** |
| CONCEPT assignment non-null | **100** |

Query latencies (local DB, indicative): subject ~2–3 ms; topic ~2–3 ms.

### Not verified

| Check | Status |
|-------|--------|
| Browser render of stem/options | **NOT VERIFIED** |
| Answer submission + correctness calculation | **NOT VERIFIED** |
| Explanation return on submit | **NOT VERIFIED** |
| Score/progress behavior | **NOT VERIFIED** |

T6-D claimed Practice YES via repository tests; T6-E does **not** re-claim browser E2E success from code inspection alone.

---

## 16. Performance / scale audit

| Measurement | Result |
|-------------|--------|
| Duplicate stem lookup (non-pilot inventory) | **~14 ms** |
| Taxonomy lineage build | **~0–2 ms** |
| 100 stem hashes | **~1–2 ms** |
| Practice scope counts | **~2–3 ms each** |
| Publication query latency (API) | **NOT MEASURED** |
| End-user question retrieval latency | **NOT MEASURED** |

### Architecture capacity (qualitative)

| Scale target | Assessment |
|--------------|------------|
| 1,000 | Structurally feasible if gates harden + indexes maintained |
| 10,000 | Needs indexed fingerprint column / batch tables; avoid full stem scans |
| 100,000+ | Requires dedicated fingerprint store, pagination discipline, async batch workers |
| 1,000,000 | Not evidenced; N+1 and full-table stem scans would fail |

Current duplicate check loads stems via SQL (`body->>'stem'`) then hashes in Python — acceptable at 5k–10k, not at 100k+ without DB-side fingerprints.

---

## 17. Throughput audit

| Metric | Value |
|--------|-------|
| 100 questions processed in | **NOT AVAILABLE** (not persisted by T6-D CLI) |
| Validation / verification / publication throughput | **NOT AVAILABLE** |
| Human intervention | Curated bank authorship (pre-runtime); runtime gates automatic |
| Minimum instrumentation before 1,000 | Wall-clock phases: bank build, gate audit, create, submit, approve, publish; per-gate reject rates; p50/p95 query times |

---

## 18. Idempotency audit

| Evidence | Result |
|----------|--------|
| T6-D reported second run `created=0` | Documented in T6-D audit |
| Mechanism | Stable slug `physics-t6d-pilot-20260902-qNNN` + skip-if-exists |
| This audit mutation re-run | **Not executed** (read-only rule) |
| Fingerprint/idempotency stability | Slug-based — **adequate** for this pilot; not content-hash based for body edits |

---

## 19. Legacy safety audit

| Invariant | Value |
|-----------|-------|
| Legacy rows | **5000** |
| Legacy `concept_id` NULL | **5000** |
| Legacy published | **0** |
| Legacy fingerprint | **`937c60a9aaa5dcbedfa9b5bc569d45a0`** |
| Legacy modifications (this audit) | **0** |
| Legacy publications | **0** |
| Legacy concept assignments | **0** |

**PASS** — matches T6-D before/after evidence.

---

## 20. 1,000-question scale readiness

| Gate | GREEN | AMBER | RED |
|------|:-----:|:-----:|:---:|
| Content correctness | | **X** | |
| Numerical correctness | | **X** | |
| NCERT fidelity | | **X** | |
| Taxonomy accuracy | **X** | | |
| Duplicate control | | **X** | |
| Provenance | **X** | | |
| Publication gates | | **X** | |
| Practice | | **X** | |
| Performance | | **X** | |
| Throughput | | **X** | |
| Idempotency | **X** | | |
| Legacy safety | **X** | | |

**OVERALL SCALE READINESS: AMBER**

---

## 21. Failure register

| Question/Component | Category | Severity | Finding | Evidence | Recommendation |
|--------------------|----------|----------|---------|----------|----------------|
| NCERT gate | NCERT fidelity | **HIGH** | No page-level verification; section+PDF only | `physics_t6d_gates.py`; 0/100 page verified | Define ADR: section+PDF sufficient **or** add excerpt/page gate before 1,000 |
| `verify_calculation` soft paths | Numerical / Scientific | **HIGH** | Accepts incomplete calc dicts | 22 items `unchecked-keys-ok` / “present” | Require closed-form keys; fail closed on soft paths |
| Correct option D | Structure / Quality | **HIGH** | D never correct (0/100) | Bank correct-option Counter | Randomize correct label; forbid zero-use options |
| Difficulty mix | Difficulty | **MEDIUM** | 84% easy, 0% hard | Inventory difficulty | Add medium/hard targets for 1,000 pilot |
| Pad kinematics `t6d-090`–`100` | Near-duplicate | **MEDIUM** | Template clones to fill n=100 | Bank `while len(out) < 100` | Prefer unique concepts; semantic near-dup detector |
| CMS publish outside T6-D | Publication gates | **HIGH** | Non-gated publish still possible | `ContentWorkflowService` vs `PhysicsT6DPilotService` | Wire factory gates into publish eligibility for Physics |
| Practice browser E2E | Practice | **MEDIUM** | Submission/scoring not re-verified | This audit | Authenticated browser or API attempt E2E before 1,000 |
| Throughput metrics | Throughput | **MEDIUM** | No wall-clock persisted | T6-D audit | Instrument CLI phases |
| Dup check scalability | Performance | **LOW** | Full stem scan then hash | `existing_physics_stem_hashes` | Persist `stem_hash` column + index |
| Assertion-reason / graphs | Coverage | **OBSERVATION** | 0 assertion; 2 graph | Type distribution | Expand types in 1,000 design |
| Soft-gated samples | Numerical | **OBSERVATION** | Spot recompute MATCH | t6d-044/048/090/100 | Still harden metadata |

---

## 22. Recommendations (before T6-F 1,000)

1. **Harden scientific gate** — no soft-pass; every numerical must recompute from inputs.
2. **NCERT policy decision** — document accepted evidence level; if page-level required, implement before volume scale.
3. **Balance difficulty + correct-option positions** (include D; add hard items).
4. **Semantic near-duplicate detector** for template families.
5. **Enforce gates on publish** for Physics factory content (not only CLI).
6. **Instrument throughput**; run authenticated Practice E2E on a sample of 20+.
7. **Index stem fingerprints** before 10k+.

Do **not** treat T6-D GREEN as automatic license for 1,000.

---

## 23. Final verdict

```text
T6-E VERDICT:
AMBER

Questions audited:
100

Structural correctness:
PASS (100/100) — caveat: correct-option D never used

Scientific correctness:
PASS on spot-checked content; AMBER on gate rigor (soft calc paths)

Numerical verification:
57 numerical; 35 independently verified; 0 failures among checkable; 22 metadata-incomplete (spot-check OK)

NCERT:
Aligned 100; section+PDF verified 100; page-level verified 0
DIRECTLY_SUPPORTED 5; SUPPORTED_WITH_INFERENCE 95; UNSUPPORTED 0; INVALID 0

Taxonomy:
PASS — Kinematics isolation OK (straight 27 / plane 16 / overlap 0)

Duplicates:
Exact 0; semantic near-dup risk among pad kinematics (OBSERVED)

Provenance:
PASS 100/100

Publication gates:
PASS inside T6-D CLI; FAIL as platform-wide invariant

Practice:
SQL pool + TOPIC isolation PASS; browser/submit E2E NOT VERIFIED

Performance:
Local query timings measured (ms); API E2E NOT MEASURED; architecture OK for ~1k with caveats

Throughput:
NOT AVAILABLE

Idempotency:
PASS (slug-based; no mutation re-run this audit)

Legacy modifications:
0
Legacy publications:
0
Legacy concept assignments:
0

1,000-question scale recommendation:
FIX FIRST

DB writes performed: 0
```

**Accuracy > volume. Evidence > assumptions. Verified > implemented.**
