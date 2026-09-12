# NEET Content Coverage Gap & Acquisition Plan (WAVE-P0-8)

**Date:** 2026-08-31  
**Database audited:** local development `trinetra_db` (read-only SELECT)  
**Mode:** PLANNING ONLY — no generation, import, approval, publish, or content mutation  
**Related:** `CONTENT_READINESS.md`, `ECAEP_CAMPAIGN_CONTROL.md`, `ECAEP_EDITORIAL_PILOT_30.md`, ADR-0012 (seed subset)

---

## Executive Summary

The platform’s **software** for practice/mock/ECAEP is largely ready; the **question bank is not**. Inventory is a monoculture:

| Area | Published | Campaign target (25) | Gap |
|------|----------:|---------------------:|----:|
| Physics | 6 | 25 | 19 |
| Chemistry | 1 | 25 | 24 |
| Biology (Botany+Zoology) | 4 | 25 | 21 |
| **Total published** | **11** | **75 (interim)** | **64** |

Almost all unpublished drafts sit in **three chapters**: Current Electricity, Chemical Bonding, Photosynthesis. **26 of 30** seeded syllabus chapters have **zero** questions. Zoology has **3 published** and **0 drafts**.

**25 published per subject is a planning floor, not product readiness.** Full NEET mock (~180 unique published) and serious chapter breadth remain far away.

**Verdict:** Content acquisition must prioritize **empty core chapters** and **Zoology**, not more Current Electricity / Chemical Bonding / Photosynthesis volume—unless SME review of the existing pilot batch is the immediate next human step.

---

## Current Inventory

**Source:** `cms.content_items` where `content_type = QUESTION` and `deleted_at IS NULL`.

| Status | Count |
|--------|------:|
| DRAFT | 78 |
| IN_REVIEW | 1 |
| APPROVED | 0 |
| PUBLISHED | **11** |
| ARCHIVED | 0 |
| CHANGES_REQUESTED | 0 |
| **Total** | **90** |
| Unmapped (`concept_id` null) | 0 |

### Provenance (latest version lineage)

| Provenance | DRAFT | IN_REVIEW | PUBLISHED |
|------------|------:|----------:|----------:|
| known (`model_used` or `knowledge_unit_id`) | 77 | 0 | 1 |
| missing | 1 | 1 | 10 |

Most **published** rows lack version lineage → **SOURCE VERIFICATION REQUIRED** at review time. Do not invent NTA/official labels.

### Structural vs scientific

Structural completeness of many drafts (see WAVE-P0-4 / pilot) is **not** scientific validity. Difficulty labels are **metadata**, not SME-certified hardness.

---

## Academic Hierarchy (authoritative DB)

Seed is a **representative NTA NEET subset**, not the full ~20 chapters/subject (see `academic/seed.py` / ADR-0012). Only one chapter per subject is fully fleshed with topics+concepts; other chapters exist as empty shells ready for acquisition.

| Subject | Code | Chapters | Topics (non-empty) | Concepts |
|---------|------|---------:|-------------------:|---------:|
| Physics | PHYSICS | 8 | 3 (all under Current Electricity) | 4 |
| Chemistry | CHEMISTRY | 8 | 3 (all under Chemical Bonding) | 3 |
| Botany | BOTANY | 7 | 3 (all under Photosynthesis) | 4 |
| Zoology | ZOOLOGY | 7 | 3 (all under Body Fluids) | 3 |
| **Total** | | **30** | **12** | **14** |

**Implication:** Coverage analysis below is against this **seeded** hierarchy. Expanding the academic tree (more chapters/topics) is a separate curriculum-ops decision; this plan treats empty seeded chapters as acquisition targets once topics/concepts exist or are created with the question.

---

## Subject Coverage

| Subject | DRAFT | IN_REVIEW | PUBLISHED | Total | vs interim target 25 pub |
|---------|------:|----------:|----------:|------:|-------------------------:|
| Physics | 38 | 1 | 6 | 45 | −19 |
| Chemistry | 30 | 0 | 1 | 31 | −24 |
| Botany | 10 | 0 | 1 | 11 | (Biology −21 combined) |
| Zoology | 0 | 0 | 3 | 3 | (Biology −21 combined) |

Campaign Biology = Botany + Zoology → **4 published / 25**.

---

## Botany / Zoology Coverage

| | Published | Unpublished | Chapters w/ any Q | Chapters empty |
|--|----------:|------------:|------------------:|---------------:|
| Botany | 1 | 10 | 1 (Photosynthesis) | 6 |
| Zoology | 3 | **0** | 1 (Body Fluids) | 6 |

**Zoology gap:** No draft pipeline. Growth requires **new acquisition**, not ECAEP review of existing drafts. Published Zoology is only *Body Fluids and Circulation* (3 topics × 1 published each).

---

## Chapter Coverage

### Classification thresholds (documented)

Applied to **published** count per chapter (usable student content):

| Band | Published | Meaning |
|------|----------:|---------|
| **GREEN** | ≥ 5 | Adequate for short chapter practice in this thin bank |
| **YELLOW** | 1–4 | Limited — demo only |
| **RED** | 0 | No usable published content |

Unpublished counts inform **pipeline**, not student readiness.

### Heatmap (all 30 seeded chapters)

| Subject | Chapter | Published | Unpublished | Total | Coverage |
|---------|---------|----------:|------------:|------:|----------|
| Physics | Kinematics | 0 | 0 | 0 | RED |
| Physics | Laws of Motion | 0 | 0 | 0 | RED |
| Physics | Work, Energy and Power | 0 | 0 | 0 | RED |
| Physics | Gravitation | 0 | 0 | 0 | RED |
| Physics | Thermodynamics | 0 | 0 | 0 | RED |
| Physics | Electrostatics | 0 | 0 | 0 | RED |
| Physics | Current Electricity | 6 | 39 | 45 | GREEN |
| Physics | Optics | 0 | 0 | 0 | RED |
| Chemistry | Some Basic Concepts of Chemistry | 0 | 0 | 0 | RED |
| Chemistry | Structure of Atom | 0 | 0 | 0 | RED |
| Chemistry | Chemical Bonding and Molecular Structure | 1 | 30 | 31 | YELLOW |
| Chemistry | Thermodynamics | 0 | 0 | 0 | RED |
| Chemistry | Equilibrium | 0 | 0 | 0 | RED |
| Chemistry | Redox Reactions | 0 | 0 | 0 | RED |
| Chemistry | Organic Chemistry - Basic Principles | 0 | 0 | 0 | RED |
| Chemistry | Electrochemistry | 0 | 0 | 0 | RED |
| Botany | The Living World | 0 | 0 | 0 | RED |
| Botany | Plant Kingdom | 0 | 0 | 0 | RED |
| Botany | Morphology of Flowering Plants | 0 | 0 | 0 | RED |
| Botany | Cell - The Unit of Life | 0 | 0 | 0 | RED |
| Botany | Photosynthesis in Higher Plants | 1 | 10 | 11 | YELLOW |
| Botany | Plant Growth and Development | 0 | 0 | 0 | RED |
| Botany | Sexual Reproduction in Flowering Plants | 0 | 0 | 0 | RED |
| Zoology | Animal Kingdom | 0 | 0 | 0 | RED |
| Zoology | Structural Organisation in Animals | 0 | 0 | 0 | RED |
| Zoology | Biomolecules | 0 | 0 | 0 | RED |
| Zoology | Digestion and Absorption | 0 | 0 | 0 | RED |
| Zoology | Breathing and Exchange of Gases | 0 | 0 | 0 | RED |
| Zoology | Body Fluids and Circulation | 3 | 0 | 3 | YELLOW |
| Zoology | Human Reproduction | 0 | 0 | 0 | RED |

**Summary:** GREEN 1 · YELLOW 3 · RED 26.

### Over-concentrated

| Chapter | Unpublished | Share of area drafts |
|---------|------------:|----------------------|
| Current Electricity | 39 | ~100% of Physics unpublished |
| Chemical Bonding… | 30 | ~100% of Chemistry unpublished |
| Photosynthesis… | 10 | ~100% of Botany unpublished |

### Under-covered / empty

All chapters except the four with any content are **empty** (RED). Highest-value empty examples (NEET weight / foundational): Electrostatics, Optics, Laws of Motion, Equilibrium, Organic basics, Cell, Human Reproduction, Animal Kingdom, Biomolecules.

---

## Topic Coverage

Only **12** topics exist in the seed; all content maps to them.

| Subject | Chapter | Topic | Published | Unpublished | Band |
|---------|---------|-------|----------:|------------:|------|
| Physics | Current Electricity | Electric Current and Ohm's Law | 4 | 21 | YELLOW |
| Physics | Current Electricity | Resistance and Resistivity | 1 | 10 | YELLOW |
| Physics | Current Electricity | Kirchhoff's Laws | 1 | 8 | YELLOW |
| Chemistry | Chemical Bonding… | Ionic Bonding | 0 | 5 | RED |
| Chemistry | Chemical Bonding… | Covalent Bonding and VSEPR Theory | 1 | 6 | YELLOW |
| Chemistry | Chemical Bonding… | Hybridization | 0 | 19 | RED |
| Botany | Photosynthesis… | Light Reaction | 0 | 2 | RED |
| Botany | Photosynthesis… | Dark Reaction (Calvin Cycle) | 0 | 3 | RED |
| Botany | Photosynthesis… | Factors Affecting Photosynthesis | 1 | 5 | YELLOW |
| Zoology | Body Fluids… | Blood and Blood Groups | 1 | 0 | YELLOW |
| Zoology | Body Fluids… | Cardiac Cycle | 1 | 0 | YELLOW |
| Zoology | Body Fluids… | Human Heart Anatomy | 1 | 0 | YELLOW |

**Topic band (published):** GREEN ≥3 · YELLOW 1–2 · RED 0.  
Only Ohm’s Law topic approaches GREEN (4 published).

---

## Difficulty Distribution

Difficulty is **stored metadata** — not scientifically certified.

### Overall inventory

| Difficulty | DRAFT | IN_REVIEW | PUBLISHED | Total |
|------------|------:|----------:|----------:|------:|
| easy | 35 | 0 | 5 | 40 |
| medium | 9 | 1 | 4 | 14 |
| hard | 34 | 0 | 2 | 36 |

### Published only

| Difficulty | Count | Share |
|------------|------:|------:|
| easy | 5 | ~45% |
| medium | 4 | ~36% |
| hard | 2 | ~18% |

### Unpublished skew

Physics/Chemistry drafts are **polarized** (many easy + hard, few medium). Pilot batch was easy-heavy. Acquisition should request **balanced easy/medium/hard** per chapter, then SME-validate labels.

---

## Content Gaps (ranked themes)

1. **Syllabus breadth:** 26/30 chapters empty.  
2. **Zoology pipeline:** 0 unpublished; cannot grow via review alone.  
3. **Chemistry published depth:** 1 published vs 30 drafts in one chapter.  
4. **Monoculture risk:** More CE/Bonding/Photosynthesis without new chapters worsens imbalance.  
5. **Published provenance:** 10/11 published lack lineage → verification backlog.  
6. **Academic tree depth:** Most chapters lack topics/concepts — acquisition must create or extend mapping nodes.  
7. **Full mock:** 11 ≪ 180 unique published questions.

---

## Acquisition Priorities

Priority scores prefer empty high-value chapters over deepening monoculture chapters. Recommended **additional published** questions are planning numbers for acquisition **after** human review—not auto-generate quotas.

| Prio | Subject | Chapter (seeded) | Pub now | Unpub now | Recommend add (to publish after SME) | Difficulty gap | Reason | Dependencies |
|-----:|---------|------------------|--------:|----------:|-------------------------------------:|----------------|--------|--------------|
| P0 | Zoology | Animal Kingdom | 0 | 0 | 8–12 | all | Empty core Bio | Create topics/concepts + legal source |
| P0 | Zoology | Biomolecules | 0 | 0 | 8–12 | all | High NEET frequency | Mapping nodes |
| P0 | Zoology | Human Reproduction | 0 | 0 | 8–12 | all | Empty core | Mapping nodes |
| P0 | Botany | Cell - The Unit of Life | 0 | 0 | 8–12 | all | Empty core | Mapping nodes |
| P0 | Physics | Electrostatics | 0 | 0 | 10–15 | all | Empty high-weight | Mapping nodes |
| P0 | Physics | Optics | 0 | 0 | 10–15 | all | Empty high-weight | Mapping nodes |
| P0 | Chemistry | Equilibrium | 0 | 0 | 10–15 | all | Empty core | Mapping nodes |
| P0 | Chemistry | Organic Chemistry - Basic Principles | 0 | 0 | 10–15 | all | Empty core | Mapping nodes |
| P1 | Physics | Laws of Motion / Work-Energy / Kinematics | 0 | 0 | 8–10 each | all | Mechanics foundation | Mapping |
| P1 | Chemistry | Structure of Atom / Thermodynamics / Electrochemistry | 0 | 0 | 8–10 each | all | Diversify Chem | Mapping |
| P1 | Botany | Morphology / Plant Kingdom / Sexual Reproduction | 0 | 0 | 6–10 each | all | Diversify Botany | Mapping |
| P1 | Zoology | Digestion / Breathing / Structural Org. | 0 | 0 | 6–10 each | all | Diversify Zoology | Mapping |
| P2 | Chemistry | Chemical Bonding… | 1 | 30 | **0–5 new**; prefer SME-publish diverse subset of drafts | medium underrepresented in drafts | Stop monoculture growth | ECAEP pilot review |
| P2 | Physics | Current Electricity | 6 | 39 | **0–5 new**; prefer SME-publish subset | medium | Already GREEN; diversify elsewhere | ECAEP pilot |
| P2 | Botany | Photosynthesis… | 1 | 10 | **0–3 new**; review existing drafts | — | Limited chapter only | ECAEP pilot |
| P2 | Zoology | Body Fluids… | 3 | 0 | 3–5 | deepen topics | Only Zoology chapter with content | Optional |

**Do not** acquire more content *because* a chapter exists in the seed shell alone without a legal source and SME capacity—but empty P0 chapters above are intentional NEET-relevant targets.

---

## Target Inventory Levels

### Assumptions

- One “usable” question = **PUBLISHED**, structurally gated, SME-reviewed.  
- Seeded hierarchy remains the curriculum spine until expanded.  
- Full paper mock ≈ 180 unique published items (45 Phy / 45 Chem / 90 Bio-ish NTA mix); platform may use subject/chapter scopes before that.  
- Personalization/mastery needs **multiple items per concept**, not one.

### LEVEL 1 — Pilot readiness

**Goal:** Reliable ~30-question mixed practice without empty-scope failures; honest thin-content UX already exists (WAVE-P0-5).

| Metric | Target |
|--------|-------:|
| Total published | ≥ 40 |
| Physics published | ≥ 12 |
| Chemistry published | ≥ 12 |
| Biology published (Bot+Zoo) | ≥ 16 |
| Distinct chapters with ≥3 published | ≥ 8 |
| Easy / medium / hard (published) | roughly 40% / 40% / 20% |

**Today:** 11 published, 4 chapters touched → **not pilot-ready for breadth**; software-ready for thin practice on Current Electricity / Body Fluids only.

**Path:** Complete human review of editorial pilot 30 **selectively** (quality over count) **and** start P0 acquisition outside monoculture chapters.

### LEVEL 2 — Serious MVP

**Goal:** Daily practice, chapter tests on ≥half of seeded chapters, subject tests, meaningful revision.

| Metric | Target |
|--------|-------:|
| Total published | ≥ 200 |
| Per subject (Phy / Chem / Bio) | ≥ 60 / 60 / 80 |
| Chapters with ≥5 published | ≥ 20 of 30 |
| Topics with ≥3 published | ≥ 40 (requires expanding topic seed) |
| Full 180 mock | Still optional / partial |

### LEVEL 3 — Mature NEET bank

**Goal:** Repeated mocks, mastery signals, retention, personalization.

| Metric | Target |
|--------|-------:|
| Total published | ≥ 800–1500 |
| Per major chapter (full syllabus, when expanded) | ≥ 15–25 |
| Multiple items per concept | ≥ 5 |
| Concurrent unique full mocks | ≥ 3–5 without heavy item reuse |
| Provenance known + SME-verified | ≥ 95% of published |

**25/subject is far below Level 2–3.**

---

## Student Experience Targets (content vs software)

| Experience | Software | Content minimum (usable published) | Status today |
|------------|----------|-------------------------------------|--------------|
| Daily practice (narrow) | Ready | ≥20 in a few concepts | Partial (CE only) |
| Chapter practice | Ready | ≥5–10 per chapter attempted | Only CE GREEN |
| Subject practice | Ready | ≥25–40 per subject | Not met |
| 30-question mixed | Ready | ≥40 pool with ≥3 subjects | Risky / thin |
| Full mock (~180) | Ready | ≥180 unique published | **Blocked** |
| Revision / recs | Ready (honest empty) | Diverse published mapped concepts | Weak |
| Mastery signals | Partial | Multi-item per concept over time | Insufficient |

Capability ≠ readiness.

---

## Source Strategy

| Category | Use | Notes |
|----------|-----|-------|
| Official examination papers | Prefer where **licensed / public-domain / permitted** | Label accurately; never “NTA official” without evidence |
| NCERT-aligned original authorship | Preferred for pedagogy | Alignment ≠ copying NCERT text illegally |
| Licensed third-party banks | Only with contract | Track license in provenance |
| Human SME-authored | Preferred for gaps | Highest control |
| AI-drafted | Assistive draft only | Must pass ECAEP human review |

**SOURCE OF CONTENT ≠ PROOF OF SCIENTIFIC CORRECTNESS.**  
Human SME remains authoritative. Never falsely label content as official.

---

## ECAEP Acquisition Workflow

```
SOURCE (legal)
  → INGEST / AUTHOR (DRAFT)
  → STRUCTURAL VALIDATION (WAVE-P0-4 gates)
  → ACADEMIC MAPPING (subject/chapter/topic/concept)
  → DUPLICATE DETECTION (surface to human)
  → AI ASSISTANCE (flags only)
  → HUMAN SME REVIEW (checklist + notes)
  → APPROVAL
  → PUBLISH (student-visible)
```

### Minimum metadata per question (existing schema)

| Field | Where |
|-------|--------|
| Source / provenance | `content_versions.model_used`, `knowledge_unit_id`, KU/ingestion lineage; notes in review comments — do not invent |
| Subject / chapter / topic / concept | via `concept_id` → academic tree |
| Difficulty | body `difficulty` (easy\|medium\|hard) |
| Correct answer + options | body |
| Explanation | body |
| Review state | `content_items.status` / version `workflow_state` |
| Reviewer / date / decision / note | `cms.content_reviews` |

**No schema change required** for this plan. Optional later: structured `source_citation` field — out of scope unless proven necessary.

### Quality gates (preserve)

- Lifecycle + `content.publish` permission  
- Four unique A–D options, explanation, difficulty, mapping  
- PUBLISHED-only student surfaces  
- AI never auto-approves  

### Anti-monoculture batch rule

Each future acquisition batch (≥20 items) should include **≥3 subjects** and **≥6 chapters**, with difficulty mix ~40/40/20, unless explicitly a “deepen one chapter” exception documented by content lead. Prefer quality over filling the quota.

---

## Recommended Next Content Batch

**Batch name:** `acquisition-batch-A-diversify-p0` (planning label only)

| Slice | Count (new drafts to author/ingest) | Chapters |
|-------|------------------------------------:|----------|
| Zoology | 24 | Animal Kingdom, Biomolecules, Human Reproduction (8 each) |
| Physics | 20 | Electrostatics (10), Optics (10) |
| Chemistry | 20 | Equilibrium (10), Organic Basic Principles (10) |
| Botany | 10 | Cell - The Unit of Life (10) |
| **Total** | **~74** | **8 chapters** |

**Parallel (not acquisition):** SME review of `ECAEP_EDITORIAL_PILOT_30` — publish only items that pass scientific review; expect **far fewer than 30** publishes if quality bar is real.

**Explicitly deprioritize:** New drafts for Current Electricity / Chemical Bonding / Photosynthesis until P0 empty chapters have a first tranche.

---

## Pilot / Serious MVP / Mature (quick ref)

| Level | Published ≈ | Chapters with content | Mock |
|-------|------------:|----------------------:|------|
| L1 Pilot | ≥40, diversified | ≥8 | No |
| L2 Serious MVP | ≥200 | ≥20/30 seeded | Partial |
| L3 Mature | ≥800–1500 | Full syllabus (expanded) | Yes, multiple |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Continue monoculture acquisition | Enforce anti-monoculture batch rule |
| Treat 25/subject as “ready” | Document L2/L3; marketing truthfulness |
| Publish unverified science | ECAEP human gate mandatory |
| Empty chapter shells without topics | Create topics/concepts with first acquisition |
| Copyright / fake “official” labels | Source strategy + provenance honesty |
| Zoology starvation | P0 acquisition without depending on drafts |
| Difficulty metadata wrong | SME re-label during review |

---

## Validation (this wave)

| Check | Result |
|-------|--------|
| Question rows modified | **No** |
| Statuses changed | **No** (checksum: DRAFT 78 / IN_REVIEW 1 / PUBLISHED 11) |
| Schema / migrations | **No** |
| App code changed | **No** (docs only) |
| External content imported | **No** |
| Auto-publish | **No** |
| Database | `trinetra_db` development only |

---

## Recommended next Cursor wave

1. **Human SME execution** of editorial pilot + selective publish, **or**  
2. **Curriculum ops:** flesh topics/concepts for P0 empty chapters, **or**  
3. **WAVE-P0-2** SMTP / ops if blocked on launch, **or**  
4. Controlled **licensed/human-authored acquisition** for Batch A (separate wave with legal sign-off).

Do **not** start AI mass-generation without ECAEP capacity and anti-monoculture controls.
