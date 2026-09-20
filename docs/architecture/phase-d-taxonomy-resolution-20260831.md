# Phase D.4 — Taxonomy Resolution

**Banner:** READ-ONLY ANALYSIS — NO DATABASE CHANGES — NO ECAEP ACTION — NO PUBLICATION

**Generated:** 2026-08-31  
**Database:** `trinetra_db` (verified read-only)  
**Pilot:** `phase-d-30-mcq-authorized-20260825`  
**Writes this phase:** `0`

---

## Executive taxonomy verdict

```text
NEW TAXONOMY CONCEPT REQUIRED
classification: PROPOSE NEW CONCEPT
```

Not ACCEPT EXISTING. Not REMAP TO EXISTING.

---

## Live database verification (read-only)

| Check | Result |
|-------|--------|
| Pilot questions | 30 |
| Pilot DRAFT | 30 |
| Pilot PUBLISHED | 0 |
| `latest_version_id` populated | 30/30 |
| `current_version_id` populated | 30/30 |
| Global QUESTION DRAFT | 78 |
| Global QUESTION IN_REVIEW | 1 |
| Global QUESTION PUBLISHED | 11 |

---

## Hierarchy discovered

```text
Subject  BOTANY
  ↓
Chapter  photosynthesis  (Photosynthesis in Higher Plants)
  ↓
Topic    factors-affecting-photosynthesis  (Factors Affecting Photosynthesis)
  ↓
Concept  photorespiration  ← ONLY concept under this topic
```

**Existing concept under topic:**

| Field | Value |
|-------|--------|
| id | `b48f10f4-e5e1-4740-a62f-c1bcaf3865fb` |
| code | `photorespiration` |
| name | Photorespiration |
| summary | Wasteful oxygenation pathway competing with carbon fixation in C3 plants. |

Seed source: `apps/backend/app/modules/academic/seed.py` — topic `factors-affecting-photosynthesis` seeds only `photorespiration`.

Broader search: no academic concept matching Blackman / limiting-factors / factors-affecting-photosynthesis-law anywhere in live taxonomy.

---

## Option evaluation

### OPTION A — Accept existing (`photorespiration`)

**REJECTED.**

`photorespiration` is NCERT §11.9 pathway chemistry (RuBisCO oxygenation). The two AMBER items test Blackman’s Law / limiting factors from §11.10. Using `photorespiration` is semantically false, not merely coarse.

### OPTION C — Remap to another existing concept

**REJECTED.**

Under `factors-affecting-photosynthesis` there is exactly one concept. No sibling exists for Blackman / limiting factors. Remapping outside this topic would place §11.10 content under the wrong topic parent.

### OPTION B — Taxonomy gap confirmed

**CONFIRMED.**

Parent topic is already correct. Gap is at **concept** level only.

---

## Affected questions

| ID | Live concept | Content | Source | D.2 body action |
|----|--------------|---------|--------|-----------------|
| `e6b9fb1e` | photorespiration | Blackman definition | §11.10 p.19 | KEEP |
| `8d50e829` | photorespiration | Blackman + chlorophyll | §11.10 p.19 | REVISE |

These are the only Phase-D AMBER findings after D.3 final candidate audit (28 GREEN / 2 AMBER / 0 RED).

---

## Taxonomy quality test

| Test | Result |
|------|--------|
| Conceptually distinct from photorespiration? | Yes |
| Supported by NCERT §11.10? | Yes |
| Correct chapter/topic? | Yes (`photosynthesis` / `factors-affecting-photosynthesis`) |
| Future MCQs would use it? | Yes (high NEET density) |
| Overlaps existing concept? | No |
| Fragmentation risk? | Low (sibling under existing topic) |

---

## Proposed concept (DO NOT CREATE IN D.4)

| Field | Proposed value |
|-------|----------------|
| **code** | `limiting-factors` |
| **name** | Limiting Factors (Blackman's Law) |
| **parent topic** | `factors-affecting-photosynthesis` (`4039d404-67cb-4e88-b924-ea873c5c91e7`) |
| **parent chapter** | `photosynthesis` |
| **subject** | BOTANY |
| **summary** | The rate of photosynthesis is controlled by the factor nearest its minimal value (Blackman's Law of Limiting Factors, 1905), including external factors (light, CO₂, temperature, water) and internal factors (leaf traits, chlorophyll amount, internal CO₂). |
| **NCERT** | Class 11 Biology Ch 11 §11.10 Factors Affecting Photosynthesis |
| **difficulty (seed)** | medium |
| **display_order** | 1 (before or after photorespiration; seed order TBD at apply time) |

### Why not a one-off

Reusable for future §11.10 items: Blackman law, light/CO₂/temperature response curves, chlorophyll as internal limiter, “factor nearest minimum” reasoning. Not created merely to satisfy two pilot items.

### Naming convention

Matches seed kebab-case peers: `photorespiration`, `c3-c4-pathway`, `photophosphorylation`.

### Implementation note (future, separate approval)

1. Add concept tuple in `academic/seed.py` under `factors-affecting-photosynthesis`.
2. Alembic data migration (or controlled seed) for deployed DBs.
3. Remap `concept_id` on the two content items **after** concept exists.
4. **Do not** bundle taxonomy seed into MCQ body revision apply without explicit human approval of both gates.

---

## Impact analysis (if concept later approved + remapped)

| Area | Impact |
|------|--------|
| Questions | `e6b9fb1e`, `8d50e829` (concept_id on `cms.content_items`) |
| KU mappings | Unchanged (section provenance remains §11.10) |
| Content versions | Unchanged for taxonomy alone |
| APIs | Concept filters / related-by-concept / browse tree |
| Analytics | Concept-level aggregates split photorespiration vs limiting-factors |
| Future ingestion | Correct target for §11.10 Blackman items |

---

## Governance

```text
AI taxonomy proposal (this document)
        ↓
Human approval of new concept
        ↓
Separate taxonomy seed / migration (Phase D.5a or later)
        ↓
Remap two items' concept_id
        ↓
MCQ body revisions may proceed independently (except remap depends on seed)
```

D.4 does **not** authorize seed or remap.

---

## Safety confirmation

```text
Database modified = NO
ECAEP submitted = NO
Questions published = NO
Concept created = NO
concept_id changed = NO
```
