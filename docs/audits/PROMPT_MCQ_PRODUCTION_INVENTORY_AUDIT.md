# CURSOR AI PROMPT — READ-ONLY MCQ Production Inventory Audit

Copy everything below the line into a new Cursor chat.

---

```text
# CURSOR AI — READ-ONLY PostgreSQL MCQ Production Inventory Audit
# TALOS / Trinetra AI Learning OS
# Goal: exact inventory numbers BEFORE loading or publishing any new content

## Mission
Perform a **READ-ONLY** production inventory audit of MCQ / QUESTION content in PostgreSQL and produce exact counts for:

1. Total MCQs
2. Published
3. Draft (and every other status)
4. Physics / Chemistry / Biology
5. Class 11 / Class 12
6. Graphic-based
7. Diagram-based
8. Source / year (PYQ or provenance)
9. Chapter / topic coverage
10. Duplicates
11. Missing metadata

Do **not** load content. Do **not** publish. Do **not** mutate rows. Do **not** run Alembic migrations. Do **not** “fix” data to make numbers look good.

## Hard rules
- **READ-ONLY only**: `SELECT` / `EXPLAIN` / introspection. No `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`/`ALTER`/`DROP`/`CREATE` (except optional throwaway report files under `docs/audits/`).
- **CONTENT INTEGRITY > REPORT CONVENIENCE**
- Prefer the live DB used by the backend (see `apps/backend/.env` `DATABASE_URL_SYNC` / `DATABASE_URL`). Do not invent numbers.
- Soft-deleted rows: exclude `deleted_at IS NOT NULL` from primary totals; report soft-deleted count separately.
- Primary MCQ universe = `cms.content_items` where `content_type = 'QUESTION'`.
- Student-visible practice pool = `status = 'PUBLISHED'` only (confirm against assessment practice code if needed).
- Do **not** silently treat factory candidates / review sandbox / JSONL pilots as production CMS inventory. Report those as **separate optional appendices** if found, clearly labeled NON-PRODUCTION.

## Repo schema facts you MUST verify against live DB (do not assume without checking)
Known intended shape (confirm with `\d` / information_schema / ORM models):

- `cms.content_items`
  - `id`, `content_type`, `status`, `concept_id`, `micro_competency_id`, `title`, `slug`, `tags`, `language`
  - `current_version_id`, `latest_version_id`
  - audit/soft-delete: `created_at`, `updated_at`, `deleted_at`, `version`, …
  - statuses expected: DRAFT | AI_CHECKED | IN_REVIEW | CHANGES_REQUESTED | APPROVED | PUBLISHED | ARCHIVED (verify actual distinct values)
- `cms.content_versions`
  - `id`, `content_item_id`, `version_no`, `body` JSONB, `workflow_state`, `knowledge_unit_id`, …
- Canonical QUESTION body keys (Pydantic `QuestionBody`):
  - `stem`, `options` (A–D), `correct_option`, `explanation`, `difficulty`, `bloom_level`, `pyq_year`
- Taxonomy:
  - `academic.subjects` (codes likely PHYSICS / CHEMISTRY / BIOLOGY)
  - `academic.chapters` → `academic.topics` → `academic.concepts`
  - QUESTION links via `content_items.concept_id` (nullable)
- Visuals:
  - Separate content_type `DIAGRAM` may exist (not the same as a QUESTION with a diagram)
  - Practice images may come from visual assets linked through knowledge units — discover tables (`ingestion` / visual asset models) before counting
  - Extra JSON keys such as `diagram_svg`, `diagram_description`, `images`, `has_diagram` may exist outside the strict schema — **discover actual body keys** with SQL before defining graphic/diagram metrics

**Class 11 / 12 is NOT a guaranteed first-class column.** Discover encoding from:
- `tags`
- `concepts.ncert_reference`
- chapter/topic/concept `code` / `name`
- body JSON extras
- ingestion / knowledge-unit / pilot metadata
If Class cannot be determined reliably, report **UNKNOWN** counts with the exact detection rules used — do not guess.

## Procedure

### Step 0 — Re-audit environment (read-only)
1. Confirm git branch and that you will not commit unless asked.
2. Confirm DB connectivity (psql or SQLAlchemy sync engine from backend `.env`).
3. List schemas/tables relevant to CMS + academic + knowledge + ingestion visual assets.
4. Sample 5 QUESTION `body` JSONB documents and list **all top-level keys** present in production.
5. Write a one-paragraph “definitions” section: how you will count Total / Published / Draft / Subject / Class / Graphic / Diagram / Source-year / Duplicate / Missing metadata.

### Step 1 — Create a read-only audit script
Create (or run via one-shot python) something like:
`apps/backend/scripts/audit_mcq_production_inventory.py`

Requirements:
- Uses sync SQLAlchemy/`psycopg` **SELECT only**
- Prints JSON summary to stdout
- Writes:
  - `docs/audits/mcq-production-inventory-audit-YYYYMMDD.md`
  - `docs/audits/mcq-production-inventory-audit-YYYYMMDD.json`
- Embeds the SQL definitions used for every metric (reproducible)
- Exit non-zero if DB unreachable; never “invent” zeros when query fails

### Step 2 — Required metrics (exact numbers)

Produce ALL of the following. Every number must come from a query.

#### A. Totals & status
- `total_questions` (non-deleted QUESTION)
- `by_status`: count per distinct `status`
- Explicit:
  - `published`
  - `draft` (status = 'DRAFT' only — do not lump other non-published into Draft)
  - `other_non_published` broken out (IN_REVIEW, APPROVED, ARCHIVED, …)
- Soft-deleted QUESTION count (separate)

Also report pointer health:
- latest_version_id NULL
- current_version_id NULL
- latest ≠ current

Version body used for content metrics: prefer **`latest_version_id`** for inventory of authored content; also report a **PUBLISHED-only** slice using the version the product treats as live (`current_version_id` if that is what publish sets — verify in code). Label both clearly.

#### B. Subject (Physics / Chemistry / Biology)
Join QUESTION → concept → topic → chapter → subject when `concept_id` present.
Report:
- PHYSICS / CHEMISTRY / BIOLOGY counts (map by `academic.subjects.code` or name; show mapping)
- `subject_unmapped` / `concept_id IS NULL`
- Crosstab: subject × status (at least Published vs non-published)

#### C. Class 11 / Class 12
After discovery, apply an explicit rule set and report:
- class_11
- class_12
- class_unknown
- class_conflicting (if multiple signals disagree)
Document the rule in the report. If confidence is low, mark Class section **LOW CONFIDENCE**.

#### D. Graphic-based vs Diagram-based
Define **after** key discovery. Suggested starting definitions (adjust only with evidence):

- **Diagram-based QUESTION**: body contains non-empty diagram representation
  (e.g. `diagram_svg` / `diagram_description` / explicit diagram flag) **OR** linked visual asset / DIAGRAM association proven by FK join
- **Graphic-based QUESTION**: broader set — diagram-based **OR** any attached image/visual asset **OR** body image fields
- Report overlap: graphic_only, diagram_only, both, neither
- Separately count `content_type = 'DIAGRAM'` items (not MCQs) so they are not confused with MCQ totals

If neither body keys nor visual-asset links exist, report **0** with evidence of absence — do not fabricate.

#### E. Source / year
From body + joins:
- `pyq_year` distribution (null vs each year)
- Any other provenance fields discovered (`source`, `exam_year`, tags, knowledge unit / ingestion job / pilot_run_id)
- Top sources / pilot_run_id breakdown if joinable via `content_version_knowledge_units` → knowledge → ingestion

#### F. Chapter / topic
- Counts by chapter name/code (top N + long tail count)
- Counts by topic name/code (top N + long tail)
- Questions with concept but missing chapter/topic (should be rare — flag)
- Questions with no concept_id

#### G. Duplicates
Detect and count (report counts + sample IDs, not full PII):
1. Exact duplicate `slug` among non-deleted QUESTIONs
2. Exact duplicate normalized stem (`lower(trim(body->>'stem'))`) across different item IDs
3. Near-duplicate optional: same stem hash / md5 of stem+options (document method)
4. Duplicate option texts inside a single question (data quality)
Do not delete duplicates — inventory only.

#### H. Missing metadata
Count QUESTIONs missing any of:
- concept_id
- stem / options / correct_option / explanation (on chosen version body)
- valid A–D option set
- difficulty
- subject mapping
- class mapping (per your rule)
- pyq_year (report as missing provenance year — may be legitimate for non-PYQ; separate “expected PYQ but year null” only if you can define PYQ membership)
- micro_competency_id (optional field — report coverage, do not treat as hard defect unless product requires it)
- publish pointer issues for PUBLISHED rows (current_version_id null, body invalid)

### Step 3 — Sanity checks
- `sum(by_status) == total_questions`
- `published + draft + other_non_published == total_questions`
- subject mapped + unmapped == total_questions
- class_11 + class_12 + class_unknown (+ conflicting) == total_questions
- Graphic/diagram sets ⊆ total_questions
- Compare PUBLISHED count to practice pool expectation (should match assessment published filter)

### Step 4 — Deliverable report format
Write Markdown + JSON with this exact executive block at the top:

# MCQ Production Inventory Audit
Date:
Database:
Read-only: YES

## Executive Numbers
| Metric | Count |
|--------|------:|
| Total MCQs (QUESTION, not deleted) | |
| Published | |
| Draft | |
| Other statuses (sum) | |
| Physics | |
| Chemistry | |
| Biology | |
| Subject unmapped | |
| Class 11 | |
| Class 12 | |
| Class unknown | |
| Graphic-based | |
| Diagram-based | |
| With pyq_year | |
| Missing concept_id | |
| Duplicate stem groups | |
| Duplicate slug groups | |

Then include:
- Definitions used
- Status breakdown table
- Subject × status
- Class detection rules + confidence
- Graphic/diagram definitions + counts
- Source/year distribution
- Chapter/topic top tables
- Duplicates (counts + up to 20 example IDs)
- Missing metadata checklist
- SQL appendix (or path to script)
- Risks / gaps before loading more content
- **Recommendation**: whether inventory is healthy enough to load more MCQs (YES / NO / CONDITIONAL) with reasons

## Final chat response
Return a short executive summary with the Executive Numbers table filled, path to the report files, and the single next recommended action (still no loading/publishing unless inventory is clearly ready).

## Explicit non-goals
- No ECAEP publish
- No status flips
- No content generation
- No backfills
- No “fixing” missing class/subject by writing tags
```
---

## How to use
1. Paste the prompt into a **new** Cursor agent chat on this repo.
2. Ensure Postgres is reachable with the backend `.env` credentials.
3. Keep the session read-only until the audit report exists under `docs/audits/`.
