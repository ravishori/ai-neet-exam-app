"""Mine literal NCERT definitional quotes for ENGINE-006 curation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.modules.cms.services.deterministic_fact_pack_loader import (  # noqa: E402
    extract_ncert_source_text,
)

BINDINGS = BACKEND / "tests/fixtures/python_mcq_engine_006_chapter_bindings.json"
OUT = BACKEND / "tests/fixtures/python_mcq_engine_006_candidate_quotes.json"

_WS = re.compile(r"\s+")
_PATTERNS = [
    re.compile(
        r".{0,80}?\b(?:is called|are called|is known as|are known as|known as|"
        r"is defined as|defined as|refers to|consists of|composed of|"
        r"on hydrolysis|SI unit|is equal to)\b.{0,100}?",
        re.IGNORECASE,
    ),
]


def _norm(value: str) -> str:
    return _WS.sub(" ", value or "").strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", _norm(text))
    usable = []
    for part in parts:
        part = _norm(part).rstrip(".")
        if 40 <= len(part) <= 220 and part.count(" ") >= 5:
            lower = part.casefold()
            if any(
                bad in lower
                for bad in ("figure", "exercise", "objectives", "summary", "reprint")
            ):
                continue
            usable.append(part)
    return usable


def main() -> int:
    bindings = json.loads(BINDINGS.read_text(encoding="utf-8"))
    chapters = []
    for row in bindings:
        text = extract_ncert_source_text(Path(row["source_pdf"]), None)
        found: list[dict] = []
        seen: set[str] = set()
        for sentence in _sentences(text):
            if not any(pattern.search(sentence) for pattern in _PATTERNS):
                continue
            key = sentence.casefold()
            if key in seen:
                continue
            seen.add(key)
            found.append({"quote": sentence, "kind": "definition", "term_guess": ""})
            if len(found) >= 20:
                break
        chapters.append(
            {
                "subject": row["subject"],
                "chapter": row["chapter"],
                "source_relative_path": row["source_relative_path"],
                "source_pdf": row["source_pdf"],
                "candidate_count": len(found),
                "candidates": found,
            }
        )
        print(f"{row['subject']}/{row['chapter']}: {len(found)}")
    OUT.write_text(
        json.dumps({"chapters": chapters}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
