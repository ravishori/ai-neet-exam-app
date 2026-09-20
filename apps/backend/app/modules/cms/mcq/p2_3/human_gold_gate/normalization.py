"""Label normalization for AI vs human gold comparison."""

from __future__ import annotations

import re
from typing import Any

from app.modules.cms.mcq.p2_3.human_gold_gate.schemas import GoldLabel

AI_TO_GOLD: dict[str, GoldLabel] = {
    "READY": "ACCEPT",
    "PASS": "ACCEPT",
    "ACCEPT": "ACCEPT",
    "MINOR_REVISION": "MINOR",
    "MINOR": "MINOR",
    "MAJOR_REVISION": "MAJOR",
    "MAJOR": "MAJOR",
    "REJECT": "REJECT",
    "FAIL": "REJECT",
    "INCONCLUSIVE": "INCONCLUSIVE",
}

HUMAN_TO_GOLD: dict[str, GoldLabel] = {
    "ACCEPT": "ACCEPT",
    "PASS": "ACCEPT",
    "OK": "ACCEPT",
    "GOOD": "ACCEPT",
    "MINOR": "MINOR",
    "MINOR_REVISION": "MINOR",
    "MINOR_ISSUE": "MINOR",
    "MINOR_ISSUES": "MINOR",
    "MAJOR": "MAJOR",
    "MAJOR_REVISION": "MAJOR",
    "MAJOR_ISSUE": "MAJOR",
    "MAJOR_ISSUES": "MAJOR",
    "REJECT": "REJECT",
    "FAIL": "REJECT",
    "INCONCLUSIVE": "INCONCLUSIVE",
    "UNCLEAR": "INCONCLUSIVE",
}

NCERT_LABELS = {
    "DIRECT",
    "SUPPORTED_INFERENCE",
    "WEAK_SUPPORT",
    "UNSUPPORTED",
    "INCORRECT_CITATION",
    "NOT_VERIFIABLE",
}

NEET_LABELS = {"SUITABLE", "SUITABLE_WITH_MINOR_EDIT", "QUESTIONABLE", "UNSUITABLE"}

DIFFICULTY_LABELS = {"EASY", "MEDIUM", "HARD", "UNKNOWN"}


def normalize_gold_label(value: Any, mapping: dict[str, GoldLabel]) -> GoldLabel:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if not text or text in {"PENDING", "N/A", "NOT_REVIEWED"}:
        return "INVALID_HUMAN_LABEL"
    if text in mapping:
        return mapping[text]
    for key, label in mapping.items():
        if text == key.upper():
            return label
    return "INVALID_HUMAN_LABEL"


def normalize_ai_verdict(row: dict[str, Any]) -> GoldLabel:
    status = (
        row.get("validation_status_after_R1")
        or row.get("validator_verdict")
        or row.get("validation_status_before_R1")
        or ""
    )
    return normalize_gold_label(status, AI_TO_GOLD)


def normalize_human_overall(row: dict[str, Any]) -> GoldLabel:
    return normalize_gold_label(row.get("human_overall"), HUMAN_TO_GOLD)


def normalize_answer_key(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or text.upper() in {"PENDING", "N/A", "NOT_REVIEWED"}:
        return None
    upper = text.upper()
    if upper in {"A", "B", "C", "D"}:
        return upper
    m = re.match(r"^(?:OPTION\s*)?([ABCD])\b", upper)
    if m:
        return m.group(1)
    m = re.match(r"^\(([ABCD])\)$", upper)
    if m:
        return m.group(1)
    if upper in {"1", "2", "3", "4"}:
        return {"1": "A", "2": "B", "3": "C", "4": "D"}[upper]
    return None


def normalize_difficulty(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if text in DIFFICULTY_LABELS:
        return text
    return None


def difficulty_within_one(ai: str | None, human: str | None) -> bool:
    if not ai or not human:
        return False
    order = {"EASY": 0, "MEDIUM": 1, "HARD": 2}
    if ai not in order or human not in order:
        return False
    return abs(order[ai] - order[human]) <= 1


def normalize_ncert(value: Any) -> str | None:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if text in NCERT_LABELS:
        return text
    aliases = {
        "DIRECT_NCERT_SUPPORT": "DIRECT",
        "SUPPORTED_WITHIN_NCERT_CONTEXT": "SUPPORTED_INFERENCE",
        "NO_SUPPORT": "UNSUPPORTED",
        "WEAK": "WEAK_SUPPORT",
    }
    return aliases.get(text)


def normalize_neet(value: Any) -> str | None:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if text in NEET_LABELS:
        return text
    return None


def ai_passed(row: dict[str, Any]) -> bool:
    ai = normalize_ai_verdict(row)
    return ai == "ACCEPT"


def ai_failed(row: dict[str, Any]) -> bool:
    ai = normalize_ai_verdict(row)
    return ai in ("MAJOR", "REJECT")
