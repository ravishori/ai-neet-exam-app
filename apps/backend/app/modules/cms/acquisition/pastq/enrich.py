"""Post-extraction enrichment: letter options, inline answers, visuals, CMS mapping."""

from __future__ import annotations

import re
from typing import Any

from app.modules.cms.pyq.pyq_extraction import ExtractedQuestion, PaperExtractionResult

LETTER_OPTION_RE = re.compile(r"(?m)^\s*([a-dA-D])[\.\)]\s+")
INLINE_ANS_RE = re.compile(r"Ans(?:wer)?\.\s*\(\s*([1-4A-Da-d])\s*\)", re.I)
VISUAL_MARKERS = (
    "figure",
    "diagram",
    "graph",
    "shown in",
    "as shown",
    "circuit",
    "table",
    "structure",
    "following figure",
    "see the figure",
)

NUM_TO_LETTER = {"1": "A", "2": "B", "3": "C", "4": "D"}
LETTER_TO_NUM = {"A": "1", "B": "2", "C": "3", "D": "4"}


def map_option_to_letter(raw: str | None) -> str | None:
    if not raw:
        return None
    v = str(raw).strip().upper()
    if v in {"A", "B", "C", "D"}:
        return v
    if v in NUM_TO_LETTER:
        return NUM_TO_LETTER[v]
    return None


def parse_letter_options(block: str) -> tuple[str, dict[str, str]]:
    matches = list(LETTER_OPTION_RE.finditer(block))
    if len(matches) < 4:
        return block.strip(), {}
    stem = block[: matches[0].start()].strip()
    stem = re.sub(r"^\d{1,3}\.\s*", "", stem, count=1).strip()
    options: dict[str, str] = {}
    for idx, match in enumerate(matches[:4]):
        key = match.group(1).upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        # Strip trailing inline answers from option text.
        text = INLINE_ANS_RE.sub("", block[start:end]).strip()
        options[LETTER_TO_NUM[key]] = text
    return stem, options


def enrich_inline_answers(questions: list[ExtractedQuestion]) -> list[dict[str, Any]]:
    """Associate Ans.(n) markers found inside the question raw text only."""
    conflicts: list[dict[str, Any]] = []
    for q in questions:
        raw = q.raw_extracted_text or ""
        hits = INLINE_ANS_RE.findall(raw)
        if not hits:
            continue
        letters = []
        for h in hits:
            mapped = map_option_to_letter(h)
            if mapped:
                letters.append(mapped)
        unique = sorted(set(letters))
        if len(unique) > 1:
            q.answer_status = "ANSWER_CONFLICT"
            q.anomalies.append("inline_answer_conflict")
            conflicts.append(
                {
                    "question_number": q.question_number,
                    "source_file": q.source_file,
                    "values": unique,
                }
            )
            continue
        if unique and not q.correct_option:
            q.correct_option = LETTER_TO_NUM[unique[0]]
            q.answer_status = "ANSWER_KNOWN"
            q.answer_source = "inline_ans_marker"
            q.answer_source_page = q.source_page
        elif unique and q.correct_option:
            existing = map_option_to_letter(q.correct_option)
            if existing and existing != unique[0]:
                q.answer_status = "ANSWER_CONFLICT"
                q.anomalies.append("inline_vs_grid_answer_conflict")
                conflicts.append(
                    {
                        "question_number": q.question_number,
                        "source_file": q.source_file,
                        "values": [existing, unique[0]],
                    }
                )
    return conflicts


def repair_letter_options(questions: list[ExtractedQuestion]) -> int:
    """Fill empty (1)-(4) options from a./b./c./d. markers when present."""
    repaired = 0
    for q in questions:
        filled = sum(1 for o in (q.option_a, q.option_b, q.option_c, q.option_d) if (o or "").strip())
        if filled >= 4:
            continue
        stem, opts = parse_letter_options(q.raw_extracted_text or "")
        if len(opts) == 4:
            q.stem = stem or q.stem
            q.option_a = opts.get("1", "")
            q.option_b = opts.get("2", "")
            q.option_c = opts.get("3", "")
            q.option_d = opts.get("4", "")
            if q.validation_status == "EXTRACTED" or not q.validation_status:
                q.validation_status = "EXTRACTED"
            repaired += 1
    return repaired


def detect_visual(question: ExtractedQuestion) -> dict[str, Any]:
    blob = " ".join(
        [
            question.stem or "",
            question.option_a or "",
            question.option_b or "",
            question.option_c or "",
            question.option_d or "",
            question.raw_extracted_text or "",
        ]
    ).lower()
    has = any(m in blob for m in VISUAL_MARKERS)
    return {
        "has_visual": has,
        "visual_status": "VISUAL_REVIEW_REQUIRED" if has else "NO_VISUAL_MARKER",
        "source_page": question.source_page,
    }


def enrich_paper_result(result: PaperExtractionResult) -> dict[str, Any]:
    repaired = repair_letter_options(result.questions)
    conflicts = enrich_inline_answers(result.questions)
    visual_count = 0
    for q in result.questions:
        vis = detect_visual(q)
        if vis["has_visual"]:
            visual_count += 1
            q.anomalies.append("VISUAL_REVIEW_REQUIRED")
    return {
        "letter_options_repaired": repaired,
        "answer_conflicts": conflicts,
        "visual_questions": visual_count,
    }
