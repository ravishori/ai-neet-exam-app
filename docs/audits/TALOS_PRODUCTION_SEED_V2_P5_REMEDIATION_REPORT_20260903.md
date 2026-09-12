# Production Seed V2 — P5 AMBER Remediation A–E

**Verdict: GREEN**  
**Date:** 2026-09-03  
**Scope:** Factory capability remediation only (no generation / approve / publish / ECAEP / Diversity / NCERT).

---

## 1. Verdict

GREEN — visual requirements are enforceable, visual-required candidates cannot silently pass without visuals, answer ambiguity has a safe detection/review path, `factory_sample_v2` is reproducible and representative, regressions pass, protected populations and the current V2 100 cohort fingerprints are unchanged, and no generation/approval/publication/ECAEP occurred.

---

## 2. Files changed

| Area | Path |
|------|------|
| Visual policy + SVG materializer | `apps/backend/app/modules/cms/services/factory_v2_visual.py` |
| Answer ambiguity | `apps/backend/app/modules/cms/services/factory_v2_answer_ambiguity.py` |
| V2 sampler | `apps/backend/app/modules/cms/services/factory_sample_v2.py` |
| Candidate validation | `apps/backend/app/modules/cms/services/factory_candidate_validation.py` |
| QuestionBody optional visual fields | `apps/backend/app/modules/cms/schemas/content_bodies.py` |
| Generation attach path | `apps/backend/app/modules/cms/services/content_factory_generation_service.py` |
| Prompt | `apps/backend/app/modules/cms/prompts/factory_mcq.py` |
| Future V2 run wiring | `apps/backend/scripts/run_factory_production_seed_v2.py` |
| Plan builder | `apps/backend/scripts/build_seed_v2_phase1_plan.py` |
| Plan enrichment (visual_* only) | `docs/audits/TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json` |
| Tests | `apps/backend/tests/test_seed_v2_p5_remediation.py` |

`factory_sample_v1` / `ContentFactorySamplingService._stratified_draw` were **not** modified.

---

## 3. Visual architecture

- Every V2 slot now has explicit `visual_required` / `visual_type` / `visual_archetype` (and labels when required).
- Only three slots are `visual_required=true`: **physics-05**, **physics-21**, **zoology-12** (no extra graphical slots invented).
- Propagation: plan → `enrich_slot_with_visual_fields` → `build_v2_generation_constraints` → blueprint constraints → generation request.
- Materialization: deterministic programmatic SVG + structured `visual_spec` (`ncert_evidence: false`). Generators: `xt_slope_graph`, `stress_strain_curve`, `ecg_wave_schematic`.
- Validation: if `visual_required`, missing SVG/spec, type mismatch, missing stem reference, or fabricated NCERT evidence → **FAIL**.
- Archetype string alone does **not** satisfy the visual requirement.

---

## 4. Answer validation architecture

- Structural MCQ checks remain the baseline (V1 callers without visual constraints unchanged in behavior for structure).
- New semantic stage statuses:
  - `STRUCTURALLY_VALID`
  - `SEMANTIC_REVIEW_REQUIRED` (soft — warning / REQUIRES_REVIEW; does not auto-reject)
  - `SEMANTIC_AMBIGUITY_DETECTED` (hard-fail)
- Zoology-15 forensic pattern (two options both pulmonary+systemic+RV+LV) → hard-fail.
- High lexical option overlap alone → review, not automatic reject of scientifically valid items.
- This is **not** a full LLM scientific uniqueness certifier.

---

## 5. V2 sampler architecture

- New module: `factory_sample_v2` / `sample_v2`.
- Seed-stable; subject-name round-robin floor (avoids UUID subject starvation).
- Prefer ≥1 visual-required and ≥1 numerical when present and sample size permits.
- Fill remaining via `subject|difficulty|archetype` buckets.
- Report includes requested/actual size, subject/difficulty/archetype/visual/numerical distributions, seed, exact IDs.

---

## 6. Tests

- New: `tests/test_seed_v2_p5_remediation.py` — **19 passed**
- Broader factory suite (P3/P4/P5 + diversity + plan + remediation): **55 passed, 0 failed**

Covered: visual propagation, missing/valid/mismatch visuals, diagram_data_interpretation without visual, semantic ambiguity + Zoology-15, sampler reproducibility/subject/visual representation.

---

## 7. Integrity

| Population | Result | Fingerprint |
|------------|--------|-------------|
| V2 current 100 | UNCHANGED | `430506b398bdbd4fa046ac218523fe748684fa948c5d3084c5a4476b125d6d66` (DRAFT×100) |
| V1 allowlist | UNCHANGED | bodies `1be73941…`; allowlist sha `c0cf7084…` |
| T6-D | UNCHANGED | `e0758fbc…` |
| T6-F2 | UNCHANGED | `17a1672c…` |
| Legacy | UNCHANGED | `13d51e69…` |
| CMS counts | UNCHANGED | 6441 / pub 1079 / draft 5351 |

Counts this task: Gemini **0**, new GenerationCandidates **0**, approvals **0**, publications **0**, ECAEP **0**.

---

## 8. Remaining limitations

1. The **existing** 100 DRAFT bodies are still text-only (including the three visual slots). Capability is fixed; historical content was intentionally not rewritten.
2. Semantic uniqueness coverage is pattern-based; residual dual-correct science cases may only reach `SEMANTIC_REVIEW_REQUIRED`.
3. Historical P5 sample (Zoology-skewed) remains reproducible via untouched `factory_sample_v1`.

---

## 9. Recommendation for next gate

**Do not** run Diversity Forensics, NCERT certification, approve, publish, or a full new 100 yet.

**Next authorized step (choose explicitly):**

1. Limited rematerialization of **physics-05 / physics-21 / zoology-12** visuals + targeted **zoology-15** correction, **or**
2. P5 re-sample of the current 100 using **`factory_sample_v2`** (seed-controlled), then human review.

Stop here after remediation.
