# ADR-0027: LanguageService — mechanical detection, normalization, and cleanup for ingested text

## Status
Accepted

## Context
ADR-0019 already made this project's *content* multi-language: a human or
the Question Generator agent picks `"en"` or `"hi"` when authoring, and
`cms.content_items.language` stores that choice. What ADR-0019 never
addressed — because it wasn't its scope — is the *ingestion* pipeline
(ADR-0022–0026), which reads raw text out of source PDFs and, until now,
assumed that text was always English: four separate call sites in
`ingestion_pipeline_service.py` passed the literal `language="en"` to
`ContentWorkflowService.create_item(...)`, regardless of what the source
material actually contained.

This request asked for a small, YAGNI-respecting `LanguageService` closing
that specific gap — English and Hindi only, no plugin framework, no new
languages beyond what's configured. It is not a redesign of ADR-0019's
content-language system; it's the missing piece upstream of it, so the
`language=` value the ingestion pipeline passes is *detected*, not assumed.

(Process note: the request named this ADR-0030. The next real number in
sequence is 0027 — 0028/0029 don't exist. Used 0027.)

## Decision

### 1. Detection is a mechanical script-ratio check, not a model call
`detect_language(text)` counts Devanagari-block characters (U+0900–U+097F)
against Latin alphabetic characters and classifies the ratio into
`en` / `hi` / `mixed`, with a confidence score. This is the same discipline
already used by `knowledge/grounding_check.py` (ADR-0024) — a mechanical
gate, not a model self-assertion — and it needs no new dependency, no API
call, and no training data. It is exactly as accurate as this project
currently needs (distinguishing English, Hindi, and a mix of the two in
NCERT/NEET source material), not a general-purpose language identifier.

### 2. Two cleanup functions, not one, because they serve different purposes
- **`normalize_unicode`** — NFC composition, zero-width character removal,
  whitespace collapsing (preserving newlines, since section-splitting's
  heading regex depends on them). Safe and effectively lossless in meaning.
  Applied when a section's text is *stored* (`IngestionSection.raw_text`),
  because that field is documented as an audit/citation source and
  shouldn't be rewritten more aggressively than "make the encoding
  correct."
- **`clean_text`** — everything `normalize_unicode` does, plus punctuation
  and smart-quote normalization and removal of the `�` replacement-character
  OCR artifact. Applied only at *use* time — building the Knowledge Unit
  structuring prompt (`knowledge_structuring_service.py`) — never persisted
  over the stored citation text.

This split means `raw_text` in the database always matches what the source
PDF actually contained (safe to cite), while the text actually sent to the
AI model is the more aggressively cleaned version (safe to reason over).

### 3. Language metadata lives on `IngestionSection`, not `KnowledgeUnit` or `VisualAsset`
Three new nullable columns — `language_code`, `language_name`,
`language_confidence` — populated once, during `_run_matching`, from the
section's (normalized) `raw_text`. Nullable because historical rows
predate this ADR and aren't backfilled, the same non-backfill precedent
every prior additive migration in this project has used.

`cms.content_items.language` (ADR-0019) is **not** duplicated or replaced.
Every one of the four generation call sites that used to pass the literal
`"en"` now calls `resolve_content_language(section_row.language_code,
settings.supported_language_list)` instead — a deliberately narrow mapping
function, not a general translation of every language code onto every
possible value:
- `"en"` or `"hi"` (whatever is in `supported_languages`) passes through.
- `"mixed"` falls back to `"en"` — ADR-0019's `language` column is a
  serving decision ("show this to an English or Hindi reader"), and mixed
  content can't honestly be either; falling back to English mirrors the
  same "fallback to English, visibly, rather than silently mislabel"
  philosophy ADR-0019 already established for missing translations.
- Anything outside `supported_languages` (a config typo, or a future
  detection value nobody's wired UI for yet) also falls back to `"en"`,
  rather than writing an unsupported code into a column other code paths
  assume is always `"en"`/`"hi"`.

Two of the four generation stages (concept notes, revision sheets)
synthesize across *multiple* matched sections, which could in principle
each detect a different language. Per YAGNI, this ADR uses the first
contributing section's language for the whole synthesized asset — in
practice, every section within one concept or one chapter is the same
language, and building per-section-language splitting for a case that has
never been observed would be exactly the premature generality this project
has repeatedly declined to build elsewhere.

### 4. Supported languages come from configuration, not a hardcoded list
`Settings.supported_languages` (default `"en,hi"`, comma-separated —
matching the existing `cors_origins`/`cors_origin_list` pattern rather than
inventing a new settings shape) with a `supported_language_list` property.
Adding a third language later is: a config change, a new entry in
`LANGUAGE_NAMES`, and whatever new detection logic that language's script
needs in `detect_language` — not a change to any calling code, and
specifically not a plugin framework. (The architecture review that
preceded this ADR named "no plugin framework until a second real
implementation exists" as the governing principle; English + Hindi, both
shipped and real, already satisfy that for language — a plugin framework
for exactly two known, real cases would still be more machinery than the
problem needs.)

### 5. Translation: an interface, deliberately not implemented
`TranslationService` (a `Protocol`) declares `translate(text,
target_language)`. The only implementation, `NotImplementedTranslationService`,
returns the `NotImplemented` singleton — not a raised exception, per the
explicit scope of this request: nothing in the system calls this today,
there's no error condition to signal, only an unimplemented one. A real
implementation (an MT API call, or an AIGateway prompt) is separately
scoped, future work, triggered by an actual need to translate content
rather than only detect its language.

## Risks
- **Script-ratio detection is a heuristic**, not a validated classifier —
  it will misclassify short strings with too little alphabetic signal
  (numbers, symbols, an equation-only line) as low-confidence English,
  which is the documented, intentional default rather than a false
  positive to chase.
- **First-section-language synthesis** (concept notes, revision sheets) is
  a real simplification if a future document genuinely mixes languages
  across sections within one concept — not observed yet, and not solved
  speculatively per §3.

## Tests
- Unit (`test_language_service.py`, 16 tests): English/Hindi/mixed
  detection with real Devanagari and Latin text, confidence behavior at
  and near the classification boundary, Unicode normalization (NFC
  composition, zero-width stripping, whitespace collapsing with paragraph
  breaks preserved), punctuation/OCR-artifact cleanup (including the exact
  `�` mangled-apostrophe case `pdf_extraction_service.py` already names),
  the translation stub, and `resolve_content_language`'s fallback rules.
- Integration (`test_language_processing_pipeline.py`): the real pilot PDF
  (Current Electricity, English NCERT text) run through real extraction +
  matching confirms every section detects as `"en"` with confidence > 0.8
  — not asserted from a synthetic fixture.
- Full backend suite: 131/131 passing (up from 114 before this ADR).

## Consequences
The ingestion pipeline's `language=` value is now a real detection result,
not a hardcoded literal, for all four generated content types. Nothing
about ADR-0019's existing content-language system changed — this ADR feeds
it a better input. Adding Hindi-source-material ingestion (a Hindi-medium
NCERT PDF, once one exists in this project) requires no code change: the
same `detect_language` call already classifies it correctly, and
`resolve_content_language` already passes `"hi"` through since it's in the
default `supported_languages` list.
