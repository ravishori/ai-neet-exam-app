# Chemistry AMBER shortfall — forensic report

**Date:** 2026-09-02  
**Scope:** Read-only diagnosis (no generation, no mutations, no P4/P5 execution)  
**Evidence:** CONTENT_FACTORY_P3_PILOT_RESULTS.json, generation_candidates run 60d1ef7a-…, _factory_p3_100_pilot_run.log, content_factory_generation_service.py

## Verdict

`	ext
B. YIELD ISSUE — controlled remediation required before rerun
`

AMBER pilot status is **not** converted to GREEN.

## Chemistry yield

| Metric | Value |
|--------|------:|
| Attempts | 50 |
| Created | 20 |
| Duplicate rejects | 17 |
| Parse rejects | 10 |
| Validation rejects | 3 |
| Other | 0 |
| Success rate | 40.0% |
| Rejection rate | 60.0% |
| Stop | ATTEMPT_LIMIT (correct: max=ceil/int 25×2.0 → 50) |

### Cross-slice comparison

| Slice | Attempts | Created | Success |
|-------|---------:|--------:|--------:|
| Physics medium | 28 | 25 | 89.3% |
| Physics easy | 17 | 15 | 88.2% |
| Zoology medium | 17 | 15 | 88.2% |
| Botany easy | 31 | 20 | 64.5% |
| **Chemistry medium** | **50** | **20** | **40.0%** |

Chemistry is anomalous (dominated by intra-run duplicates + JSON parse failures).

## Duplicates (17 Chemistry of 24 overall)

- Mechanism: normalized stem_hash (
ormalize_stem → SHA-256) vs in-memory/CREATED candidates for same concept (DUPLICATE_STEM).
- **All 8 unique rejected hashes** collided with a **CREATED** stem earlier in the **same Chemistry run**.
- Bank fingerprint / other-run collisions: **0**.
- Classification: **17/17 LEGITIMATE DUPLICATE**; **0 POSSIBLE FALSE-POSITIVE** with evidence.
- Model behavior: repeated lattice-energy conceptual stems (created stem previews share near-identical templates).

## Parse failures (10 Chemistry of 18 overall)

- Error code: MALFORMED_JSON only.
- Patterns: Expecting ',' delimiter (8), Invalid \escape (2); all with inishReason=STOP.
- Classification: **10/10 MODEL_OUTPUT_DEFECT** (not PARSER_DEFECT — json.loads correctly rejected invalid JSON; fence rule not implicated).

## Validation (3 Chemistry of 6 overall)

| Gate | Count | Interpretation | Correct? |
|------|------:|----------------|----------|
| SCHEMA:too_long | 2 | Pydantic options max_length=4 (likely >4 options) | Yes |
| SCHEMA:value_error | 1 | NEET shape validator (labels A–D / unique option texts) | Yes |

No scientifically soft overrides applied; rejections stand.

## Blueprint evidence (unchanged)

- Key: actory-p3-pilot-2026-09-01-bp-chemistry-conceptual-medium
- Hierarchy: Chemistry → Chemical Bonding and Molecular Structure → **Ionic Bonding** → **Lattice Energy**
- Family: conceptual; difficulty: medium; provenance: ai
- Constraints: MCQ_4, explanation required, void_paraphrase_duplicates: true
- Pilot asks for **25** items from this **single concept** (
un_factory_p3_pilot.py uses chains[0] only)

## Attempt limit

max_attempts = max(25, int(25 * 2.0)) = 50 → Chemistry attempted 50 → ATTEMPT_LIMIT. **Behaved as designed.** Do not raise.

## Answers (required)

1. **Why 20/25?** Cap hit after 50 attempts; yield crushed by 17 legitimate stem repeats + 10 malformed JSON + 3 schema rejects on a single-concept Lattice Energy slice.
2. **Buckets:** model 10 · duplicate 17 · validation 3 · implementation defects 0 · unknown 0.
3. **Factory defective?** No — expected yield limitation under fixed caps + narrow allocation.
4. **95/100 → P4/P5?** Yes under roadmap ~100 language; run QA/sample on existing DRAFTs. Do not fabricate fill.
5. **Min remediation before another generation:** multi-concept Chemistry allocation; keep gates/caps; optional JSON-escape prompt hygiene only.

## Recommendations

`	ext
Recommended next gate: P4 QA (+ P5 sample) on existing pilot DRAFTs — manual, not auto-run
Recommended code changes: none to unblock P4/P5; allocation diversification before any Chemistry refill
Recommended data/blueprint changes: new multi-concept GREEN Chemistry blueprints for refill only (do not rewrite closed pilot BP evidence)
Whether another live generation is justified: NO (not required for P4/P5; refill only after remediation)
Whether P4/P5 should remain blocked: NO (shortfall does not block; keep manual authorization)
`

Full machine-readable attempt ledger: TALOS_FACTORY_P3_CHEMISTRY_AMBER_FORENSICS_20260902.json
