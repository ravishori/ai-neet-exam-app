"""Deterministic text normalization — stem/options normalization for
classification only. Never mutates the persisted raw_stem/raw_options."""

from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r"\s+")
_OCR_JUNK_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _OCR_JUNK_RE.sub(" ", text)
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = _WS_RE.sub(" ", text).strip()
    return text


def combined_question_text(stem: str, options: dict) -> str:
    opt_text = " ".join(
        str(options.get(k, "")) for k in ("A", "B", "C", "D") if isinstance(options, dict)
    )
    return normalize_text(stem) + " " + normalize_text(opt_text)
