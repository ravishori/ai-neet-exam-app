import hashlib
import re
from dataclasses import dataclass

import fitz  # PyMuPDF

# NCERT's own numbered-heading convention, e.g. "3.2  ELECTRIC CURRENT" —
# see ADR-0022. Not a general-purpose layout model; this is deliberately
# narrow to the one real format the pilot chapter actually uses. The
# character class includes the apostrophe variants NCERT's PDF encoding
# mangles into U+FFFD when extracted (e.g. "OHM'S LAW" -> "OHM�S LAW"),
# confirmed against the real file — without it, "Ohm's Law" and
# "Kirchhoff's Rules" headings silently fail to match.
_HEADING_PATTERN = re.compile(r"^(\d+\.\d+)\s+([A-Z][A-Z0-9 \-,()'’�&/]{3,})\s*$", re.MULTILINE)

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
        pos = 0
        for match in _HEADING_PATTERN.finditer(page_text):
            buffer.append(page_text[pos : match.start()])
            flush()
            current_heading = f"{match.group(1)} {match.group(2).strip()}".replace("�", "'")
            current_page = page_num
            buffer = []
            pos = match.end()
        buffer.append(page_text[pos:])

    flush()
    return sections
