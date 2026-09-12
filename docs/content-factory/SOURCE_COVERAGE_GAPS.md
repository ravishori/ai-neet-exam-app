# Source Coverage Gaps

**Generated:** 2026-09-01T10:25:25.138637+00:00  
**Mode:** READ-ONLY gap analysis

## Gap summary

| Gap type | Count | Severity |
|----------|------:|----------|
| Academic chapters with zero source material | 18 | HIGH |
| Chapters with partial coverage (mapped or KU, not both) | 9 | MEDIUM |
| Fully generation-ready chapters | 3 | — |
| Unmapped source documents | 64 | HIGH |
| Source docs without ingestion | 64 | HIGH |
| Concepts without PASSED KU | 31 | HIGH |
| Mathematics contamination in NEET registry | 0 | OK |

## 1. Missing source documents

Full NCERT Class 11/12 sets are **not complete** on disk. Examples of absent or incomplete sets:

- Physics Class 11: chapters 7, 10, 15+ missing from filesystem
- Biology Class 12: chapters 2, 11, 12, 14+ missing
- No JEE-only supplements detected; corpus is NCERT PDF naming

Compare filesystem (68 NEET PDFs) to a full NEET syllabus (~90+ chapter PDFs expected).

## 2. Source documents not ingested

**64** of 68 registered documents have zero ingestion jobs.
All registered rows remain `ingestion_status = DISCOVERED` (Phase A only).

## 3. Chapters without sections

All non-ingested sources have zero sections. Ingested but zero sections: none among mapped pilots except failed legacy paths.

## 4. Sections without Knowledge Units

- `Biology/.../chapter-13.pdf` — ingested (Phase D mis-map attempt), 4 sections, **0 KU**
- `Uploads/` electrostatics PDF — 14 sections, 0 KU (excluded from NEET registry)

## 5. Knowledge Units without academic mapping

All PASSED KUs are linked to `academic.concepts` (FK required). Gap is inverse: **concepts without KU**.

## 6. Academic chapters without source material

- **BOTANY** / `the-living-world` — The Living World
- **BOTANY** / `plant-kingdom` — Plant Kingdom
- **BOTANY** / `morphology-flowering-plants` — Morphology of Flowering Plants
- **BOTANY** / `cell-unit-of-life` — Cell - The Unit of Life
- **BOTANY** / `plant-growth-development` — Plant Growth and Development
- **BOTANY** / `sexual-reproduction-flowering-plants` — Sexual Reproduction in Flowering Plants
- **CHEMISTRY** / `basic-concepts-chemistry` — Some Basic Concepts of Chemistry
- **CHEMISTRY** / `structure-of-atom` — Structure of Atom
- **CHEMISTRY** / `thermodynamics-chemistry` — Thermodynamics
- **CHEMISTRY** / `equilibrium` — Equilibrium
- **CHEMISTRY** / `redox-reactions` — Redox Reactions
- **CHEMISTRY** / `organic-chemistry-basics` — Organic Chemistry - Basic Principles
- **CHEMISTRY** / `electrochemistry` — Electrochemistry
- **PHYSICS** / `kinematics` — Kinematics
- **PHYSICS** / `laws-of-motion` — Laws of Motion
- **PHYSICS** / `work-energy-power` — Work, Energy and Power
- **PHYSICS** / `gravitation` — Gravitation
- **PHYSICS** / `thermodynamics-physics` — Thermodynamics
- **PHYSICS** / `electrostatics` — Electrostatics
- **PHYSICS** / `optics` — Optics
- **ZOOLOGY** / `animal-kingdom` — Animal Kingdom
- **ZOOLOGY** / `structural-organisation-animals` — Structural Organisation in Animals
- **ZOOLOGY** / `biomolecules` — Biomolecules
- **ZOOLOGY** / `digestion-absorption` — Digestion and Absorption
- **ZOOLOGY** / `breathing-exchange-of-gases` — Breathing and Exchange of Gases
- **ZOOLOGY** / `human-reproduction` — Human Reproduction

## 7. Source material without academic mapping

**64** documents are `UNMAPPED` (explicit registry only; never guessed).

Biology filesystem PDFs remain `BIOLOGY` at source layer until explicit Botany/Zoology mapping is approved.

## 8. Mathematics contamination

- Filesystem Maths PDFs: **0** (directory absent; stale inventory lists 6)
- DB `source_documents` with Maths: **0**
- NEET generation universe contamination: **NONE DETECTED**

## 9. Pilot vs production readiness

| Chapter | Source | Ingested | KU passed | Factory-ready |
|---------|--------|----------|-----------|---------------|
| `current-electricity` | YES | YES | 25 | YES |
| `chemical-bonding` | YES | YES | 29 | YES |
| `photosynthesis` | YES | YES | 4 | YES |
| `body-fluids-circulation` | YES | NO | 0 | NO |

## 10. Recommended remediation order

1. Expand explicit NCERT → academic registry (ADR-0031) for high-weight chapters
2. Run ingestion + KU structuring on newly mapped sources
3. Extend academic seed topics/concepts for empty chapter shells
4. Complete missing NCERT PDF acquisition where gaps block mapping
5. Do **not** bulk-generate on unmapped sources or saturated concepts
