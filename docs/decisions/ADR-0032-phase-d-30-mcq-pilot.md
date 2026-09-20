# ADR-0032: Phase D mandatory 30-MCQ pilot

## Status
Accepted

## Context
Phase A registered 68 NEET source PDFs. Phase B mapped 4 pilot-ready sources
with explicit academic chapter links and SourceDocument → IngestionJob
provenance. Before any scaled ~600 MCQ generation, a controlled 30-question
pilot must prove the full source-to-student pipeline on three approved chapters.

## Decision

### Scope
Exactly **30 MCQs** from three mapped pilot sources only:

| Subject | Source | Chapter |
|---------|--------|---------|
| Physics | Class 12 Ch 3 PDF | `current-electricity` |
| Chemistry | Class 11 Ch 4 PDF | `chemical-bonding` |
| Biology | Class 11 corpus `chapter-11.pdf` | `photosynthesis` (BOTANY) |

> Phase B.1: Biology pilot source corrected from corpus `chapter-13.pdf`
> (Plant Growth) to `chapter-11.pdf` (`PHOTOSYNTHESIS IN HIGHER PLANTS`).
> Filename NCERT numbers in this corpus do not always match academic titles.

No unmapped sources. No Maths. No auto-publish. No bypass of ECAEP.

### Orchestration
`PilotMcqOrchestrationService` runs the **existing** ingestion pipeline with:

- `target_mcq_count = 10` per subject job
- `pilot_run_id = phase-d-30-mcq-v1` for idempotency
- Checksum validation before each job
- Academic mapping validation (`pilot_ready` required)

### Generation quota
When `target_mcq_count` is set on `IngestionJob`, `_run_generation` distributes
MCQ generation across PASSED Knowledge Units until the target is reached (or
no further progress). Prompt version bumped to `v2` with parameterized count.

Pilot jobs skip flashcards in the MCQ generation phase (MCQ-only quota path).

### CMS / ECAEP
All generated questions enter **DRAFT** via `ContentWorkflowService.create_item`.
Human review and publish use existing CMS endpoints — no pilot bypass.

### CLI / API
- `python scripts/study_material_discover.py pilot-mcq [--dry-run] [--force]`
- `POST /api/v1/ingestion/pilot/mcq-run`

## Consequences
- Scaled generation remains blocked until pilot evidence is reviewed
- Re-running without `--force` is idempotent for the same `pilot_run_id`
- Feature status after Phase D execution: **PILOT VALIDATED** (if evidence passes)
  — overall StudyMaterial feature remains **NOT DoD COMPLETE**
