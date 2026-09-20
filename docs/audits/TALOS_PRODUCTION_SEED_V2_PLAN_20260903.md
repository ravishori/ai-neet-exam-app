# Production Seed V2 — Phase 1 Blueprint Plan

**Verdict:** GREEN  
**Status:** PLANNING_ONLY — Gemini not called; no CMS writes.

## Allocation

| Subject | Slots | Distinct chapters | Largest chapter cluster |
|---------|------:|------------------:|-------------------------|
| Physics | 35 | 12 | {'chapter': 'Kinematics', 'n': 4} |
| Chemistry | 35 | 8 | {'chapter': 'Some Basic Concepts of Chemistry', 'n': 5} |
| Botany | 15 | 7 | {'chapter': 'Cell - The Unit of Life', 'n': 3} |
| Zoology | 15 | 5 | {'chapter': 'Body Fluids and Circulation', 'n': 4} |

## Uniqueness

- Slots: 100
- Unique blueprint IDs: 100
- Difficulty: easy 25 / medium 60 / hard 15

## Archetypes

{
  "direct_ncert_conceptual": 42,
  "application": 22,
  "numerical_calculation": 14,
  "diagram_data_interpretation": 3,
  "comparison": 14,
  "statement_based": 2,
  "sequence_order": 3
}

## NCERT

- Unique source PDFs: 35
- All exist: True
- page_verified: false (planning)

## Previous failure avoidance

See JSON `previous_failure_avoidance`. ABO/Ohm-stretch/lattice clusters constrained.

## Generation feasibility

Estimate only. Policy caps unchanged (200 attempts, $30). V1 cost suggests V2 remains far under cap.

## Protected populations

{
  "t6d": true,
  "t6f2": true,
  "legacy": true,
  "seed_v1_allowlist_hash": true,
  "seed_v1_published_30": true
}

## Stop

Do **not** start P3 generation until separately authorized.
