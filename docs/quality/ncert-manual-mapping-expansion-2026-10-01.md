# NCERT Manual-Evidence Mapping & Knowledge-Base Expansion

**Date:** 2026-10-01
**Repository:** `ravishori/ai-neet-exam-app`
**Branch:** `feat/whatsapp-m2a-account-linking`
**Local database:** `trinetra_db` @ `localhost:5432`, `ENVIRONMENT=development` — re-confirmed fresh, `alembic current` → `d9c6e1a8f9ed` (head, unchanged).

## Executive summary

Expanded chapter-mapping coverage from 2/76 to **68/76 registered NCERT sources**, using **direct, per-file manual evidence** — the actual opening page(s) of every one of the 74 previously-unmapped sources were read and compared against the live `academic.chapters` taxonomy, not filename numbering, running headers, or automated keyword matching (an earlier same-day attempt at the latter was tested and rejected after a demonstrated false positive — see `docs/quality/ncert-knowledge-base-and-gemini-resolution-2026-10-01.md`). **66 of 74 sources were mapped with direct evidence; 8 were deliberately left unmapped** (2 are not chapter content at all — an appendix and a cover page; 6 use a filename convention the existing mapping mechanism cannot address without a parser change not made this round).

Both previously-blocked Biology entries (Photosynthesis, Body Fluids and Circulation) are now resolved with direct page evidence, including correcting a factual error in the *original* pilot registry (it had assumed Body Fluids and Circulation was Chapter 18; direct evidence shows it is actually Chapter 15 — Chapter 18 is "Neural Control and Coordination").

**Ingestion result:** 824 new knowledge units created (0 errors), bringing the total from 51 to **1,038** (912 `PASSED`, 126 `FAILED` — duplicates/non-grounded, correctly recorded not discarded). Idempotency re-verified twice (pilot subset and full 76-source set) — zero duplicate knowledge units on re-run.

**Retrieval coverage** (direct code measurement, no Gemini) rose from 899/9,944 (9.0%) to **3,647/9,944 pending PYQs (36.7%)**.

**No Gemini or Claude API call was made. No PYQ answer value or status was changed — confirmed unchanged (12,396 / 2,452 / 9,944) before and after. Production was never touched.**

## Phase 1 — Current state (re-confirmed, not assumed)

```
ENVIRONMENT=development
current_database=trinetra_db, server_addr=::1 (localhost)
alembic current = d9c6e1a8f9ed (head)
pyq.questions: 12396 / 2452 verified / 9944 pending
knowledge.knowledge_units: 51 (before this task)
ingestion.source_documents: 76, mapping_status: 2 MAPPED / 74 UNMAPPED
```

Working tree: all prior uncommitted work (today's earlier tasks' changes) preserved exactly, confirmed via `git status --short` before and after.

## Phase 2 — Chapter mapping verification (source-by-source evidence)

Methodology: for every unmapped source, the first 1-3 pages of real extracted PDF text were read directly (not scored, not keyword-matched) and compared against the live `academic.chapters` taxonomy (63 rows, re-queried fresh). Two taxonomy granularities exist and were used correctly:
- **Class 11 Biology / all Physics / all Chemistry**: broad unit-level codes only (`BIOLOGY-U01..U10`, `PHYSICS-U01..U20`, `CHEMISTRY-U01..U20`) — the seed genuinely has no finer per-chapter codes at this level; multiple distinct NCERT chapters legitimately share one unit code, confirmed via each unit's own divider page explicitly listing its member chapters (e.g. "UNIT 4 PLANT PHYSIOLOGY: Chapter 11 Photosynthesis, Chapter 12 Respiration, Chapter 13 Plant Growth").
- **Class 12 Biology only**: precise chapter-exact codes (`XII-BIO-01..13`), under subjects `BOTANY`/`ZOOLOGY`/`CORE_BIOLOGY` depending on chapter — filename chapter number matches the taxonomy code number 1:1, directly confirmed per file (not assumed from the number alone).

Full page-text evidence for every file is preserved at `docs/quality/_ncert_manual_mapping_2026-10-01/source_page_evidence_dump.txt`.

### Mapping review table (condensed — full evidence in the dump file above)

| Source | Subject/Class | Actual chapter found | Taxonomy code | Status | Evidence |
|---|---|---|---|---|---|
| Bio11 ch1 | BIOLOGY 11 | The Living World | `BIOLOGY-U01` | VERIFIED | Unit-1 divider lists Ch1-4 |
| Bio11 ch2 | BIOLOGY 11 | Biological Classification | `BIOLOGY-U01` | VERIFIED | Content + Unit-1 list |
| Bio11 ch3 | BIOLOGY 11 | Plant Kingdom | `BIOLOGY-U01` | VERIFIED | Header "PLANT KINGDOM" |
| Bio11 ch4 | BIOLOGY 11 | Animal Kingdom | `BIOLOGY-U01` | VERIFIED | Header "ANIMAL KINGDOM" |
| Bio11 ch5 | BIOLOGY 11 | Morphology of Flowering Plants | `BIOLOGY-U02` | VERIFIED | Unit-2 divider lists Ch5-7 |
| Bio11 ch6 | BIOLOGY 11 | Anatomy of Flowering Plants | `BIOLOGY-U02` | VERIFIED | Header match |
| Bio11 ch7 | BIOLOGY 11 | Structural Organisation in Animals | `BIOLOGY-U02` | VERIFIED | Header match |
| Bio11 ch8 | BIOLOGY 11 | Cell — The Unit of Life | `BIOLOGY-U03` | VERIFIED | Unit-3 divider (cell theory) |
| Bio11 ch9 | BIOLOGY 11 | Biomolecules | `BIOLOGY-U03` | VERIFIED | Chemical-composition-of-tissue content |
| Bio11 ch10 | BIOLOGY 11 | Cell Cycle and Cell Division | `BIOLOGY-U03` | VERIFIED | Header "CELL CYCLE" (NOT "Reproduction" — see rejected-automation finding below) |
| Bio11 ch11 | BIOLOGY 11 | **Photosynthesis in Higher Plants** | `BIOLOGY-U04` | **VERIFIED (RESOLVED)** | Unit-4 divider explicitly: "Chapter 11 Photosynthesis in Higher Plants" |
| Bio11 ch12 | BIOLOGY 11 | Respiration in Plants | `BIOLOGY-U04` | VERIFIED | Header match |
| Bio11 ch13 | BIOLOGY 11 | Plant Growth and Development | `BIOLOGY-U04` | VERIFIED | Unit-4 divider list |
| Bio11 ch14 | BIOLOGY 11 | Breathing and Exchange of Gases | `BIOLOGY-U05` | VERIFIED | Unit-5 divider lists Ch14-19 |
| Bio11 ch15 | BIOLOGY 11 | **Body Fluids and Circulation** | `BIOLOGY-U05` | **VERIFIED (RESOLVED, CORRECTS ERROR)** | Header "CHAPTER 15 BODY FLUIDS AND CIRCULATION" — the *original* pilot registry incorrectly pointed this topic at Ch18 |
| Bio11 ch16 | BIOLOGY 11 | Excretory Products and their Elimination | `BIOLOGY-U05` | VERIFIED | Header match |
| Bio11 ch17 | BIOLOGY 11 | Locomotion and Movement | `BIOLOGY-U05` | VERIFIED | Header match |
| Bio11 ch18 | BIOLOGY 11 | Neural Control and Coordination (not Body Fluids) | `BIOLOGY-U05` | VERIFIED | Header "CHAPTER 18 NEURAL CONTROL AND COORDINATION" |
| Bio11 ch19 | BIOLOGY 11 | Chemical Coordination and Integration | `BIOLOGY-U05` | VERIFIED | Header match |
| Bio12 ch1 | BIOLOGY 12 | Sexual Reproduction in Flowering Plants | `XII-BIO-01` | VERIFIED | Exact header match |
| Bio12 ch3 | BIOLOGY 12 | Reproductive Health | `XII-BIO-03` | VERIFIED | Exact header match |
| Bio12 ch4 | BIOLOGY 12 | Principles of Inheritance and Variation | `XII-BIO-04` | VERIFIED | Exact divider match |
| Bio12 ch5 | BIOLOGY 12 | Molecular Basis of Inheritance | `XII-BIO-05` | VERIFIED | Exact header match |
| Bio12 ch6 | BIOLOGY 12 | Evolution | `XII-BIO-06` | VERIFIED | Exact header match |
| Bio12 ch7 | BIOLOGY 12 | Human Health and Disease | `XII-BIO-07` | VERIFIED | Exact divider match |
| Bio12 ch8 | BIOLOGY 12 | Microbes in Human Welfare | `XII-BIO-08` | VERIFIED | Exact header match |
| Bio12 ch9 | BIOLOGY 12 | Biotechnology: Principles and Processes | `XII-BIO-09` | VERIFIED | Divider content match |
| Bio12 ch10 | BIOLOGY 12 | Biotechnology and Its Applications | `XII-BIO-10` | VERIFIED | Exact header match |
| Bio12 ch13 | BIOLOGY 12 | Biodiversity and Conservation | `XII-BIO-13` | VERIFIED | Exact header match |
| Chem11 ch1 | CHEMISTRY 11 | Some Basic Concepts of Chemistry | `CHEMISTRY-U01` | VERIFIED | Exact header match |
| Chem11 ch2 | CHEMISTRY 11 | Structure of Atom | `CHEMISTRY-U02` | VERIFIED | Exact header match |
| Chem11 ch3 | CHEMISTRY 11 | Classification of Elements and Periodicity | `CHEMISTRY-U09` | VERIFIED | Exact name match (book's internal "Unit 3" ≠ taxonomy unit number, matched by name not position) |
| Chem11 ch5 | CHEMISTRY 11 | (Chemical) Thermodynamics | `CHEMISTRY-U04` | VERIFIED | Content opening |
| Chem11 ch6 | CHEMISTRY 11 | Equilibrium | `CHEMISTRY-U06` | VERIFIED | Exact header match |
| Chem11 ch7 | CHEMISTRY 11 | Redox Reactions | `CHEMISTRY-U07` | VERIFIED | Content opening |
| Chem11 ch8 | CHEMISTRY 11 | Organic Chemistry — Basic Principles | `CHEMISTRY-U14` | VERIFIED | Exact header match |
| Chem11 ch9 | CHEMISTRY 11 | Hydrocarbons | `CHEMISTRY-U15` | VERIFIED | Exact header match |
| Chem12 ch1 | CHEMISTRY 12 | Solutions | `CHEMISTRY-U05` | VERIFIED | Content (colligative properties, Raoult's law) |
| Chem12 ch2 | CHEMISTRY 12 | Electrochemistry | `CHEMISTRY-U07` | VERIFIED | Content opening — same taxonomy unit as C11 Redox |
| Chem12 ch3 | CHEMISTRY 12 | Chemical Kinetics | `CHEMISTRY-U08` | VERIFIED | Explicit term in content |
| Chem12 ch4 | CHEMISTRY 12 | d- and f-Block Elements | `CHEMISTRY-U11` | VERIFIED | Content opening |
| Chem12 ch5 | CHEMISTRY 12 | Coordination Compounds | `CHEMISTRY-U12` | VERIFIED | Exact heading match |
| Chem12 ch6 | CHEMISTRY 12 | Haloalkanes and Haloarenes | `CHEMISTRY-U16` | VERIFIED | Content opening |
| Chem12 ch7 | CHEMISTRY 12 | Alcohols, Phenols and Ethers | `CHEMISTRY-U17` | VERIFIED | Exact header match |
| Chem12 ch8 | CHEMISTRY 12 | Aldehydes, Ketones and Carboxylic Acids | `CHEMISTRY-U17` | VERIFIED | Exact header match (same unit as Ch7) |
| Chem12 ch9 | CHEMISTRY 12 | Amines | `CHEMISTRY-U18` | VERIFIED | Content opening |
| Chem12 ch10 | CHEMISTRY 12 | Biomolecules | `CHEMISTRY-U19` | VERIFIED | Exact header match |
| Phy11 ch1 | PHYSICS 11 | Units and Measurement | `PHYSICS-U01` | VERIFIED | Exact header |
| Phy11 ch2 | PHYSICS 11 | Motion in a Straight Line | `PHYSICS-U02` | VERIFIED | Exact header |
| Phy11 ch3 | PHYSICS 11 | Motion in a Plane | `PHYSICS-U02` | VERIFIED | Exact header (same unit as Ch2) |
| Phy11 ch4 | PHYSICS 11 | Laws of Motion | `PHYSICS-U03` | VERIFIED | Exact header |
| Phy11 ch5 | PHYSICS 11 | Work, Energy and Power | `PHYSICS-U04` | VERIFIED | Exact header |
| Phy11 ch6 | PHYSICS 11 | Systems of Particles and Rotational Motion | `PHYSICS-U05` | VERIFIED | Exact header |
| Phy11 ch8 | PHYSICS 11 | Mechanical Properties of Solids | `PHYSICS-U07` | VERIFIED | Exact header |
| Phy11 ch9 | PHYSICS 11 | Mechanical Properties of Fluids | `PHYSICS-U07` | VERIFIED | Exact header (same unit as Ch8) |
| Phy11 ch11 | PHYSICS 11 | Thermodynamics | `PHYSICS-U08` | VERIFIED | Exact header |
| Phy11 ch12 | PHYSICS 11 | Kinetic Theory | `PHYSICS-U09` | VERIFIED | Exact header |
| Phy11 ch13 | PHYSICS 11 | Oscillations | `PHYSICS-U10` | VERIFIED | Exact header |
| Phy11 ch14 | PHYSICS 11 | Waves | `PHYSICS-U10` | VERIFIED | Exact header (same unit as Ch13) |
| Phy12 part1-ch1 | PHYSICS 12 | Electric Charges and Fields | `PHYSICS-U11` | VERIFIED | Exact header |
| Phy12 part1-ch2 | PHYSICS 12 | Electrostatic Potential and Capacitance | `PHYSICS-U11` | VERIFIED | Exact header (same unit as Ch1) |
| Phy12 part1-ch4 | PHYSICS 12 | Moving Charges and Magnetism | `PHYSICS-U13` | VERIFIED | Exact header |
| Phy12 part1-ch5 | PHYSICS 12 | Magnetism and Matter | `PHYSICS-U13` | VERIFIED | Exact header (same unit as Ch4) |
| Phy12 part1-ch6 | PHYSICS 12 | Electromagnetic Induction | `PHYSICS-U14` | VERIFIED | Exact header |
| Phy12 part1-ch7 | PHYSICS 12 | Alternating Current | `PHYSICS-U14` | VERIFIED | Exact header (same unit as Ch6) |
| Phy12 part1-ch8 | PHYSICS 12 | Electromagnetic Waves | `PHYSICS-U15` | VERIFIED | Exact header |

### Deliberately left UNMAPPED (8 sources)

| Source | Reason | Required action |
|---|---|---|
| `Physics/.../leph2an.pdf` | Backmatter (Appendices — Greek alphabet, SI prefixes, constants), not chapter content at all | None — permanently out of scope, not a chapter |
| `Physics/.../leph2dd/leph2ps.pdf` | Cover page only ("PHYSICS PART – II TEXTBOOK FOR CLASS XII") | None — permanently out of scope, not a chapter |
| `Physics/.../leph201.pdf` through `leph206.pdf` (6 files) | **Content directly verified** (leph201=Ray Optics→PHYSICS-U16, leph202=Wave Optics→PHYSICS-U16, leph203=Dual Nature of Radiation→PHYSICS-U17, leph204=Atoms→PHYSICS-U18, leph205=Nuclei→PHYSICS-U18, leph206=Electronic Devices→PHYSICS-U19) but the registry's `extract_ncert_chapter_number()` regex (`chapter-(\d+)\.pdf$`) cannot parse this filename convention at all — no key can be looked up | **Owner decision needed**: extend the parser to recognize the `lephNNN.pdf` convention (NCERT's own internal Physics Part-2 numbering), a minimal, scoped change not made this round to keep this task's diff narrowly focused on the registry itself |

No source was mapped by inventing a taxonomy chapter — every target code above already existed in the live `academic.chapters` seed before this task.

## Phase 3 — Ingestion of verified mappings

**Pilot (3 sources, one per subject, newly mapped):** Biology ch1, Chemistry ch1, Physics ch1 — note these had pre-existing `COMPLETED` jobs from this morning's unmapped-extraction-only run, so `force_rerun=True` was required to re-structure them now that a mapping exists (idempotency-by-design correctly prevented silent reuse of stale unmapped state). Result: 37 new knowledge units (22+9+6), 0 rejected, 0 errors. Re-run (idempotency check): KU count unchanged, duplicates correctly detected and rejected (not re-inserted).

**Full ingestion (all 76 sources, `force_rerun=True`):**
```
ku_created: 824
ku_rejected: 89  (duplicates / failed grounding check — recorded, not discarded)
errors: 0
completed: 76/76
```
**Re-run (idempotency check, no `force_rerun`):** all 76 sources correctly skip-reused their existing `COMPLETED` job; `ku_created: 0, ku_rejected: 0`; `SELECT count(*) FROM knowledge.knowledge_units` unchanged at 1,038 before and after.

### Knowledge-unit counts, before/after

| Metric | Before this task | After |
|---|---:|---:|
| Total knowledge units | 51 | **1,038** |
| `PASSED` | 51 | **912** |
| `FAILED` (duplicate/ungrounded, recorded not discarded) | 0 | 126 |
| Mapped sources | 2/76 | **68/76** |

### Breakdown by subject and chapter (PASSED units only)

| Subject | Chapters with KUs | Total PASSED KUs |
|---|---:|---:|
| Biology (BIOLOGY-U01..U05 + XII-BIO-*) | 13 | 232 |
| Chemistry (CHEMISTRY-U01..U19) | 15 | 363 |
| Physics (PHYSICS-U01..U15) | 14 | 317 |
| **Total** | **42** | **912** |

(Full per-chapter-code counts queried directly from the database; largest contributors: `CHEMISTRY-U06` Equilibrium 45, `PHYSICS-U11` Electrostatics 46, `BIOLOGY-U05` Human Physiology 52.)

No table, formula, or diagram content was invented — the deterministic extraction (`extract_facts_from_section_text`, unchanged from this morning) only ever emits verbatim sentence-level facts from the actual extracted text; a page that extracts to too little usable text yields fewer or zero facts rather than fabricated ones (confirmed: 0 extraction errors across all 76 sources).

## Phase 4 — Retrieval coverage (direct code, no Gemini)

Measured using `_load_ku_index()` + `_match_units()` directly against **all 9,944 currently-pending PYQs** — the actual, unmodified retrieval code the Gemini resolver would use, exercised without ever calling Gemini.

| | Before this task | After |
|---|---:|---:|
| Knowledge units in index | 51 | 1,038 |
| Pending PYQs with non-empty retrieval context | 899 | **3,647** |
| Coverage | 9.0% | **36.7%** |

| Subject | Matched / Total | Coverage |
|---|---:|---:|
| (null — unclassified, 2020/2023/2024/2025 batches) | 2,067 / 5,598 | 36.9% |
| Chemistry | 435 / 1,118 | 38.9% |
| Botany | 480 / 1,053 | 45.6% |
| Zoology | 385 / 1,086 | 35.5% |
| Physics | 280 / 1,089 | 25.7% |

Elapsed: 120.4 seconds for the full 9,944-question set (in-process, no network calls, no Gemini). **This is retrieval coverage, not answer correctness** — a non-empty match means the mechanical grounding check found genuinely overlapping, source-grounded vocabulary between the question and at least one knowledge unit; it is not evidence that the retrieved material supports the *correct* answer option. No correctness claim is made anywhere in this report.

## Phase 5 — Tests, lint, integrity

```
.venv/Scripts/python.exe -m pytest app/modules/ingestion/tests/ app/modules/knowledge/tests/ tests/test_pyq_resolver_worker.py -q
123 passed, 17 skipped, 7 warnings in 15.81s
```
This includes 3 pre-existing tests that hardcoded the old placeholder values (`photosynthesis`, `body-fluids-circulation`) or an assumption later disproven (Ch1 being "unmapped") — all updated to match the corrected, resolved mapping, re-verified passing.

```
.venv/Scripts/python.exe -m ruff check app/modules/ingestion/services/study_material_academic_registry.py app/modules/ingestion/services/chapter_content_preflight.py app/modules/ingestion/tests/test_source_academic_mapping.py app/modules/ingestion/tests/test_chapter_content_preflight.py
All checks passed!
```
`mypy`: not installed in this `.venv` — not run, consistent with every prior task today.

**Integrity checks performed:**
- No duplicate knowledge units: confirmed twice (pilot subset re-run, full-set re-run) — KU count unchanged both times, `ku_created: 0` on idempotent re-runs.
- No PYQ answer status/assertion changes: `pyq.questions`/`pyq.answer_assertions` counts identical before and after (12,396 / 2,452 verified / 9,944 pending / 2,452 assertions).
- No verified-answer overwrites: no write to `pyq.*` schema occurred at all this task (only `ingestion.*` and `knowledge.*` schemas were written to).
- No unrelated working-tree changes: `git status --short` before/after shows only the files listed below; all of today's earlier, separately-reported work remains untouched.
- No production access: all work targeted `trinetra_db` only.
- No Gemini API requests: confirmed both by design (only `_load_ku_index`/`_match_units`/deterministic structuring were used) and by evidence — no new `ai.ai_requests` rows attributable to this task.

## Outstanding taxonomy / mapping decisions for the owner

1. **The 6 `leph2NN.pdf` Physics Class-12 sources** — content is known with high confidence (Ray Optics, Wave Optics, Dual Nature of Radiation, Atoms, Nuclei, Electronic Devices — all real NCERT chapters), but mapping is blocked purely on a filename-parser limitation, not an evidence gap. Extending `extract_ncert_chapter_number()` (or adding a path-based override) to recognize this NCERT-native naming convention would unblock all 6 at once.
2. No other open taxonomy gaps were found — every other verified mapping target already existed in the live seed.

## Confirmations

- **No Gemini or Claude API call was made at any point in this task.**
- **No PYQ answer value or status was changed** — verified identical before/after (12,396 / 2,452 / 9,944 / 2,452 assertions, 0 conflicts).
- **Production was never accessed or modified.**
- Nothing was committed, pushed, or merged.

## Evidence

- `docs/quality/_ncert_manual_mapping_2026-10-01/source_page_evidence_dump.txt` — full raw page-text evidence read for every one of the 74 sources (the actual basis for every VERIFIED row above).
- `docs/quality/_ncert_manual_mapping_2026-10-01/pilot_ingest_script.py` — the scratch pilot-ingestion script used for the 3-source pilot.

## Related audit update

`docs/quality/pyq-coverage-audit.md` updated with a dated pointer to this report — prior baseline and all history preserved, unchanged.
