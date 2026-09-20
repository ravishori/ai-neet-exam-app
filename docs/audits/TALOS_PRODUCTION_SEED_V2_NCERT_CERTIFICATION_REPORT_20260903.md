# Production Seed V2 — NCERT Certification (Exact Active 100)

**Verdict: RED**  
**Captured:** 2026-09-03T18:29:40.319040+00:00  
**Mode:** NCERT evidence metadata write only — no approve / publish / ECAEP / content mutation / generation

## Independence limitation
Agent StudyMaterial PDF text search + independent numerical verification. **Not** human NCERT certification.

## 1. Population
Active **100** (Physics 35 / Chemistry 35 / Botany 15 / Zoology 15)  
Historical superseded excluded: **4**  
Replacements audited: physics-05, physics-21, zoology-12, zoology-15

## 2. Decision summary
| State | Count |
|-------|------:|
| CERTIFIED | 0 |
| CERTIFIED_WITH_LIMITATION | 96 |
| REQUIRES_HUMAN_REVIEW | 0 |
| FAIL | 4 |

## 3. NCERT source mapping
All 100 slots used plan `ncert_source_path` under `StudyMaterial/`.  
Chapter-title token check: **100/100 PASS**.  
Evidence writes (`SOURCE_TEXT_VERIFIED`, `page_number=null`): **96**.  
`PAGE_VERIFIED`: **0** (not claimed).

## 4. Failures (material — block GREEN)
- **physics-10** `4304a3ef-26c7-4494-bd87-7af1a40759f8`: Independent calc: impulse on B=8 N·s, KE loss=24 J → option C; stored answer A (KE loss 16 J) is wrong.
- **physics-11** `223c5cdf-6759-43ed-acd6-7a47b0f52d33`: Independent calc: W=∫₀³(6x-4)dx=15 J; Ki=9 J → Kf=24 J → option B; stored answer C (21 J) is wrong.
- **physics-20** `03f040b6-3623-4126-8503-e61be9b0dabd`: Independent calc: ΔL=FL/AY=800·2/(4e-6·2e11)=2.0×10⁻³ m → option B; stored answer A (1.0×10⁻³ m) is wrong.
- **physics-34** `690202d2-83dd-4645-8034-cfb19f54833a`: Independent calc: u₁=-30 cm,u₂=-25 cm,f=+15 → v₂=+37.5 cm (shift +7.5 cm away). No option matches; stored A (30 cm) is inconsistent.

## 5. Page verification
page_verified=true: **0** · false: **100**

## 6. Visual questions
- `physics-05` → CERTIFIED_WITH_LIMITATION · NCERT_CONCEPT_SUPPORTED_VISUAL_IS_FACTORY_RENDER · SVG **not** NCERT evidence
- `physics-21` → CERTIFIED_WITH_LIMITATION · NCERT_CONCEPT_SUPPORTED_VISUAL_IS_FACTORY_RENDER · SVG **not** NCERT evidence
- `zoology-12` → CERTIFIED_WITH_LIMITATION · NCERT_CONCEPT_SUPPORTED_VISUAL_IS_FACTORY_RENDER · SVG **not** NCERT evidence

## 7. Numerical questions
{'PASS': 10, 'FAIL': 4}

## 8. Rematerialized four
- `physics-05` → CERTIFIED_WITH_LIMITATION · StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-2.pdf
- `physics-21` → CERTIFIED_WITH_LIMITATION · StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-8.pdf
- `zoology-12` → CERTIFIED_WITH_LIMITATION · StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-15.pdf
- `zoology-15` → CERTIFIED_WITH_LIMITATION · StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-15.pdf

## 9. Integrity
Active core / historical / V1 / T6-D / T6-F2 / legacy unchanged: **True**  
Approvals/publications/ECAEP/generation: **0**  
Only `ncert_evidence` metadata written (96 CERTIFIED_WITH_LIMITATION); FAIL bodies left without certified evidence.

## 10. Tests
- t6e + V2 remediation + diversity + V2 plan: **45 passed**
- study_material_ncert_parser: **5 passed**
- Thresholds not weakened; content not mutated to pass

## 11. Limitations
- INDEPENDENCE LIMITATION: agent StudyMaterial PDF text search + limited numerical patterns — not human NCERT certification
- page_verified=false for all items; PDF page index ≠ printed NCERT page
- No SECTION_VERIFIED claims (section titles not invented)
- No PAGE_VERIFIED claims
- Generated visuals are not NCERT evidence
- SEMANTIC_DEDUPE_NOT_AVAILABLE (diversity) is not converted into an NCERT claim
- Numerical questions without matched automation pattern: principle supported, arithmetic limitation documented
- V2 cohort evidence only — does not certify the global question bank

## 12. Publication authorization readiness
**False**

Do NOT approve/publish. Rematerialize or correct the four FAIL numerical items (physics-10, physics-11, physics-20, physics-34) under a separately authorized remediation gate. Do not silently edit answers in this certification gate.

**Next:** Targeted numerical remediation for 4 FAIL slots, then re-run NCERT certification. Publication authorization is blocked while verdict is RED.

---
**STOP** — NCERT certification complete. Do not approve / publish / generate / start 1,000-scale production.
