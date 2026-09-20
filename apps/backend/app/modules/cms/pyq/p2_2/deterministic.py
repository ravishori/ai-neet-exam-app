"""P2.2 deterministic recovery (no AI tokens)."""

from __future__ import annotations

import re
from typing import Any

from app.modules.cms.pyq.p2_2.schemas import AIRecoveryOutput

OPTION_START_RE = re.compile(r"\(\s*([1-4])\s*\)")


def _extract_block(raw: str, qnum: int) -> str | None:
    if not raw.strip():
        return None
    pattern = re.compile(rf"(?:^|\n)\s*{qnum}(?:\.\s+|\s+)(.+)", re.S)
    m = pattern.search(raw)
    if not m:
        return None
    start = m.start()
    next_q = re.search(rf"\n\s*{qnum + 1}(?:\.\s+|\s+)", raw[m.end() :])
    end = m.end() + next_q.start() if next_q else len(raw)
    return raw[start:end].strip()


def attempt_deterministic_recovery(record: dict[str, Any]) -> AIRecoveryOutput | None:
    raw = record.get("raw_extracted_text") or ""
    qnum = record.get("question_number")
    if not raw.strip() or qnum is None:
        return None
    block = _extract_block(raw, int(qnum))
    if not block:
        return None
    stem, options, _ = _parse_options_simple(block)
    if not stem.strip():
        return None
    opt = {str(i): options.get(str(i), "") for i in range(1, 5)}
    if not any(v.strip() for v in opt.values()):
        return None
    changed: list[str] = []
    if not (record.get("stem") or "").strip() and stem.strip():
        changed.append("stem")
    for i, key in enumerate("abcd", 1):
        if not (record.get(f"option_{key}") or "").strip() and opt.get(str(i), "").strip():
            changed.append(f"option_{i}")
    if not changed:
        return None
    return AIRecoveryOutput(
        status="RECOVERED",
        stem=stem.strip(),
        options=opt,
        changed_fields=changed,
        source_evidence_used=["raw_extracted_text", "deterministic_reparse"],
        uncertainties=[],
        foreign_text_detected=False,
        confidence=0.85 if all(opt.get(str(i), "").strip() for i in range(1, 5)) else 0.65,
    )


def _parse_options_simple(block: str) -> tuple[str, dict[str, str], list[str]]:
    matches = list(OPTION_START_RE.finditer(block))
    if not matches:
        stem = re.sub(r"^\d{1,3}(?:\.\s+|\s+)", "", block.strip(), count=1).strip()
        return stem, {}, []
    stem = block[: matches[0].start()].strip()
    stem = re.sub(r"^\d{1,3}(?:\.\s+|\s+)", "", stem, count=1).strip()
    options: dict[str, str] = {}
    for j, match in enumerate(matches):
        key = match.group(1)
        start = match.end()
        end = matches[j + 1].start() if j + 1 < len(matches) else len(block)
        options[key] = block[start:end].strip()
    return stem, options, []
