"""Subsection-boundary detector for the MTG Fingertips Biology book's
consolidated "Hints & Explanations" OCR block (FACTORY-MTGHINTS-20261018).

Context: the book's answer keys are not interleaved with its MCQs -- they
are consolidated into one continuous back-matter block, itself split into
the same subsections every chapter's MCQ section uses (MCQs Corner, Exam
Scorer, NCERT Exemplar Problems, Assertion & Reason Questions, Statement
Based Questions, Matching Type Questions, Case Based Questions, Figure
Based Questions, Multidimensional Questions, Exam Archive) -- each
restarting its own "1., 2., 3., ..." numbering. A question's hint entry can
therefore only be identified correctly by (subsection, number), never by
number alone: two different subsections both have their own "Q14", and
they are different questions with different answers (confirmed directly in
docs/quality/... Phase 2 mapping task, 2026-10-18 -- Excretory Products
MCQs Corner Q44 matches content-wise to an Exam-Scorer-subsection entry
numbered "9", not to any entry numbered "44").

No OCR is performed here. Input is already-OCR'd text (from
pyq_image_pipeline.ocr_extractor, reused as-is) -- this module only parses
structure out of that text. No network calls, no LLM calls, no database
writes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# --- subsection heading detection ------------------------------------------
#
# OCR noise is heavy in this block (e.g. "Exam: Scorer", "pints &
# Explanations" for "Hints & Explanations", "ent Based Questions" for a
# truncated "Statement Based Questions"). Patterns below are deliberately
# loose on whitespace/punctuation between words but still require the
# distinguishing word roots, so they don't false-positive on prose that
# merely mentions "exam" or "case" in passing.
SUBSECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("MCQS_CORNER", re.compile(r"MC[Qq0][Ss]?\s*Co[r~]+ner", re.I)),
    ("EXAM_SCORER", re.compile(r"Exam[:\s]*Scorer", re.I)),
    ("NCERT_EXEMPLAR", re.compile(r"NCERT\s*Exemplar", re.I)),
    ("ASSERTION_REASON", re.compile(r"Assertion\s*&?\s*Reason\s*Questions?", re.I)),
    ("STATEMENT_BASED", re.compile(r"[A-Za-z]*ent\s*Based\s*Questions?", re.I)),
    ("MATCHING_TYPE", re.compile(r"Match(?:ing)?\s*Type\s*Questions?", re.I)),
    ("CASE_BASED", re.compile(r"Case\s*Based\s*Questions?", re.I)),
    ("FIGURE_BASED", re.compile(r"Figure\s*Based\s*Questions?", re.I)),
    ("MULTIDIMENSIONAL", re.compile(r"Multidimensional\s*Questions?", re.I)),
    ("EXAM_ARCHIVE", re.compile(r"Exam\s*Archive", re.I)),
]

# A chapter boundary inside the consolidated hints block. OCR of "Chapter
# 10 : Cell Cycle and Cell Division" degrades heavily (seen directly:
# "(10 ) tert Cycle and Cell Divis"), so this is intentionally permissive --
# it only needs to catch "a new chapter's MCQs Corner just started", not
# read the chapter name reliably. The chapter NAME is supplied externally
# by the caller (who already knows which chapter's range they asked for);
# this pattern exists only to stop a chapter-10 "MCQs Corner Q1" from being
# silently merged into chapter 9's own "MCQs Corner" run.
_CHAPTER_HEADING_RE = re.compile(r"\(?\d{1,2}\s*\)?\s*[A-Za-z]{3,}\s*Cycle|Chapter\s*\d{1,2}\s*:", re.I)

# An answer entry: "<n>. (<letter>)" optionally followed by ": <explanation
# text up to the next entry>". Requires the parenthesised single letter a-d
# immediately after the number + delimiter, which is specific enough not to
# false-positive on ordinary prose numbering (e.g. a numbered list inside an
# explanation uses "(i)", "(ii)" roman-numeral style, not "(a)".."(d)").
# The delimiter accepts "." but also "," and ";" -- confirmed directly in
# this book's own OCR (e.g. "14, (b) : The amino acid tryptophan...", where
# Tesseract rendered the period after "14" as a comma): the same tolerance
# already established in pyq_image_pipeline/ocr_extractor.py's _Q_RE for
# exactly this font/scan behaviour.
_ENTRY_RE = re.compile(r"(\d{1,3})\s*[.,;]\s*\(([a-dA-D])\)")

# Reset tolerance: a legitimate continuation of the same subsection's
# numbering across a page-half boundary never decreases; it may skip ahead
# (terse runs like "15. (b) 16. (b)" are still increasing). A genuine reset
# to a new subsection always drops by more than this, OR coincides with a
# detected heading. Anything in between (e.g. the next number is only 1-2
# below the running max) is OCR noise in the number itself, not a reset --
# treated as a continuation with reduced confidence rather than guessed.
_RESET_DROP_THRESHOLD = 3


@dataclass
class HintEntry:
    subsection: str | None  # one of SUBSECTION_PATTERNS' keys, or None if never resolved
    number: int
    answer_letter: str
    explanation_snippet: str
    source_ref: str  # caller-supplied page/half reference, e.g. "PDF555-LEFT"
    confidence: str  # "high" (heading-anchored), "low" (reset-inferred), "unresolved" (no anchor at all)
    char_offset: int


@dataclass
class SegmentResult:
    entries: list[HintEntry] = field(default_factory=list)
    headings_found: list[tuple[str, int]] = field(default_factory=list)
    unresolved_resets: list[int] = field(default_factory=list)


def _find_headings(text: str) -> list[tuple[int, str]]:
    """Returns (char_offset, subsection_key) for every heading match,
    position-sorted. Overlapping matches at the same spot keep only the
    first pattern that matched (patterns are mutually distinguishing by
    construction -- no two are expected to match the same span)."""
    hits: list[tuple[int, str]] = []
    for key, pat in SUBSECTION_PATTERNS:
        for m in pat.finditer(text):
            hits.append((m.start(), key))
    hits.sort(key=lambda h: h[0])
    return hits


def segment_hints_text(text: str, *, source_ref: str) -> SegmentResult:
    """Parse one OCR'd half-page (or larger block) of the consolidated
    Hints & Explanations text into (subsection, number, answer) entries.

    Never guesses a subsection for an entry it cannot anchor -- an entry
    reached before any heading has been seen, or after a numbering drop
    with no nearby heading, is recorded with confidence 'low' or
    'unresolved' rather than silently assigned to the wrong subsection."""
    result = SegmentResult()
    headings = _find_headings(text)
    result.headings_found = [(key, pos) for pos, key in headings]

    current_subsection: str | None = None
    last_number = 0
    last_was_high_confidence_anchor = False

    entry_matches = list(_ENTRY_RE.finditer(text))
    heading_idx = 0

    for m in entry_matches:
        pos = m.start()
        # advance to the last heading at or before this entry's position
        while heading_idx < len(headings) and headings[heading_idx][0] <= pos:
            current_subsection = headings[heading_idx][1]
            last_number = 0
            last_was_high_confidence_anchor = True
            heading_idx += 1

        number = int(m.group(1))
        letter = m.group(2).lower()
        confidence = "high" if last_was_high_confidence_anchor else "low"

        if number <= last_number - _RESET_DROP_THRESHOLD or (last_number > 0 and number < last_number and number <= 2):
            # Looks like a reset the heading scan didn't anchor (a subsection
            # heading OCR likely failed entirely for this block). Do not
            # invent a subsection name -- mark unresolved instead of
            # silently continuing the previous one.
            current_subsection = None
            confidence = "unresolved"
            result.unresolved_resets.append(pos)
        elif number < last_number:
            # A small non-monotonic wobble (OCR digit misread) -- kept in
            # the current subsection but flagged lower-confidence, never
            # silently treated as equal to a clean continuation.
            confidence = "low" if confidence == "high" else confidence

        last_number = max(last_number, number)
        last_was_high_confidence_anchor = False  # only the entry immediately after a heading gets 'high' for free

        explanation_end = min(len(text), m.end() + 220)
        snippet = text[m.end():explanation_end].strip()

        result.entries.append(
            HintEntry(
                subsection=current_subsection,
                number=number,
                answer_letter=letter,
                explanation_snippet=snippet,
                source_ref=source_ref,
                confidence=confidence,
                char_offset=pos,
            )
        )

    return result


def segment_multiple(blocks: list[tuple[str, str]]) -> SegmentResult:
    """Run segment_hints_text over several (text, source_ref) blocks in
    page order and concatenate results, carrying heading/number state
    across block boundaries the same way a single contiguous OCR pass
    would (so a subsection that starts on one half-page and continues on
    the next isn't wrongly reset)."""
    combined = SegmentResult()
    carried_subsection: str | None = None
    carried_last_number = 0
    for text, ref in blocks:
        res = segment_hints_text(text, source_ref=ref)
        # Re-anchor the first entries of this block to the carried
        # subsection if this block had no heading of its own before them
        # and the numbering plausibly continues.
        for e in res.entries:
            if e.confidence != "high" and carried_subsection is not None:
                if e.number == carried_last_number + 1 or e.number > carried_last_number:
                    e.subsection = e.subsection or carried_subsection
            carried_subsection = e.subsection or carried_subsection
            carried_last_number = max(carried_last_number, e.number) if e.subsection == carried_subsection else e.number
        combined.entries.extend(res.entries)
        combined.headings_found.extend(res.headings_found)
        combined.unresolved_resets.extend(res.unresolved_resets)
    return combined


# --- content-based matching (never by number alone) ------------------------

@dataclass
class MatchResult:
    status: str  # "CONFIRMED" | "AMBIGUOUS" | "NOT_FOUND"
    entry: HintEntry | None
    candidates_considered: int
    reason: str


def match_question_to_hint(
    entries: list[HintEntry],
    *,
    subsection: str,
    number: int,
    content_keywords: list[str],
) -> MatchResult:
    """Find the hint entry for (subsection, number) and require at least
    one of content_keywords to appear in its explanation text -- content
    is the deciding signal, not the number. If no entry in the requested
    subsection matches but the number matches in a DIFFERENT subsection
    whose content keywords hit, that is reported as AMBIGUOUS (a real,
    audit-worthy case), never silently accepted as the target subsection."""
    same_subsection_same_number = [
        e for e in entries if e.subsection == subsection and e.number == number
    ]
    any_subsection_same_number = [e for e in entries if e.number == number]

    def _content_hits(e: HintEntry) -> bool:
        low = e.explanation_snippet.lower()
        return any(kw.lower() in low for kw in content_keywords)

    exact_content_matches = [e for e in same_subsection_same_number if _content_hits(e)]
    if len(exact_content_matches) == 1:
        return MatchResult("CONFIRMED", exact_content_matches[0], len(any_subsection_same_number), "subsection+number+content all agree")
    if len(exact_content_matches) > 1:
        return MatchResult("AMBIGUOUS", None, len(exact_content_matches), "multiple entries share subsection, number AND content keyword")

    other_subsection_content_matches = [e for e in any_subsection_same_number if e not in same_subsection_same_number and _content_hits(e)]
    if other_subsection_content_matches:
        return MatchResult(
            "AMBIGUOUS",
            other_subsection_content_matches[0],
            len(any_subsection_same_number),
            f"number {number} matches content only in a different subsection "
            f"({other_subsection_content_matches[0].subsection!r}), not in the requested one ({subsection!r})",
        )

    if same_subsection_same_number:
        return MatchResult("AMBIGUOUS", None, len(same_subsection_same_number), "number+subsection found but no content keyword matched -- not confirmed")

    return MatchResult("NOT_FOUND", None, 0, "no entry found for this number in any subsection")
