"""Deterministic (non-AI) PYQ text + image extraction pipeline.

Parses NEET Past Papers PDFs found in
`D:\\ravishori\\AI Neet Exam App\\NEET Past Papers\\` into two shapes:

- 2015 "Question Paper with Answers" style:
    <n>.\n<stem...>\n(1)\n<opt1>\n(2)\n<opt2>\n(3)\n<opt3>\n(4)\n<opt4>\n
    Solution: (<ans>) <explanation...>      [Code A/C]
    Answer Key: (<ans>) \nSolution: <explanation...>   [Code B/D]

- 2025 "... Analysis ..." style (confirmed to contain full question +
  option + answer + solution text, NOT pure commentary):
    Question <n>: <stem...>\nOptions:\n(a) ...\n(b) ...\n(c) ...\n(d) ...
    \nAnswer: (<ans>)\nSolution: <explanation...>

No AI/LLM calls anywhere in this module. All segmentation is regex/
heuristic based on PyMuPDF (fitz) text extraction. Nothing here guesses
missing content — gaps are flagged via review_flags/extraction_status.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

PIPELINE_VERSION = "pyq_image_pipeline_v1"

IMAGE_KEYWORDS = [
    "figure", "diagram", "graph", "as shown", "shown below", "shown in",
    "given figure", "following figure", "represented", "circuit shown",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def identity_key(source_file: str, page: int, question_number_raw: str | None, paper_code: str | None) -> str:
    raw = f"{source_file}|{page}|{question_number_raw or ''}|{paper_code or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


@dataclass
class ExtractedQuestion:
    source_file: str
    source_file_sha256: str
    page_number: int
    question_number_raw: str | None
    paper_code: str | None
    exam_year: int | None
    exam_name: str | None
    subject: str | None
    doc_kind: str
    stem_text: str | None
    options: dict | None
    answer_raw: str | None
    explanation_text: str | None
    raw_block_text: str
    extraction_status: str
    extraction_confidence: float
    review_flags: list[str] = field(default_factory=list)
    has_image_reference: bool = False
    identity_key: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.identity_key:
            self.identity_key = identity_key(
                self.source_file, self.page_number, self.question_number_raw, self.paper_code
            )


@dataclass
class ExtractedImage:
    source_file: str
    source_file_sha256: str
    page_number: int
    image_index_on_page: int
    stored_path: str
    width_px: int | None
    height_px: int | None
    image_format: str | None
    association_confidence: str  # NONE | LOW | MEDIUM | HIGH
    association_basis: str | None
    question_identity_key: str | None  # resolved to question_id later by caller
    identity_key: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.identity_key:
            raw = f"{self.source_file}|{self.page_number}|{self.image_index_on_page}"
            self.identity_key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


# --- file-level classification -----------------------------------------------

def classify_file(filename: str) -> tuple[int | None, str | None, str | None, str | None, str]:
    """Return (exam_year, exam_name, paper_code, subject, doc_kind)."""
    fname = filename.lower()
    if "2015" in fname and "question paper" in fname:
        m = re.search(r"code[\s_-]*([a-d])", fname)
        code = m.group(1).upper() if m else None
        return 2015, "NEET (UG) 2015", code, None, "RAW_QUESTION_PAPER_WITH_ANSWERS"
    if "2025" in fname:
        subject = None
        for s in ("chemistry", "physics", "biology"):
            if s in fname:
                subject = s.capitalize()
                break
        return 2025, "NEET (UG) 2025", None, subject, "ANALYSIS_DOC_WITH_FULL_QA_TEXT"
    return None, None, None, None, "OTHER"


# --- text segmentation --------------------------------------------------------

_2015_Q_RE = re.compile(r"(?m)^(\d{1,3})\.\s")
_2025_Q_RE = re.compile(r"(?m)Question\s+(\d{1,3})\s*:\s*")
_OPT_NUM_RE = re.compile(r"\n\((\d)\)\s*\n?")
_OPT_ALPHA_RE = re.compile(r"\n\(([a-d])\)\s*")
_ANSWER_KEY_RE = re.compile(r"Answer\s*Key:\s*\((\d)\)")
_SOLUTION_NUM_RE = re.compile(r"Solution:\s*\((\d)\)")
_ANSWER_2025_RE = re.compile(r"Answer:\s*\(([a-dA-D])\)")
_SOLUTION_SPLIT_RE = re.compile(r"Solution:")


def _has_image_keyword(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in IMAGE_KEYWORDS)


_REPLACEMENT_CHAR = "�"
_FOOTER_LEAK_RE = re.compile(r"\s*(www\.\w+\.\w+\s*\n?\d*|Answer\s*Key:\s*\(\d\)|Solution:.*)$", re.DOTALL)


def _has_ocr_glyph_error(text: str) -> bool:
    return _REPLACEMENT_CHAR in text


def _clean_trailing_footer_leak(text: str) -> tuple[str, bool]:
    """Strip page-footer / answer-key boilerplate that bled into the last
    option's text due to naive slicing. Returns (cleaned_text, was_dirty)."""
    m = _FOOTER_LEAK_RE.search(text)
    if m and m.group(0).strip():
        cleaned = text[: m.start()].rstrip()
        return cleaned, True
    return text, False


def _filter_sequential(matches: list[re.Match], max_gap: int = 5) -> list[re.Match]:
    """Drop regex matches whose captured number breaks the expected
    increasing sequence (these are false positives from stray numerals
    at a line start inside a worked solution, e.g. a lone "3." in an
    equation). A match is kept when its number is strictly greater than
    the last kept number and within `max_gap` of it (so a genuinely
    missed question number — e.g. an OCR-mangled "113." — doesn't
    permanently stall the sequence the way a strict n -> n+1 rule
    would); anything that goes backward, or jumps further than
    `max_gap`, is treated as a false positive and skipped."""
    kept: list[re.Match] = []
    last_num: int | None = None
    for m in matches:
        try:
            num = int(m.group(1))
        except ValueError:
            continue
        if last_num is None or (last_num < num <= last_num + max_gap):
            kept.append(m)
            last_num = num
        # else: skip — breaks the expected sequence, treat as false positive
    return kept


def segment_2015(full_text: str, page_breaks: list[tuple[int, int]], source_file: str,
                  source_sha: str, paper_code: str | None, exam_year: int, exam_name: str) -> list[ExtractedQuestion]:
    """page_breaks: list of (char_offset_start, page_number_1_indexed) sorted ascending."""
    out: list[ExtractedQuestion] = []
    raw_matches = list(_2015_Q_RE.finditer(full_text))
    matches = _filter_sequential(raw_matches)
    for i, m in enumerate(matches):
        q_num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        page_num = 1
        for offset, pnum in page_breaks:
            if offset <= m.start():
                page_num = pnum
            else:
                break

        flags: list[str] = []
        status = "COMPLETE"
        confidence = 0.9

        ans_m = _ANSWER_KEY_RE.search(block) or _SOLUTION_NUM_RE.search(block)
        answer_raw = ans_m.group(1) if ans_m else None
        if not answer_raw:
            flags.append("missing_answer")
            status = "NEEDS_REVIEW"
            confidence -= 0.3

        sol_split = _SOLUTION_SPLIT_RE.search(block)
        pre_solution = block[: sol_split.start()] if sol_split else block
        explanation = block[sol_split.end():].strip() if sol_split else None
        if not sol_split:
            flags.append("missing_explanation")
            confidence -= 0.1

        opt_matches = list(_OPT_NUM_RE.finditer(pre_solution))
        if len(opt_matches) >= 4:
            stem = pre_solution[: opt_matches[0].start()].strip()
            opts = {}
            for j in range(4):
                ostart = opt_matches[j].end()
                oend = opt_matches[j + 1].start() if j + 1 < 4 else len(pre_solution)
                opts[str(j + 1)] = pre_solution[ostart:oend].strip()
        else:
            stem = pre_solution.strip()
            opts = None
            flags.append("missing_options")
            status = "NEEDS_REVIEW"
            confidence -= 0.3

        if opts is not None:
            last_key = str(len(opts))
            cleaned, was_dirty = _clean_trailing_footer_leak(opts[last_key])
            if was_dirty:
                opts[last_key] = cleaned
                flags.append("footer_boilerplate_leaked_into_option")
                status = "NEEDS_REVIEW"
                confidence -= 0.15

        if _has_ocr_glyph_error(stem) or (opts is not None and any(_has_ocr_glyph_error(v) for v in opts.values())):
            flags.append("ocr_glyph_error_signal")
            status = "NEEDS_REVIEW"
            confidence -= 0.1

        has_img_ref = _has_image_keyword(stem) or (opts is not None and sum(len(v) for v in opts.values()) < 12)
        if has_img_ref:
            flags.append("possible_image_dependency")

        if len(stem) < 5:
            flags.append("uncertain_question_boundary")
            status = "NEEDS_REVIEW"
            confidence -= 0.2

        confidence = max(0.1, min(1.0, confidence))
        out.append(ExtractedQuestion(
            source_file=source_file,
            source_file_sha256=source_sha,
            page_number=page_num,
            question_number_raw=q_num,
            paper_code=paper_code,
            exam_year=exam_year,
            exam_name=exam_name,
            subject=None,
            doc_kind="RAW_QUESTION_PAPER_WITH_ANSWERS",
            stem_text=stem,
            options=opts,
            answer_raw=answer_raw,
            explanation_text=explanation,
            raw_block_text=block[:4000],
            extraction_status=status,
            extraction_confidence=confidence,
            review_flags=flags,
            has_image_reference=has_img_ref,
        ))
    _flag_number_gaps(out)
    return out


def _flag_number_gaps(questions: list[ExtractedQuestion]) -> None:
    """Mark a question NEEDS_REVIEW when its number isn't exactly one
    more than the previous one — this means a question in between was
    never matched by the segmentation regex at all (distinct from
    missing_options/missing_answer, which are about a *matched*
    question with incomplete content)."""
    last_num: int | None = None
    for q in questions:
        try:
            num = int(q.question_number_raw)
        except (TypeError, ValueError):
            last_num = None
            continue
        if last_num is not None and num != last_num + 1:
            q.review_flags.append(f"question_number_gap_before_{num}_prev_{last_num}")
            q.extraction_status = "NEEDS_REVIEW"
            q.extraction_confidence = max(0.1, q.extraction_confidence - 0.2)
        last_num = num


def segment_2025(full_text: str, page_breaks: list[tuple[int, int]], source_file: str,
                  source_sha: str, exam_year: int, exam_name: str, subject: str | None) -> list[ExtractedQuestion]:
    out: list[ExtractedQuestion] = []
    matches = list(_2025_Q_RE.finditer(full_text))
    for i, m in enumerate(matches):
        q_num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        page_num = 1
        for offset, pnum in page_breaks:
            if offset <= m.start():
                page_num = pnum
            else:
                break

        flags: list[str] = []
        status = "COMPLETE"
        confidence = 0.9

        ans_m = _ANSWER_2025_RE.search(block)
        answer_raw = ans_m.group(1).lower() if ans_m else None
        if not answer_raw:
            flags.append("missing_answer")
            status = "NEEDS_REVIEW"
            confidence -= 0.3

        sol_split = _SOLUTION_SPLIT_RE.search(block)
        pre_solution = block[: sol_split.start()] if sol_split else block
        explanation = block[sol_split.end():].strip() if sol_split else None
        if not sol_split:
            flags.append("missing_explanation")
            confidence -= 0.1

        opts_idx = pre_solution.find("Options:")
        if opts_idx == -1:
            stem = pre_solution.strip()
            opts = None
            flags.append("missing_options")
            status = "NEEDS_REVIEW"
            confidence -= 0.3
        else:
            stem = pre_solution[:opts_idx].strip()
            opt_block = pre_solution[opts_idx + len("Options:"):]
            opt_matches = list(_OPT_ALPHA_RE.finditer(opt_block))
            if len(opt_matches) >= 4:
                opts = {}
                for j in range(len(opt_matches)):
                    letter = opt_matches[j].group(1).lower()
                    ostart = opt_matches[j].end()
                    oend = opt_matches[j + 1].start() if j + 1 < len(opt_matches) else len(opt_block)
                    text_before_answer = opt_block[ostart:oend]
                    ans_cut = text_before_answer.find("Answer:")
                    if ans_cut != -1:
                        text_before_answer = text_before_answer[:ans_cut]
                    opts[letter] = text_before_answer.strip()
            else:
                opts = None
                flags.append("missing_options")
                status = "NEEDS_REVIEW"
                confidence -= 0.3

        if _has_ocr_glyph_error(stem) or (opts is not None and any(_has_ocr_glyph_error(v) for v in opts.values())):
            flags.append("ocr_glyph_error_signal")
            status = "NEEDS_REVIEW"
            confidence -= 0.1

        has_img_ref = _has_image_keyword(stem)
        if has_img_ref:
            flags.append("possible_image_dependency")

        if len(stem) < 5:
            flags.append("uncertain_question_boundary")
            status = "NEEDS_REVIEW"
            confidence -= 0.2

        confidence = max(0.1, min(1.0, confidence))
        out.append(ExtractedQuestion(
            source_file=source_file,
            source_file_sha256=source_sha,
            page_number=page_num,
            question_number_raw=q_num,
            paper_code=None,
            exam_year=exam_year,
            exam_name=exam_name,
            subject=subject,
            doc_kind="ANALYSIS_DOC_WITH_FULL_QA_TEXT",
            stem_text=stem,
            options=opts,
            answer_raw=answer_raw,
            explanation_text=explanation,
            raw_block_text=block[:4000],
            extraction_status=status,
            extraction_confidence=confidence,
            review_flags=flags,
            has_image_reference=has_img_ref,
        ))
    _flag_number_gaps(out)
    return out


# --- top-level per-file extraction -------------------------------------------

# --- NEET Past Papers_V2 batch (2020/2022/2023/2024) -------------------------
#
# Verified by direct PDF-text inspection (not filename assumption) on
# 2026-10-10:
#   - 2020 "Code-F1" paper: numbered "<n>." stems (no space required after
#     the dot, e.g. "112.Which..."), options inline as "\n(A) ...", mostly
#     ONLY a worked "Solutions:" section with no clean per-question answer
#     *letter* marker (grep for answer-like tokens found just 18 hits across
#     180 questions) -> most rows will be honestly flagged missing_answer.
#   - 2022/2023/2024 papers: "Question <n>: ... Options: ... Answer: (<x>)
#     Solution: ..." shape identical to the existing 2025-analysis shape,
#     except (a) numbering is global across the whole combined paper (up to
#     200, reflecting NEET's optional section-B choice format) rather than
#     offset per-subject-PDF, and (b) the option/answer marker is sometimes
#     a digit (1-4) and sometimes a letter (a-d) depending on the source.

_V2_2020_Q_RE = re.compile(r"(?m)^(\d{1,3})\.")
_V2_OPT_INLINE_RE = re.compile(r"\n\(([A-Da-d])\)\s*")

_V2_QA_Q_RE = re.compile(r"Question\s+(\d{1,3})\s*:\s*")
_V2_QA_OPT_RE = re.compile(r"\n\(([1-4a-dA-D])\)\s*")
_V2_QA_ANSWER_RE = re.compile(r"Answer:\s*\(([1-4a-dA-D])\)")


def classify_file_v2(filename: str) -> tuple[int | None, str | None, str | None, str]:
    """Return (exam_year, exam_name, paper_code, doc_kind) for a PDF in
    `NEET Past Papers_V2/`. Subject is not determined from the filename for
    this batch (all 4 are combined, all-subject papers) -- it is left for
    the existing deterministic subject-classification pass
    (`classify_subject.py`) to propose per-question, same as the original
    899-row batch's null `subject` column."""
    fname = filename.lower()
    if "2020" in fname:
        m = re.search(r"code[\s_-]*([a-z]\d?)", fname)
        code = m.group(1).upper() if m else None
        return 2020, "NEET (UG) 2020", code, "RAW_QUESTION_PAPER_V2_INLINE_SOLUTIONS"
    if "2022" in fname:
        m = re.search(r"code\s*[–-]?\s*([a-z]\d?)", fname)
        return 2022, "NEET (UG) 2022", None, "QA_DOC_V2_FULL"
    if "2023" in fname:
        return 2023, "NEET (UG) 2023", None, "QA_DOC_V2_FULL"
    if "2024" in fname:
        return 2024, "NEET (UG) 2024", None, "QA_DOC_V2_FULL"
    return None, None, None, "OTHER"


def segment_v2_2020(full_text: str, page_breaks: list[tuple[int, int]], source_file: str,
                     source_sha: str, paper_code: str | None, exam_year: int, exam_name: str) -> list[ExtractedQuestion]:
    """2020 Code-F1 shape: '<n>.<stem...>' then inline '(A)'..'(D)' options,
    then (usually, not always) a 'Solutions:' worked-math block with NO
    reliable per-question answer letter -- never guessed, only flagged."""
    out: list[ExtractedQuestion] = []
    raw_matches = list(_V2_2020_Q_RE.finditer(full_text))
    matches = _filter_sequential(raw_matches)
    for i, m in enumerate(matches):
        q_num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        page_num = 1
        for offset, pnum in page_breaks:
            if offset <= m.start():
                page_num = pnum
            else:
                break

        flags: list[str] = []
        status = "COMPLETE"
        confidence = 0.85

        sol_split = _SOLUTION_SPLIT_RE.search(block)
        pre_solution = block[: sol_split.start()] if sol_split else block
        explanation = block[sol_split.end():].strip() if sol_split else None
        if not sol_split:
            flags.append("missing_explanation")
            confidence -= 0.1

        opt_matches = list(_V2_OPT_INLINE_RE.finditer(pre_solution))
        if len(opt_matches) >= 4:
            stem = pre_solution[: opt_matches[0].start()].strip()
            opts = {}
            for j in range(min(4, len(opt_matches))):
                letter = opt_matches[j].group(1).upper()
                ostart = opt_matches[j].end()
                oend = opt_matches[j + 1].start() if j + 1 < len(opt_matches) else len(pre_solution)
                opts[letter] = pre_solution[ostart:oend].strip()
        else:
            stem = pre_solution.strip()
            opts = None
            flags.append("missing_options")
            status = "NEEDS_REVIEW"
            confidence -= 0.3

        # This source has no clean per-question answer-letter marker in the
        # text layer in the general case (verified by inspection -- see
        # module docstring above). Only accept an explicit, unambiguous
        # "Answer: (X)" / "Ans: (X)" marker if present; otherwise flag
        # missing_answer rather than inferring anything from the solution
        # prose.
        ans_m = re.search(r"\bAns(?:wer)?\s*[:.]?\s*\(([A-Da-d])\)", block)
        answer_raw = ans_m.group(1).upper() if ans_m else None
        if not answer_raw:
            flags.append("missing_answer")
            status = "NEEDS_REVIEW"
            confidence -= 0.3

        if _has_ocr_glyph_error(stem) or (opts is not None and any(_has_ocr_glyph_error(v) for v in opts.values())):
            flags.append("ocr_glyph_error_signal")
            status = "NEEDS_REVIEW"
            confidence -= 0.1

        has_img_ref = _has_image_keyword(stem)
        if has_img_ref:
            flags.append("possible_image_dependency")

        if len(stem) < 5:
            flags.append("uncertain_question_boundary")
            status = "NEEDS_REVIEW"
            confidence -= 0.2

        confidence = max(0.1, min(1.0, confidence))
        out.append(ExtractedQuestion(
            source_file=source_file,
            source_file_sha256=source_sha,
            page_number=page_num,
            question_number_raw=q_num,
            paper_code=paper_code,
            exam_year=exam_year,
            exam_name=exam_name,
            subject=None,
            doc_kind="RAW_QUESTION_PAPER_V2_INLINE_SOLUTIONS",
            stem_text=stem,
            options=opts,
            answer_raw=answer_raw,
            explanation_text=explanation,
            raw_block_text=block[:4000],
            extraction_status=status,
            extraction_confidence=confidence,
            review_flags=flags,
            has_image_reference=has_img_ref,
        ))
    _flag_number_gaps(out)
    return out


def segment_v2_qa(full_text: str, page_breaks: list[tuple[int, int]], source_file: str,
                   source_sha: str, exam_year: int, exam_name: str) -> list[ExtractedQuestion]:
    """2022/2023/2024 shape: 'Question <n>: ... Options: (x) ... Answer:
    (x) Solution: ...', global numbering up to 200 (NEET optional-section
    format). Mirrors segment_2025 but accepts digit OR letter option/answer
    markers, and does not assume a per-subject numbering offset."""
    out: list[ExtractedQuestion] = []
    matches = list(_V2_QA_Q_RE.finditer(full_text))
    for i, m in enumerate(matches):
        q_num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        page_num = 1
        for offset, pnum in page_breaks:
            if offset <= m.start():
                page_num = pnum
            else:
                break

        flags: list[str] = []
        status = "COMPLETE"
        confidence = 0.9

        ans_m = _V2_QA_ANSWER_RE.search(block)
        answer_raw = ans_m.group(1).lower() if ans_m else None
        if not answer_raw:
            flags.append("missing_answer")
            status = "NEEDS_REVIEW"
            confidence -= 0.3

        sol_split = _SOLUTION_SPLIT_RE.search(block)
        pre_solution = block[: sol_split.start()] if sol_split else block
        explanation = block[sol_split.end():].strip() if sol_split else None
        if not sol_split:
            flags.append("missing_explanation")
            confidence -= 0.1

        opts_idx = pre_solution.find("Options:")
        if opts_idx == -1:
            stem = pre_solution.strip()
            opts = None
            flags.append("missing_options")
            status = "NEEDS_REVIEW"
            confidence -= 0.3
        else:
            stem = pre_solution[:opts_idx].strip()
            opt_block = pre_solution[opts_idx + len("Options:"):]
            opt_matches = list(_V2_QA_OPT_RE.finditer(opt_block))
            if len(opt_matches) >= 4:
                opts = {}
                for j in range(len(opt_matches)):
                    letter = opt_matches[j].group(1).lower()
                    ostart = opt_matches[j].end()
                    oend = opt_matches[j + 1].start() if j + 1 < len(opt_matches) else len(opt_block)
                    text_before_answer = opt_block[ostart:oend]
                    ans_cut = text_before_answer.find("Answer:")
                    if ans_cut != -1:
                        text_before_answer = text_before_answer[:ans_cut]
                    opts[letter] = text_before_answer.strip()
            else:
                opts = None
                flags.append("missing_options")
                status = "NEEDS_REVIEW"
                confidence -= 0.3

        if _has_ocr_glyph_error(stem) or (opts is not None and any(_has_ocr_glyph_error(v) for v in opts.values())):
            flags.append("ocr_glyph_error_signal")
            status = "NEEDS_REVIEW"
            confidence -= 0.1

        has_img_ref = _has_image_keyword(stem)
        if has_img_ref:
            flags.append("possible_image_dependency")

        if len(stem) < 5:
            flags.append("uncertain_question_boundary")
            status = "NEEDS_REVIEW"
            confidence -= 0.2

        confidence = max(0.1, min(1.0, confidence))
        out.append(ExtractedQuestion(
            source_file=source_file,
            source_file_sha256=source_sha,
            page_number=page_num,
            question_number_raw=q_num,
            paper_code=None,
            exam_year=exam_year,
            exam_name=exam_name,
            subject=None,
            doc_kind="QA_DOC_V2_FULL",
            stem_text=stem,
            options=opts,
            answer_raw=answer_raw,
            explanation_text=explanation,
            raw_block_text=block[:4000],
            extraction_status=status,
            extraction_confidence=confidence,
            review_flags=flags,
            has_image_reference=has_img_ref,
        ))
    _flag_number_gaps(out)
    return out


def extract_file_v2(pdf_path: Path, image_out_dir: Path) -> tuple[list[ExtractedQuestion], list[ExtractedImage]]:
    """Same pipeline shape as extract_file(), routed through the
    NEET Past Papers_V2 classifier/segmenters instead of the original
    7-PDF batch's classify_file()."""
    source_file = str(pdf_path)
    source_sha = sha256_file(pdf_path)
    exam_year, exam_name, paper_code, doc_kind = classify_file_v2(pdf_path.name)

    doc = fitz.open(pdf_path)
    full_text_parts = []
    page_breaks: list[tuple[int, int]] = []
    offset = 0
    for i in range(doc.page_count):
        page = doc[i]
        t = page.get_text()
        page_breaks.append((offset, i + 1))
        full_text_parts.append(t)
        offset += len(t)
    full_text = "".join(full_text_parts)

    if doc_kind == "RAW_QUESTION_PAPER_V2_INLINE_SOLUTIONS":
        questions = segment_v2_2020(full_text, page_breaks, source_file, source_sha, paper_code, exam_year, exam_name)
    elif doc_kind == "QA_DOC_V2_FULL":
        questions = segment_v2_qa(full_text, page_breaks, source_file, source_sha, exam_year, exam_name)
    else:
        questions = []

    images = _extract_images_for_questions(doc, questions, pdf_path, source_file, source_sha, image_out_dir)
    doc.close()
    return questions, images


def _extract_images_for_questions(doc, questions, pdf_path: Path, source_file: str, source_sha: str,
                                    image_out_dir: Path) -> list[ExtractedImage]:
    """Factored out of extract_file() so extract_file_v2() can reuse the
    identical image-extraction + confidence-tiered association logic
    without duplicating it."""
    images: list[ExtractedImage] = []
    image_out_dir.mkdir(parents=True, exist_ok=True)
    questions_by_page: dict[int, list[ExtractedQuestion]] = {}
    for q in questions:
        questions_by_page.setdefault(q.page_number, []).append(q)

    stem = pdf_path.stem.replace(" ", "_")
    for i in range(doc.page_count):
        page = doc[i]
        page_num = i + 1
        img_list = page.get_images(full=True)
        candidates_this_page = questions_by_page.get(page_num, [])
        img_wanting = [q for q in candidates_this_page if q.has_image_reference]
        for idx, img in enumerate(img_list):
            xref = img[0]
            try:
                base = doc.extract_image(xref)
                ext = base.get("ext", "png")
                img_bytes = base["image"]
                w = base.get("width")
                h = base.get("height")
            except Exception:
                continue
            if w and h and (w < 20 or h < 20):
                continue
            fname = f"{stem}_p{page_num:03d}_img{idx:02d}.{ext}"
            out_path = image_out_dir / fname
            if not out_path.exists():
                out_path.write_bytes(img_bytes)

            if len(img_wanting) == 1:
                assoc_conf = "MEDIUM"
                assoc_basis = f"single image-dependent question on page {page_num} ({img_wanting[0].question_number_raw})"
                assoc_q = img_wanting[0].identity_key
            elif len(img_wanting) > 1:
                assoc_conf = "LOW"
                assoc_basis = f"{len(img_wanting)} image-dependent questions on page {page_num}; ambiguous which image belongs to which"
                assoc_q = None
            elif len(candidates_this_page) == 1:
                assoc_conf = "LOW"
                assoc_basis = f"only question on page {page_num}, but stem gave no image keyword"
                assoc_q = candidates_this_page[0].identity_key
            else:
                assoc_conf = "NONE"
                assoc_basis = "no confident question association on this page"
                assoc_q = None

            images.append(ExtractedImage(
                source_file=source_file,
                source_file_sha256=source_sha,
                page_number=page_num,
                image_index_on_page=idx,
                stored_path=str(out_path),
                width_px=w,
                height_px=h,
                image_format=ext,
                association_confidence=assoc_conf,
                association_basis=assoc_basis,
                question_identity_key=assoc_q,
            ))
    return images


def extract_file(pdf_path: Path, image_out_dir: Path) -> tuple[list[ExtractedQuestion], list[ExtractedImage]]:
    source_file = str(pdf_path)
    source_sha = sha256_file(pdf_path)
    exam_year, exam_name, paper_code, subject, doc_kind = classify_file(pdf_path.name)

    doc = fitz.open(pdf_path)
    full_text_parts = []
    page_breaks: list[tuple[int, int]] = []
    offset = 0
    for i in range(doc.page_count):
        page = doc[i]
        t = page.get_text()
        page_breaks.append((offset, i + 1))
        full_text_parts.append(t)
        offset += len(t)
    full_text = "".join(full_text_parts)

    if doc_kind == "RAW_QUESTION_PAPER_WITH_ANSWERS":
        questions = segment_2015(full_text, page_breaks, source_file, source_sha, paper_code, exam_year, exam_name)
    elif doc_kind == "ANALYSIS_DOC_WITH_FULL_QA_TEXT":
        questions = segment_2025(full_text, page_breaks, source_file, source_sha, exam_year, exam_name, subject)
    else:
        questions = []

    # image extraction: pull every embedded image per page, flag association confidence
    images: list[ExtractedImage] = []
    image_out_dir.mkdir(parents=True, exist_ok=True)
    questions_by_page: dict[int, list[ExtractedQuestion]] = {}
    for q in questions:
        questions_by_page.setdefault(q.page_number, []).append(q)

    stem = pdf_path.stem.replace(" ", "_")
    for i in range(doc.page_count):
        page = doc[i]
        page_num = i + 1
        img_list = page.get_images(full=True)
        candidates_this_page = questions_by_page.get(page_num, [])
        img_wanting = [q for q in candidates_this_page if q.has_image_reference]
        for idx, img in enumerate(img_list):
            xref = img[0]
            try:
                base = doc.extract_image(xref)
                ext = base.get("ext", "png")
                img_bytes = base["image"]
                w = base.get("width")
                h = base.get("height")
            except Exception:
                continue
            # skip trivially tiny images (likely decorative lines/bullets), keep threshold conservative
            if w and h and (w < 20 or h < 20):
                continue
            fname = f"{stem}_p{page_num:03d}_img{idx:02d}.{ext}"
            out_path = image_out_dir / fname
            if not out_path.exists():
                out_path.write_bytes(img_bytes)

            if len(img_wanting) == 1:
                assoc_conf = "MEDIUM"
                assoc_basis = f"single image-dependent question on page {page_num} ({img_wanting[0].question_number_raw})"
                assoc_q = img_wanting[0].identity_key
            elif len(img_wanting) > 1:
                assoc_conf = "LOW"
                assoc_basis = f"{len(img_wanting)} image-dependent questions on page {page_num}; ambiguous which image belongs to which"
                assoc_q = None
            elif len(candidates_this_page) == 1:
                assoc_conf = "LOW"
                assoc_basis = f"only question on page {page_num}, but stem gave no image keyword"
                assoc_q = candidates_this_page[0].identity_key
            else:
                assoc_conf = "NONE"
                assoc_basis = "no confident question association on this page"
                assoc_q = None

            images.append(ExtractedImage(
                source_file=source_file,
                source_file_sha256=source_sha,
                page_number=page_num,
                image_index_on_page=idx,
                stored_path=str(out_path),
                width_px=w,
                height_px=h,
                image_format=ext,
                association_confidence=assoc_conf,
                association_basis=assoc_basis,
                question_identity_key=assoc_q,
            ))

    doc.close()
    return questions, images
