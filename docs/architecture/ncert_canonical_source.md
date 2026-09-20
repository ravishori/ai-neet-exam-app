# CF-SOURCE-001 — Canonical NCERT source root

## Status

Accepted for forward-looking NCERT MCQ generation.

## Decision

All **NCERT-derived** MCQ generation must use PDFs whose resolved filesystem
path is contained in:

```text
NCERT_SOURCE_ROOT
```

Developer default (local checkout):

```text
<repo>/NCERT Books
```

Configured via pydantic settings:

| Setting | Env | Default |
|---------|-----|---------|
| `ncert_source_root` | `NCERT_SOURCE_ROOT` | `_default_data_dir("NCERT Books")` |

Single accessor: `get_ncert_source_root()` in
`app.modules.ingestion.services.ncert_canonical_source`.

## Non-goals

- Does **not** delete or migrate `StudyMaterial/`
- Does **not** rewrite existing question provenance
- Does **not** auto-publish or certify NCERT evidence
- Does **not** commit textbook PDFs to Git

## Guards

- `is_allowed_ncert_source(path)` — pathlib containment (not string prefix)
- `validate_ncert_generation_source(path)` — exists + readable PDF + inside root
- `assert_blueprint_ncert_source(...)` — factory blueprints that declare NCERT
- P2.3 / page-source discovery must scan `NCERT_SOURCE_ROOT` only

Typed codes: `NCERT_SOURCE_NOT_ALLOWED`, `NCERT_SOURCE_MISSING`,
`NCERT_SOURCE_UNREADABLE`, `NCERT_SOURCE_AMBIGUOUS`,
`NCERT_SOURCE_IDENTITY_MISMATCH`, `NCERT_SOURCE_NOT_PDF`.

## CI / Linux

Set `NCERT_SOURCE_ROOT` to an explicit fixture directory. Do not rely on a
developer Windows absolute path in production images.
