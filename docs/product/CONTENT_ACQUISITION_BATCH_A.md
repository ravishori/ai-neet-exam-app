# Content Acquisition Batch A — Diversify P0 (WAVE-P0-9)

**Batch ID:** `acquisition-batch-A-diversify-p0`  
**Executed:** 2026-08-31 on local development `trinetra_db`  
**Mode:** Create **DRAFT** only via existing `ContentWorkflowService.create_item`  
**Auto-approve / auto-publish:** **None**

---

## Source strategy

| Attribute | Value |
|-----------|--------|
| Origin | **Human-authored** catalog (`model_used=human-authored-batch-a`) |
| Alignment | NCERT UG **curriculum-aligned** conceptual MCQs |
| Official NTA/NEET papers | **Not claimed** (`not-official-nta` tag) |
| Licensed third-party bank | Not used |
| AI generation | Not used for this batch |
| SME | **Still required** before approve/publish |

Truthful provenance: human-authored educational drafts for diversification. Scientific correctness is **not** certified by import.

---

## Batch objectives

From `NEET_CONTENT_COVERAGE_PLAN.md`:

- ~74 drafts across **8 empty/high-value chapters**
- ≥3 subjects, ≥6 chapters, multi-topic, multi-difficulty
- Avoid Current Electricity / Chemical Bonding / Photosynthesis monocultures

---

## Target chapters

| Subject | Chapter | Planned |
|---------|---------|--------:|
| Physics | Electrostatics | 10 |
| Physics | Optics | 10 |
| Chemistry | Equilibrium | 10 |
| Chemistry | Organic Chemistry - Basic Principles | 10 |
| Botany | Cell - The Unit of Life | 10 |
| Zoology | Animal Kingdom | 8 |
| Zoology | Biomolecules | 8 |
| Zoology | Human Reproduction | 8 |
| **Total** | **8 chapters** | **74** |

Hierarchy fill: topics/concepts created under existing chapter codes (idempotent). No new chapter names invented.

---

## Actual questions created

| Metric | Count |
|--------|------:|
| Planned | 74 |
| **Created (DRAFT)** | **74** |
| Rejected | 0 |
| Skipped (idempotent re-run) | 0 on first run; **74** on second run |
| PUBLISHED changed | **0** (stayed 11) |

Post-import inventory: DRAFT **152** · IN_REVIEW 1 · PUBLISHED **11**.

---

## Subject distribution

| Subject | Created |
|---------|--------:|
| Physics | 20 |
| Chemistry | 20 |
| Botany | 10 |
| Zoology | 24 |

## Chapter distribution

| Chapter | Created |
|---------|--------:|
| Electrostatics | 10 |
| Optics | 10 |
| Equilibrium | 10 |
| Organic Chemistry - Basic Principles | 10 |
| Cell - The Unit of Life | 10 |
| Animal Kingdom | 8 |
| Biomolecules | 8 |
| Human Reproduction | 8 |

## Topic distribution

24 topics populated (3 topics × 8 chapters). See runtime audit; examples: Coulomb’s Law, Capacitance, YDSE, Kc/pH/Ksp, Homologous series, Cell organelles, Chordate features, Enzymes, Menstrual cycle.

## Difficulty distribution

| Difficulty | Count |
|------------|------:|
| easy | 34 |
| medium | 26 |
| hard | 14 |

Metadata only — SME may re-label.

## Provenance coverage

| Field | Coverage |
|-------|----------|
| `model_used=human-authored-batch-a` | 74/74 |
| `prompt_version=batch-a-v1` | 74/74 |
| Tags include `acquisition-batch-A-diversify-p0`, `origin:human-authored`, `sme-review-required` | 74/74 |
| Official NTA claim | **False** |

## Duplicate findings

- Exact stem vs existing bank: **0** rejected  
- Idempotent slug `batch-a-{source_key}`: second run skipped all 74  

## Validation failures

**0** on successful import (catalog pre-validated against WAVE-P0-4 QUESTION gates).

## Questions requiring SME attention

**All 74.** Especially:

- Confirm scientific accuracy and single defensible answer  
- Confirm NEET depth/style  
- Confirm academic mapping  
- Confirm difficulty labels  
- Do not treat as official exam items  

Filter in admin: tag `acquisition-batch-A-diversify-p0` or slug prefix `batch-a-`.

## Database safety

| Check | Result |
|-------|--------|
| Target DB | `trinetra_db` (dev); CLI refuses other DBs |
| Production | Not touched |
| Existing PUBLISHED | Unchanged (11) |
| Existing non-batch drafts | Unchanged |
| Schema migrations | None |
| Transaction | Per-item create via existing workflow commits; failed item does not block others |

## Rollback / idempotency

- **Idempotency:** re-run creates 0 new rows (slug match).  
- **Rollback (manual):** delete/archive items with tag `acquisition-batch-A-diversify-p0` if needed — not automated.  
- Audit action: `content.acquisition_batch`.

## Next editorial-review batch

1. Open Editorial Review & Campaign.  
2. Filter/submit Batch A drafts for IN_REVIEW (do not bulk-publish).  
3. Prioritize Zoology + empty-chapter diversification over monoculture drafts.  
4. Publish only after SME checklist.

---

## How to re-run (dev)

```text
cd apps/backend
.venv\Scripts\python.exe -m app.modules.cms.acquisition.run_batch_a
```

Or authorized API: `POST /api/v1/cms/acquisition/batch-a` (`content.create` + CSRF).

---

## Acceptance (WAVE-P0-9)

| Criterion | Met |
|-----------|-----|
| Diversified 8 chapters / 4 subjects | Yes |
| Structurally valid DRAFTs | Yes |
| Provenance preserved | Yes |
| No auto-publish | Yes |
| Idempotent | Yes |
| Tests | `tests/test_batch_a_acquisition.py` |
| Docs | This file |
