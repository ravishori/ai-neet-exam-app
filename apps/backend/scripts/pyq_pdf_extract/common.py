"""Shared schema, hashing, and segmentation primitives for the two
NEET-study-material PDF extractions (FACTORY-PYQPDF-20261018):

  - "33 Years NEET-AIPMT Chapterwise Solutions - Biology 2020.pdf" (MTG
    Learning Media), 485 pages, text-native, per-chapter-resetting
    question numbering (38 chapters: 22 Class XI + 16 Class XII).
  - "neet_pyp.pdf" ("NEET 2025 Chapterwise Index" / "NEET Solved Paper -
    2025"), 34 pages, text-native but AES-256 encrypted (readable only
    because it carries no *open* password), globally-numbered 1-180
    questions across Physics/Chemistry/Biology.

No AI/LLM calls anywhere in this package. No database writes. No network
calls. Nothing here invents missing content -- every uncertainty is
surfaced via `review_flags` / `extraction_status`, never silently
resolved, matching the discipline already established in
`scripts/pyq_image_pipeline/extractor.py`.

--- PROVENANCE / RIGHTS STATUS (read before reusing this output) --------

The user was told directly, and explicitly acknowledged, that both source
PDFs show real evidence of restricted/uncertain distribution rights:

  - The 33-Years-Biology PDF's very first line of extracted text is
    "Telegram @unacademyplusdiscounts" -- a watermark pattern
    characteristic of unauthorized/piracy-channel redistribution of a
    commercial coaching-book title (publisher: MTG Learning Media (P)
    Ltd., per the PDF's own copyright page, PDF page 3). This copy did
    not demonstrably come through a legitimate purchase channel.
  - neet_pyp.pdf carries PDF Standard V5 R6 256-bit AES encryption (a
    publisher-applied DRM/copy-protection flag). It is readable here only
    because it has no *open* password -- the encryption flag itself is
    evidence the publisher restricted copying/printing, not evidence that
    redistribution or reuse was authorized.

Every record produced from either file below carries a `rights_status`
field for exactly this reason, and the output is NOT cleared for
publishing, redistribution, or commercial reuse -- local, personal,
non-redistributed database use only. This statement is repeated verbatim
in every manifest/report this package writes; never dropped downstream.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PIPELINE_VERSION = "pyq_pdf_extract_v1_20261018"

RIGHTS_STATUS_33YEARS = "UNVERIFIED_POSSIBLE_UNAUTHORIZED_SOURCE_WATERMARK"
RIGHTS_STATUS_NEET_PYP = "DRM_PROTECTED_SOURCE_PERSONAL_USE_ONLY"

RIGHTS_RESTATEMENT = (
    "This output is for local, personal, non-redistributed database use "
    "only -- NOT cleared for publishing, redistribution, or commercial "
    "reuse. Source 1 (33 Years NEET-AIPMT Chapterwise Solutions - Biology "
    "2020.pdf) carries a 'Telegram @unacademyplusdiscounts' watermark on "
    "its first page, a pattern characteristic of unauthorized/piracy-"
    "channel distribution of this MTG Learning Media commercial coaching "
    "title; rights_status=UNVERIFIED_POSSIBLE_UNAUTHORIZED_SOURCE_WATERMARK "
    "on every record from it. Source 2 (neet_pyp.pdf) carries PDF Standard "
    "V5 R6 256-bit AES encryption (publisher DRM/copy-protection), readable "
    "here only because it has no open password, not because reuse was "
    "authorized; rights_status=DRM_PROTECTED_SOURCE_PERSONAL_USE_ONLY on "
    "every record from it."
)


def extract_page_text_column_aware(page: Any) -> str:
    """PyMuPDF's plain `page.get_text()` reads text BLOCK-BY-BLOCK in the
    order MuPDF happens to emit them, which is NOT reliably top-to-bottom
    reading order on a two-column page -- confirmed by direct inspection
    on neet_pyp.pdf's physics pages (page.get_text("blocks") shows Q23-29
    (left column, lower half) emitted AFTER Q30-35 (right column, upper
    half), splicing the right column's questions into the middle of the
    left column's own sequence). Reconstructs reading order by splitting
    blocks into left/right halves using each block's own x0 against the
    page's horizontal midpoint, sorting each half top-to-bottom by y0,
    and concatenating left-half-then-right-half. A genuinely single-
    column page is unaffected (every block's x0 lands left of the
    midpoint, so the "right half" is empty and this reduces to a plain
    y0 sort -- i.e. normal reading order)."""
    blocks = page.get_text("blocks")
    mid_x = page.rect.width / 2
    left = sorted((b for b in blocks if b[0] < mid_x), key=lambda b: b[1])
    right = sorted((b for b in blocks if b[0] >= mid_x), key=lambda b: b[1])
    return "".join(b[4] for b in left) + "".join(b[4] for b in right)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_for_dedup(text: str | None) -> str:
    """Lowercase, whitespace-collapsed normalization used only for
    duplicate detection -- never written back into the stored stem."""
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip().lower()
    t = re.sub(r"[^\w\s]", "", t)
    return t


def identity_key(*parts: str) -> str:
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


@dataclass
class Option:
    label: str
    text: str


@dataclass
class ExtractedRecord:
    """Common output record shape for both books. Field list matches the
    schema designed in docs/quality/neet_mcq_pdf_extraction_33years_and_pyp_20261018.md
    Step 2 (stable id, stem, options, answer, explanation, subject,
    chapter/topic, source metadata, extraction provenance, rights
    status, review flags)."""

    id: str
    identity_key: str
    source_file: str
    source_file_sha256: str
    source_book_title: str
    source_publisher: str | None
    source_edition: str | None
    pdf_page_number: int
    printed_page_number: str | None
    question_number_raw: str | None
    global_sequence_in_file: int
    subject: str | None
    class_level: str | None
    chapter: str | None
    topic: str | None
    stem_text: str | None
    options: list[dict] | None  # [{"label": "a", "text": "..."}]
    answer_raw: str | None
    explanation_text: str | None
    exam_name: str | None
    exam_year: int | None
    extraction_method: str  # text_native | ocr
    extraction_status: str  # COMPLETE | NEEDS_REVIEW
    extraction_confidence: float
    rights_status: str
    review_flags: list[str] = field(default_factory=list)
    raw_block_text: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())


def options_list(opts: dict[str, str] | None) -> list[dict] | None:
    if opts is None:
        return None
    return [{"label": k, "text": v} for k, v in opts.items()]


def option_integrity_flags(opts: list[dict] | None) -> list[str]:
    flags: list[str] = []
    if opts is None:
        return flags
    if len(opts) != 4:
        flags.append(f"option_count_not_4_got_{len(opts)}")
    for o in opts:
        if not o.get("text") or len(o["text"].strip()) == 0:
            flags.append(f"option_{o.get('label')}_empty")
    return flags


# --- generalized option-marker regex -----------------------------------
#
# Discovered by direct inspection (2026-10-18) that MTG's InDesign export
# does NOT consistently put a literal tab between an option's closing
# paren and its text -- short options are frequently packed two-per-line
# with a tab before the SECOND marker but only a bare space after it
# (e.g. "(a)\t ss RNA \t\n(b) ds RNA"). The marker itself must therefore be
# preceded by start-of-string, a newline, or a tab (never a bare space,
# which would false-positive inside running prose like "word (a) word"),
# and followed by a tab OR a single space (never zero -- that would merge
# into the option text).
# Python's `re` lookbehind must be fixed-width, so the "preceded by \n or
# \t, possibly with one extra run-together space/tab before the paren"
# cases (both confirmed by direct inspection -- see module docstring)
# are matched as a consumed (non-lookbehind) leading group instead. This
# makes the match start 1-2 chars earlier than the "(" itself when that
# extra delimiter is present; callers only use these matches as slice
# boundaries into text that gets `.strip()`-ed anyway, so the couple of
# consumed whitespace chars are harmless.
OPT_ALPHA_RE = re.compile(r"(?:^|[\n\t])[\t ]?\(([a-d])\)[\t ]")

# An "answer-entry" block (used both for the compact/quick answer list and
# for the detailed, explained answer key) starts with a bare option-letter
# marker -- optionally preceded by leading whitespace left over from the
# number's own tab/space delimiter -- and optionally continues with a
# ":"-introduced explanation. Multi-letter answers (e.g. "(a,b)", seen once
# in the 33-years book) are captured whole rather than forced to a single
# letter.
ANSWER_ENTRY_RE = re.compile(r"^[\t \n]*\(([a-d](?:\s*,\s*[a-d])*)\)\s*:?\s*")


def classify_block(block: str) -> tuple[str, list[re.Match]]:
    """Classify a numbered block as QUESTION (>=4 distinct option letters
    found) or ANSWER_ENTRY (starts with a single bare option-letter
    marker) or OTHER (neither -- e.g. a table-of-contents line, a stray
    false-positive numeral inside prose). Never guesses; OTHER is a
    legitimate, explicitly-flagged outcome, not an error."""
    opt_matches = list(OPT_ALPHA_RE.finditer(block))
    letters_seen = []
    seen = set()
    for m in opt_matches:
        if m.group(1) not in seen:
            seen.add(m.group(1))
            letters_seen.append(m)
    if len(seen) >= 4:
        return "QUESTION", letters_seen
    if ANSWER_ENTRY_RE.match(block):
        return "ANSWER_ENTRY", []
    return "OTHER", []


@dataclass
class NumberedMatch:
    number: int
    raw: str
    match: re.Match
    run_id: int = -1


def segment_into_runs(
    matches: list[re.Match], *, max_gap: int = 5, min_confirmed_run_len: int = 8
) -> tuple[list[list[NumberedMatch]], list[NumberedMatch]]:
    """Group a flat list of `^<n>.` regex matches into ascending runs.

    A genuine chapter/section restart (both source books reuse 1..N
    numbering for their question stream, their compact answer-key
    stream, and [33-years book only] their detailed answer-key stream,
    back to back) looks, locally, exactly like a numbered sub-list
    EMBEDDED inside a single question's own stem -- e.g. a "match the
    following" or multi-statement question that itself contains a
    "1. ... 2. ... 3. ... 4. ... 5. ..." list. Both start with a "1."
    appearing right after some unrelated last-kept number > 1.

    Confirmed by direct inspection (2026-10-18, 33-years-Biology book,
    "Digestion and Absorption" chapter): treating EVERY such "1." as an
    unconditional reset corrupts the run structure two ways at once --
    (a) the embedded sub-list's few items form a bogus tiny "run" that
    then silently swallows the real compact/detailed answer-key run
    lookup downstream (nothing later can tell the fake run from a real
    one), AND (b) worse, the real questions immediately AFTER the
    embedded sub-list (e.g. Q76-Q92, following a stem whose own "1..5"
    sub-list stalled the sequence at 5) can no longer continue the
    original run (76 is far outside 5's max_gap window) and are DROPPED
    as noise entirely, even though they are real, well-formed questions.

    Fix: a reset-to-1 is only ACCEPTED once the tentative new run
    actually reaches `min_confirmed_run_len` members (real chapters run
    to dozens of questions; the embedded-sub-list false positives
    observed were all well under 8 items). Until confirmed, the
    ORIGINAL run is kept alive in parallel so a later number that
    plausibly continues IT (not the tentative reset) reattaches there
    instead of being dropped. If the tentative run never reaches the
    confirmation threshold before the document ends, it is abandoned
    entirely -- its members are returned separately as `orphaned`
    (never silently discarded, never silently merged into the wrong
    run; the caller decides how to report them)."""
    runs: list[list[NumberedMatch]] = []
    orphaned: list[NumberedMatch] = []
    active: list[NumberedMatch] | None = None
    active_last: int | None = None
    pending: list[NumberedMatch] | None = None
    pending_last: int | None = None

    for m in matches:
        try:
            num = int(m.group(1).replace(",", "").split(",")[0])
        except (ValueError, AttributeError):
            continue
        raw = m.group(1)
        nm = NumberedMatch(num, raw, m)

        if active is None:
            active = [nm]
            active_last = num
            continue

        if pending is not None and pending_last < num <= pending_last + max_gap:
            pending.append(nm)
            pending_last = num
            if len(pending) >= min_confirmed_run_len:
                runs.append(active)
                active, active_last = pending, pending_last
                pending, pending_last = None, None
            continue

        if active_last < num <= active_last + max_gap:
            if pending is not None:
                orphaned.extend(pending)
                pending, pending_last = None, None
            active.append(nm)
            active_last = num
            continue

        if num == 1 and active_last > 1:
            if pending is not None:
                orphaned.extend(pending)
            pending = [nm]
            pending_last = num
            continue

        # neither a continuation of the active run, a continuation of a
        # not-yet-confirmed pending reset, nor a fresh reset candidate --
        # noise, dropped. Recorded in the overall raw-match-count vs
        # run-member-count diff the caller reports, never hidden.

    if active is not None:
        runs.append(active)
    if pending is not None:
        orphaned.extend(pending)

    for idx, run in enumerate(runs):
        for nm in run:
            nm.run_id = idx
    return runs, orphaned


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def record_to_dict(r: ExtractedRecord) -> dict[str, Any]:
    return asdict(r)
