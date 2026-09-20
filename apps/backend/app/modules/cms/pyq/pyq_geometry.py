"""FACTORY-PYQ-P2.1C — geometry-first column layout for OCR resegmentation.

Uses PyMuPDF page geometry (mediabox) plus existing OCR text. Does NOT invoke
Tesseract or modify source PDFs/ZIPs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import fitz

from app.modules.cms.pyq.pyq_extraction import (
    COLUMN_GAP_RE,
    _break_inline_ocr_question_numbers,
)

# Footer/header patterns — exclude from question body assembly when possible.
FOOTER_RE = re.compile(
    r"(?i)(?:G\d_English|T\d_English|H\d_English|E\d_English|\[\s*Contd|\]\s*\d+\s*\[|"
    r"T\d_Hindi\+English|Hindi\+English\s*\])"
)
PAGE_NUM_ONLY_RE = re.compile(r"^\s*\d{1,3}\s*$")
INSTRUCTION_MARKERS = (
    "important instructions",
    "read carefully the following instructions",
    "do not open this test booklet",
    "candidate must show",
    "answer sheet is inside",
    "space for rough work",
    "unfair means",
    "booklet code",
    "centre superintendent",
)

QUESTION_NUM_RE = re.compile(r"^\s*(\d{1,3})(?:\.\s+|\s+)(?=[A-Z(])")
MIDLINE_QUESTION_NUM_RE = re.compile(r"(?<=[?.!\s])(\d{1,3})(?:\.\s+|\s+)(?=[A-Z(])")
OPTION_LINE_RE = re.compile(r"^\s*\(\s*([1-4])\s*\)")


class PageLayout(str, Enum):
    ONE_COLUMN = "ONE_COLUMN"
    TWO_COLUMN = "TWO_COLUMN"
    UNKNOWN = "UNKNOWN"


@dataclass
class PageGeometry:
    page_number: int
    width: float
    height: float
    split_x: float | None = None

    @classmethod
    def from_page(cls, page_number: int, page: fitz.Page) -> PageGeometry:
        rect = page.rect
        return cls(page_number=page_number, width=float(rect.width), height=float(rect.height))


@dataclass
class ColumnSplitResult:
    layout: PageLayout
    left_text: str
    right_text: str
    split_x: float | None
    pipe_line_ratio: float
    orphan_lines: int
    evidence: list[str] = field(default_factory=list)


@dataclass
class PageGeometryAnnotation:
    page_number: int
    layout: str
    width: float
    height: float
    split_x: float | None
    pipe_line_ratio: float
    word_count: int
    evidence: list[str]


def extract_page_words(page: fitz.Page) -> list[tuple[float, float, float, float, str]]:
    """Return (x0, y0, x1, y1, text) for each word from PyMuPDF."""
    words: list[tuple[float, float, float, float, str]] = []
    for w in page.get_text("words") or []:
        if len(w) >= 5 and str(w[4]).strip():
            words.append((float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])))
    return words


def _instruction_density(text: str) -> int:
    low = text.lower()
    return sum(1 for m in INSTRUCTION_MARKERS if m in low)


def is_instruction_page(ocr_text: str, page_number: int) -> bool:
    """Detect bilingual/instruction cover pages — must not yield questions."""
    if page_number == 1:
        return True
    low = ocr_text.lower()
    if _instruction_density(ocr_text) >= 2:
        return True
    if "important instructions" in low and "answer sheet is inside" in low:
        return True
    if "do not open this test booklet" in low:
        return True
    return False


def _split_merged_question_line(line: str) -> list[str]:
    """Split a single OCR line that contains multiple question-number starts."""
    matches = list(QUESTION_NUM_RE.finditer(line))
    if not matches:
        matches = list(MIDLINE_QUESTION_NUM_RE.finditer(line))
    if len(matches) <= 1:
        return [line]
    parts: list[str] = []
    # Prefix before first question marker stays with first segment if non-empty.
    prefix = line[: matches[0].start()].strip()
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
        chunk = line[start:end].strip()
        if i == 0 and prefix:
            chunk = f"{prefix} {chunk}".strip()
        if chunk:
            parts.append(chunk)
    return parts if parts else [line]


def _split_inline_column_bleed(text: str) -> str:
    """Break lines where a second question number appears mid-line after column split."""
    out_lines: list[str] = []
    for line in text.splitlines():
        expanded: list[str] = []
        for piece in _split_merged_question_line(line):
            expanded.extend(_split_merged_question_line(piece))
        out_lines.extend(expanded)
    return "\n".join(out_lines)


def _is_header_footer_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if PAGE_NUM_ONLY_RE.match(stripped):
        return True
    if FOOTER_RE.search(stripped) and len(stripped) < 80:
        return True
    return False


def _question_numbers_in_text(text: str) -> list[int]:
    nums: list[int] = []
    for line in text.splitlines():
        m = QUESTION_NUM_RE.match(line.strip())
        if m:
            nums.append(int(m.group(1)))
    return nums


def detect_page_layout(
    ocr_text: str,
    page_geom: PageGeometry,
    *,
    rough_work: bool = False,
) -> tuple[PageLayout, list[str], float]:
    """Classify page layout from OCR pipe density and page geometry."""
    evidence: list[str] = []
    lines = [ln for ln in ocr_text.splitlines() if ln.strip()]
    if rough_work or ("SPACE FOR ROUGH WORK" in ocr_text.upper() and len(ocr_text.strip()) < 120):
        evidence.append("rough_work_blank")
        return PageLayout.ONE_COLUMN, evidence, 0.0

    if not lines:
        evidence.append("empty_page")
        return PageLayout.ONE_COLUMN, evidence, 0.0

    instr = _instruction_density(ocr_text)
    if is_instruction_page(ocr_text, page_geom.page_number):
        evidence.append("instruction_page")
        return PageLayout.ONE_COLUMN, evidence, 0.0

    if instr >= 2 and _instruction_density(ocr_text[:800]) >= 2:
        evidence.append("instruction_page")
        return PageLayout.ONE_COLUMN, evidence, 0.0

    pipe_lines = sum(1 for ln in lines if COLUMN_GAP_RE.search(ln))
    ratio = pipe_lines / max(len(lines), 1)
    evidence.append(f"pipe_line_ratio={ratio:.3f}")

    # Scanned NEET pages: image-only PDFs still have portrait mediabox geometry.
    if page_geom.width > 0:
        evidence.append(f"page_width={page_geom.width:.1f}")

    if ratio >= 0.20 or (pipe_lines >= 4 and ratio >= 0.10):
        evidence.append("two_column_pipe_evidence")
        split_x = page_geom.width / 2.0 if page_geom.width else None
        page_geom.split_x = split_x
        return PageLayout.TWO_COLUMN, evidence, ratio

    if ratio >= 0.05 and pipe_lines >= 2:
        evidence.append("two_column_weak_pipe_evidence")
        page_geom.split_x = page_geom.width / 2.0 if page_geom.width else None
        return PageLayout.TWO_COLUMN, evidence, ratio

    # Word geometry when PDF has an embedded text layer (TEXT/MIXED papers).
    words = getattr(page_geom, "_words", None)
    if words and len(words) >= 12:
        centers = [(w[0] + w[2]) / 2.0 for w in words]
        mid = page_geom.width / 2.0
        left = sum(1 for c in centers if c < mid - 10)
        right = sum(1 for c in centers if c > mid + 10)
        if left >= 5 and right >= 5:
            evidence.append("two_column_word_cluster_evidence")
            page_geom.split_x = mid
            return PageLayout.TWO_COLUMN, evidence, ratio

    if ratio < 0.03 and len(lines) >= 3:
        evidence.append("single_column_low_pipe")
        return PageLayout.ONE_COLUMN, evidence, ratio

    evidence.append("layout_uncertain")
    return PageLayout.UNKNOWN, evidence, ratio


def _assign_orphan_lines(
    orphans: list[str],
    left_lines: list[str],
    right_lines: list[str],
) -> tuple[list[str], list[str]]:
    """Assign non-pipe OCR lines to left or right column using numbering context."""
    if not orphans:
        return left_lines, right_lines

    left_nums = _question_numbers_in_text("\n".join(left_lines))
    right_nums = _question_numbers_in_text("\n".join(right_lines))
    max_left = max(left_nums) if left_nums else 0
    min_right = min(right_nums) if right_nums else 999

    active: str | None = None  # last column that received content

    for line in orphans:
        stripped = line.strip()
        if _is_header_footer_line(line):
            continue

        qm = QUESTION_NUM_RE.match(stripped)
        if qm:
            qn = int(qm.group(1))
            # Right column numbers on typical NEET pages exceed left-column max.
            if right_nums and qn >= min_right:
                right_lines.append(line)
                active = "RIGHT"
            elif left_nums and qn <= max_left + 1:
                left_lines.append(line)
                active = "LEFT"
            elif qn > max_left and max_left > 0:
                right_lines.append(line)
                active = "RIGHT"
            else:
                left_lines.append(line)
                active = "LEFT"
            continue

        if OPTION_LINE_RE.match(stripped):
            if active == "RIGHT":
                right_lines.append(line)
            elif active == "LEFT":
                left_lines.append(line)
            elif right_lines and not left_lines:
                right_lines.append(line)
            else:
                left_lines.append(line)
            continue

        # Continuation line — prefer column with open/incomplete last question.
        if active == "RIGHT":
            right_lines.append(line)
        elif active == "LEFT":
            left_lines.append(line)
        elif max_left and not right_nums:
            left_lines.append(line)
            active = "LEFT"
        else:
            left_lines.append(line)
            active = "LEFT"

    return left_lines, right_lines


def _line_question_number(line: str) -> int | None:
    stripped = line.strip()
    m = QUESTION_NUM_RE.match(stripped) or MIDLINE_QUESTION_NUM_RE.search(stripped)
    if m:
        return int(m.group(1))
    return None


def _relocate_high_number_lines(
    left_lines: list[str],
    right_lines: list[str],
) -> tuple[list[str], list[str]]:
    """Move lines starting with Q# that belong to the right column off the left stack."""
    right_nums = _question_numbers_in_text("\n".join(right_lines))
    if not right_nums:
        return left_lines, right_lines
    min_right = min(right_nums)
    new_left: list[str] = []
    relocated: list[str] = []
    for line in left_lines:
        qn = _line_question_number(line)
        if qn is not None and qn >= min_right:
            relocated.append(line)
        else:
            new_left.append(line)
    if relocated:
        right_lines = right_lines + relocated
    return new_left, right_lines


def split_page_columns(
    ocr_text: str,
    layout: PageLayout,
    page_geom: PageGeometry,
) -> ColumnSplitResult:
    """Split OCR page text into left/right columns using pipe markers and geometry."""
    if layout == PageLayout.ONE_COLUMN:
        cleaned = _clean_column_text(ocr_text)
        return ColumnSplitResult(
            layout=layout,
            left_text=cleaned,
            right_text="",
            split_x=None,
            pipe_line_ratio=0.0,
            orphan_lines=0,
            evidence=["one_column_no_split"],
        )

    if layout == PageLayout.UNKNOWN:
        cleaned = _clean_column_text(ocr_text)
        return ColumnSplitResult(
            layout=layout,
            left_text=cleaned,
            right_text="",
            split_x=None,
            pipe_line_ratio=0.0,
            orphan_lines=0,
            evidence=["unknown_layout_whole_page"],
        )

    left_lines: list[str] = []
    right_lines: list[str] = []
    orphans: list[str] = []
    pipe_count = 0

    for line in ocr_text.splitlines():
        if _is_header_footer_line(line):
            continue
        parts = COLUMN_GAP_RE.split(line, maxsplit=1) if COLUMN_GAP_RE.search(line) else None
        if parts and len(parts) == 2 and parts[0].strip() and parts[1].strip():
            left_lines.append(parts[0].rstrip())
            right_lines.append(parts[1].lstrip())
            pipe_count += 1
        elif line.strip():
            orphans.append(line)

    left_lines, right_lines = _assign_orphan_lines(orphans, left_lines, right_lines)
    left_lines, right_lines = _relocate_high_number_lines(left_lines, right_lines)
    split_x = page_geom.split_x or (page_geom.width / 2.0 if page_geom.width else None)

    left_text = _clean_column_text("\n".join(left_lines))
    right_text = _clean_column_text("\n".join(right_lines))

    lines_total = max(len([ln for ln in ocr_text.splitlines() if ln.strip()]), 1)
    return ColumnSplitResult(
        layout=PageLayout.TWO_COLUMN,
        left_text=left_text,
        right_text=right_text,
        split_x=split_x,
        pipe_line_ratio=pipe_count / lines_total,
        orphan_lines=len(orphans),
        evidence=[f"split_x={split_x}", f"orphans={len(orphans)}"],
    )


def _clean_column_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _split_inline_column_bleed(text.strip())
    return _break_inline_ocr_question_numbers(cleaned)


def build_geometry_page_corpus(
    *,
    page_number: int,
    ocr_text: str,
    page: fitz.Page,
    rough_work: bool = False,
) -> tuple[str, PageGeometryAnnotation]:
    """Build tagged corpus fragment for one page with column ordering."""
    page_geom = PageGeometry.from_page(page_number, page)
    words = extract_page_words(page)
    page_geom._words = words  # type: ignore[attr-defined]

    layout, evidence, ratio = detect_page_layout(ocr_text, page_geom, rough_work=rough_work)
    split = split_page_columns(ocr_text, layout, page_geom)

    parts: list[str] = [f"<<<PAGE:{page_number}>>>", f"<<<LAYOUT:{layout.value}>>>"]
    if is_instruction_page(ocr_text, page_number):
        parts.append("<<<SKIP_QUESTIONS:instruction>>>")
    if split.split_x is not None:
        parts.append(f"<<<SPLIT_X:{split.split_x:.2f}>>>")

    if layout == PageLayout.TWO_COLUMN:
        parts.append("<<<COLUMN:LEFT>>>")
        parts.append(split.left_text)
        parts.append("<<<COLUMN:RIGHT>>>")
        parts.append(split.right_text)
    else:
        parts.append(split.left_text)

    annotation = PageGeometryAnnotation(
        page_number=page_number,
        layout=layout.value,
        width=page_geom.width,
        height=page_geom.height,
        split_x=split.split_x,
        pipe_line_ratio=ratio,
        word_count=len(words),
        evidence=evidence + split.evidence,
    )
    return "\n".join(parts), annotation


COLUMN_MARKER_RE = re.compile(r"<<<COLUMN:(LEFT|RIGHT)>>>")
LAYOUT_MARKER_RE = re.compile(r"<<<LAYOUT:(ONE_COLUMN|TWO_COLUMN|UNKNOWN)>>>")
SPLIT_X_RE = re.compile(r"<<<SPLIT_X:([\d.]+)>>>")

# Known P2.1B-HR cross-column contamination signatures (stem fragment → wrong options).
CROSS_COLUMN_SIGNATURES: list[tuple[str, str]] = [
    ("remove the ac", "yellow"),
    ("ripple from the rectified", "orange"),
    ("net magnetic flux through any closed", "random error"),
    ("unpredictable fluctuations", "zero"),
    ("metal wire has mass", "along north"),
    ("suddenly turns eastward", "1.4%"),
    ("electric dipole is placed", "gm"),
    ("gravitational potential", "mc"),
]


def detect_cross_column_contamination(record: dict[str, Any]) -> list[str]:
    """Flag stem/option mismatches indicative of L↔R merge (P2.1B-HR regression)."""
    flags: list[str] = []
    stem = (record.get("stem") or "").lower()
    opts = " ".join(
        (record.get(k) or "").lower() for k in ("option_a", "option_b", "option_c", "option_d")
    )
    for stem_frag, opt_frag in CROSS_COLUMN_SIGNATURES:
        if stem_frag in stem and opt_frag in opts:
            flags.append(f"cross_column_signature:{stem_frag}+{opt_frag}")

    # Mandatory HR cases: resistor colour options must not pair with non-Q8 stems.
    color_opts = {"yellow", "red", "green", "orange"}
    opt_set = {(record.get(k) or "").strip().lower() for k in ("option_a", "option_b", "option_c", "option_d")}
    if len(color_opts & opt_set) >= 2:
        if "colour" not in stem and "color" not in stem and "third band" not in stem and "carbon resistor" not in stem:
            if "rectifier" in stem or "through e" in stem or "transformer" in stem or "ripple" in stem:
                flags.append("cross_column_q5_q8_resistor_colors")

    # Q15/Q11 pattern: magnetic flux stem + error-type options.
    if "magnetic flux" in stem and any(x in opts for x in ("random error", "instrumental error", "personal error")):
        flags.append("cross_column_q15_q11_error_types")

    col = record.get("geometry_column")
    if col and record.get("geometry_layout") == "TWO_COLUMN":
        # Options referencing another column's question number in first line.
        for k in ("option_a", "option_b", "option_c", "option_d"):
            o = record.get(k) or ""
            if re.search(r"\n\s*\d{1,3}\s+[A-Z]", o):
                flags.append("option_contains_foreign_question_marker")
                break

    return flags


def run_automated_quality_checks(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Run P2.1C automated checks; flag only — never delete."""
    summary: dict[str, Any] = {
        "cross_column_contamination": 0,
        "question_option_mismatch": 0,
        "header_footer_contamination": 0,
        "page_number_false_positive": 0,
        "instruction_false_positive": 0,
        "duplicate_extraction": 0,
        "fragmented_extraction": 0,
        "empty_stems": 0,
        "suspiciously_short": 0,
        "foreign_options": 0,
        "impossible_qnum_jumps": 0,
        "page_boundary_anomalies": 0,
        "flagged_records": [],
    }

    by_paper_page: dict[tuple[str, int], list[int]] = {}

    for r in records:
        flags: list[str] = []
        stem = (r.get("stem") or "").strip()
        qn = r.get("question_number")
        page = r.get("source_page")
        sha = r.get("source_sha256") or ""

        flags.extend(detect_cross_column_contamination(r))
        if flags:
            summary["cross_column_contamination"] += 1

        if not stem:
            flags.append("empty_stem")
            summary["empty_stems"] += 1
        elif len(stem) < 20:
            flags.append("suspiciously_short_stem")
            summary["suspiciously_short"] += 1

        if "contd" in stem.lower() or "g2_english" in stem.lower():
            flags.append("header_footer_contamination")
            summary["header_footer_contamination"] += 1

        raw = (r.get("raw_extracted_text") or "").lower()
        if any(m in raw for m in ("important instructions", "read carefully the following")):
            flags.append("instruction_false_positive")
            summary["instruction_false_positive"] += 1

        if isinstance(qn, int) and isinstance(page, int):
            key = (sha, page)
            by_paper_page.setdefault(key, []).append(qn)
            # Physics section early pages should not have Q>60 without section change.
            if page <= 7 and qn >= 70:
                flags.append("impossible_qnum_for_page")
                summary["page_number_false_positive"] += 1

        filled = sum(1 for k in ("option_a", "option_b", "option_c", "option_d") if (r.get(k) or "").strip())
        if filled == 4 and r.get("missing_options"):
            flags.append("question_option_mismatch")
            summary["question_option_mismatch"] += 1

        if filled < 4 and len(stem) < 40:
            flags.append("fragmented")
            summary["fragmented_extraction"] += 1

        if r.get("duplicate_within_paper"):
            flags.append("duplicate_extraction")
            summary["duplicate_extraction"] += 1

        if r.get("geometry_layout") == "UNKNOWN":
            flags.append("unknown_layout_page")
            summary["page_boundary_anomalies"] += 1

        if flags:
            summary["flagged_records"].append(
                {
                    "staging_id": (r.get("staging_id") or "")[:20],
                    "question_number": qn,
                    "source_page": page,
                    "flags": flags,
                }
            )

    return summary
