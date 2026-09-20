# FACTORY-P3 Pilot Results

**Pilot tag:** `factory-p3-pilot-2026-09-01`  
**Date:** 2026-09-01  
**Database:** development `trinetra_db` only  
**Machine-readable:** `CONTENT_FACTORY_P3_PILOT_RESULTS.json`

---

## Executive outcome

| Gate | Result |
|------|--------|
| Implementation + mocked tests | **PASS** (18 factory P1–P3 tests) |
| Live ~100 DRAFT generation | **BLOCKED_PROVIDER** |
| Fabricated questions to hit count | **Not done** (forbidden) |
| Existing question bank mutated | **No** |
| PUBLISHED count changed | **No** (11 → 11) |
| Auto-submit / approve / publish | **None** |

Anthropic API key is present, but live calls fail with **credit balance too low**. Per FACTORY-P3 stop condition §41, the pilot does not invent DRAFT questions.

Earlier in the same session, Claude successfully returned MCQ JSON (before credits exhausted), but persistence failed until the `knowledge.knowledge_units` metadata import fix. After the fix, billing blocked further live creates.

---

## Question counts (dev DB)

| Metric | Before | After |
|--------|--------|-------|
| Total questions | 164 | 164 |
| PUBLISHED | 11 | 11 |
| DRAFT | 142 | 142 |
| IN_REVIEW | 11 | 11 |
| Item checksum | `ce682b03848bf9b3a5b4058308ac6d62` | **unchanged** |
| Body checksum | `6e1e7062fe5b94e9b83516750ff6bb1e` | **unchanged** |
| Review count | 11 | 11 |

---

## Smoke attempt (FACTORY_P3_SMOKE=1)

Diversified GREEN blueprints (reused):

| Slice | Target | Created | Stop |
|-------|--------|---------|------|
| PHYSICS / Current Electricity / medium | 2 | 0 | `PROVIDER_BLOCKED` |
| CHEMISTRY / Chemical Bonding… / medium | 2 | 0 | `PROVIDER_BLOCKED` |
| BOTANY / Photosynthesis… / easy | 1 | 0 | `PROVIDER_BLOCKED` |

**Totals:** requested 5 · attempted 3 · created **0** · cost **$0.00** (failed before billed completion).

---

## Full ~100 pilot

**Not executed** after smoke BLOCKED (would only burn blocked attempts). Allocation planned:

| Subject | Family | Difficulty | Target |
|---------|--------|------------|--------|
| PHYSICS | formula_application | medium | 25 |
| PHYSICS | direct_concept | easy | 15 |
| CHEMISTRY | conceptual | medium | 25 |
| BOTANY | ncert_fact | easy | 20 |
| ZOOLOGY | process_sequence | medium | 15 |
| **Sum** | | | **100** |

---

## New question IDs

*None* (live create count = 0).

---

## Distributions (live)

N/A — no successful creations. Mocked tests exercise Physics-concept blueprints only.

---

## Provider / model / cost

| Field | Live smoke |
|-------|------------|
| Provider | Anthropic (Claude via AIGateway) |
| Successful model completions | 0 (this blocked run) |
| Failures | credit balance / invalid_request |
| Estimated cost | $0.00 |

---

## Failure statistics

| Class | Count (smoke) |
|-------|----------------|
| Provider blocked (billing) | 3 |
| Validation / parse / duplicate | 0 |
| Orphan content | 0 |

---

## Human review preparation

No DRAFT queue to sample — unblock Anthropic credits, re-run `scripts/run_factory_p3_pilot.py`, then export candidate IDs from `CONTENT_FACTORY_P3_PILOT_RESULTS.json` for P4/P5 sampling. **Do not auto-submit.**

---

## Unblock checklist

1. Top up Anthropic credits (or configure a funded dev key)
2. Re-run smoke (`FACTORY_P3_SMOKE=1`)
3. Confirm DRAFT-only + checksum of *pre-existing* items still stable
4. Run full ~100 diversified pilot
5. Update this doc + JSON with metrics (created, reject/dup rates, cost, distributions)
