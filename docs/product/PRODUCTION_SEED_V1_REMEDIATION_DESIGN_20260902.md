# Production Seed V1 — Remediation Design (2026-09-02)

Status: AUTHORITATIVE for this seed run. Does not reopen T6-F2 / T6-F3 / T6-G.

## Problem (forensically closed 95)

P3 pilot batch `factory-p3-pilot-2026-09-01-batch` produced systemic template concentration
(`SYSTEMIC_DIVERSITY_RISK`): blueprint `chains[0]` pinning, soft paraphrase hint only,
Gate F exact/normalized only, and one Rh phenotype↔explanation gap pattern.

## Remediations (minimum effective)

| Code | Change | Where |
|------|--------|--------|
| **B** | Diversified blueprint allocation: 30 slots, distinct concept codes per subject (Chem ≤1 lattice; Bot avoids non-cyclic photophosphorylation; Zoo avoids ABO) | `factory_seed_diversity.seed_slot_spec` + `run_factory_production_seed_v1.py` |
| **C** | Prior-stem + forbidden-template diversity at generation; prompt injection of recent batch stems | `classify_against_prior`, `build_user_prompt(prior_stems=…)`, `_batch_created_stems` in generation service |
| **E** | Rh/phenotype stem requires Rh/Anti-D in explanation | `phenotype_explanation_error` → `validate_candidate_body` + Gate E RED |

## Non-goals

- No parallel generator
- No cosine/embedding threshold invention
- No publication / ECAEP / APPROVED
- No mutation of existing 95, T6-D, T6-F2, legacy 5k

## Batch identity

- `batch_key`: `production-seed-v1-2026-09-02-batch`
- Tag prefix: `production-seed-v1-2026-09-02`

## Definition of done

See task §16. Certification artifacts under `docs/audits/` and blueprint under `docs/product/`.
Publication is a **separate** authorized task.
