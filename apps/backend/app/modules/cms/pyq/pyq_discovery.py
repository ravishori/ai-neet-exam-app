"""Deterministic NEET PYQ ZIP discovery utilities (FACTORY-PYQ-P0).

Read-only: inventories ZIP, classifies files, probes PDF extractability.
No database writes, no AI calls, no question import.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath

import fitz

SCOPE_YEARS = frozenset({"2020", "2021", "2022", "2023", "2024", "2025"})
NEET_SUBJECT_MARKERS = {
    "PHYSICS": ("PHYSICS", "PHYSICAL SCIENCES"),
    "CHEMISTRY": ("CHEMISTRY",),
    "BIOLOGY": ("BIOLOGY", "BOTANY", "ZOOLOGY"),
}
MATH_MARKERS = ("MATHEMATICS", "MATHS", "MATH ")


class FileClassification(str, Enum):
    NEET_QUESTION_PAPER = "NEET_QUESTION_PAPER"
    ANSWER_KEY = "ANSWER_KEY"
    SOLUTION = "SOLUTION"
    DUPLICATE_PAPER = "DUPLICATE_PAPER"
    EXCLUDED_MATHEMATICS = "EXCLUDED_NON_NEET_SUBJECT"
    NON_NEET = "NON_NEET"
    UNKNOWN = "UNKNOWN"


@dataclass
class ZipFileEntry:
    relative_path: str
    file_name: str
    file_size: int
    compressed_size: int
    sha256: str
    year: str | None
    classification: FileClassification
    paper_code: str | None = None
    language: str | None = None
    set_code: str | None = None
    notes: str = ""


@dataclass
class PdfProbeResult:
    relative_path: str
    page_count: int
    text_chars: int
    image_page_count: int
    extractability: str  # TEXT | SCANNED | MIXED
    sample_text: str
    subject_sections_detected: list[str] = field(default_factory=list)
    question_number_hits: int = 0
    option_pattern_hits: int = 0
    anomalies: list[str] = field(default_factory=list)


@dataclass
class DiscoveryReport:
    zip_path: str
    zip_sha256: str
    zip_size_bytes: int
    total_entries: int
    pdf_count: int
    scope_pdf_count: int
    out_of_scope_pdf_count: int
    files: list[ZipFileEntry] = field(default_factory=list)
    by_year: dict[str, list[ZipFileEntry]] = field(default_factory=dict)
    by_classification: dict[str, int] = field(default_factory=dict)
    duplicate_file_groups: list[list[str]] = field(default_factory=list)
    probes: list[PdfProbeResult] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


_YEAR_PATH_RE = re.compile(r"/(\d{4})/")
_PAPER_TIMESTAMP_RE = re.compile(r"Paper_(\d{14})(?:_[0-9a-f]{8})?", re.I)
_NTA_2025_RE = re.compile(r"NEET_2025_([A-Z]{2})_(\d+)_NTA(?:_V(\d+))?", re.I)
_QNUM_RE = re.compile(r"(?<!\d)(?:Q(?:uestion)?\.?\s*)?(\d{1,3})[\).:\s]", re.I)
_OPTION_RE = re.compile(r"\(\s*([1-4A-Da-d])\s*\)")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_year(relative_path: str) -> str | None:
    m = _YEAR_PATH_RE.search("/" + relative_path.replace("\\", "/"))
    return m.group(1) if m else None


def classify_entry(relative_path: str, *, sha256: str, seen_hashes: dict[str, str]) -> ZipFileEntry:
    name = PurePosixPath(relative_path).name
    lower = name.lower()
    year = extract_year(relative_path)

    if any(m.lower() in lower for m in ("math", "mathematics")):
        classification = FileClassification.EXCLUDED_MATHEMATICS
    elif "answer" in lower or "key" in lower or "response" in lower:
        classification = FileClassification.ANSWER_KEY
    elif "solution" in lower or "soln" in lower or "explanation" in lower:
        classification = FileClassification.SOLUTION
    elif "paper" in lower or "neet_" in lower or "question" in lower:
        classification = FileClassification.NEET_QUESTION_PAPER
    else:
        classification = FileClassification.UNKNOWN

    if sha256 in seen_hashes and classification == FileClassification.NEET_QUESTION_PAPER:
        classification = FileClassification.DUPLICATE_PAPER

    paper_code = None
    language = None
    set_code = None
    notes = ""

    m25 = _NTA_2025_RE.search(name)
    if m25:
        language = m25.group(1)
        set_code = m25.group(2)
        paper_code = f"NEET-2025-{language}-{set_code}"
        if m25.group(3):
            paper_code += f"-V{m25.group(3)}"
            notes = "NTA V2 variant present"
    else:
        m = _PAPER_TIMESTAMP_RE.search(name)
        if m:
            paper_code = f"Paper-{m.group(1)}"

    if name.endswith(".pdf.pdf"):
        notes = (notes + "; " if notes else "") + "double .pdf extension"

    if " (1)" in name:
        notes = (notes + "; " if notes else "") + "filename duplicate marker (1)"

    return ZipFileEntry(
        relative_path=relative_path,
        file_name=name,
        file_size=0,
        compressed_size=0,
        sha256=sha256,
        year=year,
        classification=classification,
        paper_code=paper_code,
        language=language,
        set_code=set_code,
        notes=notes.strip("; "),
    )


def inventory_zip(zip_path: Path, *, hash_contents: bool = True) -> DiscoveryReport:
    raw = zip_path.read_bytes()
    report = DiscoveryReport(
        zip_path=str(zip_path),
        zip_sha256=sha256_bytes(raw),
        zip_size_bytes=len(raw),
        total_entries=0,
        pdf_count=0,
        scope_pdf_count=0,
        out_of_scope_pdf_count=0,
    )

    seen_hashes: dict[str, str] = {}
    hash_to_paths: dict[str, list[str]] = {}

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        report.total_entries = len(zf.infolist())
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".pdf"):
                continue
            rel = info.filename.replace("\\", "/")
            data = zf.read(info)
            digest = sha256_bytes(data) if hash_contents else ""
            entry = classify_entry(rel, sha256=digest, seen_hashes=seen_hashes)
            entry.file_size = info.file_size
            entry.compressed_size = info.compress_size
            report.files.append(entry)
            report.pdf_count += 1

            if entry.year in SCOPE_YEARS:
                report.scope_pdf_count += 1
            else:
                report.out_of_scope_pdf_count += 1

            if digest:
                hash_to_paths.setdefault(digest, []).append(rel)
                if digest not in seen_hashes:
                    seen_hashes[digest] = rel

            report.by_year.setdefault(entry.year or "unknown", []).append(entry)
            report.by_classification[entry.classification.value] = (
                report.by_classification.get(entry.classification.value, 0) + 1
            )

    report.duplicate_file_groups = [paths for paths in hash_to_paths.values() if len(paths) > 1]

    if "2022" not in report.by_year:
        report.blockers.append("MISSING_YEAR: no PDFs found for exam year 2022 in ZIP")
    if report.by_classification.get(FileClassification.ANSWER_KEY.value, 0) == 0:
        report.blockers.append("MISSING_ANSWER_KEYS: no separate answer-key files detected by filename")
    if report.by_classification.get(FileClassification.EXCLUDED_MATHEMATICS.value, 0) > 0:
        report.blockers.append("MATHEMATICS_PRESENT: Mathematics files detected — must remain excluded")

    return report


def probe_pdf_bytes(relative_path: str, pdf_bytes: bytes, *, max_pages: int = 6) -> PdfProbeResult:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_count = doc.page_count
        text_chars = 0
        image_pages = 0
        chunks: list[str] = []
        for idx in range(min(page_count, max_pages)):
            page = doc.load_page(idx)
            text = page.get_text() or ""
            text_chars += len(text.strip())
            chunks.append(text)
            if len(text.strip()) < 40 and page.get_images():
                image_pages += 1

        sample = "\n".join(chunks)[:3000]
        upper = sample.upper()
        subjects = [s for s, markers in NEET_SUBJECT_MARKERS.items() if any(m in upper for m in markers)]
        math_hit = any(m in upper for m in MATH_MARKERS)

        q_hits = len(_QNUM_RE.findall(sample))
        opt_hits = len(_OPTION_RE.findall(sample))

        if text_chars < 200 and image_pages >= max(1, min(page_count, max_pages) // 2):
            extractability = "SCANNED"
        elif image_pages > 0 and text_chars > 500:
            extractability = "MIXED"
        else:
            extractability = "TEXT"

        anomalies: list[str] = []
        if math_hit:
            anomalies.append("mathematics_marker_in_text")
        if q_hits == 0:
            anomalies.append("no_question_number_pattern_in_sample")
        if opt_hits < 4:
            anomalies.append("few_option_patterns_in_sample")
        if extractability == "SCANNED":
            anomalies.append("likely_scanned_or_image_pdf")

        return PdfProbeResult(
            relative_path=relative_path,
            page_count=page_count,
            text_chars=text_chars,
            image_page_count=image_pages,
            extractability=extractability,
            sample_text=sample[:800],
            subject_sections_detected=subjects,
            question_number_hits=q_hits,
            option_pattern_hits=opt_hits,
            anomalies=anomalies,
        )
    finally:
        doc.close()


def probe_sample_pdfs(zip_path: Path, entries: list[ZipFileEntry], *, max_files: int = 12) -> list[PdfProbeResult]:
    """Probe representative PDFs without modifying the ZIP."""
    # One sample per year + a few extras
    chosen: list[ZipFileEntry] = []
    by_year: dict[str, list[ZipFileEntry]] = {}
    for e in entries:
        if e.year in SCOPE_YEARS and e.classification == FileClassification.NEET_QUESTION_PAPER:
            by_year.setdefault(e.year, []).append(e)
    for year in sorted(by_year):
        if by_year[year]:
            chosen.append(by_year[year][0])
    for e in entries:
        if len(chosen) >= max_files:
            break
        if e not in chosen and e.classification == FileClassification.NEET_QUESTION_PAPER:
            chosen.append(e)

    results: list[PdfProbeResult] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in chosen[:max_files]:
            data = zf.read(entry.relative_path)
            results.append(probe_pdf_bytes(entry.relative_path, data))
    return results


def normalized_question_hash(stem: str, options: list[str]) -> str:
    blob = "|".join([re.sub(r"\s+", " ", stem.strip().lower()), *[re.sub(r"\s+", " ", o.strip().lower()) for o in options]])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
