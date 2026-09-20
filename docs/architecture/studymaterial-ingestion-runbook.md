# StudyMaterial ingestion runbook (ADR-0030 Phase A)

## Purpose

Register the NEET StudyMaterial corpus (Physics, Chemistry, Biology only)
into `ingestion.source_documents` via recursive discovery. This does **not**
generate MCQs and does **not** replace the existing ingestion pipeline.

## Configured root

Discovery always uses:

```text
Settings.study_material_dir   # env: STUDY_MATERIAL_DIR
```

Local default: `<repo>/StudyMaterial`  
Docker default: `/data/studymaterial`

Clients **cannot** supply an arbitrary filesystem root to scan.

## NEET scope

In scope (subject roots only):

- `Physics/`
- `Chemistry/`
- `Biology/`

Out of scope (ignored at discovery time — not deleted or modified):

- `Maths/` — outside the NEET-UG corpus for this product
- `Uploads/` — operator upload scratch area

Do not describe Maths as a supported NEET subject.

## Identity and metadata

| Field | Role |
|---|---|
| `checksum_sha256` | Canonical content identity (unique) |
| `relative_source_path` | Path relative to `study_material_dir` |
| `class_level` | `11` \| `12` (source metadata only) |
| `subject_code` | `PHYSICS` \| `CHEMISTRY` \| `BIOLOGY` |
| `absolute_source_path_dev` | Dev-only; omitted from public API |
| `storage_key` | Reserved for future production storage |

Repeated discovery is idempotent: same SHA-256 → no new row.

## Source-document lifecycle (Phase A)

```text
DISCOVERED → (later phases) QUEUED → INGESTED
```

Phase A only creates `DISCOVERED` rows.

## Relationship to existing ingestion

```text
SourceDocument (optional)
      ↓ source_document_id
IngestionJob
      ↓
IngestionSection → KnowledgeUnit → ContentVersion → Question (ECAEP)
```

Path-based `POST /api/v1/ingestion/jobs` and upload endpoints remain
supported. Discovery does **not** auto-start ingestion or MCQ generation.

## API

```http
POST /api/v1/ingestion/source-documents/discover
Authorization: content.create + CSRF
Body: { "dry_run": false }

GET /api/v1/ingestion/source-documents?subject_code=PHYSICS&class_level=11
```

Example discovery result:

```json
{
  "discovered": 68,
  "registered": 68,
  "duplicates": 0,
  "skipped": 0,
  "errors": 0
}
```

## CLI

From `apps/backend`:

```bash
python scripts/study_material_discover.py discover
python scripts/study_material_discover.py discover --dry-run
python scripts/study_material_discover.py import-inventory
```

Or:

```bash
python -m app.modules.ingestion.cli.study_material discover
```

`import-inventory` is a one-shot helper for `scripts/StudyMaterial_INVENTORY.json`.
It ignores Maths. Runtime source of truth is always filesystem + registry.

## Security model

- No client-supplied scan roots
- Paths resolved and required to stay under `study_material_dir`
- `../`, absolute escapes, and symlink/junction escapes rejected
- Public API responses omit absolute filesystem paths

## Baseline corpus (dev verification)

When the full tree is present, expect approximately:

| Subject   | PDFs |
|-----------|-----:|
| Physics   |    20 |
| Chemistry |    19 |
| Biology   |    29 |
| **Total** | **68** |

Pages ≈ 1,477. If counts differ, investigate the filesystem — do not force-match.

## Status

**Phase A + B: IMPLEMENTED — NOT DoD COMPLETE**

Phase B (ADR-0031) adds academic mapping and SourceDocument → IngestionJob
provenance. Next authorized phase: mandatory 30-question pilot (Phase D).

## Phase B — Academic mapping (ADR-0031)

### Mapping table

`ingestion.source_academic_mappings` — one row per source document.

| Status | Meaning |
|--------|---------|
| `MAPPED` | Explicit registry entry + academic chapter exists |
| `UNMAPPED` | No confident mapping — **not guessed** |

### Biology

Filesystem `Biology/` maps to academic **BOTANY** or **ZOOLOGY** only via
explicit registry entries. No automatic split by filename alone.

### Pilot-ready sources

| Subject | Source PDF | Academic chapter |
|---------|------------|------------------|
| Physics | Class 12 Ch 3 | `current-electricity` |
| Chemistry | Class 11 Ch 4 | `chemical-bonding` |
| Biology (Botany) | Class 11 corpus `chapter-11.pdf` | `photosynthesis` |

> Phase B.1: Biology pilot uses `ncert-books-class-11-biology-chapter-11.pdf`
> (`PHOTOSYNTHESIS IN HIGHER PLANTS`). Corpus `chapter-13.pdf` is Plant Growth
> and stays **UNMAPPED** — not photosynthesis.

### Sync mappings

```bash
python scripts/study_material_discover.py map
python scripts/study_material_discover.py coverage
```

```http
POST /api/v1/ingestion/source-documents/map
GET  /api/v1/ingestion/source-documents/coverage
GET  /api/v1/ingestion/source-documents/{id}   # includes academic_mapping
```

Expected after sync on full corpus: **4 mapped / 64 unmapped** (explicit
registry only — missing NCERT chapters are not invented).

## Provenance — starting ingestion jobs

### By source document ID (preferred)

```http
POST /api/v1/ingestion/jobs
{ "source_document_id": "<uuid>" }
```

Uses registry path + checksum validation + mapping-derived `chapter_code`.

### Legacy path-based (backward compatible)

```http
POST /api/v1/ingestion/jobs
{ "file_path": "...", "chapter_code": "current-electricity" }
```

Auto-links `source_document_id` when SHA-256 matches a registered source.

### Checksum validation

If on-disk bytes differ from `checksum_sha256`, ingestion is rejected with
`SOURCE_CHECKSUM_MISMATCH`. Rediscover/re-register before ingesting.

### Unmapped sources

Starting via `source_document_id` when mapping is `UNMAPPED` returns
`UNMAPPED_SOURCE` — no MCQ generation, no invented chapters.

## API (Phase A + B)

```http
POST /api/v1/ingestion/source-documents/discover
POST /api/v1/ingestion/source-documents/map
GET  /api/v1/ingestion/source-documents/coverage
GET  /api/v1/ingestion/source-documents/{id}
GET  /api/v1/ingestion/source-documents

POST /api/v1/ingestion/jobs
  { "source_document_id": "..." }           # mapping authoritative
  { "file_path": "...", "chapter_code": "..." }  # legacy + auto-link
```

## CLI

```bash
python scripts/study_material_discover.py discover
python scripts/study_material_discover.py map
python scripts/study_material_discover.py coverage
python scripts/study_material_discover.py import-inventory
```

## Status (summary)

**IMPLEMENTED — NOT DoD COMPLETE** — ready for Phase D pilot planning, not
for scaled MCQ generation.

## Phase D — 30-MCQ pilot (ADR-0032)

### Target

```text
Physics     = 10  (current-electricity)
Chemistry   = 10  (chemical-bonding)
Biology     = 10  (photosynthesis / BOTANY)
Total       = 30
```

### Run (does not auto-publish)

```bash
python scripts/study_material_discover.py pilot-mcq --dry-run   # verify sources
python scripts/study_material_discover.py pilot-mcq           # execute pilot
python scripts/study_material_discover.py pilot-mcq --force   # re-run
```

```http
POST /api/v1/ingestion/pilot/mcq-run?dry_run=false
GET  /api/v1/ingestion/pilot/provenance
```

Idempotent per `pilot_run_id=phase-d-30-mcq-v1` unless `--force`.

## Status

Pilot orchestration: **IMPLEMENTED**. Phase B.1 corrected Biology mapping to
`chapter-11.pdf` → `photosynthesis`. Phase D real 30-MCQ pilot: **NOT YET EXECUTED**.

`pilot_ready` requires registry mapping + topic/concept tree + PDF content
preflight match (`chapter_content_preflight.py`).

### After generation

All 30 questions start as **DRAFT**. Complete ECAEP manually:

```text
submit → review (approve) → publish
```

Then verify student practice → assessment → mastery using existing flows.

### Status

Pilot orchestration: **IMPLEMENTED**. Full pilot validation requires human
ECAEP review + student E2E evidence. Overall feature: **NOT DoD COMPLETE**.
