"""Regression tests for the MTG Fingertips Biology Hints & Explanations
subsection-boundary detector (scripts/pyq_pdf_extract/mtg_hints_segmenter.py).

Fixtures are real OCR output captured directly from the book during the
Phase 2 answer-key mapping task (2026-10-18) -- not synthetic text. No OCR
runs in this test; it only exercises the parser against already-captured
text, per the "no full-book OCR in this task" constraint.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from pyq_pdf_extract.mtg_hints_segmenter import (  # noqa: E402
    match_question_to_hint,
    segment_hints_text,
)

FIXTURES = BACKEND_ROOT / "scripts" / "pyq_pdf_extract" / "fixtures" / "mtg_biology_hints_ocr"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def biomolecules_entries():
    text = _load("biomolecules_pdf555_557.txt")
    return segment_hints_text(text, source_ref="PDF555-557").entries


@pytest.fixture(scope="module")
def respiration_entries():
    text = _load("respiration_pdf563.txt")
    return segment_hints_text(text, source_ref="PDF563").entries


@pytest.fixture(scope="module")
def excretory_entries():
    text = _load("excretory_pdf574_576.txt")
    return segment_hints_text(text, source_ref="PDF574-576").entries


# --- known-case regressions -------------------------------------------------

def test_biomolecules_q14_tryptophan_subsection_is_genuinely_unresolvable(biomolecules_entries):
    """MCQs Corner Q14: 'vitamin nicotinamide can be synthesised ... from
    tryptophan'. The Phase 2 report (2026-10-18) labelled this hint entry
    'MCQs Corner' by proximity alone, without verifying the subsection.
    Running the detector on the exact same OCR text shows why that
    labelling was never actually verifiable: in this region the printed
    page packs two independently-numbered runs into what this tool reads
    as one column (a 'MCQs Corner' heading for the NEXT chapter appears
    upstream, then the numbering visibly interleaves -- 8, 1, 10, 2, 4, 12,
    6, 13, 14 -- which is this detector correctly recognising a subsection
    reset with no heading of its own to anchor to, not a bug). The honest,
    correct output is 'unresolved', for BOTH subsection guesses -- this
    test asserts that neither a 'MCQs Corner' nor an 'Exam Archive' claim
    for this entry can be confirmed, and that the content match itself
    (independent of subsection) is nonetheless real."""
    for guessed_subsection in ("MCQS_CORNER", "EXAM_ARCHIVE", "STATEMENT_BASED"):
        result = match_question_to_hint(
            biomolecules_entries,
            subsection=guessed_subsection,
            number=14,
            content_keywords=["tryptophan", "nicotinamide"],
        )
        assert result.status != "CONFIRMED", (
            f"subsection={guessed_subsection!r} must not be confirmable for this entry -- "
            "its true subsection is unresolved in this OCR, not any specific label"
        )

    content_matches = [
        e for e in biomolecules_entries
        if e.number == 14 and "tryptophan" in e.explanation_snippet.lower()
    ]
    assert len(content_matches) == 1
    assert content_matches[0].subsection is None
    assert content_matches[0].confidence == "low"


def test_respiration_q11_number_is_ocr_destroyed_not_a_detector_bug(respiration_entries):
    """MCQs Corner Q11 ('Glycolysis ... occurs in cytoplasm') is real,
    present content in this fixture -- but Tesseract rendered its leading
    '11.' as 'Hp' (no recognisable digit at all), confirmed by direct
    inspection of the raw fixture text. No number-matching strategy, this
    detector's or any other's, can recover a number that was never OCR'd
    as a number. This is a genuine, irrecoverable OCR failure for this one
    entry, not a flaw in the segmenter's regex or reset logic -- and it
    must show up as NOT_FOUND via structured matching rather than being
    silently papered over."""
    structured = match_question_to_hint(
        respiration_entries,
        subsection="MCQS_CORNER",
        number=11,
        content_keywords=["glycolysis", "cytoplasm"],
    )
    assert structured.status == "NOT_FOUND"

    # The content is recoverable only by raw-text keyword search, never by
    # structured (subsection, number) lookup -- this gap is the reportable
    # limitation, not a hidden success.
    raw_text = _load("respiration_pdf563.txt")
    assert "cytoplasm" in raw_text.lower()
    assert "glycolysis durin" in raw_text.lower()  # OCR-truncated "during"


def test_excretory_q44_renin_is_not_confirmable_by_mcqs_corner_subsection_alone(excretory_entries):
    """The Phase 2 report's deliberately-adversarial case: MCQs Corner Q44
    ('fall in GFR activates ... release renin') has real matching content
    at a hint entry numbered '9', not '44' -- and that '9' entry's own
    subsection anchor is unreliable in this OCR (the nearest detected
    'Exam Scorer' heading in this fixture appears textually AFTER this
    entry, not before it, because the subsection label sits in a sidebar
    the column-OCR reading order does not place correctly relative to the
    entries it labels). The detector must NOT claim MCQS_CORNER confidently
    for this entry -- requiring subsection='MCQS_CORNER' must fail to
    confirm by number 44 (nothing exists there) and must not silently
    accept the number-9 entry as if it were the real target."""
    result_by_number_44 = match_question_to_hint(
        excretory_entries,
        subsection="MCQS_CORNER",
        number=44,
        content_keywords=["renin", "gfr"],
    )
    assert result_by_number_44.status == "NOT_FOUND"

    # The real content lives at number 9, in some subsection -- never
    # accept it as MCQS_CORNER without evidence.
    renin_entries = [e for e in excretory_entries if e.number == 9 and "renin" in e.explanation_snippet.lower()]
    assert renin_entries, "fixture must contain the real renin/GFR entry numbered 9"
    assert renin_entries[0].subsection != "MCQS_CORNER", (
        "this entry's true subsection is NOT MCQs Corner -- a detector that "
        "labelled it MCQS_CORNER would be fabricating an anchor this OCR "
        "does not support"
    )


def test_biomolecules_block_detects_mcqs_corner_and_statement_based_headings(biomolecules_entries):
    subsections_seen = {e.subsection for e in biomolecules_entries if e.subsection}
    assert "MCQS_CORNER" in subsections_seen
    # Statement Based Questions heading is present in this fixture (556 RIGHT)
    assert "STATEMENT_BASED" in subsections_seen or "MATCHING_TYPE" in subsections_seen


def test_confidence_levels_are_only_high_low_or_unresolved(biomolecules_entries, respiration_entries, excretory_entries):
    allowed = {"high", "low", "unresolved"}
    for entries in (biomolecules_entries, respiration_entries, excretory_entries):
        for e in entries:
            assert e.confidence in allowed


def test_no_entry_is_assigned_a_subsection_without_either_a_heading_or_a_carried_state(biomolecules_entries):
    """An entry with confidence='unresolved' must have subsection=None --
    the detector must never attach a subsection label it isn't confident
    about."""
    for e in biomolecules_entries:
        if e.confidence == "unresolved":
            assert e.subsection is None
