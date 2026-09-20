# Physics 5000 Taxonomy Resolution Audit — 2026-09-02

**Mode:** READ-ONLY (proposal only)  
**Batch:** `legacy-physics-5000-import-20260902`  
**Generated:** 2026-09-02  

**Hard safety:** No PostgreSQL writes. No `concept_id` assignments. No taxonomy creates. No publication. No source file modifications.

---

## 0. Correction: unresolved count is 5, not 6

`docs/audits/PHYSICS_5000_TALOS_IMPORT_AUDIT_20260902.md` stated “**6 chapters UNRESOLVED**”.  
The authoritative mapping in `apps/backend/app/modules/cms/acquisition/physics_5000_mapping.py` defines **exactly five** entries with `confidence=UNRESOLVED` and `talos_chapter_code=None`.

DB confirmation (SELECT only):

| `mapping_confidence` tag | Questions |
|--------------------------|----------:|
| UNRESOLVED | **2500** |
| LOW | 1000 |
| MEDIUM | 1500 |

| `talos_chapter:UNRESOLVED` by `legacy_chapter_id` | n | diagrams |
|--------------------------------------------------|---:|--------:|
| 1 | 500 | 150 |
| 6 | 500 | 150 |
| 7 | 500 | 150 |
| 8 | 500 | 150 |
| 10 | 500 | 150 |

**Sum = 2500** (half of the 5000-question import). The “6” figure in the import audit is incorrect.

---

## 1. Exact unresolved legacy chapters

| Legacy CH ID | Legacy chapter name | Mapping note in code |
|-------------:|---------------------|----------------------|
| **1** | Units and Measurement | No TALOS chapter |
| **6** | Systems of Particles and Rotational Motion | No TALOS chapter |
| **7** | Mechanical Properties of Solids | No TALOS chapter |
| **8** | Mechanical Properties of Fluids | No TALOS chapter |
| **10** | Kinetic Theory | No TALOS chapter |

Source of truth: `LEGACY_CHAPTER_MAP` in `physics_5000_mapping.py` (chapters 2–5 and 9 already have a TALOS chapter *code* at LOW/MEDIUM; they are out of scope for this unresolved audit).

---

## 2. Affected question counts

| Legacy CH | Legacy name | Questions | Diagrams | ID range |
|----------:|-------------|----------:|--------:|----------|
| 1 | Units and Measurement | 500 | 150 | `PHY11-CH01-0001` … `PHY11-CH01-0500` |
| 6 | Systems of Particles and Rotational Motion | 500 | 150 | `PHY11-CH06-2501` … `PHY11-CH06-3000` |
| 7 | Mechanical Properties of Solids | 500 | 150 | `PHY11-CH07-3001` … `PHY11-CH07-3500` |
| 8 | Mechanical Properties of Fluids | 500 | 150 | `PHY11-CH08-3501` … `PHY11-CH08-4000` |
| 10 | Kinetic Theory | 500 | 150 | `PHY11-CH10-4501` … `PHY11-CH10-5000` |
| **Total unresolved** | | **2500** | **750** | |

Counts verified from legacy JSON and from CMS tags on the import batch. Each of the ten legacy chapters has 500 questions; five unresolved → **2500**.

---

## 3. TALOS Physics taxonomy (read-only)

**Subject:** PHYSICS (`8546ab39-2401-4e1f-91e7-a22e27afe147`)

### Chapters present (8)

| Chapter ID | code | name | Topics? | Concepts? |
|------------|------|------|---------|-----------|
| `b20f8158-cba8-41d2-a88e-3fbd1b2261d2` | `kinematics` | Kinematics | none | none |
| `433d0aa4-5edd-4ddf-9729-e3cfc9299e1f` | `laws-of-motion` | Laws of Motion | none | none |
| `81f3a1f9-8348-401f-b35d-0a196c97f2ea` | `work-energy-power` | Work, Energy and Power | none | none |
| `d1f5f09d-037a-4e1d-abcb-1a760a4be031` | `gravitation` | Gravitation | none | none |
| `2f62c566-16e5-4996-a5e3-d003592dd35b` | `thermodynamics-physics` | Thermodynamics | none | none |
| `ed3e1c7b-f27a-483a-85ee-9a851f3c0963` | `electrostatics` | Electrostatics | yes | yes |
| `44e651c0-5346-4439-a60d-6424e0768a9f` | `current-electricity` | Current Electricity | yes | yes |
| `b35e04b3-ab7b-4bb5-bfc4-ad7e914297c1` | `optics` | Optics | yes | yes |

### Chapters absent (needed for NCERT Class 11 unresolved set)

- Units and Measurement  
- Systems of Particles and Rotational Motion  
- Mechanical Properties of Solids  
- Mechanical Properties of Fluids  
- Kinetic Theory  

Confirmed against `apps/backend/app/modules/academic/seed.py` (`PHYSICS_CHAPTERS`) — these titles are not seeded.

### Concepts under Class 11 mechanics/thermo chapters

**None.** The only Physics concepts in TALOS today sit under Electrostatics, Current Electricity, and Optics — none of which match any of the 2500 unresolved stems.

---

## 4. Mapping analysis (chapter-level)

Rule applied: **never map merely because names look similar**; evidence must come from stem subject matter **and** an existing TALOS node.

### Critical evidence: legacy chapter labels are not content-faithful

Across **all ten** legacy chapters (including “resolved” ones), the bank recycles the **same eight algorithmic topics**:

| Legacy topic label | Global count | Actual stem subject matter |
|--------------------|-------------:|----------------------------|
| Young modulus | 880 | Young’s modulus / stress–strain |
| ideal gas | 880 | Ideal gas, isochoric heating |
| kinematic equations | 870 | 1-D kinematics (stopping distance) |
| work | 870 | Work by constant force |
| friction on inclined plane | 450 | Incline friction / Atwood |
| kinematic graphs | 450 | v–t / a–t kinematics |
| PV work | 350 | Thermodynamic cyclic PV work |
| manometer / stress-strain | 250 | Mixed: U-tube manometer **or** stress–strain curve |

Chapter titles are injected into stems as parenthetical dressing (e.g. “A car in a Kinetic Theory problem…”). After stripping the chapter title from stems:

| Legacy CH | Chapter-faithful keyword hits |
|----------:|------------------------------:|
| 1 Units and Measurement | **0 / 500** (no dimensions / significant figures / errors content) |
| 6 Rotational Motion | **0 / 500** (no torque / MOI / COM content) |
| 7 Solids | **98 / 500** (only Young-modulus / stress–strain subset) |
| 8 Fluids | **13 / 500** (manometer subset only; no Bernoulli / viscosity) |
| 10 Kinetic Theory | **0 / 500** (no mean free path / DoF / RMS; “ideal gas” stems are thermo-style) |

**Conclusion:** Mapping by `legacy_chapter_id` → a single TALOS chapter is **unsafe** even if TALOS later creates matching chapter names. Content does not belong to those NCERT chapters.

### Per-chapter verdict (A–D)

| Legacy CH | A Exact TALOS chapter | B Close TALOS chapter | C Topic/concept only | D No safe equivalent |
|----------:|:---------------------:|:---------------------:|:--------------------:|:--------------------:|
| 1 | No | No | No (no units concepts) | **Yes** |
| 6 | No | No | No (no rotational concepts) | **Yes** |
| 7 | No | No | Partial stems → no solids chapter/concepts | **Yes** (chapter-level) |
| 8 | No | No | Partial stems → no fluids chapter/concepts | **Yes** (chapter-level) |
| 10 | No | No | Ideal-gas stems resemble thermo but chapter label ≠ Kinetic Theory | **Yes** (for Kinetic Theory identity) |

Candidate IDs for “close” names that were **rejected** as chapter equivalents:

| Rejected candidate | Chapter ID | Why rejected |
|--------------------|------------|--------------|
| Thermodynamics (`thermodynamics-physics`) for CH10 | `2f62c566-16e5-4996-a5e3-d003592dd35b` | NCERT Kinetic Theory ≠ Thermodynamics; only ~88/500 stems are ideal-gas; rest are kinematics/solids/work/friction |
| Kinematics for CH1 | `b20f8158-…` | Name mismatch; CH1 has 0 units content; kinematics is only one of eight recycled topics |
| Laws of Motion for CH6 | `433d0aa4-…` | Rotational chapter identity false; Atwood/friction subset only |
| Work, Energy and Power for any | `81f3a1f9-…` | Only `work` topic subset aligns |

**Topic/concept candidates:** none exist under kinematics / laws-of-motion / work-energy-power / thermodynamics-physics. Assigning any Electrostatics / Optics / Current Electricity concept would be factually wrong.

---

## 5. Representative question validation (≥10 per unresolved chapter)

Confidence below is for **legacy-chapter → single TALOS chapter** mapping. Content-based remapping is discussed in §6 / appendix.

### CH1 — Units and Measurement

| Legacy ID | Legacy topic | Subject matter (stem) | Candidate TALOS chapter | Topic / concept | Rationale | Confidence |
|-----------|--------------|----------------------|-------------------------|-----------------|-----------|------------|
| PHY11-CH01-0127 | PV work | Cyclic PV `|W_net|` | thermodynamics-physics (content) / none for Units | none | Stem is thermo, not units | LOW / chapter NO SAFE |
| PHY11-CH01-0012 | PV work | Cyclic PV work | same | none | same | LOW / chapter NO SAFE |
| PHY11-CH01-0163 | Young modulus | Y = stress/strain | none (solids missing) | none | Solids content under Units label | chapter NO SAFE |
| PHY11-CH01-0195 | Young modulus | Young’s modulus | none | none | same | chapter NO SAFE |
| PHY11-CH01-0060 | friction on inclined plane | Atwood tension | laws-of-motion (content) | none | Mechanics, not units | chapter NO SAFE |
| PHY11-CH01-0064 | friction on inclined plane | μs on incline | laws-of-motion (content) | none | same | chapter NO SAFE |
| PHY11-CH01-0408 | ideal gas | Isochoric P factor | thermodynamics-physics (content) | none | Thermo/KT-adjacent, not units | chapter NO SAFE |
| PHY11-CH01-0460 | ideal gas | Ideal gas heating | thermodynamics-physics (content) | none | same | chapter NO SAFE |
| PHY11-CH01-0165 | kinematic equations | Stopping distance | kinematics (content) | none | Kinematics under Units label | chapter NO SAFE |
| PHY11-CH01-0437 | kinematic equations | Stopping distance | kinematics (content) | none | same | chapter NO SAFE |

**Chapter decision:** NO SAFE MAPPING.

### CH6 — Systems of Particles and Rotational Motion

| Legacy ID | Legacy topic | Subject matter | Candidate | Topic/concept | Rationale | Confidence |
|-----------|--------------|----------------|-----------|---------------|-----------|------------|
| PHY11-CH06-2578 | PV work | Cyclic PV | thermo (content) | none | Not rotational | chapter NO SAFE |
| PHY11-CH06-2502 | PV work | Cyclic PV | thermo (content) | none | same | chapter NO SAFE |
| PHY11-CH06-2731 | Young modulus | Young’s modulus | none (solids) | none | Not rotational | chapter NO SAFE |
| PHY11-CH06-2867 | Young modulus | Young’s modulus | none | none | same | chapter NO SAFE |
| PHY11-CH06-2551 | friction… | Atwood | laws-of-motion (content) | none | No COM/torque | chapter NO SAFE |
| PHY11-CH06-2541 | friction… | Incline μs | laws-of-motion (content) | none | same | chapter NO SAFE |
| PHY11-CH06-2728 | ideal gas | Isochoric | thermo (content) | none | Not rotational | chapter NO SAFE |
| PHY11-CH06-2760 | ideal gas | Isochoric | thermo (content) | none | same | chapter NO SAFE |
| PHY11-CH06-2825 | kinematic equations | Stopping distance | kinematics (content) | none | Not rotational | chapter NO SAFE |
| PHY11-CH06-2705 | kinematic equations | Stopping distance | kinematics (content) | none | same | chapter NO SAFE |

**Chapter decision:** NO SAFE MAPPING. Zero rotational stems found after stripping title.

### CH7 — Mechanical Properties of Solids

| Legacy ID | Legacy topic | Subject matter | Candidate | Topic/concept | Rationale | Confidence |
|-----------|--------------|----------------|-----------|---------------|-----------|------------|
| PHY11-CH07-3062 | PV work | Cyclic PV | thermo (content) | none | Not solids | chapter NO SAFE |
| PHY11-CH07-3009 | PV work | Cyclic PV | thermo (content) | none | same | chapter NO SAFE |
| PHY11-CH07-3383 | Young modulus | Young’s modulus | **would need** Solids chapter | missing | Content fits Solids, but **no TALOS chapter/topic/concept** | chapter NO SAFE |
| PHY11-CH07-3423 | Young modulus | Young’s modulus | Solids (missing) | missing | same | chapter NO SAFE |
| PHY11-CH07-3031 | friction… | Atwood | laws-of-motion | none | Misfiled under Solids | chapter NO SAFE |
| PHY11-CH07-3095 | friction… | Atwood | laws-of-motion | none | same | chapter NO SAFE |
| PHY11-CH07-3192 | ideal gas | Isochoric | thermo | none | Misfiled | chapter NO SAFE |
| PHY11-CH07-3432 | ideal gas | Isochoric | thermo | none | same | chapter NO SAFE |
| PHY11-CH07-3301 | kinematic equations | Stopping distance | kinematics | none | Misfiled | chapter NO SAFE |
| PHY11-CH07-3473 | kinematic equations | Stopping distance | kinematics | none | same | chapter NO SAFE |

**Chapter decision:** NO SAFE MAPPING. Even the ~88 Young-modulus questions cannot attach: Solids chapter/topic/concept do not exist.

### CH8 — Mechanical Properties of Fluids

| Legacy ID | Legacy topic | Subject matter | Candidate | Topic/concept | Rationale | Confidence |
|-----------|--------------|----------------|-----------|---------------|-----------|------------|
| PHY11-CH08-3630 | PV work | Cyclic PV | thermo | none | Not fluids | chapter NO SAFE |
| PHY11-CH08-3547 | PV work | Cyclic PV | thermo | none | same | chapter NO SAFE |
| PHY11-CH08-3799 | Young modulus | Young’s modulus | Solids (missing) | missing | Solids content under Fluids label | chapter NO SAFE |
| PHY11-CH08-3691 | Young modulus | Young’s modulus | Solids (missing) | missing | same | chapter NO SAFE |
| PHY11-CH08-3648 | friction… | Atwood | laws-of-motion | none | Misfiled | chapter NO SAFE |
| PHY11-CH08-3542 | friction… | Atwood | laws-of-motion | none | same | chapter NO SAFE |
| PHY11-CH08-3700 | ideal gas | Isochoric | thermo | none | Misfiled | chapter NO SAFE |
| PHY11-CH08-3844 | ideal gas | Isochoric | thermo | none | same | chapter NO SAFE |
| PHY11-CH08-3793 | kinematic equations | Stopping distance | kinematics | none | Misfiled | chapter NO SAFE |
| PHY11-CH08-3885 | kinematic equations | Stopping distance | kinematics | none | same | chapter NO SAFE |

**Chapter decision:** NO SAFE MAPPING. Manometer subset (~13) would need a Fluids chapter that does not exist.

### CH10 — Kinetic Theory

| Legacy ID | Legacy topic | Subject matter | Candidate | Topic/concept | Rationale | Confidence |
|-----------|--------------|----------------|-----------|---------------|-----------|------------|
| PHY11-CH10-4649 | PV work | Cyclic PV | thermo | none | Not KT chapter identity | chapter NO SAFE |
| PHY11-CH10-4549 | PV work | Cyclic PV | thermo | none | same | chapter NO SAFE |
| PHY11-CH10-4999 | Young modulus | Young’s modulus | Solids missing | missing | Misfiled | chapter NO SAFE |
| PHY11-CH10-4979 | Young modulus | Young’s modulus | Solids missing | missing | same | chapter NO SAFE |
| PHY11-CH10-4519 | friction… | Atwood | laws-of-motion | none | Misfiled | chapter NO SAFE |
| PHY11-CH10-4544 | friction… | Incline μs | laws-of-motion | none | same | chapter NO SAFE |
| PHY11-CH10-4924 | ideal gas | Isochoric P factor | thermo (content) / KT chapter missing | none | Ideal gas ≠ full KT chapter; no KT concepts | chapter NO SAFE |
| PHY11-CH10-4776 | ideal gas | Isochoric | thermo (content) | none | same | chapter NO SAFE |
| PHY11-CH10-4733 | kinematic equations | Stopping distance | kinematics | none | Misfiled | chapter NO SAFE |
| PHY11-CH10-4889 | kinematic equations | Stopping distance | kinematics | none | same | chapter NO SAFE |

**Chapter decision:** NO SAFE MAPPING.

---

## 6. Structural problems flagged

| Flag | Evidence |
|------|----------|
| **Inconsistent legacy classification** | All 10 chapters share the same 8 topic templates; chapter title is cosmetic. |
| **One legacy chapter → multiple TALOS chapters** | Each unresolved chapter’s 500 stems span kinematics, laws-of-motion, work-energy, thermo, solids, fluids. |
| **One legacy chapter → multiple possible concepts** | Even after content remapping, concepts do not exist under candidate chapters. |
| **Missing TALOS chapter** | Units, Rotational Motion, Solids, Fluids, Kinetic Theory. |
| **Missing TALOS topic** | All five unresolved NCERT chapters have zero topics in TALOS. |
| **Missing TALOS concept** | No concepts under kinematics / laws-of-motion / work-energy-power / thermodynamics-physics. |
| **TALOS concept too broad / too narrow** | N/A — no candidate concepts exist for these stems. |
| **Questions spanning multiple concepts** | Mixed topic `manometer / stress-strain` mixes fluids and solids in one label. |
| **Prior LOW/MEDIUM chapter tags also unsafe for concept_id** | Chapters 2–5 and 9 have the **same** topic pollution; chapter-code tags must not be treated as concept assignment authority. |

---

## 7. Decision matrix

Primary decision = **legacy chapter identity → existing TALOS chapter**.  
Mapping Level = Chapter (no Topic/Concept available).

| Legacy Chapter | Questions | TALOS Candidate | Candidate ID | Mapping Level | Confidence | Decision |
| -------------- | --------: | --------------- | ------------ | --------------------- | --------------- | ---------------------------------- |
| 1 Units and Measurement | 500 | — (none exists) | — | Chapter | LOW | **NO SAFE MAPPING** |
| 6 Systems of Particles and Rotational Motion | 500 | — (none exists) | — | Chapter | LOW | **NO SAFE MAPPING** |
| 7 Mechanical Properties of Solids | 500 | — (none exists) | — | Chapter | LOW | **NO SAFE MAPPING** |
| 8 Mechanical Properties of Fluids | 500 | — (none exists) | — | Chapter | LOW | **NO SAFE MAPPING** |
| 10 Kinetic Theory | 500 | — (none exists) | — | Chapter | LOW | **NO SAFE MAPPING** |

No row qualifies for **MAP**. No row qualifies for **SME REVIEW** at *chapter-identity* level without first creating missing chapters **and** reclassifying stems by content (that is a separate remediation program).

### Appendix — content-based remapping buckets (informative only; not authorized)

If SME later remaps **by stem topic**, ignoring legacy chapter labels, among the 2500 unresolved questions:

| Bucket | Questions | Notes |
|--------|----------:|-------|
| SME → `kinematics` (chapter stub only) | 657 | No topic/concept yet |
| SME → `laws-of-motion` (chapter stub only) | 219 | No topic/concept yet |
| SME → `work-energy-power` (chapter stub only) | 435 | No topic/concept yet |
| SME → `thermodynamics-physics` (chapter stub only) | 610 | No topic/concept yet |
| NO SAFE (needs Solids chapter) | 498 | Young modulus + stress–strain stems |
| NO SAFE (needs Fluids chapter) | 81 | Manometer stems |

This appendix is **not** a `concept_id` recommendation. Chapter stubs still lack topics/concepts; inventing concepts is out of scope for this audit.

---

## 8. Final summary

```text
Unresolved chapters (exact)     = 5
  (Import audit “6” was incorrect)

HIGH confidence chapter mapping = 0 questions
MEDIUM / SME chapter mapping    = 0 questions
NO SAFE MAPPING                 = 2500 questions

Total affected                  = 2500
```

**Recommendation:** Keep `concept_id = NULL` for all 2500 unresolved (and, operationally, for the full 5000 until content-based reclassification + taxonomy expansion + ECAEP). Creating chapters named after the legacy labels would **not** make assigning those IDs safe, because stems do not match those NCERT chapters.

---

## 9. Database safety proof

| Check | Result |
|-------|--------|
| Database writes | **0** (SELECT-only via async SQLAlchemy; no UPDATE/INSERT/DELETE) |
| Question modifications | **0** |
| `concept_id` assignments | **0** (batch still `null_concept = 5000`) |
| Publication changes | **0** (batch published = 0, draft = 5000) |
| Source modifications | **0** (legacy JSON/CSV/ZIP/SQLite untouched) |
| Taxonomy creates | **0** |
| This audit artifact | Markdown report only under `docs/audits/` |

---

## Verdict

**RED for chapter-level resolution of the unresolved set** — not because import failed, but because:

1. Five (not six) chapters lack any TALOS equivalent.  
2. Legacy chapter labels are not reliable content classifiers.  
3. No safe Topic/Concept nodes exist for these stems under TALOS Physics today.

**Action deferred:** taxonomy expansion + content-based reclassification under ECAEP — separate approved change, not performed here.
