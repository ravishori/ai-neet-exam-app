r"""Regression tests for two parser bugs found during the NEET 2023 corpus
individual-level verification pass
(`docs/quality/neet_corpus_2023_verified_recovery_manifest_20261011.md`, §5):

1. `69d94884` (source PDF Question 30): the source's answer is the literal
   text "Answer: None of the options are correct" (a known voided NEET 2023
   physics question) rather than an "Answer: (x)" lettered marker. The
   current `_V2_QA_ANSWER_RE` regex in
   `scripts/pyq_image_pipeline/extractor.py` only matches a parenthesised
   letter/digit, so this case is wrongly flagged `missing_answer`.

2. `d82241e3` (source PDF Question 197): the source's option (d) is not
   preceded by a newline ("...due to \nit. (d) It decreases...") because of
   how the PDF's text layer wraps that line. The current `_V2_QA_OPT_RE`
   regex requires `\n\(` before the option marker, so only options (a)-(c)
   are matched (3 < 4) and the whole `options` dict is dropped
   (`missing_options`), even though the answer and all 4 options are
   plainly legible on the page.

Both fixture text blocks below are the ACTUAL `Question 30:` / `Question
197:` text extracted from
`NEET Past Papers_V2/NEET 2023 Question Paper with Solutions - Boost Your
Prep!.pdf` via PyMuPDF in this session (not synthetic/invented text) —
verbatim down to the exact whitespace/newline placement that triggers each
bug, including the known-voided-question phrasing for Q30 and the
line-wrap-straddled "it. (d)" for Q197.

These tests document the CURRENT (buggy) behavior honestly: they assert
the CORRECT extraction, so they are expected to FAIL against the
unmodified `extractor.py` as of 2026-10-11. This task does not fix the
bugs — see the audit report
(`docs/quality/neet_corpus_2023_preimport_audit_20261011.md`) for the
actual pass/fail results captured when these tests were run.
"""
from __future__ import annotations

from scripts.pyq_image_pipeline.extractor import segment_v2_qa

# Page break covering the whole synthetic single-page full_text used below.
_PAGE_BREAKS = [(0, 1)]

# Verbatim text block for PDF "Question 30:" (source: NEET 2023 Question
# Paper with Solutions - Boost Your Prep!.pdf, physics radius-of-gyration
# question). Reproduced exactly as extracted by PyMuPDF `page.get_text()`.
Q30_FULL_TEXT = (
    "Question 30: The ratio of radius of gyration of a solid sphere of mass M and radius R about its \n"
    "own axis to the radius of gyration of the thin hollow sphere of same mass and radius about its \n"
    "axis is:  \n"
    "Options:  \n"
    "(a) 3 : 5 \n"
    "(b) 5 : 3 \n"
    "(c) 2 : 5 \n"
    "(d) 5 : 2 \n"
    "Answer: None of the options are correct \n"
    "Solution:  \n"
    "None of the options matching  \n"
)

# Verbatim text block for PDF "Question 197:" (source: same PDF, biology
# inbreeding question). Note option (d) runs on immediately after option
# (c)'s wrapped line ("...due to \nit. (d) ...") with NO leading newline
# before "(d)" -- this is the actual PDF text-layer wrap, not invented.
Q197_FULL_TEXT = (
    "Question 197: Which one of the following is NOT an advantage of inbreeding?  \n"
    "Options: \n"
    "(a) It decreases homozygosity.  \n"
    "(b) It exposes harmful recessive genes that are eliminated by selection.  \n"
    "(c) Elimination of less desirable genes and accumulation of superior genes takes place due to \n"
    "it. (d) It decreases the productivity of inbred population, after continuous inbreeding, \n"
    "Answer: (a)  \n"
)


def test_q30_none_of_the_options_are_correct_is_extracted_as_valid_answer():
    """Bug 1 reproduction (stub 69d94884 / PDF Q30).

    The literal text "None of the options are correct" is a real,
    source-stated answer (a known voided NEET 2023 question) and must be
    extracted as a present, non-missing answer -- not treated as a missing
    answer just because it isn't a parenthesised letter.

    Expected to currently FAIL: `_V2_QA_ANSWER_RE` only matches
    `Answer:\\s*\\(([1-4a-dA-D])\\)`, so this literal-text answer is not
    captured, `answer_raw` ends up `None`, and `missing_answer` /
    `NEEDS_REVIEW` are wrongly set.
    """
    questions = segment_v2_qa(
        Q30_FULL_TEXT, _PAGE_BREAKS, "Q30_fixture.pdf", "deadbeef", 2023, "NEET (UG) 2023"
    )
    assert len(questions) == 1
    q = questions[0]

    assert q.answer_raw is not None, (
        "answer_raw is None: the literal 'None of the options are correct' "
        "answer was not captured (bug 1 reproduced)"
    )
    assert "none of the options are correct" in (q.answer_raw or "").lower()
    assert "missing_answer" not in q.review_flags
    assert q.extraction_status == "COMPLETE"


def test_q197_options_split_across_line_wrap_are_all_extracted():
    """Bug 2 reproduction (stub d82241e3 / PDF Q197).

    All 4 options and the answer are plainly present on the source page;
    option (d) is only missed because the PDF text layer wraps it onto the
    same line as the tail of option (c) with no preceding newline.

    Expected to currently FAIL: `_V2_QA_OPT_RE` requires `\\n\\(` before the
    marker, so only 3 of 4 options match, the whole `options` dict is
    dropped (set to `None`), and `missing_options` / `NEEDS_REVIEW` are
    wrongly set even though option (d)'s text is sitting right there in
    the block.
    """
    questions = segment_v2_qa(
        Q197_FULL_TEXT, _PAGE_BREAKS, "Q197_fixture.pdf", "deadbeef", 2023, "NEET (UG) 2023"
    )
    assert len(questions) == 1
    q = questions[0]

    assert q.options is not None, (
        "options is None: 4-option parse failed because option (d) wasn't "
        "preceded by a newline in the source text layer (bug 2 reproduced)"
    )
    assert set(q.options.keys()) == {"a", "b", "c", "d"}
    assert "decreases the productivity" in q.options["d"].lower()
    assert "missing_options" not in q.review_flags
    assert q.answer_raw == "a"
    assert q.extraction_status == "COMPLETE"
