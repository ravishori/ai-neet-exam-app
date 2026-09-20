# TALOS T6-D Physics Content Pilot Audit — 2026-09-02

## Executive Verdict

**GREEN**

End-to-end pilot proven: 100 NEW curated NCERT-aligned Physics MCQs validated, published via ECAEP, and visible in Practice with TOPIC isolation. Legacy 5,000 unchanged.

---

## 1. Objective

Prove a repeatable factory pipeline:

```text
NCERT / Gate-4 P0 refs + Class XI PDFs
 → curated candidates (100)
 → structural / scientific / NCERT / taxonomy / duplicate gates
 → DRAFT
 → ECAEP submit → approve → publish
 → Practice (FULL / SUBJECT / CHAPTER / TOPIC / CONCEPT)
```

## 2. Scope

| Item | Value |
|------|-------|
| Batch ID | `physics-t6d-pilot-20260902` |
| Target | 100 NEW Physics MCQs |
| Taxonomy | TALOS Physics P0 (74 nodes) |
| Out of scope | Legacy `legacy-physics-5000-import-20260902`, P1/P2, Gravitation, bulk classification |

## 3. Source-of-truth verification

- Concept `ncert_reference` from Gate-4 approved P0 manifest
- Class XI NCERT PDFs present under `StudyMaterial/Physics/Class 11-Physics/`
- Gate requires PDF file on disk + matching section reference
- Content is curated parametric templates with independent numeric checks (not LLM-invented citations)

**Limitation (documented):** verification is section-ref + PDF presence, not OCR page extraction.

## 4. Candidate generation/import

| Metric | Count |
|--------|------:|
| Candidates processed | 100 |
| Created (first apply) | 100 |
| Idempotent re-run created | 0 |
| Slug pattern | `physics-t6d-pilot-20260902-q001`…`q100` |

## 5. Validation results

| Metric | Count |
|--------|------:|
| Accepted | 100 |
| Rejected | 0 |
| Held | 0 |
| Acceptance rate | 1.0 |
| Duplicate rate | 0.0 |

## 6. Scientific verification

Numeric templates re-validated (`v=u+at`, projectile range, vector magnitude, `F=ma`, work/power/energy, etc.). Conceptual items checked for NCERT-consistent statements.

## 7. NCERT verification

Pass rate: **100/100** (section ref + PDF present).

## 8. Taxonomy verification

Pass rate: **100/100**. Chapter/topic/concept codes match P0 lineage.

Kinematics:

| Topic | Published pilot count |
|-------|----------------------:|
| Motion in a Straight Line | 27 |
| Motion in a Plane | 16 |
| Kinematics CHAPTER (both) | 43 |
| Topic ID overlap | **0** |

## 9. Duplicate detection

Intra-pilot stem hashes unique; compared against non-legacy / non-pilot inventory. Duplicate rate **0**.

## 10. Quality audit

| Area | Notes |
|------|-------|
| Structure | 4 options A–D, one correct, unique texts |
| Difficulty | mix of easy/medium |
| Chapter distribution | Kinematics-heavy (TOPIC proof) + coverage across P0 chapters |
| Provenance tags | batch, chapter, topic, concept, ncert, source_pdf |

## 11. Publication results

| Metric | Count |
|--------|------:|
| Newly published (first run) | 100 |
| Publish failures | 0 |
| Pilot published (DB) | 100 |
| Global PUBLISHED questions after | 111 (was 11) |

Path: `ContentWorkflowService` DRAFT → IN_REVIEW → APPROVED → PUBLISHED (with `run_ai_check` on submit).

## 12. Practice verification

| Check | Result |
|-------|--------|
| Pilot in Practice pool | YES (`pilot_published=100`) |
| TOPIC straight vs plane overlap | 0 |
| CONCEPT scope | OK (`concept_scope_ok=true`) |
| CHAPTER kinematics | 43 |
| Empty pool UX | Preserved from T6-B (unchanged) |

## 13. Authentication verification

Unauthenticated `POST /assessments/practice` remains rejected (tested in `test_physics_t6d_pilot.py`). Auth not weakened.

## 14. Legacy 5,000 safety verification

| Invariant | Before | After | Result |
|-----------|-------:|------:|--------|
| Legacy Physics rows | 5000 | 5000 | MATCH |
| Legacy `concept_id IS NULL` | 5000 | 5000 | MATCH |
| Legacy published | 0 | 0 | MATCH |
| Legacy fingerprint | `937c60a9aaa5dcbedfa9b5bc569d45a0` | `937c60a9aaa5dcbedfa9b5bc569d45a0` | MATCH |

## 15. Database changes

- **Only** new rows with slug `physics-t6d-pilot-20260902-q*` / tag batch
- No legacy updates
- No P0 taxonomy node changes
- No schema migration

## 16. Tests

```text
pytest tests/test_physics_t6d_pilot.py
7 passed
```

Coverage: bank size/structure, gates+PDFs, invalid reject, kinematics topics present, legacy dry safety, apply/publish idempotency + TOPIC practice + auth.

## 17. Idempotency test

Second `--apply --publish`: `created=0`, no duplicate inserts; existing published reused. Pilot count remains 100.

## 18. Known limitations

- NCERT gate is section-ref + PDF presence (not page OCR)
- First-law sign-convention wording follows NCERT discussion style; not a full thermodynamics problem set
- Scale next: 100 → 1,000 with measured gate failure rates

## 19. Failed checks

None on final GREEN run.

## 20. Final verdict

**GREEN**

### Acceptance checklist

```text
[x] 100 new pilot candidates processed
[x] Accepted/rejected/held reported
[x] Exactly one defensible answer / four options
[x] Scientific correctness verified
[x] NCERT source verified (section + PDF)
[x] Taxonomy verified
[x] Provenance recorded
[x] Duplicate detection passed
[x] Quality audit passed
[x] Only fully verified questions published (100/100)
[x] Published pilot appears in Practice
[x] TOPIC scope verified (overlap 0)
[x] CONCEPT scope verified
[x] Kinematics topic isolation verified
[x] Authentication remains enforced
[x] Pilot rerun idempotent
[x] Legacy 5,000 unchanged
[x] Legacy concept_id NULL unchanged
[x] Legacy published remains 0
[x] Automated tests pass
[x] Audit report created
```

## Machine-readable summary

```text
T6-D VERDICT: GREEN
Pilot candidates: 100
Accepted: 100
Rejected: 0
Held: 0
Published: 100
Validation pass rate: 1.0
NCERT verification pass rate: 1.0
Taxonomy pass rate: 1.0
Duplicate rate: 0.0
Legacy modifications: 0
Legacy publications: 0
Legacy concept assignments: 0
Practice verified: YES
TOPIC verified: YES
CONCEPT verified: YES
Tests: 7 passed
Audit: docs/audits/TALOS_T6D_PHYSICS_CONTENT_PILOT_AUDIT_20260902.md
```
