# ADR-0026: Visual asset extraction — first-class diagrams, figures, and tables in the ingestion pipeline

## Status
Accepted

## Context
This session did two pieces of standalone work outside the pipeline entirely:
(1) hand-extracted three real NEET 2024 PYQ papers (200 questions) into JSON
files, initially marking every diagram-dependent question `"uncertain": true`
because the only PDF-reading path available (`Read`'s page-image renderer)
depends on `pdftoppm`/poppler, which isn't installed in this environment; (2)
after discovering `PyMuPDF` (already a pipeline dependency, see ADR-0022) can
render pages to images directly with no poppler dependency, re-inspected
every flagged page, replaced all 33 `uncertain` flags with real content, and
then built a small standalone script that assigns UUIDs and pixel-accurate
bounding boxes to 15 of those visual elements, crops them to PNG, and writes
a JSON manifest — proven correct by direct visual spot-check against the
source PDF.

None of this touched the database. Both artifacts are files sitting in
`PYExamPapers/2024/extracted/`, disconnected from `IngestionJob`,
`IngestionSection`, and `KnowledgeUnit` (ADR-0022/0023/0024/0025). A follow-up
request then asked for a full generic, multi-exam (NEET/JEE/UPSC/SSC/State
Boards/international) Document Intelligence Platform — new schema families,
a CV layout-detection stage, a vector DB, object storage, and a worker queue,
implemented as 20 sections of architecture and code in one pass. That request
is explicitly **not** what this ADR does: it's a proposal to build a second,
parallel system sized for exam families and asset volumes this codebase has
never touched, when the concrete, proven thing this session actually built —
UUID-tagged, bounding-boxed, storage-backed visual assets — has never been
given a home in the schema at all. This ADR gives it one, sized to what was
actually proven, for the one platform (NEET/TALOS) that exists.

## Decision

### 1. One new table, in the existing `ingestion` schema, not a new schema
`ingestion.visual_assets`, following the same schema-per-domain convention
`IngestionSection` already uses (visual assets are raw extracted material
tied to a source page, the same category as section text — not yet a
published, versioned content asset, which is `cms.content_versions`'s job).

Columns:
- `id` (uuid, pk), `job_id` → `ingestion_jobs` (CASCADE)
- `section_id` → `ingestion_sections`, **nullable, SET NULL** — a visual
  element can be detected on a page before or independent of section-
  matching (as every element in this session's manifest was: matched to a
  *question number*, not a section)
- `source_page` (int), `bounding_box` (JSONB: `x0,y0,x1,y1`, unit
  `pdf_points_72dpi` — matching what this session's manifest already emits),
  `render_dpi`, `width_px`, `height_px`
- `asset_type`: `image | diagram | table | equation | chemical_structure` —
  the four categories this session actually produced plus `equation`
  (already partially handled today as inline text by
  `pdf_extraction_service.py`; kept here as a type slot, not a new detector)
- `detection_method`: `embedded_image | vector_cluster | manual` — **stated
  honestly, not hidden.** This session proved `embedded_image` (via
  `get_image_rects`) and `vector_cluster` (proximity-merge over
  `get_drawings()` paths) both work, but `vector_cluster` only reliably
  isolates multi-option grids (3–4 same-sized diagrams with real gaps) —
  single vector-drawn diagrams (a lone chemical structure, a lone circuit)
  routinely merge with `List-I`/`List-II` table borders or the page's
  translucent watermark, which are built from the same kind of vector path.
  Tuning the merge distance to fix one case broke the other; this is a
  genuine geometric ambiguity, not a bug to iterate away — hence `manual` is
  a first-class value, not a fallback to apologize for.
- `storage_path` — local filesystem, under a new `visual_assets_dir` setting
  (same pattern as `study_material_dir`, ADR-0022). **Not S3/Blob/GCS** —
  none of those are provisioned, credentialed, or budgeted for this project;
  adopting one is a real infrastructure and recurring-cost decision that
  deserves its own ADR when there's an actual multi-instance deployment
  need, not a line item inherited from a platform-scale prompt.
- `content_hash` (sha256 of the crop file) — same idempotency pattern as
  `KnowledgeUnit.content_hash` (ADR-0024)
- `vision_description`, `ocr_text` — both nullable; populated by whichever
  process (this session's manual `Read`-tool inspection today, an
  automated vision-model call later) actually looked at the crop. Absence
  is a legitimate state, not an error.
- `knowledge_unit_id` → `knowledge.knowledge_units`, nullable, RESTRICT —
  populated only when a Knowledge Unit's `structured_facts` actually cites
  this asset. A single nullable FK is sufficient here (unlike ADR-0025's
  N:1 join table for content versions) because one visual asset is
  authored once, on one page, for one concept — there's no proven case yet
  of one diagram legitimately grounding multiple Knowledge Units.
- `review_status`: `AUTO_DETECTED | VERIFIED | NEEDS_MANUAL_BBOX | REJECTED`
  — this is the ADR's answer to "never discard a diagram" from the
  platform-scale prompt, sized honestly: a page where clustering couldn't
  isolate the diagram gets a row with `NEEDS_MANUAL_BBOX` and a null
  `bounding_box`, not a silently dropped page. `IngestionJob` gets a new
  `visual_assets_needing_review` counter (same observability pattern as
  `knowledge_units_rejected`), so this state is queryable, not a buried
  TODO.

### 2. Detection is exactly the two methods this session proved, nothing invented
`embedded_image` via `page.get_image_rects()` and `vector_cluster` via a
proximity-merge over `page.get_drawings()` paths (gap-tolerance merge,
generously-sized noise-region exclusion for the watermark/footer/banner
patterns this session identified by direct inspection). **Explicitly not
built here:** OCR (Tesseract/PaddleOCR), a trained layout-detection model
(LayoutParser/Docling), or a chemistry/biology-specific classifier (Lewis
structure vs. reaction scheme vs. circuit). Those all require either a new
dependency this project doesn't have, or a labeled dataset that doesn't
exist. `asset_type` and `vision_description` are filled in by an agent (or
human) actually looking at the crop — same as this session's own process —
until a real detector is separately proposed and justified.

### 3. Runs inside the existing pipeline, not a new worker system
A new stage in `IngestionPipelineService`, after extraction and before (or
alongside) section-splitting, using the same `FastAPI BackgroundTasks`
execution model the pipeline already uses (`ingestion_router.py`) — no
Celery, no Redis, no new queue infrastructure. That stack is real
infrastructure this project doesn't run today; introducing it for one new
stage, rather than because the *existing* pipeline actually needs
horizontal workers, would be exactly the kind of premature-generality this
project's own frozen-architecture process exists to prevent.

### 4. Explicitly out of scope for this ADR
- The generic, multi-exam schema (`Documents`, `ExamYears`, `References`,
  and a from-scratch table set) — this ADR extends the NEET-specific
  pipeline that exists; a multi-exam platform is a distinct product
  decision with its own migration and licensing questions (see
  ADR-0005), not a schema-design exercise.
- pgvector / embeddings for visual assets — no embedding column, same
  reasoning ADR-0024 already gave for `KnowledgeUnit` (a real capability
  decision, not a speculative nullable column).
- Retroactively migrating this session's three standalone JSON files or
  15-asset manifest into this table — they predate it and stay as files;
  this ADR governs assets extracted by ingestion runs going forward, the
  same non-backfill precedent ADR-0024 set for pre-existing content.
- Solving `NEEDS_MANUAL_BBOX` automatically — that remains real,
  tracked, agent-or-human-assisted work per asset, not something this ADR
  claims to close.

## Risks
- **`review_status` could become a silent backlog** if nothing ever
  processes `NEEDS_MANUAL_BBOX` rows — mitigated by the
  `visual_assets_needing_review` counter surfacing it on every job, the
  same visibility precedent as `knowledge_units_rejected`.
- **Local filesystem storage doesn't survive a multi-instance or
  container-recycled deployment** — acceptable at current single-instance
  pilot scale; explicitly the reason object storage is named as a
  near-term, separately-justified follow-up rather than silently deferred.
- **Vector-cluster detection will keep producing false groupings** on pages
  this session didn't specifically tune against — `review_status` exists
  precisely so a wrong auto-cluster is a flagged, correctable row, not a
  wrong answer served as fact.

## Tests
- Unit: the proximity-merge clustering function against fixtures built from
  this session's own findings (a page with one clean embedded image, a page
  with a 4-way option grid, a page where clustering is known to over-merge
  with a table border) — asserting `review_status` lands correctly for each
  case, not asserting perfect detection.
- Integration: a pipeline run against the existing pilot PDF (Current
  Electricity chapter) creates `visual_asset` rows with plausible
  `detection_method`/`review_status` values; the run's existing
  question/flashcard/note counts are unchanged (this stage doesn't touch
  generation).
- Manual verification step, same discipline this session used: crop output
  spot-checked against the source PDF before `review_status` moves from
  `AUTO_DETECTED` to `VERIFIED`.

## Consequences
Future ingestion runs get a real, queryable place to put diagrams instead
of the two options that existed before this ADR — silently dropping them
(the original text-only PDF extraction path) or a one-off standalone script
per document (this session). It does not close the "detect every diagram
automatically" problem; it makes the gap between what's auto-detected and
what needs manual placement an explicit, visible, per-asset status instead
of an invisible one.
