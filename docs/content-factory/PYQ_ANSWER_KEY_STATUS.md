# PYQ Answer Key Status — P2

**Generated:** 2026-09-01T11:58:47.340348+00:00

## Corpus search result

No separate answer-key PDFs exist in the supplied ZIP (confirmed P0/P1/P2).
Embedded authoritative answer grids (≥10 consecutive lines inside answer-key sections) were **not found**.

## Classification counts (TEXT extracted questions)

| Status | Count |
|--------|------:|
| ANSWER_KNOWN | 0 |
| ANSWER_PENDING | 7679 |
| ANSWER_CONFLICT | 0 |
| ANSWER_UNVERIFIED | 0 |

## Policy

- No AI-generated answers used.
- Instructional 'Answer Sheet' mentions are not treated as authoritative keys.
- Isolated ratio lines inside question bodies (e.g. `1 : c`) are rejected as false positives.

---

## 2026-10-22 — Four-Option Completeness Audit (`ANSWER_PENDING` cohort)

**Audit type:** Structural data-quality audit only. This is **not** an answer-resolution
or publication exercise, and it does not determine or imply the correct answer letter for
any question. It measures whether each question's four options (A–D) are present, non-empty,
distinct, and free of extraction corruption — independent of whether the correct option is
known.

### Objective and scope

Before any future answer-resolution planning, determine how many `NEET_PYQ_OFFICIAL`
questions currently in `state = 'ANSWER_PENDING'` have four complete, valid, distinct answer
options. This audit is separate from, and does not change, the answer-availability findings
already recorded in `docs/PRODUCTION_READINESS.md` §8.1–8.3 (which cover whether a *correct
answer* can be determined for this cohort). This section covers only option *structure*.

### Production population (verified live, read-only)

```sql
SELECT COUNT(*) FROM pyq.questions q
JOIN pyq.source_files sf ON sf.id = q.source_file_id
JOIN pyq.import_batches b ON b.id = sf.batch_id
JOIN pyq.sources src ON src.id = b.source_id
WHERE src.source_key = 'NEET_PYQ_OFFICIAL' AND q.state = 'ANSWER_PENDING';
```

**Result: 8,928 questions.** This matches the population already reconciled in
`PRODUCTION_READINESS.md` §8.3 for the same cohort.

`raw_options` (jsonb) key-shape was independently verified via `jsonb_object_keys(...) GROUP BY`
across all 8,928 rows: every row has exactly the keys `{A, B, C, D}` present — no row is missing
a key outright. This audit measures option *content* (empty, duplicate, or malformed values
under those keys), not key presence.

### Methodology

All 8,928 rows were bulk-extracted in a single read-only `COPY (...) TO STDOUT WITH CSV HEADER`
query (`id, staging_id, exam_year, subject, opt_a..opt_d`) and classified locally in Python.
Each question is counted exactly once, keyed by its database `id`/`staging_id` (verified:
0 duplicate ids in the extracted set, and classification totals sum to exactly 8,928).

**Classification categories (applied in this precedence order — structural invalidity is
checked before duplicate detection, so a corrupted option is never miscounted as a genuine
duplicate):**

1. **`MALFORMED_OPTIONS`** — structurally invalid: an option is `NULL` while sibling options
   are not (inconsistent nullability), or two or more options share an internal line break
   *and* are identical after normalization (a signature of mis-segmented OCR/extraction, where
   one garbled multi-line block was copied across option slots — not a real repeated exam
   option, which in this corpus is always a short single-line phrase or expression).
2. **`REQUIRES_MANUAL_REVIEW`** — one or more options are empty, and at least one of the
   present options references a figure/diagram/image (`figure`, `diagram`, `image`, `graph`,
   `shown below/above`, `as shown`) — flagged for human review rather than assumed invalid,
   since the missing content may be an image the text extraction legitimately could not
   capture.
3. **`MISSING_OPTION`** — one or more of A–D is empty (whitespace-only values are treated as
   empty) and the question is not image-dependent per above.
4. **`DUPLICATE_OPTIONS`** — all four options are present and non-empty, but fewer than four
   distinct values remain after conservative normalization (Unicode NFKC normalization,
   whitespace collapse, case-fold only — digits, symbols, units, and mathematical/chemical
   notation are never stripped or altered, so options differing only in a numeral or unit,
   e.g. `2 mC` vs `4 mC`, are correctly kept distinct).
5. **`FOUR_VALID_OPTIONS`** — four present, non-empty, pairwise-distinct options after the
   above normalization; no corruption signature detected.

This is a structural check only — a question classified `FOUR_VALID_OPTIONS` has four
complete, distinct options, but this says nothing about which option (if any) is the
scientifically correct answer.

### Results

| Category | Count | % of 8,928 |
|---|---:|---:|
| `FOUR_VALID_OPTIONS` | 7,720 | 86.47% |
| `MISSING_OPTION` | 1,148 | 12.86% |
| `MALFORMED_OPTIONS` | 32 | 0.36% |
| `DUPLICATE_OPTIONS` | 27 | 0.30% |
| `REQUIRES_MANUAL_REVIEW` | 1 | 0.01% |
| **Total** | **8,928** | **100.00%** |

**By exam year:**

| Year | FOUR_VALID | MISSING | DUPLICATE | MALFORMED | REVIEW |
|---|---:|---:|---:|---:|---:|
| 2020 | 2,004 | 80 | — | 10 | — |
| 2021 | 3,919 | 216 | — | 22 | — |
| 2023 | 1,480 | 646 | 23 | — | 1 |
| 2024 | 314 | 206 | 4 | — | — |
| 2025 | 3 | — | — | — | — |

**By subject** (only where the `subject` column is populated; `(unclassified)` denotes rows
with no subject tag, which cuts across all five categories and should not be read as its own
subject):

| Subject | FOUR_VALID | MISSING | DUPLICATE | MALFORMED | REVIEW |
|---|---:|---:|---:|---:|---:|
| Botany | 1,018 | — | — | — | — |
| Chemistry | 888 | 168 | — | — | — |
| Physics | 979 | 48 | — | 22 | — |
| Zoology | 1,034 | — | — | — | — |
| (unclassified) | 3,801 | 932 | 27 | 10 | 1 |

### Reconciliation and validation evidence

- Live production population (8,928) matches the population independently established in
  `PRODUCTION_READINESS.md` §8.3 for the same filter (`source_key = 'NEET_PYQ_OFFICIAL'`,
  `state = 'ANSWER_PENDING'`).
- Zero duplicate question `id`s in the extracted set — each of the 8,928 questions was
  classified exactly once.
- The five category counts sum exactly to 8,928, with no unclassified remainder.
- An initial classification pass found 59 `DUPLICATE_OPTIONS`; manual inspection showed 47 of
  these were garbled multi-line OCR corruption duplicated across option slots (not genuine
  repeated exam text). These were reclassified to `MALFORMED_OPTIONS` per the documented
  precedence rule, yielding the final 27 / 32 split reported above. This correction is recorded
  here for transparency since it changed the reported counts during the audit itself.
- No comparison against the canonical (`data/staging/pyq/2020-2025/papers/*/questions.jsonl`)
  or R3 (`.../p2_1e_full_r3/questions.p2_1e_full.jsonl`) local files was required for *this*
  structural check, since option text is read directly from production `raw_options` (the
  authoritative, already-imported content); canonical/R3 reconciliation by `staging_id` was
  already performed for the separate answer-availability audit in
  `PRODUCTION_READINESS.md` §8.3 and is not repeated here.

### Is four-valid-options already enforced somewhere downstream?

**Yes — at publication time, in code, not by assumption.** `QuestionBody`
(`app/modules/cms/schemas/content_bodies.py`) requires `options: list[QuestionOption] =
Field(min_length=4, max_length=4)`, each `QuestionOption.text: str = Field(min_length=1)`
(non-empty), and a `model_validator` (`validate_neet_mcq_shape`) that rejects any body where
the four option labels are not exactly `{A, B, C, D}` or where the four option texts are not
pairwise distinct. This validation runs via `evaluate_question_publication_gates` →
`assert_question_publishable` → `assert_body_publishable("QUESTION", body)` in
`app/modules/cms/services/publication_gates.py`, i.e. before a question can reach
`PUBLISHED` status. At the assessment-eligibility layer itself
(`weekly_assessment_service.py`, `weekly_revision_service.py`), only `ContentItem.status ==
"PUBLISHED"` is checked — there is no separate option-count re-check at query time, because
the structural guarantee is already enforced upstream at publication. Practically, this means
the `MISSING_OPTION`, `DUPLICATE_OPTIONS`, and most `MALFORMED_OPTIONS` rows in this cohort
would already be rejected by the existing publication gate if an attempt were made to publish
them as-is — they are not a new risk the gate fails to catch, but they do need their
underlying option text repaired (a separate task) before they are publishable.

### Limitations

- The 1 `REQUIRES_MANUAL_REVIEW` case and the 32 `MALFORMED_OPTIONS` cases need individual
  human review; this audit intentionally does not infer or repair option text.
- Subject attribution is only as reliable as the `subject` column on `pyq.questions`; a large
  share of rows (`(unclassified)`) have no subject tag and are reported separately rather than
  forced into a subject bucket.
- `FOUR_VALID_OPTIONS` is a structural statement only. It does not imply the correct answer is
  known — cross-reference `PRODUCTION_READINESS.md` §8.1–8.3 for the separate
  answer-availability status of this same cohort (which remains unresolved for the vast
  majority of these questions regardless of option completeness).

### Recommended next step

Plan answer-resolution work only after this structural audit is reviewed. Any future
answer-resolution effort should exclude the `MISSING_OPTION`, `DUPLICATE_OPTIONS`, and
`MALFORMED_OPTIONS` rows from automated resolution until their option text is independently
repaired, since a resolved answer letter is meaningless against incomplete or corrupted
options.

---

## 2026-10-22 — Deeper Validation Pass: Stem/Content Integrity of the `FOUR_VALID_OPTIONS` Subset

**Audit type:** Deeper, read-only validation pass over the subset of the `ANSWER_PENDING`
cohort that the audit above classified `FOUR_VALID_OPTIONS`. This section does **not** redo
the full-cohort structural audit above (counts there stand as recorded) — it re-derives the
live `FOUR_VALID_OPTIONS`-equivalent population fresh, then checks what that audit explicitly
did not: stem completeness, source fidelity against the canonical/R3 JSONL files, encoding
corruption, truncation, damaged scientific notation, and whether the real production
serialization path renders the content losslessly. It does not touch or revise the
structural audit above, and makes no claim about scientific/answer correctness.

### Phase 1 — Code read (no modifications)

- `app/modules/cms/schemas/content_bodies.py`: `QuestionBody` requires exactly 4 options
  labeled A–D, each non-empty, pairwise-distinct (case-folded), stem/explanation non-empty,
  `correct_option` ∈ labels. This is the gate a draft must pass to become `PUBLISHED`.
- `app/modules/cms/services/publication_gates.py`: `evaluate_question_publication_gates` runs
  `assert_body_publishable` + `QuestionBody.model_validate` as the `structural_ok` gate, plus
  separate scientific/NCERT/taxonomy/duplicate/provenance/review-state gates. A corrupted or
  incomplete option would fail `structural_ok` (non-empty, min_length=1) or, for duplicates,
  the uniqueness check — but **not** for encoding corruption, truncation, or stray control
  characters inside an otherwise non-empty string, since Pydantic's `min_length=1` only checks
  the string is non-empty, not that it is clean.
- `app/modules/cms/pyq/pyq_option_eligibility.py` (`classify_option_structure`) is the
  **production** re-implementation of this exact structural check, used live by the
  answer-review queue — confirmed to mirror this audit's 2026-10-22 methodology exactly
  (same normalization, same precedence order).
- `app/modules/cms/pyq/pyq_answer_review.py` is the **real serialization path** a human
  reviewer hits: `get_queue_counts`, `list_review_queue`, and `get_question_review_detail` all
  read `q.raw_options` and `q.raw_stem` directly (not `normalized_options`/`normalized_stem`)
  and return `"options": row.raw_options` verbatim in the API response. This confirms the
  prior audit's implicit assumption (checking `raw_options`) matches what is actually served —
  there is no separate serializer field this audit needed to re-check.
- `weekly_assessment_service.py` / `weekly_revision_service.py`: only gate on
  `ContentItem.status == "PUBLISHED"`; no option-count or content re-check at query time
  (confirmed, matches prior audit's note).
- Schema check: `pyq.questions` (22 columns) and `pyq.source_files` (8 columns) were inspected
  directly via `information_schema.columns`. **Neither table has any image/asset/figure path
  column.** There is no field anywhere in this schema for an image-dependent PYQ question to
  resolve a figure asset — confirmed by schema inspection, not inferred.

### Phase 2/3 — Live re-derivation and whole-question classification

**Live base population** (identical filter, re-run fresh): `src.source_key =
'NEET_PYQ_OFFICIAL' AND q.state = 'ANSWER_PENDING'` → **8,928 rows**, unchanged from the prior
audit (same `ANSWER_PENDING` count, confirming no resolution/import activity occurred between
audits).

All 8,928 rows were bulk-extracted via `COPY (...) TO STDOUT WITH CSV HEADER`
(`id, staging_id, exam_year, subject, state, stem_len, norm_stem_len, raw_stem, raw_options,
normalized_options`) and reclassified locally in Python, replicating
`classify_option_structure` plus new checks for: non-string option values, Unicode replacement
characters, ASCII control characters (`\x00`–`\x08`, `\x0b`, `\x0c`, `\x0e`–`\x1f`), mojibake
patterns, and trailing-ellipsis truncation signals, run over stem + all four options.

**Precedence order applied (documented, checked top-down):**

1. `INCOMPLETE_OR_EMPTY_STEM` — `raw_stem` null/whitespace-only.
2. `MALFORMED_OR_CORRUPTED_CONTENT` — prior audit's `MALFORMED_OPTIONS` signature, OR any new
   corruption signal (control char / replacement char / mojibake) anywhere in stem or options.
3. `MISSING_OR_INCOMPLETE_OPTION` — prior audit's `MISSING_OPTION` or `DUPLICATE_OPTIONS`
   (an option that is absent, or that collapses on normalization, is "incomplete" at the
   whole-question level regardless of which sub-reason).
4. `MISSING_REQUIRED_IMAGE_OR_FIGURE` — prior audit's `REQUIRES_MANUAL_REVIEW` (empty option
   co-occurring with a figure/diagram/image reference).
5. `SOURCE_MISMATCH_OR_TRUNCATION` — would catch rows that pass 1–4 but diverge from the local
   canonical/R3 record by `staging_id`; see result below (zero rows reached this rule).
6. `COMPLETE_STEM_AND_FOUR_OPTIONS` — passes all of the above.
7. `REQUIRES_MANUAL_REVIEW` — catch-all; zero rows fell through to this rule.

### Results — whole-question categories (sum = 8,928)

| Category | Count | % of 8,928 |
|---|---:|---:|
| `COMPLETE_STEM_AND_FOUR_OPTIONS` | 7,682 | 86.07% |
| `MISSING_OR_INCOMPLETE_OPTION` | 1,175 | 13.16% |
| `MALFORMED_OR_CORRUPTED_CONTENT` | 70 | 0.78% |
| `MISSING_REQUIRED_IMAGE_OR_FIGURE` | 1 | 0.01% |
| `INCOMPLETE_OR_EMPTY_STEM` | 0 | 0.00% |
| `SOURCE_MISMATCH_OR_TRUNCATION` | 0 | 0.00% |
| `REQUIRES_MANUAL_REVIEW` (catch-all) | 0 | 0.00% |
| **Total** | **8,928** | **100.00%** |

Note the live `FOUR_VALID_OPTIONS`-equivalent population is **7,682**, not the prior audit's
7,720 — the difference (38 rows) is exactly the rows now caught by the new corruption-signal
check (embedded ASCII control characters) that the prior, options-shape-only audit did not
screen for. No rows moved in the opposite direction; this pass is strictly stricter, not a
contradiction of the prior counts (`MISSING_OPTION`+`DUPLICATE_OPTIONS` = 1,148+27 = 1,175
reconciles exactly; `MALFORMED_OPTIONS` 32 + 38 newly-caught corruption rows = 70 reconciles
exactly; `REQUIRES_MANUAL_REVIEW` stays 1).

**By exam year:**

| Year | COMPLETE | MISSING/INCOMPLETE OPT | MALFORMED/CORRUPT | MISSING IMAGE |
|---|---:|---:|---:|---:|
| 2020 | 1,985 | 80 | 29 | — |
| 2021 | 3,900 | 216 | 41 | — |
| 2023 | 1,480 | 669 | — | 1 |
| 2024 | 314 | 210 | — | — |
| 2025 | 3 | — | — | — |

Subject attribution is as unreliable as noted in the prior section (most `ANSWER_PENDING`
rows have no `subject` tag); this pass did not re-derive a more reliable subject signal and
defers to the prior section's subject table and caveat.

**Image/figure-dependent questions:** 24 rows (of 8,928) have at least one option text
matching the figure/diagram/image/graph/"shown above/below"/"as shown" pattern (up from the 1
counted in the prior audit, because the prior audit's figure check only fired when combined
with a missing option — this pass counts the pattern independently). **None of the 24 have any
image-asset reference field to resolve against**, because, per the Phase 1 schema inspection,
`pyq.questions` and `pyq.source_files` have no image/asset/figure path column at all. This is
a schema-level gap, not a per-row data defect — it cannot be fixed by cleaning existing rows.

### Source fidelity (canonical/R3 comparison)

All 8,928 `staging_id`s were looked up (not sampled — full join) against a locally-built index
of all 73 canonical/R3 JSONL files (72 per-paper `questions.jsonl` + the R3
`questions.p2_1e_full.jsonl`, 13,405 records indexed total). **Every one of the 8,928
production rows had a matching local `staging_id` record** (zero "no local record" cases), and
**after conservative normalization (Unicode NFKC + whitespace collapse only — no stripping of
symbols/digits/units), all 8,928 production `(raw_stem, option_a..d)` tuples matched their
canonical source record exactly — zero mismatches.** `SOURCE_MISMATCH_OR_TRUNCATION = 0`
is therefore an exact result, not an estimate: the production import pipeline has not
introduced any truncation or divergence from the canonical staging files for this cohort.
Any corruption present (see below) already exists in the canonical source JSONL itself and
was carried through faithfully, not introduced at import time.

### Corruption signal detail (concrete examples)

The 38 newly-flagged rows (`staging_id`s include `f5d9003c-0d80-4d1e-89d0-d4ab265d863f`,
`ec3d0b0f-5963-43e0-88bd-fd866fafb6fd`, `85fd9ba2-30e2-444a-b35b-f03df385636d`,
`19765369-2fde-41e3-b94c-41f644044602`, `744e6b9d-cd73-47e8-8612-feb38d3a3199`) all contain a
literal ASCII SOH control byte (`\x01`) embedded inside a damaged scientific-notation fragment
— e.g. a stem/option segment resembling repeated `\r\n−\r\n−\r\n+\r\n−\r\n=\r\n=\r\n\x01\r\n\x01`
immediately preceding values like `"2.50×10−..."`. This is consistent with an exponent/sign
line being mis-segmented during the original PDF/OCR extraction (each `−`, `+`, `=` token and
a stray control byte landed on its own line), not a database-layer defect — confirmed above to
already exist identically in the canonical JSONL. These rows need individual human review of
the original source PDF to recover the intended exponent; this audit does not attempt to
infer or repair the value.

### Phase 4 — Real application path and publication-gate reasoning

The actual reviewer-facing path (`pyq_answer_review.py`, confirmed above) serves `raw_stem` and
`raw_options` verbatim with no further transformation — so whatever corruption exists in the
column is exactly what a reviewer would see (no additional serializer-level loss or gain to
account for). For the 7,682 `COMPLETE_STEM_AND_FOUR_OPTIONS` rows, this path renders all 4
options losslessly as plain text (control chars aside, which render as invisible/garbled
glyphs in a browser but do not crash rendering).

Reasoning against `publication_gates.py` (no production/dev call made — code-only reasoning,
per the read-only constraint):
- `MISSING_OR_INCOMPLETE_OPTION` and `INCOMPLETE_OR_EMPTY_STEM` rows would already fail
  `structural_ok` (`QuestionBody` `min_length=1` / `min_length=4` on options, uniqueness
  check) if promotion were attempted — same conclusion as the prior audit.
- `MALFORMED_OR_CORRUPTED_CONTENT` rows driven by the prior audit's shape signature
  (inconsistent nullability / mis-segmented duplicate) would also fail `structural_ok`.
  **However, the 38 rows newly found here (embedded control characters in an otherwise
  non-empty, non-duplicate string) would currently PASS `structural_ok`** — `Field(min_length=1)`
  only checks the string is non-empty, not that it is free of control characters or encoding
  damage. This is a real gap: `publication_gates.py` does not reject this defect class. It is
  a finding for the separate admin-review-interface effort, not something this read-only audit
  fixes.
- `MISSING_REQUIRED_IMAGE_OR_FIGURE` rows would fail `structural_ok` on the missing option,
  same as `MISSING_OPTION` — the gate has no awareness of "image-dependent" as a distinct
  reason, it simply rejects the empty option field.

### What was automated vs. needs human review

- Automated (deterministic, re-run and verified in this pass): base population count, option
  presence/distinctness/structural-shape classification, stem emptiness, non-string-value
  detection, control-character/replacement-character/mojibake detection, full canonical/R3
  source-fidelity comparison (exact match, not sampled), image-reference-pattern detection,
  schema inspection for an asset-path column.
- Needs human review: the 70 `MALFORMED_OR_CORRUPTED_CONTENT` rows (32 shape-corrupted + 38
  control-character rows) need a human to consult the original source PDF and decide the
  correct text; the 1 `MISSING_REQUIRED_IMAGE_OR_FIGURE` row and the 24 image-referencing rows
  generally need a human (and, eventually, an added schema field) to resolve or confirm the
  figure is genuinely unavailable; the 1,175 `MISSING_OR_INCOMPLETE_OPTION` rows need the same
  manual repair path already recommended in the prior section. None of this audit's findings
  should be used to auto-repair or auto-promote any row.

### Validation path and limitations

- All SQL was read-only (`COPY ... TO STDOUT`, `SELECT` against `information_schema`), executed
  via `railway run --service NEET-Postgres -- psql ... -f <script.sql>`, no writes.
- No AI-resolution, OCR, migration, import, or backfill was performed or invoked.
- Source-fidelity comparison normalizes whitespace/Unicode form only; it does not re-OCR or
  independently verify the canonical JSONL itself is correct relative to the original PDF —
  only that production matches that intermediate canonical file.
- Control-character/mojibake detection is heuristic pattern-matching, not exhaustive encoding
  validation; it will miss subtler corruption (e.g. a digit silently dropped without leaving a
  control byte) and the "trailing ellipsis" truncation heuristic produced no flags in this
  cohort but is a narrow signal, not a guarantee against truncation.
- "Image/figure-dependent" detection is the same text-pattern heuristic as the prior audit,
  applied only to option text (not stem) for continuity with that methodology; a stem-only
  figure reference with intact options would not be flagged by this pass.
- No live/dev call was made against the actual API endpoint; Phase 4 conclusions are from
  reading `pyq_answer_review.py` and `publication_gates.py` directly, not from an observed
  HTTP response.
- This pass does not evaluate scientific/answer correctness for any row, consistent with the
  constraint that structural/integrity findings never imply answer-key correctness.

---

## 2026-10-22 — TALOS Admin Interface: Individual PYQ Answer Review (feature, not an audit)

This section documents the admin review feature built on top of the structural audits above.
Unlike the preceding sections, it describes *shipped code*, not an audit finding — it is
appended here (rather than a new top-level doc) because eligibility for this queue is exactly
the `FOUR_VALID_OPTIONS` classification defined above, and the feature reuses that
classification's live implementation directly.

### Where to find it

- Backend API: `/api/v1/admin/pyq-answer-review` (GET `/counts`, GET `` list, GET
  `/{question_id}` detail, POST `/{question_id}/review` save, POST `/{question_id}/skip`).
  Router: `app/modules/cms/pyq/api/pyq_answer_review_router.py`. Domain service:
  `app/modules/cms/pyq/pyq_answer_review.py`. Eligibility classification (shared with, and
  kept in sync with, the audit methodology above): `app/modules/cms/pyq/pyq_option_eligibility.py`.
- Required permission: **`pyq.answer_review`** (seeded in `app/modules/identity/seed.py`,
  granted to `SUPER_ADMIN`, `ADMIN`, and `CONTENT_MANAGER` by default). Every endpoint rejects
  unauthenticated requests (401) and authenticated users lacking this permission (403).
  Mutating endpoints (`/review`, `/skip`) also require the existing double-submit CSRF header.

### Eligibility rules

A question is queued for review only if it is `source_key = 'NEET_PYQ_OFFICIAL'`,
`state = 'ANSWER_PENDING'`, **and** `classify_option_structure(raw_options) ==
FOUR_VALID_OPTIONS` — the identical structural check and precedence order documented earlier
in this file (malformed > image-dependent-missing > missing > duplicate > valid). Questions
classified `MISSING_OPTION`, `DUPLICATE_OPTIONS`, or `MALFORMED_OPTIONS` are excluded from the
queue entirely; `REQUIRES_MANUAL_REVIEW` questions are also excluded from this queue (they need
a different, not-yet-built review path for image-dependent content, since no image-asset field
exists on this schema — see the integrity-audit section above). Counts and the queue list are
always computed live against the current database state — never from a cached or hardcoded
total.

### How to record an answer and supporting evidence

On the detail screen the reviewer: (1) selects exactly one of A/B/C/D — never pre-selected or
inferred; (2) picks an `evidence_source_type` (`OFFICIAL_ANSWER_KEY`, `TEXTBOOK_REFERENCE`,
`EXPERT_REVIEW`, or `OTHER`) and, where applicable, an `evidence_locator` (e.g. a document name,
page, or URL) plus an optional free-text review note; (3) **explicitly confirms
`source_consulted_confirmed: true`** — a required boolean distinct from merely picking an
evidence-source-type value, enforced server-side (an omitted or `false` value is rejected with
422, `SOURCE_NOT_CONFIRMED`). Only after all three does the save proceed. "Skip" persists a
`pyq.answer_review.skip` audit-log entry (no `answer_assertions` row, no state change) so a
skipped question is distinguishable from "not yet reviewed" in progress counts, without a new
table.

### Asserted vs. verified — and the deliberate policy here

Elsewhere in this codebase (`pyq.qa_reviews`), a human decision is a gated
APPROVED/REJECTED/NEEDS_INFO review that does not itself assert a specific answer option. This
feature is different and the policy is an explicit product decision, not an oversight: **every
successful single-reviewer save writes `verification_status = 'VERIFIED'`** and transitions the
question straight to `ANSWER_VERIFIED` — regardless of which `evidence_source_type` was picked —
provided `source_consulted_confirmed` was true. This intentionally does not gate verification
strength on the evidence type itself; the explicit confirmation step is the gate. Every written
row still carries `reviewer_user_id`, `reviewed_at`, `evidence_source_type`, and
`evidence_locator` for later audit, so a weakly-sourced (`OTHER`) verification remains fully
traceable and distinguishable from an `OFFICIAL_ANSWER_KEY`-backed one even though both reach
`ANSWER_VERIFIED`.

### Conflict handling

Each reviewer's assertion is stored under its own stable `assertion_source =
f"human_review:{reviewer_user_id}"`, so one reviewer's `VERIFIED` row is never silently
overwritten by another reviewer choosing a different option. If a second reviewer asserts a
**different** option than an existing human-review assertion on the same question, both
assertions are kept, every `human_review:*` row for that question is marked
`verification_status = 'DISPUTED'`, and the question is routed to `ANSWER_CONFLICT` — the same
outcome convention already used by the Gemini backfill worker
(`pyq_gemini_backfill.py`) whenever more than one option is "supported" for a question. A
retry of the exact same reviewer's identical prior selection is a no-op (`idempotent_noop`),
even after the question has since moved to `ANSWER_VERIFIED`/`ANSWER_CONFLICT` as a direct
result of that same earlier save. A stale write (the question's state changed since the queue
was loaded) is rejected with 409 (`STALE_QUESTION_STATE`) and the admin must reload.

### How review-progress counts are calculated

`GET /counts` returns, from a small fixed number of bounded queries (never one query per
question): `eligible` / `requires_manual_review` / `structurally_invalid` (live reclassification
of the current `ANSWER_PENDING` cohort), `total_pending`, `reviewed_by_human` (distinct
questions with a `human_review:*` assertion now in `ANSWER_VERIFIED` or `ANSWER_CONFLICT`), and
`skipped` (distinct questions with a `pyq.answer_review.skip` audit-log entry that do not
already have a `human_review:*` assertion — so a question skipped and later actually reviewed
is no longer counted as skipped).

### Security and audit behaviour

Every list/detail/mutation endpoint requires the `pyq.answer_review` permission; a
nonexistent or non-`NEET_PYQ_OFFICIAL` question id returns 404, never a silent success (IDOR
coverage). All validation (option ∈ {A,B,C,D}, evidence-source-type enum, eligibility, state
concurrency, confirmation flag) is enforced server-side regardless of what the frontend sends.
Every successful save or skip writes to the existing cross-cutting audit trail
(`app/modules/system/services/audit_service.py`, `system.audit_logs`,
actions `pyq.answer_review.save` / `pyq.answer_review.skip`) with reviewer id, timestamp,
question id, and a non-secret metadata summary. This feature never writes to
`cms.content_items` and never calls any publication-gate or promotion code path — publication
and assessment eligibility remain governed entirely by the existing gates described earlier in
this file.

---

## 2026-10-22 — Control-Character Hardening (shared validator fix, closes a real gate gap)

Follow-up to the deeper validation pass above, which found 38 `ANSWER_PENDING` rows with
embedded C0 control characters but noted `QuestionBody`/`QuestionOption`'s `min_length=1` check
would not reject them. This section documents the fix: a **shared** rule in
`app/modules/cms/schemas/content_bodies.py`, not a one-off check in the review module, so every
caller of `QuestionBody`/`QuestionOption` benefits identically.

### Precise finding (re-verified directly, not re-quoted)

A fresh bulk, read-only re-dump and Unicode-category scan of the full live
`NEET_PYQ_OFFICIAL` / `ANSWER_PENDING` cohort (8,928 rows) found exactly **38 affected rows**,
all in **`raw_stem` only — never in any option** (the earlier framing of "option text" was
imprecise; the actual data confirms stem-only). Exactly two control characters occur:
**U+0001 (SOH)**, 38 occurrences across 19 rows, and **U+0004 (EOT)**, 19 occurrences across 19
rows (19 + 19 = 38 affected rows, matching the deeper audit's count exactly).

### Rule implemented and why

`find_prohibited_control_characters()` / `reject_prohibited_control_characters()`
(`app/modules/cms/schemas/content_bodies.py`) flag any character whose `unicodedata.category()`
is `"Cc"` (Unicode's own control-character category) **except** `\t`, `\n`, `\r`, which remain
legitimate. This is deliberately a Unicode-category check, not an ASCII-range check or a
stripping/normalization pass:

- It catches every C0 control code except the three allowed whitespace ones (`\x00`–`\x08`,
  `\x0B`, `\x0C`, `\x0E`–`\x1F`), plus `DEL` (`\x7F`) and the C1 range (`\x80`–`\x9F`) — not just
  the two codepoints (`\x01`, `\x04`) actually observed, since any other C0/C1 byte landing in
  future extraction output is the same corruption class.
- It never flags scientific notation (`2.50×10⁻³`), chemical formula subscripts/superscripts
  (`H₂SO₄`), Greek letters (`α`, `β`, `Δ`), arrows (`→`, `⇌`), the degree symbol (`°`), or any
  other printable Unicode — none of those are category `"Cc"`.
- It never performs ASCII-only restriction or indiscriminate stripping — the rule only rejects
  (raises `ValueError`), it never silently removes characters or rewrites the string.
- Legitimate intentional multi-line options/stems (containing `\n`/`\r`/`\t`) remain valid.

### Call-path verification (traced, not assumed)

Every caller of `QuestionBody`/`QuestionOption` benefits automatically because the rule lives
inside their field validators (`strip_text`, `strip_required_text`), not in a caller-specific
check. Traced call paths: `app/modules/cms/services/publication_gates.py`
(`assert_body_publishable`/`evaluate_question_publication_gates` — the publish gate),
`app/modules/cms/services/content_workflow_service.py` (the create/submit path),
`app/modules/cms/services/factory_candidate_validation.py`,
`app/modules/cms/services/editorial_review_service.py`,
`app/modules/ingestion/services/ingestion_pipeline_service.py`, the acquisition importers under
`app/modules/cms/acquisition/`, and `app/modules/ai/services/question_generator_service.py` —
all call `validate_body("QUESTION", ...)` / `QuestionBody.model_validate(...)` and therefore all
now reject this corruption class identically. Within this feature,
`app/modules/cms/pyq/pyq_option_eligibility.py`'s `classify_option_structure` was updated to
import `find_prohibited_control_characters` directly from `content_bodies.py` (not a
reimplementation) and now also inspects `raw_stem` (previously it only looked at the four
options) — `app/modules/cms/pyq/pyq_answer_review.py`'s four call sites
(`get_queue_counts`, `list_review_queue`, `get_question_review_detail`, `save_answer_review`)
were updated to pass `raw_stem` through.

### Regression tests added

`app/modules/cms/tests/test_content_bodies.py`: reproduces the real production corruption
pattern verbatim (the SOH-before-damaged-exponent fragment), a parametrized test over all C0/DEL
control codes, and must-pass cases for scientific notation, chemical formulas, Greek letters,
arrows, degree symbol, and intentional multi-line options with legitimate whitespace.
`tests/test_pyq_answer_review.py`: confirms `classify_option_structure` now catches stem-level
corruption that clean options alone would have hidden, and that scientific/chemical notation in
options is never misflagged. All new and existing tests pass (57/57 in
`tests/test_pyq_answer_review.py` + `app/modules/cms/tests/test_content_bodies.py`; 557
passed / 3 pre-existing, unrelated failures across the full regression sweep of every module
that imports `content_bodies.py`).

### Full-cohort re-audit under the improved rule (read-only, reuses the real validator code)

Re-run against the same live 8,928-row `ANSWER_PENDING` cohort, reusing
`classify_option_structure` directly against a bulk `COPY` dump (not a reimplemented rule):

| Category | Count (prior audit) | Count (improved rule) |
|---|---:|---:|
| `FOUR_VALID_OPTIONS` | 7,720 | **7,682** |
| `MISSING_OPTION` | 1,148 | 1,148 |
| `DUPLICATE_OPTIONS` | 27 | 27 |
| `MALFORMED_OPTIONS` | 32 | **70** |
| `REQUIRES_MANUAL_REVIEW` | 1 | 1 |
| **Total** | **8,928** | **8,928** |

The 38-row shift reconciles exactly (7,720 − 38 = 7,682; 32 + 38 = 70) with the deeper audit's
earlier finding — confirming both independent passes agree. The 70 `MALFORMED_OPTIONS` rows
(32 original shape-corruption + 38 control-character rows) are **repair candidates for future,
source-backed manual correction only** — none were touched, repaired, re-imported, promoted, or
published by this work.

### Explicitly not done

No production writes, no auto-repair, no deletion, no re-import, no promotion/publication, no
AI-resolution calls, no migrations beyond the already-applied `d2e3f4a5b6c7`. All SQL run
against production was read-only (`COPY ... TO STDOUT`), via the existing `railway run`
read-only pattern.
