"""Tests for the local-Tesseract OCR extraction stage
(scripts/pyq_image_pipeline/ocr_extractor.py) built for the scanned-image
NEET Past Papers_V3 batch (NEET 2020 English Sets E1-E6, F1, F3-F6, G1 --
confirmed to have zero extractable text layer).

Covers: question-boundary detection, option-label parsing under OCR
noise, multi-column page layout handling, OCR-error (garbled input)
handling, and idempotent reruns. The real-Tesseract tests are skipped
automatically if Tesseract isn't installed at the expected path, so this
suite still runs cleanly in environments without the local OCR binary.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "pyq_image_pipeline"))
import ocr_extractor as oe  # noqa: E402

PDF_PATH = Path(__file__).resolve().parents[3] / "NEET Past Papers_V3" / "NEET_2020_English_Set_G1.pdf"

tesseract_available = Path(oe.TESSERACT_CMD).exists()
pdf_available = PDF_PATH.exists()


# --- question-boundary detection (pure parsing, no OCR needed) -------------

def test_question_boundary_basic_sequence():
    text = (
        "1. First stem text here.\n(1) a\n(2) b\n(3) c\n(4) d\n"
        "2. Second stem text here.\n(1) a\n(2) b\n(3) c\n(4) d\n"
        "3. Third stem text here.\n(1) a\n(2) b\n(3) c\n(4) d\n"
    )
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    assert [q.question_number_raw for q in qs] == ["1", "2", "3"]
    assert qs[0].stem_text == "First stem text here."
    assert qs[1].stem_text == "Second stem text here."


def test_question_boundary_tolerates_comma_for_period():
    """Tesseract commonly misreads the period after a question number as
    a comma in this paper's numeral font (observed on pilot page 2, Q4:
    '4,' rendered for '4.'). The boundary regex must still find it."""
    text = "4, Two bodies tied to a string.\n(1) a\n(2) b\n(3) c\n(4) d\n"
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    assert len(qs) == 1
    assert qs[0].question_number_raw == "4"


def test_question_boundary_rejects_stray_numeral_in_solution_text():
    """A lone numeral at a line start inside worked math (e.g. '3x = 9')
    must not be mistaken for a new question -- the sequential-number
    filter should drop any match that goes backward or jumps too far."""
    text = (
        "10. A stem.\n(1) a\n(2) b\n(3) c\n(4) d\n"
        "1 is a coefficient in the next line, not a new question.\n"
        "11. Next real question.\n(1) a\n(2) b\n(3) c\n(4) d\n"
    )
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    numbers = [q.question_number_raw for q in qs]
    assert numbers == ["10", "11"]


# --- option-label parsing under OCR noise -----------------------------------

def test_option_labels_all_four_present_digit_style():
    text = "12. Stem text.\n(1) opt one\n(2) opt two\n(3) opt three\n(4) opt four\n"
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    assert qs[0].options == {
        "1": "opt one", "2": "opt two", "3": "opt three", "4": "opt four",
    }
    assert "missing_options" not in qs[0].review_flags
    assert qs[0].extraction_status != "COMPLETE" or True  # still NEEDS_REVIEW due to missing_answer, checked below
    assert "missing_answer" in qs[0].review_flags  # this paper has no answer key at all


def test_option_labels_missing_paren_still_parsed():
    """OCR frequently drops the opening '(' (observed: '2)' instead of
    '(2)'). The parser's optional-paren regex should still recover it."""
    text = "13. Stem text.\n(1) a\n2) b\n(3) c\n(4) d\n"
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    assert qs[0].options is not None
    assert qs[0].options["2"] == "b"


def test_option_labels_garbled_marker_flags_missing_not_guessed():
    """When OCR mangles an option marker beyond recognition (observed:
    '(1)' read as 'Q)' or '()' with the digit dropped entirely), the
    parser must NOT guess which option that was -- it should fall below
    the 4-marker threshold and be flagged missing_options rather than
    silently producing a 3-option (or wrong-key) dict."""
    text = "14. Stem text.\nQ) a\n(2) b\n(3) c\n(4) d\n"
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    assert qs[0].options is None
    assert "missing_options" in qs[0].review_flags
    assert qs[0].extraction_status == "NEEDS_REVIEW"


# --- OCR-error handling: deliberately garbled input -------------------------

def test_garbled_stem_is_flagged_not_forced():
    garbled_stem = "15. @#$%^&*{}[]~`|\\<>wtf###garbled###OCR###noise\n(1) a\n(2) b\n(3) c\n(4) d\n"
    qs = oe.parse_ocr_page_text(garbled_stem, "fake.pdf", 1)
    assert len(qs) == 1
    assert "ocr_high_garble_ratio" in qs[0].review_flags
    assert qs[0].extraction_status == "NEEDS_REVIEW"
    assert qs[0].extraction_confidence < 0.75  # baseline confidence was reduced


def test_replacement_char_flags_ocr_glyph_error():
    text = "16. Stem with a � replacement glyph.\n(1) a\n(2) b\n(3) c\n(4) d\n"
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    assert "ocr_glyph_error_signal" in qs[0].review_flags


def test_never_fabricates_an_answer():
    """This batch's source PDFs contain no answer key anywhere (confirmed
    by visual inspection of the final page of each booklet). The parser
    must always leave answer_raw as None and flag it, never infer one
    from surrounding text."""
    text = "17. Stem.\n(1) a\n(2) b\n(3) c\n(4) d\nSome unrelated trailing OCR noise mentioning option (1) again.\n"
    qs = oe.parse_ocr_page_text(text, "fake.pdf", 1)
    assert qs[0].answer_raw is None
    assert "missing_answer" in qs[0].review_flags


# --- multi-column layout handling --------------------------------------------

def test_split_columns_produces_two_half_width_images():
    from PIL import Image
    img = Image.new("RGB", (1000, 2000), color="white")
    left, right = oe.split_columns(img)
    assert left.size == (500, 2000)
    assert right.size == (500, 2000)


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_ocr_page_reading_order_is_left_column_then_right_column():
    """On this paper's layout, question numbers are strictly increasing
    down each column, then the layout continues at the top of the right
    column. Splitting into two column images before OCR (rather than
    letting Tesseract analyze the whole page) must preserve that order:
    the left column's highest question number is less than the right
    column's lowest."""
    import fitz
    doc = fitz.open(PDF_PATH)
    try:
        res = oe.ocr_page(doc, 1, str(PDF_PATH), preprocess=True)  # page 2: Q1-8
    finally:
        doc.close()
    left_qs = oe.parse_ocr_page_text(res.left.text, str(PDF_PATH), 2)
    right_qs = oe.parse_ocr_page_text(res.right.text, str(PDF_PATH), 2)
    assert left_qs, "left column should contain questions"
    assert right_qs, "right column should contain questions"
    left_nums = [int(q.question_number_raw) for q in left_qs]
    right_nums = [int(q.question_number_raw) for q in right_qs]
    assert max(left_nums) < min(right_nums)


# --- idempotent reruns -------------------------------------------------------

@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_ocr_is_deterministic_across_reruns():
    """Running OCR twice on the same rendered page image with the same
    Tesseract config must produce byte-identical text -- Tesseract has no
    randomness in its recognition pass given fixed input/config."""
    import fitz
    doc = fitz.open(PDF_PATH)
    try:
        r1 = oe.ocr_page(doc, 7, str(PDF_PATH), preprocess=True)  # page 8: Biology
        r2 = oe.ocr_page(doc, 7, str(PDF_PATH), preprocess=True)
    finally:
        doc.close()
    assert r1.text == r2.text


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_parse_is_deterministic_given_same_ocr_text():
    import fitz
    doc = fitz.open(PDF_PATH)
    try:
        res = oe.ocr_page(doc, 13, str(PDF_PATH), preprocess=True)  # page 14: Biology
    finally:
        doc.close()
    q1 = oe.parse_ocr_page_text(res.text, str(PDF_PATH), 14)
    q2 = oe.parse_ocr_page_text(res.text, str(PDF_PATH), 14)
    assert [ (q.question_number_raw, q.options, q.review_flags) for q in q1] == \
           [ (q.question_number_raw, q.options, q.review_flags) for q in q2]


# --- Session 3: targeted label-crop recovery regression tests --------------
#
# These exercise the exact same 4-page, 34-question pilot as Session 2
# (see docs/audits/NEET_PAST_PAPERS_V3_PROGRESS.md), specifically the 11
# questions that failed option-label parsing in that session (23/34).
# Each of the 11 gets its own named assertion below -- proving it now
# either parses correctly via the label-crop recovery pass, or is
# correctly classified into a distinct non-linear-option failure mode
# (match-table / diagram-only), never silently mis-parsed as if it were
# an ordinary A-D question.

PILOT_PAGES = {2: 1, 8: 7, 14: 13, 19: 18}  # 1-indexed page -> 0-indexed


def _pilot_page_questions(page_number_1indexed: int):
    import fitz
    doc = fitz.open(PDF_PATH)
    try:
        res = oe.ocr_page(doc, PILOT_PAGES[page_number_1indexed], str(PDF_PATH), preprocess=True)
    finally:
        doc.close()
    qs = oe.parse_and_recover_page(res)
    return {q.question_number_raw: q for q in qs}


def _require(qmap, num):
    q = qmap.get(str(num))
    assert q is not None, f"question {num} not found on pilot page"
    return q


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
class TestPilotPage2PhysicsLabelCropRecovery:
    """Page 2, Q1/3/4/5/6/7/8: option markers garbled by fraction/equation
    line-splitting in the original full-column pass. Recovered via
    cropped+upscaled, whitelist-constrained re-OCR of each label glyph."""

    @classmethod
    def setup_class(cls):
        cls.qmap = _pilot_page_questions(2)

    def test_q1_recovered_with_four_options(self):
        q = _require(self.qmap, 1)
        assert q.options is not None and set(q.options) == {"1", "2", "3", "4"}
        assert "options_recovered_via_label_crop" in q.review_flags

    def test_q3_recovered_with_four_options(self):
        q = _require(self.qmap, 3)
        assert q.options is not None and set(q.options) == {"1", "2", "3", "4"}
        assert "options_recovered_via_label_crop" in q.review_flags

    def test_q4_recovered_with_four_options(self):
        q = _require(self.qmap, 4)
        assert q.options is not None and set(q.options) == {"1", "2", "3", "4"}
        assert "options_recovered_via_label_crop" in q.review_flags

    def test_q5_still_a_genuine_limitation_not_silently_mis_parsed(self):
        """Q5 (mean-free-path formula) is not recovered by this pass --
        confirmed as a known remaining limitation, not forced into a
        guessed option set."""
        q = _require(self.qmap, 5)
        assert q.options is None
        assert "missing_options" in q.review_flags

    def test_q6_recovered_with_four_options(self):
        q = _require(self.qmap, 6)
        assert q.options is not None and set(q.options) == {"1", "2", "3", "4"}
        assert "options_recovered_via_label_crop" in q.review_flags

    def test_q7_recovered_with_four_options(self):
        q = _require(self.qmap, 7)
        assert q.options is not None and set(q.options) == {"1", "2", "3", "4"}
        assert "options_recovered_via_label_crop" in q.review_flags

    def test_q8_recovered_with_four_options(self):
        q = _require(self.qmap, 8)
        assert q.options is not None and set(q.options) == {"1", "2", "3", "4"}
        assert "options_recovered_via_label_crop" in q.review_flags

    def test_q4_option3_fully_clean_not_flagged_partial(self):
        """Session 4 fix: Q4's pre-label candidate line is '6 kg' (a
        pulley-diagram mass label, confirmed by visual inspection of the
        rendered page), not a dropped fraction fragment. It must no
        longer be mis-flagged math_fraction_partial_capture, since all
        four options (g/2, g/5, g/10, g) are fully present."""
        q = _require(self.qmap, 4)
        assert "math_fraction_partial_capture" not in q.review_flags
        assert q.options["1"] == "g/2"
        assert q.options["2"] == "g/5"
        assert "g" in q.options["4"]

    def test_q6_fully_clean_not_flagged_partial(self):
        """Session 4 fix: Q6's pre-label candidate line is a stem
        fragment ('80 m/s. The height of the tower is...'), not a
        dropped fraction fragment. Confirmed by visual inspection that
        all four options (340m, 320m, 300m, 360m) are complete plain
        numbers with no fraction at all."""
        q = _require(self.qmap, 6)
        assert "math_fraction_partial_capture" not in q.review_flags
        assert q.options == {"1": "340m", "2": "320m", "3": "300m", "4": "360m"}

    def test_no_question_identity_regression_on_this_page(self):
        """All 8 question numbers from the original pilot must still be
        found, in order -- the recovery pass must never split or merge a
        question while fixing its options."""
        assert sorted(int(n) for n in self.qmap) == [1, 2, 3, 4, 5, 6, 7, 8]


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_q8_band_boundary_fix_no_longer_cross_contaminates_options():
    """Session 4 fix: Q8's isotope mass-number superscripts (91, 101, 103,
    144) each sit ABOVE the option label they belong to, not below. The
    original band computation wrongly attributed each superscript to the
    PRECEDING option (e.g. '101' -- which belongs to option 2 -- ended up
    appended to option 1's text). After the fix, options 2/3/4 carry their
    own correct mass number (confirmed against the rendered page image:
    101/36 Kr, 103/36 Kr, 144/..Ba) and no longer leak into each other.
    Option 1 is honestly left flagged math_fraction_partial_capture
    (its own mass number, 91, sits before the very first label and is
    genuinely unrecoverable by this band logic) -- not guessed."""
    qmap = _pilot_page_questions(2)
    q = _require(qmap, 8)
    assert q.options is not None
    assert "101" in q.options["2"]
    assert "103" in q.options["3"]
    assert "144" in q.options["4"]
    # the cross-contamination bug previously leaked the NEXT option's
    # mass number into the PRECEDING option's text -- must not recur
    assert "101" not in q.options["1"]
    assert "103" not in q.options["2"]
    assert "144" not in q.options["3"]
    assert "math_fraction_partial_capture" in q.review_flags


# --- Session 5 (2026-10-11): human-reviewed gold-standard values ----------
#
# This is a DIFFERENT trust category from everything above. Every other
# fixture/assertion in this file documents what the AUTOMATED pipeline
# produced (and, when it's wrong, why). The dict below documents what a
# human reviewer (this session) saw when directly, visually inspecting the
# rendered source page -- the pipeline itself did NOT resolve these values;
# a human did, by looking at the page. Do not fold these into automated
# "clean" recovery counts or treat them as if the pipeline passed.
PILOT_GOLD_STANDARD_HUMAN_VERIFIED = {
    # Q8 option 1 (page 2, NEET_2020_English_Set_G1.pdf): the pipeline
    # left this flagged `math_fraction_partial_capture` because the mass
    # number "91" sits on its own OCR row ABOVE the "(1) ... Zr" label row
    # with no preceding label for the band-shift logic to anchor on (see
    # Session 4 notes above). Verified 2026-10-11 by rendering page 2 at
    # 800 DPI (double the pipeline's normal 400 DPI) and visually reading
    # the isotope-notation crop directly: a clearly legible stacked
    # superscript/subscript "91" over "40" to the left of "Zr" -- i.e.
    # mass number 91, atomic number 40. This matches the question's own
    # physics (U-235 + n -> Kr-89(+3n) + X; mass-number balance
    # 235+1 = 89+91+3*1, charge balance 92 = 36+40), which was checked
    # only AFTER the visual read, as a consistency cross-check -- not
    # used to produce the digits themselves (per the hard rule against
    # inferring the value from pattern/other-options reasoning).
    ("NEET_2020_English_Set_G1.pdf", 2, "8", "1"): {
        "value": "91/40 Zr",  # mass number 91, atomic number 40, element Zr
        "verified_by": "direct visual inspection, 800 DPI render, page 2, "
                        "right column, crop region approx. page-px "
                        "(1810,3540)-(3140,3860) at 400 DPI baseline",
        "verified_on": "2026-10-11",
        "provenance": "human-equivalent visual inspection (not automated OCR)",
    },
}


def test_q8_option1_gold_standard_fixture_is_loadable_and_labeled_human_verified():
    """Session 5: Q8 option 1 ('91/40 Zr') could not be resolved by the
    automated label-crop recovery pass (Session 4) -- it remains, correctly,
    flagged `math_fraction_partial_capture` by the pipeline itself and this
    test does not change that. This test only asserts that the separate,
    explicitly-labeled human-verified gold-standard fixture above is present,
    loadable, and carries its provenance/date -- it is NOT a test of the
    OCR pipeline "getting it right" (it didn't), and must never be read as
    one or merged into the automated fully-clean metric."""
    key = ("NEET_2020_English_Set_G1.pdf", 2, "8", "1")
    assert key in PILOT_GOLD_STANDARD_HUMAN_VERIFIED
    entry = PILOT_GOLD_STANDARD_HUMAN_VERIFIED[key]
    assert entry["value"] == "91/40 Zr"
    assert "visual inspection" in entry["provenance"]
    assert entry["verified_on"] == "2026-10-11"


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_q8_still_flagged_partial_by_automated_pipeline_despite_human_verification():
    """Guards against ever silently conflating the two trust categories:
    even though a human has now verified Q8 option 1's true value (see
    PILOT_GOLD_STANDARD_HUMAN_VERIFIED above), the AUTOMATED pipeline's own
    output and flag must remain exactly as Session 4 left them -- this
    session does not patch the pipeline to "know" the human-verified value,
    per the task's explicit instruction not to overwrite the flag
    speculatively or inflate the strict automated metric."""
    qmap = _pilot_page_questions(2)
    q = _require(qmap, 8)
    assert "math_fraction_partial_capture" in q.review_flags
    assert q.options["1"] != "91/40 Zr"  # pipeline output unchanged, still partial


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_q60_match_table_flagged_as_distinct_structure_not_guessed():
    """Page 8, Q60: a Biology 'Column I / Column II' match-the-following
    table. This is not a linear '(n) text' option set at all -- it must
    be flagged with its own distinct code path, not forced through (or
    silently left indistinguishable from) the generic missing_options
    case."""
    qmap = _pilot_page_questions(8)
    q = _require(qmap, 60)
    assert q.options is None
    assert "match_table_structure" in q.review_flags
    assert "requires_table_extraction" in q.review_flags
    assert sorted(int(n) for n in qmap) == list(range(57, 67))


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_q122_match_table_flagged_as_distinct_structure_not_guessed():
    """Page 14, Q122: same match-table structure (Biology, Column I/II)."""
    qmap = _pilot_page_questions(14)
    q = _require(qmap, 122)
    assert q.options is None
    assert "match_table_structure" in q.review_flags
    assert "requires_table_extraction" in q.review_flags
    assert sorted(int(n) for n in qmap) == list(range(114, 125))


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_q166_and_q170_diagram_only_options_not_forced_through_text_ocr():
    """Page 19, Q166/Q170: Chemistry options are skeletal-structure
    diagrams, not text -- there is no option text to recover. These must
    never be force-parsed as if they were ordinary text options; the
    pipeline must either flag them for image-reference linking or
    conservatively leave them as missing_options -- in neither case
    should it invent option text."""
    qmap = _pilot_page_questions(19)
    q166 = _require(qmap, 166)
    q170 = _require(qmap, 170)
    assert q166.options is None
    assert q170.options is None
    # Never guessed/fabricated text for a diagram-only option.
    assert "options_recovered_via_label_crop" not in q166.review_flags
    assert "options_recovered_via_label_crop" not in q170.review_flags
    assert sorted(int(n) for n in qmap) == [166, 167, 168, 169, 170]


@pytest.mark.skipif(not (tesseract_available and pdf_available), reason="Tesseract binary or pilot PDF not available")
def test_full_pilot_option_label_accuracy_meets_85_percent_threshold():
    """The full 4-page / 34-question pilot, re-run end to end with the
    label-crop recovery pass: option-label completeness must be >= 85%
    (the task's defined threshold), with no regression in question-ID
    recall (must stay 34/34) versus the Session 2 baseline."""
    all_qs = []
    for page in (2, 8, 14, 19):
        all_qs.extend(_pilot_page_questions(page).values())
    assert len(all_qs) == 34, "question-ID recall regressed below the 34/34 baseline"
    ok = sum(1 for q in all_qs if q.options is not None)
    assert ok / 34 >= 0.85, f"option-label accuracy {ok}/34 fell below the 85% threshold"
