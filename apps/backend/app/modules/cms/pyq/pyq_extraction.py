"""Deterministic NEET PYQ extraction (FACTORY-PYQ-P1).

Local PDF text extraction only — no AI, no OCR APIs, no DB writes.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import fitz

from app.modules.cms.pyq.pyq_discovery import (
    MATH_MARKERS,
    ZipFileEntry,
    normalized_question_hash,
)

PAGE_MARKER_RE = re.compile(r"<<<PAGE:(\d+)>>>")
SECTION_HEADER_RE = re.compile(
    r"Section\s*-\s*[AB]\s*\(\s*(Physics|Chemistry|Biology\s*:\s*Botany|Biology\s*:\s*Zoology|Biology|Botany|Zoology|Mathematics|Maths)\s*\)",
    re.I,
)
QUESTION_START_RE = re.compile(r"(?m)^\s*(\d{1,3})\.\s+")
# OCR often drops the '.' after question numbers and merges two columns with ' | '.
OCR_QUESTION_START_RE = re.compile(
    r"(?m)(?:^|\|\s*)\s*(\d{1,3})(?:\.\s+|\s+)(?=[A-Z(])"
)
OPTION_START_RE = re.compile(r"\(\s*([1-4])\s*\)")
COLUMN_GAP_RE = re.compile(r"\s+\|\s+")
# Scanned NEET headers often appear as "Physics : Section-A" rather than "Section - A (Physics)".
OCR_SECTION_HEADER_RE = re.compile(
    r"(Physics|Chemistry|Biology(?:\s*:\s*(?:Botany|Zoology))?|Botany|Zoology)\s*:\s*Section\s*-?\s*[AB]",
    re.I,
)
ANSWER_KEY_SECTION_RE = re.compile(
    r"(?m)^\s*(?:answer\s*key|key\s*to\s*questions)\s*:?\s*$",
    re.I,
)
ANSWER_GRID_RE = re.compile(
    r"(?m)^\s*(\d{1,3})\s*[\).:\-]\s*([1-4A-Da-d])\s*$",
)


class ExtractionMode(str, Enum):
    TEXT = "TEXT"
    SCANNED = "SCANNED"
    MIXED = "MIXED"
    OCR_REQUIRED = "OCR_REQUIRED"


class AnswerStatus(str, Enum):
    ANSWER_PENDING = "ANSWER_PENDING"
    ANSWER_KNOWN = "ANSWER_KNOWN"
    ANSWER_CONFLICT = "ANSWER_CONFLICT"
    ANSWER_UNVERIFIED = "ANSWER_UNVERIFIED"


class ValidationStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    OCR_REQUIRED = "OCR_REQUIRED"
    OCR_EXTRACTED = "OCR_EXTRACTED"
    OCR_FAILED = "OCR_FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    EXCLUDED_NON_NEET_SUBJECT = "EXCLUDED_NON_NEET_SUBJECT"
    DUPLICATE_EXTRACTION_CANDIDATE = "DUPLICATE_EXTRACTION_CANDIDATE"
    VALIDATION_FLAG = "VALIDATION_FLAG"


@dataclass
class PageText:
    page_number: int
    text: str
    char_count: int
    is_scanned: bool


@dataclass
class ExtractedQuestion:
    staging_id: str
    paper_id: str
    exam_year: str | None
    paper_code: str | None
    set_code: str | None
    language: str | None
    question_number: int | None
    subject: str | None
    subsection: str | None
    stem: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str | None
    answer_status: str
    answer_source: str | None
    answer_source_page: int | None
    source_file: str
    source_sha256: str
    source_page: int | None
    question_hash: str
    normalized_question_hash: str
    extraction_mode: str
    extraction_confidence: float
    validation_status: str
    raw_extracted_text: str
    duplicate_within_paper: bool = False
    anomalies: list[str] = field(default_factory=list)


@dataclass
class PaperExtractionResult:
    paper_id: str
    source_file: str
    source_sha256: str
    exam_year: str | None
    paper_code: str | None
    set_code: str | None
    language: str | None
    page_count: int
    extraction_mode: str
    extraction_confidence: float
    booklet_code: str | None
    questions: list[ExtractedQuestion] = field(default_factory=list)
    ocr_required_pages: list[int] = field(default_factory=list)
    answer_key_hits: list[dict[str, Any]] = field(default_factory=list)
    validation_anomalies: list[str] = field(default_factory=list)
    mathematics_exclusions: int = 0


def question_hash(stem: str, options: list[str]) -> str:
    blob = "|".join([stem.strip(), *[o.strip() for o in options]])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _normalize_subject(label: str) -> tuple[str | None, str | None]:
    cleaned = re.sub(r"\s+", " ", label.strip().lower())
    if any(m.lower() in cleaned for m in MATH_MARKERS):
        return None, "EXCLUDED_NON_NEET_SUBJECT"
    if "botany" in cleaned:
        return "Botany", None
    if "zoology" in cleaned:
        return "Zoology", None
    if "biology" in cleaned:
        return "Biology", None
    if "physics" in cleaned:
        return "Physics", None
    if "chemistry" in cleaned:
        return "Chemistry", None
    if "math" in cleaned:
        return None, "EXCLUDED_NON_NEET_SUBJECT"
    return None, None


def detect_document_extractability(pages: list[PageText]) -> tuple[str, float, list[int]]:
    if not pages:
        return ExtractionMode.SCANNED.value, 0.0, []

    scanned_pages = [p.page_number for p in pages if p.is_scanned]
    text_pages = [p for p in pages if not p.is_scanned and p.char_count > 40]
    total_chars = sum(p.char_count for p in pages)

    if not text_pages and scanned_pages:
        return ExtractionMode.SCANNED.value, 0.1, scanned_pages
    if scanned_pages and text_pages:
        ratio = len(scanned_pages) / max(len(pages), 1)
        confidence = max(0.2, 0.8 - ratio * 0.5)
        return ExtractionMode.MIXED.value, confidence, scanned_pages
    confidence = min(0.95, 0.5 + min(total_chars, 50000) / 100000)
    return ExtractionMode.TEXT.value, confidence, scanned_pages


def extract_pages(pdf_bytes: bytes) -> list[PageText]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[PageText] = []
    try:
        for idx in range(doc.page_count):
            page = doc.load_page(idx)
            text = page.get_text() or ""
            stripped = text.strip()
            is_scanned = len(stripped) < 40 and bool(page.get_images())
            pages.append(
                PageText(
                    page_number=idx + 1,
                    text=text,
                    char_count=len(stripped),
                    is_scanned=is_scanned,
                )
            )
    finally:
        doc.close()
    return pages


def build_tagged_corpus(pages: list[PageText]) -> str:
    chunks: list[str] = []
    for page in pages:
        chunks.append(f"<<<PAGE:{page.page_number}>>>\n{page.text}")
    return "\n".join(chunks)


def page_for_position(corpus: str, pos: int) -> int:
    markers = [(m.start(), int(m.group(1))) for m in PAGE_MARKER_RE.finditer(corpus)]
    current = 1
    for start, page_num in markers:
        if start <= pos:
            current = page_num
        else:
            break
    return current


def find_section_spans(corpus: str) -> list[tuple[int, str | None, str | None]]:
    spans: list[tuple[int, str | None, str | None]] = [(0, None, None)]
    for match in SECTION_HEADER_RE.finditer(corpus):
        subject, exclusion = _normalize_subject(match.group(1))
        spans.append((match.start(), subject, exclusion))
    for match in OCR_SECTION_HEADER_RE.finditer(corpus):
        subject, exclusion = _normalize_subject(match.group(1))
        spans.append((match.start(), subject, exclusion))
    spans.sort(key=lambda item: item[0])
    return spans


def normalize_ocr_multicolumn_text(text: str) -> str:
    """Deterministically de-interleave OCR lines that merged left|right columns.

    Contiguous runs of 'left | right' lines are rewritten as all-left then
    all-right. Non-pipe lines stay in place so section headers/options are not
    relocated. Does not invent stems, options, or answers.
    """
    if not text or " | " not in text:
        return _break_inline_ocr_question_numbers(text)

    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = COLUMN_GAP_RE.split(line, maxsplit=1) if " | " in line else None
        if parts and len(parts) == 2 and parts[0].strip() and parts[1].strip():
            left: list[str] = []
            right: list[str] = []
            while i < len(lines):
                cur = lines[i]
                cur_parts = COLUMN_GAP_RE.split(cur, maxsplit=1) if " | " in cur else None
                if not (cur_parts and len(cur_parts) == 2 and cur_parts[0].strip() and cur_parts[1].strip()):
                    break
                left.append(cur_parts[0].rstrip())
                right.append(cur_parts[1].lstrip())
                i += 1
            if len(left) >= 2:
                out.extend(left)
                out.extend(right)
            else:
                # Single ambiguous split — keep original wording.
                out.extend(lines[i - len(left) : i] if left else [line])
            continue
        out.append(line)
        i += 1

    return _break_inline_ocr_question_numbers("\n".join(out))


def _break_inline_ocr_question_numbers(text: str) -> str:
    """Insert line breaks before mid-line OCR question numbers (no '.')."""
    if not text:
        return text
    # Avoid breaking option markers like "(1)" — require no '(' immediately before.
    return re.sub(
        r"(?<=[a-zA-Z\)\]])(\s+)(\d{1,3})(?:\.\s+|\s+)(?=[A-Z(])",
        r"\n\2. ",
        text,
    )


def normalize_ocr_corpus(corpus: str) -> str:
    """Normalize a tagged <<<PAGE:N>>> OCR corpus page-by-page."""
    if "<<<PAGE:" not in corpus:
        return normalize_ocr_multicolumn_text(corpus)

    parts = PAGE_MARKER_RE.split(corpus)
    # split yields: [pre, page_num, body, page_num, body, ...]
    if len(parts) < 3:
        return normalize_ocr_multicolumn_text(corpus)

    out: list[str] = []
    pre = parts[0]
    if pre.strip():
        out.append(normalize_ocr_multicolumn_text(pre))
    idx = 1
    while idx + 1 < len(parts):
        page_num = parts[idx]
        body = parts[idx + 1]
        out.append(f"<<<PAGE:{page_num}>>>\n{normalize_ocr_multicolumn_text(body)}")
        idx += 2
    return "\n".join(out)


def subject_at_position(spans: list[tuple[int, str | None, str | None]], pos: int) -> tuple[str | None, str | None]:
    subject = None
    exclusion = None
    for start, subj, excl in spans:
        if start <= pos:
            subject = subj
            exclusion = excl
        else:
            break
    return subject, exclusion


def _is_instruction_block(corpus: str, start: int) -> bool:
    window = corpus[max(0, start - 240) : start + 160].lower()
    markers = (
        "important instructions",
        "answer sheet is inside",
        "candidate must show",
        "do not open this test booklet",
        "read carefully the following instructions",
        "following instructions",
        "admit card to the invigilator",
        "attendance sheet",
        "unfair means",
        "space for rough work",
        "use of electronic/manual calculator",
        "booklet code",
    )
    return any(m in window for m in markers)


def _confidence_for_question(stem: str, options: dict[str, str]) -> float:
    score = 0.2
    if stem.strip():
        score += 0.25
    filled = sum(1 for key in ("1", "2", "3", "4") if options.get(key, "").strip())
    score += filled * 0.125
    if len(stem.strip()) > 20:
        score += 0.05
    return min(score, 0.99)


def parse_options(block: str) -> tuple[str, dict[str, str]]:
    matches = list(OPTION_START_RE.finditer(block))
    if not matches:
        return block.strip(), {}

    stem = block[: matches[0].start()].strip()
    # Remove leading question number from stem
    stem = re.sub(r"^\d{1,3}\.\s*", "", stem, count=1).strip()

    options: dict[str, str] = {}
    for idx, match in enumerate(matches):
        key = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        options[key] = block[start:end].strip()
    return stem, options


def search_embedded_answers(corpus: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for match in ANSWER_KEY_SECTION_RE.finditer(corpus):
        hits.append(
            {
                "pattern": match.group(0),
                "page": page_for_position(corpus, match.start()),
                "position": match.start(),
            }
        )

    for match in ANSWER_GRID_RE.finditer(corpus):
        hits.append(
            {
                "pattern": "answer_grid_line",
                "question_number": int(match.group(1)),
                "correct_option": match.group(2).upper(),
                "page": page_for_position(corpus, match.start()),
                "position": match.start(),
            }
        )
    return hits


def _answer_key_regions(corpus: str) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    for match in ANSWER_KEY_SECTION_RE.finditer(corpus):
        start = match.start()
        regions.append((start, min(len(corpus), start + 8000)))
    return regions


def authoritative_answers(corpus: str) -> dict[int, dict[str, Any]]:
    """Return grid-style answers only inside explicit answer-key regions."""
    answers: dict[int, dict[str, Any]] = {}
    for region_start, region_end in _answer_key_regions(corpus):
        region = corpus[region_start:region_end]
        grid_hits: list[tuple[int, str, int]] = []
        for match in ANSWER_GRID_RE.finditer(region):
            qn = int(match.group(1))
            opt = match.group(2).upper()
            if opt in {"A", "B", "C", "D"}:
                mapped = {"A": "1", "B": "2", "C": "3", "D": "4"}[opt]
            elif opt in {"1", "2", "3", "4"}:
                mapped = opt
            else:
                continue
            grid_hits.append((qn, mapped, region_start + match.start()))

        # Require a dense authoritative grid, not isolated ratio lines inside questions.
        if len(grid_hits) < 10:
            continue
        for qn, mapped, abs_pos in grid_hits:
            answers[qn] = {
                "correct_option": mapped,
                "answer_source": "embedded_answer_grid",
                "answer_source_page": page_for_position(corpus, abs_pos),
                "answer_confidence": 0.85,
            }
    return answers


def extract_booklet_code(corpus: str) -> str | None:
    match = re.search(r"CODE for this Booklet is\s+([A-Z0-9]+)", corpus, re.I)
    if match:
        return match.group(1).upper()
    match = re.search(r"Booklet\s+([A-Z0-9]{1,4})\b", corpus, re.I)
    return match.group(1).upper() if match else None


def segment_questions_from_text(
    corpus: str,
    *,
    paper_id: str,
    entry: ZipFileEntry,
    extraction_mode: str,
    extraction_confidence: float,
    ocr_pages: list[int],
) -> list[ExtractedQuestion]:
    mode_upper = extraction_mode.upper()
    if mode_upper == "OCR":
        corpus = normalize_ocr_corpus(corpus)
    # OCR_GEOMETRY: corpus already column-ordered by pyq_geometry — do not re-normalize.

    section_spans = find_section_spans(corpus)
    answer_map = authoritative_answers(corpus)

    # When explicit subject sections exist, ignore preamble/instruction numbering.
    content_start = 0
    real_sections = [(pos, subj, excl) for pos, subj, excl in section_spans if subj or excl]
    if real_sections:
        content_start = real_sections[0][0]
    else:
        page_two = corpus.find("<<<PAGE:2>>>")
        if page_two != -1:
            content_start = page_two

    start_re = (
        OCR_QUESTION_START_RE
        if mode_upper in {"OCR", "OCR_GEOMETRY"}
        else QUESTION_START_RE
    )
    question_starts = [
        (int(match.group(1)), match.start(), match.end())
        for match in start_re.finditer(corpus)
        if match.start() >= content_start and not _is_instruction_block(corpus, match.start())
    ]
    if not question_starts:
        return []

    # Drop duplicate question numbers — keep first occurrence only for segmentation
    seen_numbers: set[int] = set()
    filtered: list[tuple[int, int, int]] = []
    for qnum, start, end in question_starts:
        if qnum in seen_numbers:
            continue
        # OCR mode: ignore implausible numbers outside NEET booklet ranges.
        if extraction_mode.upper() in {"OCR", "OCR_GEOMETRY"} and (qnum < 1 or qnum > 200):
            continue
        seen_numbers.add(qnum)
        filtered.append((qnum, start, end))

    questions: list[ExtractedQuestion] = []
    for idx, (qnum, start, end_marker) in enumerate(filtered):
        block_end = filtered[idx + 1][1] if idx + 1 < len(filtered) else len(corpus)
        block = corpus[end_marker:block_end]
        page = page_for_position(corpus, start)
        if page in ocr_pages:
            continue

        subject, exclusion = subject_at_position(section_spans, start)
        stem, options = parse_options(block)
        raw_text = re.sub(r"<<<PAGE:\d+>>>\n?", "", block).strip()

        opt_list = [options.get(str(i), "") for i in range(1, 5)]
        if exclusion == "EXCLUDED_NON_NEET_SUBJECT":
            validation_status = ValidationStatus.EXCLUDED_NON_NEET_SUBJECT.value
            subject = "Mathematics"
        elif not stem and not any(opt_list):
            validation_status = ValidationStatus.OCR_REQUIRED.value
        else:
            validation_status = ValidationStatus.EXTRACTED.value

        q_conf = _confidence_for_question(stem, options)
        ans = answer_map.get(qnum)
        if ans:
            answer_status = AnswerStatus.ANSWER_KNOWN.value
            correct_option = ans["correct_option"]
            answer_source = ans["answer_source"]
            answer_source_page = ans["answer_source_page"]
        else:
            answer_status = AnswerStatus.ANSWER_PENDING.value
            correct_option = None
            answer_source = None
            answer_source_page = None

        questions.append(
            ExtractedQuestion(
                staging_id=str(uuid.uuid4()),
                paper_id=paper_id,
                exam_year=entry.year,
                paper_code=entry.paper_code,
                set_code=entry.set_code,
                language=entry.language,
                question_number=qnum,
                subject=subject,
                subsection=subject if subject in {"Botany", "Zoology"} else None,
                stem=stem,
                option_a=opt_list[0],
                option_b=opt_list[1],
                option_c=opt_list[2],
                option_d=opt_list[3],
                correct_option=correct_option,
                answer_status=answer_status,
                answer_source=answer_source,
                answer_source_page=answer_source_page,
                source_file=entry.relative_path,
                source_sha256=entry.sha256,
                source_page=page,
                question_hash=question_hash(stem, opt_list),
                normalized_question_hash=normalized_question_hash(stem, opt_list),
                extraction_mode=extraction_mode,
                extraction_confidence=round(min(extraction_confidence, q_conf), 3),
                validation_status=validation_status,
                raw_extracted_text=raw_text,
            )
        )
    return questions


def mark_within_paper_duplicates(questions: list[ExtractedQuestion]) -> None:
    seen: dict[str, int] = {}
    for question in questions:
        key = question.normalized_question_hash
        if not question.stem.strip():
            continue
        if key in seen:
            question.duplicate_within_paper = True
            question.validation_status = ValidationStatus.DUPLICATE_EXTRACTION_CANDIDATE.value
        else:
            seen[key] = question.question_number or -1


def extract_paper(entry: ZipFileEntry, pdf_bytes: bytes) -> PaperExtractionResult:
    paper_id = entry.sha256[:16]
    pages = extract_pages(pdf_bytes)
    mode, confidence, ocr_pages = detect_document_extractability(pages)
    corpus = build_tagged_corpus(pages)
    booklet_code = extract_booklet_code(corpus)
    answer_hits = search_embedded_answers(corpus)

    result = PaperExtractionResult(
        paper_id=paper_id,
        source_file=entry.relative_path,
        source_sha256=entry.sha256,
        exam_year=entry.year,
        paper_code=entry.paper_code,
        set_code=entry.set_code,
        language=entry.language,
        page_count=len(pages),
        extraction_mode=mode,
        extraction_confidence=confidence,
        booklet_code=booklet_code,
        ocr_required_pages=ocr_pages,
        answer_key_hits=answer_hits,
    )

    if entry.classification.value == "EXCLUDED_NON_NEET_SUBJECT":
        result.validation_anomalies.append("file_classified_as_mathematics_excluded")
        return result

    if mode == ExtractionMode.SCANNED.value:
        result.validation_anomalies.append("paper_requires_ocr")
        for page_num in ocr_pages or [p.page_number for p in pages]:
            result.questions.append(
                ExtractedQuestion(
                    staging_id=str(uuid.uuid4()),
                    paper_id=paper_id,
                    exam_year=entry.year,
                    paper_code=entry.paper_code,
                    set_code=entry.set_code,
                    language=entry.language,
                    question_number=None,
                    subject=None,
                    subsection=None,
                    stem="",
                    option_a="",
                    option_b="",
                    option_c="",
                    option_d="",
                    correct_option=None,
                    answer_status=AnswerStatus.ANSWER_PENDING.value,
                    answer_source=None,
                    answer_source_page=None,
                    source_file=entry.relative_path,
                    source_sha256=entry.sha256,
                    source_page=page_num,
                    question_hash="",
                    normalized_question_hash="",
                    extraction_mode=ExtractionMode.OCR_REQUIRED.value,
                    extraction_confidence=0.0,
                    validation_status=ValidationStatus.OCR_REQUIRED.value,
                    raw_extracted_text="",
                    anomalies=["ocr_required_page"],
                )
            )
        return result

    questions = segment_questions_from_text(
        corpus,
        paper_id=paper_id,
        entry=entry,
        extraction_mode=mode,
        extraction_confidence=confidence,
        ocr_pages=ocr_pages,
    )
    mark_within_paper_duplicates(questions)
    result.questions = questions
    result.mathematics_exclusions = sum(
        1 for q in questions if q.validation_status == ValidationStatus.EXCLUDED_NON_NEET_SUBJECT.value
    )

    if ocr_pages:
        for page_num in ocr_pages:
            result.questions.append(
                ExtractedQuestion(
                    staging_id=str(uuid.uuid4()),
                    paper_id=paper_id,
                    exam_year=entry.year,
                    paper_code=entry.paper_code,
                    set_code=entry.set_code,
                    language=entry.language,
                    question_number=None,
                    subject=None,
                    subsection=None,
                    stem="",
                    option_a="",
                    option_b="",
                    option_c="",
                    option_d="",
                    correct_option=None,
                    answer_status=AnswerStatus.ANSWER_PENDING.value,
                    answer_source=None,
                    answer_source_page=None,
                    source_file=entry.relative_path,
                    source_sha256=entry.sha256,
                    source_page=page_num,
                    question_hash="",
                    normalized_question_hash="",
                    extraction_mode=ExtractionMode.OCR_REQUIRED.value,
                    extraction_confidence=0.0,
                    validation_status=ValidationStatus.OCR_REQUIRED.value,
                    raw_extracted_text="",
                    anomalies=["ocr_required_page"],
                )
            )
    return result


def validate_paper_extraction(result: PaperExtractionResult) -> list[str]:
    anomalies: list[str] = []
    extracted = [
        q for q in result.questions if q.validation_status == ValidationStatus.EXTRACTED.value
    ]
    ocr_stubs = [
        q for q in result.questions if q.validation_status == ValidationStatus.OCR_REQUIRED.value
    ]

    if result.extraction_mode == ExtractionMode.SCANNED.value:
        anomalies.append("full_paper_ocr_required")
        return anomalies

    numbers = sorted(q.question_number for q in extracted if q.question_number is not None)
    if numbers:
        expected = list(range(min(numbers), max(numbers) + 1))
        missing = sorted(set(expected) - set(numbers))
        if missing:
            anomalies.append(f"missing_question_numbers:{missing[:20]}")
        dup_nums = sorted({n for n in numbers if numbers.count(n) > 1})
        if dup_nums:
            anomalies.append(f"duplicate_question_numbers:{dup_nums}")

    for q in extracted:
        if not q.stem.strip():
            anomalies.append(f"empty_stem:Q{q.question_number}")
        opts = [q.option_a, q.option_b, q.option_c, q.option_d]
        if sum(1 for o in opts if o.strip()) < 4:
            anomalies.append(f"missing_options:Q{q.question_number}")
        if q.duplicate_within_paper:
            anomalies.append(f"duplicate_extraction:Q{q.question_number}")

    if ocr_stubs:
        anomalies.append(f"ocr_required_pages:{len(ocr_stubs)}")

    if result.mathematics_exclusions:
        anomalies.append(f"mathematics_exclusions:{result.mathematics_exclusions}")

    answer_grids = [h for h in result.answer_key_hits if h.get("pattern") == "answer_grid_line"]
    if answer_grids and all(q.answer_status == AnswerStatus.ANSWER_PENDING.value for q in extracted):
        anomalies.append("answer_key_markers_without_authoritative_grid")

    result.validation_anomalies.extend(anomalies)
    return anomalies
