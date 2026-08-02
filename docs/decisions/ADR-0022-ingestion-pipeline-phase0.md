# ADR-0022: Study-material ingestion pipeline — Phase 0, one real chapter

## Status
Accepted

## Context
A user-supplied master-prompt proposed a full production-grade ingestion
platform: 24/7 file watcher over `StudyMaterial/`, OCR, DOCX/PPTX/ZIP/RAR
support, chapter/topic/concept/knowledge-graph extraction, a vector
database, dedup via embeddings, and generation of a dozen learning-asset
types (MCQs, flashcards, mind maps, mock tests, ...), sized for "100,000+
books, 10 million+ questions." `StudyMaterial/` does contain real content
— 74 born-digital NCERT chapter PDFs across four subjects — so this isn't
purely hypothetical. But building the full brief before a single file has
been ingested for real would repeat the exact mistake ADR-0012 and
ADR-0021 already cut once each: scaffolding for a scale the project
hasn't earned yet, most of it unused. Two more concrete corrections:
this project has no Flutter client (Next.js web only — the master prompt
assumed Flutter screens), and multi-AI-provider swapping already exists
(`AIGateway._build_provider()`, ADR-0004) — the pipeline reuses it rather
than rebuilding it.

## Decision

**One real file, end to end, before anything else.** The pilot target is
`StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf`
— NCERT's actual "Current Electricity" chapter, which is also the one
chapter per subject ADR-0009/ADR-0012 already seeded completely (3
topics, 4 concepts: Ohm's Law, Drift Velocity, Factors Affecting
Resistance, Kirchhoff's Laws). This lets the pipeline be graded against
ground truth that already exists, instead of inventing taxonomy from
nothing on the first try.

**No OCR, no vector DB, no knowledge graph, no file watcher — yet.** The
74 files are born-digital PDFs (confirmed by extracting one: PyMuPDF
pulls clean text directly, no scanned-image artifacts). OCR is dead
weight until a scanned file actually shows up. Dedup uses Postgres'
`pg_trgm` (already enabled since ADR-0001) for stem-similarity matching
against existing published questions for the same concept — adequate at
this scale, and the standard escape hatch (pgvector/a real vector store)
is a schema-additive change later, not a redesign, the same shape as
every other "add it when it's earned" call this project has made. The
directory is processed on-demand via an API trigger, not a 24/7 watcher
— proving the extract→generate→review chain matters before proving it
can run unattended.

**Pipeline stages (new `ingestion` schema, mirroring the
schema-per-domain convention):**
1. `IngestionJob` row created for the file — checksum (sha256) recorded
   so re-running against an unchanged file is a no-op, matching "process
   files only once."
2. PDF text extraction (PyMuPDF) — page-by-page, concatenated.
3. Section splitting — NCERT's own heading convention (`N.M  HEADING`,
   e.g. "3.2  ELECTRIC CURRENT") via regex. Real NCERT chapters are
   consistently formatted this way; no ML-based layout model needed yet.
4. Concept matching — each section heading matched by name against the
   chapter's *existing* seeded concepts (already-solved problem for this
   pilot chapter; sections with no match are recorded but skipped for
   generation rather than inventing new taxonomy silently).
5. MCQ generation — reuses `AIGateway`, a new prompt that's explicitly
   grounded in the *actual extracted section text* (not just the
   concept's short summary, unlike the existing admin-triggered
   generator), asking for 2 questions per matched section.
6. Dedup — trigram similarity (`pg_trgm`) between a generated stem and
   existing published question stems for the same concept; above a
   0.6 similarity threshold, the candidate is dropped and logged, not
   stored.
7. Storage — surviving questions land as `DRAFT` `cms.content_items` via
   the *existing* `ContentWorkflowService.create_item` — same
   draft→review→publish gate as human-authored content and the existing
   admin-triggered generator (ADR-0004). "Only store verified questions"
   is already true by construction: nothing this pipeline produces is
   visible to students until a human approves it.

**What's explicitly deferred, not forgotten:** file watcher (24/7
monitoring), OCR, DOCX/PPTX/ZIP/RAR support, subject/book/edition
auto-detection, knowledge graph, embeddings/vector DB, the 12 companion
learning-asset types (flashcards, mind maps, mock tests, ...), and admin
UI for triggering/monitoring jobs. Each is additive once this slice
proves the core loop works on real material — same pattern as every
other phased module in this project.

## Consequences
Ingestion only works today for NCERT-formatted PDFs against chapters
that already have seeded topics/concepts — by design, not oversight.
Generalizing to the other 73 files means either seeding more chapters'
taxonomy first (the known, deliberate bottleneck from ADR-0009) or
teaching the pipeline to propose new topics/concepts instead of only
matching existing ones — a real decision to make once this pilot's
output quality is judged good enough to trust.
