# NEET Content Factory — Sampling Preparation

**Status:** FACTORY-P4 implemented · 2026-09-01  
**Scope:** Reproducible eligibility draws — **not** certification, approval, or publish.

---

## Principles

1. GREEN sample estimates residual defect rate — items remain DRAFT until ECAEP.
2. YELLOW → 100% human-review eligibility.
3. RED → quarantine / exception list; never enters GREEN sample.
4. Stratify to catch systematic blueprint/model/prompt defects.
5. Store seed + policy version for auditability.

---

## Policy `factory_sample_v1`

| Stream | Rule |
|--------|------|
| GREEN | Stratified sample size \(n=\min(N_{green},\max(5,\lceil 2\sqrt{N_{green}}\rceil))\) (configurable) |
| YELLOW | All IDs |
| RED | All IDs (quarantine confirmation) |

Strata key: `subject_id|family_id|difficulty|blueprint_id` with round-robin selection.

Uncertainty: YELLOW already prioritizes possible duplicates / soft metadata; uncommon strata appear in `strata_summary`.

---

## Persistence

`cms.review_samples`:

- `sample_key` (unique idempotency)
- `seed`, `policy_version`
- `selected_candidate_ids` (GREEN draw)
- `yellow_candidate_ids`, `red_candidate_ids`
- `selection_reasons`, `strata_summary`
- Disclaimer note: sampling ≠ scientific certification

---

## API

`POST /api/v1/cms/content-batches/{batch_id}/sample`  
Permission: `content.factory.execute`

---

## What P5 adds

SME queue UX, review outcomes on sample members, statistical reporting — still without auto-approve/publish.
