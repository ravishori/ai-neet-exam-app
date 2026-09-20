# ADR-0031: NEET StudyMaterial Academic Mapping and Source Provenance

## Status
Accepted

## Context
Phase A (ADR-0030) registered 68 NEET source PDFs and added
`IngestionJob.source_document_id`, but ingestion jobs still required manual
`chapter_code` and did not auto-link registry rows. The academic model uses
`PHYSICS`, `CHEMISTRY`, `BOTANY`, and `ZOOLOGY` while the filesystem uses a
single `Biology/` tree. Most NCERT chapter PDFs have no seeded topic/concept
tree yet — the system must not invent chapters or guess Biology splits.

## Decision

### Mapping table
Introduce `ingestion.source_academic_mappings` — one row per
`SourceDocument`, linking to `academic.chapters` when an **explicit,
human-approved registry entry** exists. Otherwise status is `UNMAPPED`.

### Explicit registry
`study_material_academic_registry.py` holds approved
`(source_subject, class_level, ncert_chapter_number) → (academic_subject, chapter_code)`
entries. No filename-only inference beyond extracting the NCERT chapter number.

### Biology
Biology filesystem sources map to **BOTANY or ZOOLOGY** only via explicit
registry entries. Phase B.1 corrected the Botany pilot mapping after corpus
verification: Class 11 file `chapter-11.pdf` contains
`PHOTOSYNTHESIS IN HIGHER PLANTS` and maps to `photosynthesis`.
`chapter-13.pdf` in this corpus is Plant Growth and remains **UNMAPPED**
(must not map to photosynthesis). Class 11 Ch 18 → `body-fluids-circulation`
(Zoology) is unchanged.

### Class metadata
`SourceDocument.class_level` (`11` | `12`) remains source metadata. No new
academic Class entity.

### Provenance wiring
`IngestionPipelineService.start_job` supports:
- **`source_document_id`**: registry path + checksum validation + mapping-derived
  `chapter_code`
- **`file_path` + `chapter_code`** (legacy): auto-links `source_document_id` when
  SHA-256 matches a registered source

Modified on-disk files are rejected with `SOURCE_CHECKSUM_MISMATCH`.
Unmapped sources are rejected with `UNMAPPED_SOURCE` when starting via
`source_document_id`.

### Pilot readiness
`pilot_ready` is true only when:
- an explicit registry mapping exists
- the academic chapter has a seeded topic/concept tree
- the on-disk PDF body matches chapter content markers
  (`chapter_content_preflight.py`)

Documented pilot sources:
- Physics: `current-electricity` (Class 12 Ch 3)
- Chemistry: `chemical-bonding` (Class 11 Ch 4)
- Biology: `photosynthesis` (Class 11 corpus `chapter-11.pdf`, Botany)

## Consequences
- 64/68 corpus PDFs remain `UNMAPPED` until explicit registry entries are added
- Phase D (30-MCQ pilot) can start from pilot-ready mapped sources only
- Path-based ingestion remains backward compatible with improved provenance
- Feature status: **IMPLEMENTED — NOT DoD COMPLETE**
