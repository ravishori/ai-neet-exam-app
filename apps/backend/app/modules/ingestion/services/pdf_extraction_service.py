import hashlib
import re
from dataclasses import dataclass

import fitz  # PyMuPDF

# NCERT numbered-heading conventions — see ADR-0022 / Phase D pilot corpus.
# Physics uses all-caps titles on one line ("3.2  ELECTRIC CURRENT").
# Chemistry uses mixed-case titles, often after a tab ("4.1.1\t Octet Rule")
# or a line break ("4.8\nBONDING IN SOME HOMONUCLEAR"). The character class
# includes apostrophe variants NCERT PDFs mangle into U+FFFD.
_HEADING_PATTERN = re.compile(
    r"^(\d+(?:\.\d+)+)[\t\s]+([A-Za-z][A-Za-z0-9 \-,()'’�&/]{3,})\s*$",
    re.MULTILINE,
)

# End-of-chapter exercise lines reuse section numbers ("4.1 Explain…") — drop them.
_EXERCISE_LEAD_WORDS = frozenset(
    {
        "Explain",
        "Write",
        "Define",
        "Draw",
        "Describe",
        "List",
        "Name",
        "Give",
        "What",
        "How",
        "Why",
        "Compare",
        "Discuss",
        "Calculate",
        "State",
        "Identify",
    }
)

# Below this, a "section" is almost always a stray heading match with no
# real body (table of contents, running header) — drop it rather than
# generate questions from noise.
MIN_SECTION_CHARS = 200


@dataclass
class ExtractedSection:
    heading: str
    source_page: int
    text: str


def compute_checksum(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_pages(file_path: str) -> list[str]:
    doc = fitz.open(file_path)
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def _normalize_page_text(page_text: str) -> str:
    """Join section numbers split across lines by PyMuPDF layout."""
    page_text = page_text.replace("�", "'")
    return re.sub(
        r"(?m)^(\d+(?:\.\d+)+)[\t\s]*\r?\n[\t\s]*([A-Za-z])",
        r"\1 \2",
        page_text,
    )


def _is_section_heading(title: str) -> bool:
    first = title.split()[0] if title.split() else ""
    if first in _EXERCISE_LEAD_WORDS or title.rstrip().endswith("?"):
        return False
    return True


def split_into_sections(pages: list[str]) -> list[ExtractedSection]:
    sections: list[ExtractedSection] = []
    current_heading: str | None = None
    current_page = 0
    buffer: list[str] = []

    def flush() -> None:
        if not current_heading:
            return
        text = "".join(buffer).strip().replace("�", "'")
        if len(text) >= MIN_SECTION_CHARS:
            sections.append(ExtractedSection(heading=current_heading, source_page=current_page, text=text))

    for page_num, page_text in enumerate(pages, start=1):
        normalized = _normalize_page_text(page_text)
        pos = 0
        for match in _HEADING_PATTERN.finditer(normalized):
            title = match.group(2).strip()
            if not _is_section_heading(title):
                continue
            buffer.append(normalized[pos : match.start()])
            flush()
            current_heading = f"{match.group(1)} {title}"
            current_page = page_num
            buffer = []
            pos = match.end()
        buffer.append(normalized[pos:])

    flush()
    return sections
