# ADR-0030: NEET StudyMaterial Source Registry and Recursive Discovery

## Status
Accepted

## Context
ADR-0022 established a single-PDF, path-based ingestion endpoint
(`POST /api/v1/ingestion/jobs`) that is sufficient for a pilot chapter
but insufficient for a corpus of **68 NEET** Physics / Chemistry /
Biology PDFs under the configured `STUDY_MATERIAL_DIR`. Operators would
otherwise hand-supply absolute paths one file at a time, with no first-class
registry of source identity, Class 11/12 metadata, or auditable discovery
results.

The real development tree also contains **Maths/** (outside NEET-UG scope
for this product) and **Uploads/** (operator-uploaded scratch files). A
naive recursive walk that later “filters Maths” is unsafe as a design —
discovery must never treat Maths as a NEET source candidate.

## Decision

Introduce `ingestion.source_documents` as the first-class registry of
NEET source documents discovered under the configured StudyMaterial root.

### Scope (NEET subjects only)

Only these three subject roots are in scope:

- `Physics/`
- `Chemistry/`
- `Biology/`

Allowed `subject_code` values: `PHYSICS`, `CHEMISTRY`, `BIOLOGY`.

### Explicit exclusion

**Maths is outside the NEET source corpus and must not be registered.**
`StudyMaterial/Maths/` (and all descendants) are ignored at discovery
time — not deleted, not modified, not counted in NEET totals.

**Uploads** (`StudyMaterial/Uploads/` and descendants) are excluded from
corpus discovery. Upload-triggered jobs continue to use the existing
path-based / upload APIs; they do not become corpus `source_documents`
via discovery.

### Discovery

Discovery recursively walks the configured root (`Settings.study_material_dir`)
but **only accepts** the three NEET subject roots. It does not accept a
client-supplied filesystem root. Path parsing normalizes whitespace and
case so irregularities such as `Class 11- Chemistry` (space after hyphen)
still yield `class_level=11` and `subject_code=CHEMISTRY`.

### Identity

**SHA-256 checksum is the canonical content identity.** Uniqueness is
enforced on `checksum_sha256`. Repeated discovery is idempotent: the same
bytes do not create a second row. `relative_source_path` (relative to the
configured root) is the human/auditable path identity; absolute Windows
dev paths are never the canonical key.

### Class

`class_level` (`11` | `12`) is **source metadata** on the document row.
This phase does **not** introduce an academic Class entity.

### Biology

Do **not** automatically create `Biology → Botany` / `Biology → Zoology`
academic mappings. Academic tree mapping is a later phase (Phase B).

### Security

Discovery cannot escape the configured root: reject `../`, absolute paths
outside the root, and symlink/junction escapes where the OS resolves them
outside `study_material_dir`. The discovery API never accepts an arbitrary
scan root from the client.

### Production storage

- `absolute_source_path_dev` — development-only convenience; may be null
  in production.
- `storage_key` — future production storage abstraction (object key or
  equivalent); nullable in Phase A.

### Integration with the existing pipeline

Keep a **single** ingestion pipeline:

```
NEET StudyMaterial filesystem
        ↓
Recursive Discovery
        ↓
SourceDocument Registry
        ↓
IngestionJob  (optional source_document_id FK)
        ↓
Existing PDF Extraction → Knowledge → MCQ → ECAEP → CMS
```

`IngestionJob.source_document_id` is additive and nullable so the existing
path-based and upload-based job APIs remain backward compatible.

### Scope boundary

**Phase A does not generate MCQs**, does not run the 600-question corpus
job, and does not reorganize or rename StudyMaterial PDFs.

## Consequences

- Operators can discover and register the NEET corpus once, with SHA-256
  deduplication and Class/subject metadata preserved.
- Maths and Uploads remain on disk but never enter the NEET registry via
  discovery.
- Downstream phases (academic mapping, pilot MCQs, scaled generation)
  attach to `source_documents` without inventing a second pipeline.
- Feature status after Phase A: **IMPLEMENTED — NOT DoD COMPLETE**.
