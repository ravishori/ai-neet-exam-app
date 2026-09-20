"""Local deterministic OCR utilities for NEET PYQ (FACTORY-PYQ-P2 / P2.1).

Uses PyMuPDF page rendering + local Tesseract CLI only.
No external AI/OCR APIs. No Pillow required.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from app.modules.cms.pyq.pyq_extraction import ValidationStatus

# Reporting vocabulary (maps onto ValidationStatus where applicable)
OCR_SUCCESS = "OCR_SUCCESS"
OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
OCR_FAILED = "OCR_FAILED"
NEEDS_REVIEW = "NEEDS_REVIEW"

DEFAULT_DPI = 300
LOW_CONFIDENCE_THRESHOLD = 55.0
MIN_TEXT_CHARS_SUCCESS = 40

_WINDOWS_CANDIDATES = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


@dataclass
class TesseractInfo:
    available: bool
    executable: str | None
    version: str | None
    languages: list[str] = field(default_factory=list)
    discovery_method: str | None = None
    anomalies: list[str] = field(default_factory=list)


@dataclass
class OcrWordRecord:
    """Single Tesseract word with geometry (P2.1E bbox persistence)."""

    page: int
    block_num: int
    par_num: int
    line_num: int
    word_num: int
    left: int
    top: int
    width: int
    height: int
    conf: float
    text: str

    @property
    def x_center(self) -> float:
        return self.left + self.width / 2.0

    @property
    def y_center(self) -> float:
        return self.top + self.height / 2.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "block_num": self.block_num,
            "par_num": self.par_num,
            "line_num": self.line_num,
            "word_num": self.word_num,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "conf": self.conf,
            "text": self.text,
        }


@dataclass
class OcrPageResult:
    page_number: int
    status: str  # OCR_SUCCESS | OCR_LOW_CONFIDENCE | OCR_FAILED | NEEDS_REVIEW
    validation_status: str
    text_chars: int
    image_count: int
    ocr_engine: str | None
    ocr_version: str | None
    ocr_confidence: float | None
    dpi: int
    raw_text: str
    anomalies: list[str] = field(default_factory=list)


@dataclass
class OcrPageWithWordsResult(OcrPageResult):
    words: list[OcrWordRecord] = field(default_factory=list)
    page_width_px: int = 0
    page_height_px: int = 0


@dataclass
class OcrPaperResult:
    source_sha256: str
    source_file: str
    exam_year: str | None
    extraction_mode: str
    tesseract_available: bool
    tesseract_executable: str | None
    tesseract_version: str | None
    dpi: int
    pages_processed: int
    pages_success: int
    pages_low_confidence: int
    pages_failed: int
    pages_needs_review: int
    page_results: list[OcrPageResult] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    # backward-compatible aliases used by P2
    pages_extracted: int = 0


def discover_tesseract(explicit_path: str | None = None) -> TesseractInfo:
    """Discover local Tesseract without committing machine-specific paths to callers."""
    candidates: list[tuple[str, str]] = []
    if explicit_path:
        candidates.append((explicit_path, "explicit_arg"))
    env_path = os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")
    if env_path:
        candidates.append((env_path, "env_TESSERACT_CMD"))
    which = shutil.which("tesseract")
    if which:
        candidates.append((which, "path_which"))
    for path in _WINDOWS_CANDIDATES:
        candidates.append((path, "windows_common_location"))

    seen: set[str] = set()
    for path, method in candidates:
        normalized = str(Path(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        if not Path(path).is_file():
            continue
        version = _tesseract_version(path)
        langs = _tesseract_languages(path)
        info = TesseractInfo(
            available=True,
            executable=path,
            version=version,
            languages=langs,
            discovery_method=method,
        )
        if "eng" not in langs and langs:
            info.anomalies.append("eng_language_pack_missing")
        return info

    return TesseractInfo(
        available=False,
        executable=None,
        version=None,
        anomalies=["tesseract_not_found"],
    )


def tesseract_available(explicit_path: str | None = None) -> bool:
    return discover_tesseract(explicit_path).available


def _tesseract_version(executable: str) -> str | None:
    try:
        proc = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
        match = re.search(r"tesseract\s+([vV]?\d[\w.\-]+)", blob)
        return match.group(1) if match else blob.strip().splitlines()[0] if blob.strip() else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _tesseract_languages(executable: str) -> list[str]:
    try:
        proc = subprocess.run(
            [executable, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        lines = (proc.stdout or "").splitlines()
        langs = [ln.strip() for ln in lines if ln.strip() and not ln.lower().startswith("list of")]
        return langs
    except (OSError, subprocess.TimeoutExpired):
        return []


def _page_image_count(page: fitz.Page) -> int:
    return len(page.get_images(full=True))


def _render_page_png(page: fitz.Page, *, dpi: int) -> bytes:
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return pix.tobytes("png")


def _run_tesseract_on_png(
    executable: str,
    png_bytes: bytes,
    *,
    lang: str = "eng",
) -> tuple[str, float | None, list[str]]:
    """Return (text, mean_confidence_or_None, anomalies). Single TSV pass."""
    anomalies: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pyq_ocr_") as tmp:
        img_path = Path(tmp) / "page.png"
        img_path.write_bytes(png_bytes)
        base = Path(tmp) / "out"
        cmd_tsv = [
            executable,
            str(img_path),
            str(base),
            "-l",
            lang,
            "--psm",
            "6",
            "tsv",
        ]
        try:
            subprocess.run(cmd_tsv, capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            anomalies.append("tesseract_timeout")
            return "", None, anomalies
        except OSError as exc:
            anomalies.append(f"tesseract_os_error:{type(exc).__name__}")
            return "", None, anomalies

        tsv_path = Path(str(base) + ".tsv")
        if not tsv_path.exists():
            anomalies.append("tsv_missing")
            return "", None, anomalies
        text, confidence = _text_and_confidence_from_tsv(tsv_path)
        return text, confidence, anomalies


def _run_tesseract_tsv_on_png(
    executable: str,
    png_bytes: bytes,
    *,
    page_number: int = 1,
    lang: str = "eng",
) -> tuple[str, float | None, list[OcrWordRecord], list[str]]:
    """Run Tesseract once; return text, confidence, word records, anomalies."""
    anomalies: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pyq_ocr_") as tmp:
        img_path = Path(tmp) / "page.png"
        img_path.write_bytes(png_bytes)
        base = Path(tmp) / "out"
        cmd_tsv = [
            executable,
            str(img_path),
            str(base),
            "-l",
            lang,
            "--psm",
            "6",
            "tsv",
        ]
        try:
            subprocess.run(cmd_tsv, capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            anomalies.append("tesseract_timeout")
            return "", None, [], anomalies
        except OSError as exc:
            anomalies.append(f"tesseract_os_error:{type(exc).__name__}")
            return "", None, [], anomalies

        tsv_path = Path(str(base) + ".tsv")
        if not tsv_path.exists():
            anomalies.append("tsv_missing")
            return "", None, [], anomalies
        text, confidence = _text_and_confidence_from_tsv(tsv_path)
        words = parse_tesseract_tsv_words(tsv_path, page_number=page_number)
        if not words:
            anomalies.append("tsv_no_word_boxes")
        return text, confidence, words, anomalies


def parse_tesseract_tsv_words(tsv_path: Path, *, page_number: int = 1) -> list[OcrWordRecord]:
    """Parse full Tesseract TSV including word bounding boxes."""
    try:
        lines = tsv_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if len(lines) < 2:
        return []

    words: list[OcrWordRecord] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        try:
            conf = float(parts[10])
            left = int(parts[6])
            top = int(parts[7])
            width = int(parts[8])
            height = int(parts[9])
            block = int(parts[2])
            par = int(parts[3])
            line_num = int(parts[4])
            word_num = int(parts[5])
        except ValueError:
            continue
        text = parts[11]
        if conf < 0 or not text.strip():
            continue
        if width <= 0 or height <= 0:
            continue
        words.append(
            OcrWordRecord(
                page=page_number,
                block_num=block,
                par_num=par,
                line_num=line_num,
                word_num=word_num,
                left=left,
                top=top,
                width=width,
                height=height,
                conf=conf,
                text=text,
            )
        )
    return words


def _text_and_confidence_from_tsv(tsv_path: Path) -> tuple[str, float | None]:
    try:
        lines = tsv_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "", None
    if len(lines) < 2:
        return "", None

    confs: list[float] = []
    rows: list[tuple[int, int, str]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        try:
            block = int(parts[2])
            line_num = int(parts[4])
            conf = float(parts[10])
        except ValueError:
            continue
        word = parts[11]
        if conf >= 0 and word.strip():
            confs.append(conf)
            rows.append((block, line_num, word))

    if not rows:
        return "", (sum(confs) / len(confs) if confs else None)

    # Reconstruct reading order by block/line.
    text_lines: list[str] = []
    current_key: tuple[int, int] | None = None
    current_words: list[str] = []
    for block, line_num, word in rows:
        key = (block, line_num)
        if current_key is None:
            current_key = key
        if key != current_key:
            text_lines.append(" ".join(current_words))
            current_words = []
            current_key = key
        current_words.append(word)
    if current_words:
        text_lines.append(" ".join(current_words))

    confidence = sum(confs) / len(confs) if confs else None
    return "\n".join(text_lines), confidence


def _status_from_ocr(
    text: str,
    confidence: float | None,
    *,
    image_count: int,
) -> tuple[str, str, list[str]]:
    anomalies: list[str] = []
    stripped = text.strip()
    if not stripped:
        anomalies.append("image_page_without_ocr_text" if image_count else "no_images_and_no_text")
        return OCR_FAILED, ValidationStatus.OCR_FAILED.value, anomalies

    upper = stripped.upper()
    if "SPACE FOR ROUGH WORK" in upper and len(stripped) < 120:
        anomalies.append("rough_work_blank_page")
        # OCR succeeded; page simply has no questions.
        return OCR_SUCCESS, ValidationStatus.OCR_EXTRACTED.value, anomalies

    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        anomalies.append(f"low_mean_confidence:{confidence:.1f}")
        return OCR_LOW_CONFIDENCE, ValidationStatus.NEEDS_REVIEW.value, anomalies

    if len(stripped) < MIN_TEXT_CHARS_SUCCESS:
        anomalies.append("low_ocr_yield")
        return NEEDS_REVIEW, ValidationStatus.NEEDS_REVIEW.value, anomalies

    return OCR_SUCCESS, ValidationStatus.OCR_EXTRACTED.value, anomalies


def ocr_page(
    page: fitz.Page,
    *,
    page_number: int,
    tesseract: TesseractInfo,
    dpi: int = DEFAULT_DPI,
    lang: str = "eng",
) -> OcrPageResult:
    image_count = _page_image_count(page)
    anomalies: list[str] = []

    if not tesseract.available or not tesseract.executable:
        return OcrPageResult(
            page_number=page_number,
            status=OCR_FAILED,
            validation_status=ValidationStatus.OCR_FAILED.value,
            text_chars=0,
            image_count=image_count,
            ocr_engine=None,
            ocr_version=None,
            ocr_confidence=None,
            dpi=dpi,
            raw_text="",
            anomalies=["tesseract_not_installed"],
        )

    try:
        png = _render_page_png(page, dpi=dpi)
        text, confidence, run_anomalies = _run_tesseract_on_png(
            tesseract.executable,
            png,
            lang=lang,
        )
        anomalies.extend(run_anomalies)
    except Exception as exc:  # pragma: no cover - defensive
        return OcrPageResult(
            page_number=page_number,
            status=OCR_FAILED,
            validation_status=ValidationStatus.OCR_FAILED.value,
            text_chars=0,
            image_count=image_count,
            ocr_engine="tesseract",
            ocr_version=tesseract.version,
            ocr_confidence=None,
            dpi=dpi,
            raw_text="",
            anomalies=[f"ocr_exception:{type(exc).__name__}"],
        )

    status, validation_status, status_anomalies = _status_from_ocr(
        text,
        confidence,
        image_count=image_count,
    )
    anomalies.extend(status_anomalies)

    return OcrPageResult(
        page_number=page_number,
        status=status,
        validation_status=validation_status,
        text_chars=len(text.strip()),
        image_count=image_count,
        ocr_engine="tesseract",
        ocr_version=tesseract.version,
        ocr_confidence=round(confidence, 2) if confidence is not None else None,
        dpi=dpi,
        raw_text=text.strip(),
        anomalies=anomalies,
    )


def ocr_page_with_words(
    page: fitz.Page,
    *,
    page_number: int,
    tesseract: TesseractInfo,
    dpi: int = DEFAULT_DPI,
    lang: str = "eng",
) -> OcrPageWithWordsResult:
    """OCR a page and persist word-level Tesseract geometry (P2.1E)."""
    image_count = _page_image_count(page)
    anomalies: list[str] = []
    page_width_px = 0
    page_height_px = 0

    if not tesseract.available or not tesseract.executable:
        base = OcrPageResult(
            page_number=page_number,
            status=OCR_FAILED,
            validation_status=ValidationStatus.OCR_FAILED.value,
            text_chars=0,
            image_count=image_count,
            ocr_engine=None,
            ocr_version=None,
            ocr_confidence=None,
            dpi=dpi,
            raw_text="",
            anomalies=["tesseract_not_installed"],
        )
        return OcrPageWithWordsResult(
            page_number=base.page_number,
            status=base.status,
            validation_status=base.validation_status,
            text_chars=base.text_chars,
            image_count=base.image_count,
            ocr_engine=base.ocr_engine,
            ocr_version=base.ocr_version,
            ocr_confidence=base.ocr_confidence,
            dpi=base.dpi,
            raw_text=base.raw_text,
            anomalies=base.anomalies,
            words=[],
        )

    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        page_width_px = pix.width
        page_height_px = pix.height
        png = pix.tobytes("png")
        text, confidence, words, run_anomalies = _run_tesseract_tsv_on_png(
            tesseract.executable,
            png,
            page_number=page_number,
            lang=lang,
        )
        anomalies.extend(run_anomalies)
    except Exception as exc:  # pragma: no cover
        return OcrPageWithWordsResult(
            page_number=page_number,
            status=OCR_FAILED,
            validation_status=ValidationStatus.OCR_FAILED.value,
            text_chars=0,
            image_count=image_count,
            ocr_engine="tesseract",
            ocr_version=tesseract.version,
            ocr_confidence=None,
            dpi=dpi,
            raw_text="",
            anomalies=[f"ocr_exception:{type(exc).__name__}"],
            words=[],
            page_width_px=page_width_px,
            page_height_px=page_height_px,
        )

    status, validation_status, status_anomalies = _status_from_ocr(
        text,
        confidence,
        image_count=image_count,
    )
    anomalies.extend(status_anomalies)

    return OcrPageWithWordsResult(
        page_number=page_number,
        status=status,
        validation_status=validation_status,
        text_chars=len(text.strip()),
        image_count=image_count,
        ocr_engine="tesseract",
        ocr_version=tesseract.version,
        ocr_confidence=round(confidence, 2) if confidence is not None else None,
        dpi=dpi,
        raw_text=text.strip(),
        anomalies=anomalies,
        words=words,
        page_width_px=page_width_px,
        page_height_px=page_height_px,
    )


def process_scanned_pdf(
    pdf_bytes: bytes,
    *,
    source_sha256: str,
    source_file: str,
    exam_year: str | None,
    extraction_mode: str,
    target_pages: list[int] | None = None,
    dpi: int = DEFAULT_DPI,
    tesseract_path: str | None = None,
    lang: str = "eng",
) -> OcrPaperResult:
    tesseract = discover_tesseract(tesseract_path)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    result = OcrPaperResult(
        source_sha256=source_sha256,
        source_file=source_file,
        exam_year=exam_year,
        extraction_mode=extraction_mode,
        tesseract_available=tesseract.available,
        tesseract_executable=tesseract.executable,
        tesseract_version=tesseract.version,
        dpi=dpi,
        pages_processed=0,
        pages_success=0,
        pages_low_confidence=0,
        pages_failed=0,
        pages_needs_review=0,
    )
    if not tesseract.available:
        result.anomalies.append("local_tesseract_unavailable")
    result.anomalies.extend(tesseract.anomalies)

    try:
        pages = target_pages or list(range(1, doc.page_count + 1))
        for page_number in pages:
            if page_number < 1 or page_number > doc.page_count:
                continue
            page = doc.load_page(page_number - 1)
            page_result = ocr_page(
                page,
                page_number=page_number,
                tesseract=tesseract,
                dpi=dpi,
                lang=lang,
            )
            result.page_results.append(page_result)
            result.pages_processed += 1
            if page_result.status == OCR_SUCCESS:
                result.pages_success += 1
            elif page_result.status == OCR_LOW_CONFIDENCE:
                result.pages_low_confidence += 1
            elif page_result.status == NEEDS_REVIEW:
                result.pages_needs_review += 1
            else:
                result.pages_failed += 1
    finally:
        doc.close()

    result.pages_extracted = result.pages_success
    if result.pages_success == 0 and result.pages_processed > 0:
        result.anomalies.append("no_pages_ocr_extracted")
    return result


def build_ocr_corpus(page_results: list[OcrPageResult]) -> str:
    chunks: list[str] = []
    for page in page_results:
        chunks.append(f"<<<PAGE:{page.page_number}>>>\n{page.raw_text}")
    return "\n".join(chunks)


def ocr_paper_to_dict(result: OcrPaperResult, *, include_text: bool = False) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for p in result.page_results:
        item: dict[str, Any] = {
            "page_number": p.page_number,
            "status": p.status,
            "validation_status": p.validation_status,
            "text_chars": p.text_chars,
            "image_count": p.image_count,
            "ocr_engine": p.ocr_engine,
            "ocr_version": p.ocr_version,
            "ocr_confidence": p.ocr_confidence,
            "dpi": p.dpi,
            "anomalies": p.anomalies,
        }
        if include_text:
            item["raw_text"] = p.raw_text
        pages.append(item)
    return {
        "source_sha256": result.source_sha256,
        "source_file": result.source_file,
        "exam_year": result.exam_year,
        "extraction_mode": result.extraction_mode,
        "tesseract_available": result.tesseract_available,
        "tesseract_executable_basename": Path(result.tesseract_executable).name
        if result.tesseract_executable
        else None,
        "tesseract_version": result.tesseract_version,
        "dpi": result.dpi,
        "pages_processed": result.pages_processed,
        "pages_success": result.pages_success,
        "pages_extracted": result.pages_extracted,
        "pages_low_confidence": result.pages_low_confidence,
        "pages_failed": result.pages_failed,
        "pages_needs_review": result.pages_needs_review,
        "anomalies": result.anomalies,
        "pages": pages,
    }
