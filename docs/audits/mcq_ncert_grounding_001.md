# MCQ-NCERT-GROUNDING-001 — Harden NCERT-Evidence-Grounded MCQ Generation

**Date:** 2026-09-14  
**Verdict:** GREEN — NCERT GROUNDING HARDENED / READY FOR CONTROLLED RE-TEST  
**DB mutations:** none  
**MCQ generation this task:** none  
**271 resume:** not started  

---

## 1. Architecture findings (pre-change)

Factory path (`ContentFactoryGenerationService` → `mcq_llm_provider` → gateway → adapter):

| Question | Finding |
|----------|---------|
| What NCERT evidence is passed to the LLM? | **None** (text). Only hierarchy + blueprint constraint metadata. |
| Full relevant NCERT evidence? | **No** — only `ncert_source_path` existence/path policy via `assert_blueprint_ncert_source`. |
| KU text passed? | **No** — `ku_id` stored on constraints but never loaded into the prompt. |
| Section/page passed? | **No** — `ncert_section_heading` not injected. |
| Can model generate from general knowledge? | **Yes** — system prompt asked for scientific accuracy without a bound passage. |
| Validator check claims vs NCERT? | **No** — structural/semantic/visual only (`validate_candidate_body`). |
| Where to insert gates? | (a) Evidence sufficiency **before** LLM in `_execute_run`; (b) Claim grounding **after** `validate_candidate_body`, before persist. |

Root cause of VERIFY-001 Chem/Botany failures: model enriched from pretrained knowledge (urea/BME/Anfinsen; streptomycin/Streptomyces/secondary metabolites) because the factory never supplied the canonical PDF excerpt as the sole factual source.

---

## 2. Grounding architecture (implemented)

Provider-neutral layers **above** adapters:

1. **`ncert_generation_evidence.py`** — resolve canonical PDF + optional KU → `NcertEvidencePack`
   - Status: `NCERT_EVIDENCE_READY` | `NCERT_EVIDENCE_INSUFFICIENT` | `NCERT_EVIDENCE_NOT_REQUIRED`
2. **`factory_mcq.py` v2** — evidence block injected into user prompt; system contract forbids out-of-evidence facts
3. **`ncert_claim_grounding.py`** — claim/entity gate on stem, every option, explanation
4. **Wired in** `content_factory_generation_service.py`
   - Insufficient NCERT evidence → stop **without** provider call (`NCERT_EVIDENCE_INSUFFICIENT`)
   - Grounding fail → `REJECTED_VALIDATION` / `NCERT_UNSUPPORTED` (no DRAFT persist)

```
NCERT PDF (+ KU)
  → evidence resolver / sufficiency
  → prompt (evidence as ONLY factual source)
  → provider adapter (unchanged)
  → parse + structural validate
  → claim grounding validate
  → persist CREATED DRAFT (or reject)
```

---

## 3. Evidence retrieval & sufficiency

- Canonical root only: `NCERT Books` via existing path policy.
- PDF text via PyMuPDF; short chapter PDFs (≤20 pages) included up to char budget.
- KU `summary` + `structured_facts` composed when `ku_id` present.
- Sufficiency: non-empty (≥400 chars) + keyword relevance hits.
- Insufficient → **do not call provider**.

---

## 4. Claim-level validation

- Extracts high-signal anchors (reagents, named principles, antibiotic/taxa enrichment phrases, molarity protocols).
- Each material anchor in stem / options / explanation must appear in **supplied** evidence.
- Scientifically true but source-absent enrichment → `NCERT_UNSUPPORTED`.
- Near-duplicate correct options → `NCERT_AMBIGUOUS`.
- Simple work–energy numerical independent check when applicable.
- Does **not** self-certify; does **not** mutate legacy candidates.

---

## 5. Provider neutrality

Grounding sits in CMS factory services, not in OpenAI/Anthropic/Gemini adapters. Applies equally whenever factory generation runs.

---

## 6. Regression tests

File: `apps/backend/tests/test_mcq_ncert_grounding_001.py` — **16 passed**

| # | Coverage |
|---|----------|
| 1 | NCERT evidence resolution |
| 2 | Evidence sufficiency gate |
| 3 | Evidence passed into generation request |
| 4–6 | Unsupported claim / option / explanation rejection |
| 7 | Multiple-answer detection |
| 8 | Numerical verification (Physics WE fixture) |
| 9 | Provider-neutral operation |
| 10 | Chemistry regression (urea/BME/Anfinsen) → UNSUPPORTED |
| 11 | Botany regression (streptomycin/Streptomyces/secondary metabolites) → UNSUPPORTED |
| 12 | Positive Zoology + Physics WE fixtures → SUPPORTED |
| 13 | No DB mutation (read-only fixtures + freeze) |

Also: `tests/test_content_factory_p3.py` updated for `PROMPT_VERSION` (`neet_mcq_factory_v2`, ≤20 chars for `content_versions.prompt_version`).

---

## 7. Safety / freeze verification

| Metric | Expected | Observed |
|--------|---------:|---------:|
| PUBLISHED | 1479 | 1479 |
| IN_REVIEW | 111 | 111 |
| SUPERSEDED | 6 | 6 |
| chapters / topics / concepts | 56 / 192 / 318 | OK |
| KUs / blueprints | 381 / 445 | OK |
| unmapped DRAFT | 5024 | 5024 |
| pilot CREATED | 129 | 129 |
| smoke + 5 benchmark candidates | CREATED | unchanged |

Legacy candidates were **not** retroactively certified or invalidated.

---

## 8. Remaining limitations

- Entity lexicon is pattern-based (high-signal enrichment classes), not a full semantic entailment model — novel unsupported phrasing without those anchors may still slip through until patterns expand.
- Explanation soft paraphrases of NCERT-supported content are allowed if they do not introduce high-signal absent entities.
- Non-NCERT (`ai`) blueprints skip the NCERT evidence gate by design.
- Controlled re-benchmark of OpenAI is **out of scope** for this task (explicit STOP).

---

## 9. Files touched

| Path | Role |
|------|------|
| `apps/backend/app/modules/cms/services/ncert_generation_evidence.py` | Evidence resolve + sufficiency |
| `apps/backend/app/modules/cms/services/ncert_claim_grounding.py` | Claim grounding validator |
| `apps/backend/app/modules/cms/prompts/factory_mcq.py` | v2 evidence prompt contract |
| `apps/backend/app/modules/cms/services/content_factory_generation_service.py` | Wire gates |
| `apps/backend/tests/test_mcq_ncert_grounding_001.py` | Regression suite |
| `apps/backend/tests/test_content_factory_p3.py` | Prompt version assert |

---

## STOP

No new benchmark. No MCQ generation. No 271 resume. No publish/certify. No commit/push.
