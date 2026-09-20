# Production Seed V2 — NCERT Certification Re-run (Exact Active 100)

**Verdict: GREEN**  
**Captured:** 2026-09-03T18:54:31.999957+00:00  
**Mode:** NCERT evidence metadata write only — no approve / publish / ECAEP / generation / stem-option-answer-explanation mutation

Supersedes `TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_20260903.json` (prior **RED** on four numerical failures).  
Active IDs follow finalized `TALOS_PRODUCTION_SEED_V2_NUMERICAL_REMEDIATION_20260904.json` (**AMBER**). Historical superseded numerical/visual originals were **not** certified as active.

## Independence limitation

Agent StudyMaterial PDF text search + deterministic numerical solvers. **Not** independent human NCERT certification. `page_verified=false` for all 100; PDF page index is not a printed NCERT page number.

## 1. Final verdict

**GREEN** under the same V2 certification rule as 2026-09-03: 100/100 `CERTIFIED_WITH_LIMITATION`, 0 FAIL, 0 REQUIRES_HUMAN_REVIEW, integrity preserved, no fabricated page/section numbers.

Bare `CERTIFIED` is never emitted while `page_verified=false`.

## 2. Exact active population

| Subject | Count |
|---------|------:|
| Physics | 35 |
| Chemistry | 35 |
| Botany | 15 |
| Zoology | 15 |
| **Total** | **100** |

All 100 items **DRAFT**. Historical excluded: **8** (4 visual originals + 4 numerical originals).

Numerical replacement IDs (current active):

| Slot | Replacement ID |
|------|----------------|
| physics-10 | `2e43ef71-d72a-423a-b9be-2e44c51de8b1` |
| physics-11 | `5b4f381e-0dee-4118-b237-fbaabbe1d0f5` |
| physics-20 | `f60e3124-8aa0-4ff6-b3e1-f8ad81eadce9` |
| physics-34 | `b98e5873-8352-4bb6-9a30-368e2f0ce6f7` |

Full slot→ID map: `active_population.ids_by_slot` in the JSON artifact.

## 3. Certification counts

| State | Count |
|-------|------:|
| CERTIFIED | 0 |
| CERTIFIED_WITH_LIMITATION | 100 |
| REQUIRES_HUMAN_REVIEW | 0 |
| FAIL | 0 |

Evidence writes (`SOURCE_TEXT_VERIFIED`, `page_number=null`, `section=null`): **100**.  
Chapter-title token check vs mapped PDF: **100/100 PASS**.  
Unique mapped NCERT PDFs: **35**.

## 4. NCERT source mapping

Each slot used the V2 plan `ncert_source_path` under `StudyMaterial/`. No KEPH, no invented sources.

Numerical remat sources:

- physics-10 → `StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-4.pdf` (Laws of Motion)
- physics-11 → `StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-5.pdf` (Work, Energy and Power)
- physics-20 → `StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-8.pdf` (Mechanical Properties of Solids)
- physics-34 → `StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-2-chapter-9.pdf` (Optics)

Per-item source file, excerpt, and `pdf_page_index` are in JSON `items[]` (`search_hits_summary`). Printed page numbers are **not** claimed.

## 5. Four numerical replacement results

Prior 2026-09-03 FAIL status was **not** inherited. Current replacements were independently re-solved.

| Slot | Stored | Independent | Decision | Semantic |
|------|--------|-------------|----------|----------|
| physics-10 | B | PASS (impulse 15, ΔKE 60) | CERTIFIED_WITH_LIMITATION | SEMANTIC_REVIEW_REQUIRED (soft; `hard_fail=false`) |
| physics-11 | B | PASS (Kf=46 J) | CERTIFIED_WITH_LIMITATION | SEMANTIC_REVIEW_REQUIRED (soft; `hard_fail=false`) |
| physics-20 | A | PASS (ΔL≈1.29×10⁻³ m) | CERTIFIED_WITH_LIMITATION | STRUCTURALLY_VALID |
| physics-34 | B | PASS (shift +15 cm away) | CERTIFIED_WITH_LIMITATION | STRUCTURALLY_VALID |

Soft semantic flags are **not** treated as full uniqueness certification. They are recorded limitations. They did not overturn independent numerical uniqueness (distinct option values / direction-aware match).

All independently verified numerical slots in this gate: **14 PASS** (including the four replacements).

## 6. Graphical results

Generated SVG ≠ NCERT evidence (`visual_spec.ncert_evidence` not used as source).

| Slot | ID | Decision | Classification |
|------|----|----------|----------------|
| physics-05 | `9c51f8a1-…ee53` | CERTIFIED_WITH_LIMITATION | NCERT_CONCEPT_SUPPORTED_VISUAL_IS_FACTORY_RENDER |
| physics-21 | `1633f068-…1729e` | CERTIFIED_WITH_LIMITATION | NCERT_CONCEPT_SUPPORTED_VISUAL_IS_FACTORY_RENDER |
| zoology-12 | `ca0e7a05-…6b07` | CERTIFIED_WITH_LIMITATION | NCERT_CONCEPT_SUPPORTED_VISUAL_IS_FACTORY_RENDER |

## 7. Page verification

- `page_verified=true`: **0**
- `page_verified=false`: **100**
- `PAGE_VERIFIED` claims: **0**
- `SECTION_VERIFIED` claims: **0**

## 8. Human review requirements

**None** (`REQUIRES_HUMAN_REVIEW` = 0, `FAIL` = 0).

Bounded documented limitations remain (independence, no printed page, soft semantic flags on physics-10/11). These are **not** open review tickets under this gate’s decision taxonomy.

## 9. Integrity

| Check | Result |
|-------|--------|
| Active core fingerprint unchanged | True (`adb5ae60…`) |
| Historical superseded (n=8) unchanged | True |
| V1 / T6-D / T6-F2 / legacy unchanged | True |
| Approvals / V2 publications / ECAEP | 0 / 0 / 0 |
| Stem / options / answer / explanation mutations | 0 |
| Only `ncert_evidence` metadata written | True |
| Active count | 100 DRAFT |

## 10. Tests

**58 passed**, 0 failed:

- `tests/test_seed_v2_numerical_remediation.py`
- `tests/test_factory_seed_diversity.py`
- `tests/test_seed_v2_p5_remediation.py`
- `tests/test_t6e_fix_gates.py`
- `tests/test_seed_v2_phase1_plan.py`
- `app/modules/ingestion/tests/test_study_material_ncert_parser.py`

Thresholds not weakened.

## 11. Limitations

- Not human NCERT certification
- No printed page verification
- Factory visuals are not NCERT evidence
- physics-10/11: `SEMANTIC_REVIEW_REQUIRED` is a limitation, not uniqueness certification
- Diversity `SEMANTIC_DEDUPE_NOT_AVAILABLE` is not an NCERT claim
- V2 cohort only — does not certify the global bank

## 12. Publication authorization

**Certification gate does not authorize publication.**

`publication_authorization_ready`: **true** only in the sense that this NCERT re-run is GREEN and the prior RED numerical block is cleared. A **separate Publication Authorization** gate is still required. This run did not approve, publish, create ECAEP, generate, or deploy.

**Next gate (if separately authorized):** Publication Authorization — Exact Active 100.

---

**STOP** — NCERT certification re-run complete. Do not approve / publish / generate / start 1,000-scale production / deploy.
