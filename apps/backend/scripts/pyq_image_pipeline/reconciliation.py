# -*- coding: utf-8 -*-
"""Reconciliation helpers for already-staged `pyq_image_staging` rows.

This module is deliberately separate from `extractor.py`: it operates on
rows that have already been extracted and staged, proposing *derived*
fields (a cleaned option/stem text, a candidate image-question association)
without ever overwriting the original `raw_block_text`/`stem_text`/
`options` or silently promoting a guess to a real link.

Footer-leak pattern (confirmed against real staged rows from the NEET 2015
Code A/B/C/D PDFs): a page footer/header block -- "www.<domain>.com" plus a
bare page-number line, the paper's "NATIONAL ELIGIBILITY CUM ENTRANCE TEST /
NEET (UG) YYYY (CODE-X) / Answers & Solutions / <Subject>" header, or the
"Answer Key: (n)" / "Solution: ..." trailer -- gets spliced into whichever
option text was mid-parse when the PDF's page or column broke. It is not
always the *last* option (that's why `extractor._FOOTER_LEAK_RE`, which only
inspects the last option, misses a real minority of cases).
"""
from __future__ import annotations

import re

_TRAILING_SOLUTION_RE = re.compile(
    r"\s*(Answer\s*Key:\s*\(\d\)\s*)?Solution:.*$", re.IGNORECASE | re.DOTALL
)
_MID_FOOTER_RE = re.compile(
    r"\s*(www\.[a-z0-9]+\.[a-z]{2,}\s*\n?\d{0,4}|"
    r"NATIONAL\s+ELIGIBILITY\s+CUM\s+ENTRANCE\s+TEST.*?(?:Chemistry|Physics|Botany|Zoology|Biology)|"
    r"NEET\s*\(UG\)[^\n]*|Answers\s*&\s*Solutions)\s*",
    re.IGNORECASE | re.DOTALL,
)
_RESIDUAL_FOOTER_RE = re.compile(
    r"www\.[a-z0-9]+\.[a-z]{2,}|NEET\s*\(UG\)|Answers\s*&\s*Solutions", re.IGNORECASE
)


def clean_footer_text(text: str | None) -> tuple[str, bool]:
    """Strip footer/header boilerplate wherever it occurs in `text` (not
    only at the end). Returns (cleaned_text, changed). Never mutates the
    input; callers write the result to a *new* derived column and must
    leave the original raw field untouched."""
    if not text:
        return text or "", False
    original_normalized = re.sub(r"\s+", " ", text).strip()
    new = _TRAILING_SOLUTION_RE.sub("", text)
    new = _MID_FOOTER_RE.sub(" ", new)
    new = re.sub(r"\s+", " ", new).strip()
    return new, new != original_normalized


def footer_cleanup_status(cleaned_value: str) -> str:
    """FULL if no residual footer marker remains, else PARTIAL."""
    return "PARTIAL" if _RESIDUAL_FOOTER_RE.search(cleaned_value) else "FULL"


def propose_image_candidate(
    *,
    questions_on_page: list,
    unlinked_images_on_page: int,
    already_linked_images_on_page: int,
) -> tuple[object | None, str, str]:
    """Propose (candidate_question_id, confidence, evidence) for one
    unlinked image, given counts for its (source_file, page_number).

    Never returns HIGH unless the image is the ONLY unlinked image on a
    page that has exactly one question and no image already linked to it
    -- the one case explicit in the task's own HIGH bar. Everything else
    is MEDIUM/LOW/NONE and is a proposal for human review, never a
    silent link.
    """
    if not questions_on_page:
        return None, "NONE", "no staged question found on this page of this file"
    if (
        len(questions_on_page) == 1
        and unlinked_images_on_page == 1
        and already_linked_images_on_page == 0
    ):
        return (
            questions_on_page[0],
            "HIGH",
            "only unlinked image on the page; exactly one question on that "
            "page; no other image already linked there",
        )
    if len(questions_on_page) == 1 and already_linked_images_on_page == 0:
        return (
            questions_on_page[0],
            "MEDIUM",
            f"exactly one question on the page, but {unlinked_images_on_page} "
            "unlinked images share it -> ambiguous which image is which",
        )
    return (
        questions_on_page[0],
        "LOW",
        f"{len(questions_on_page)} questions and {unlinked_images_on_page} "
        "unlinked images share the page -> no reliable 1:1 basis; this is "
        "not a real association, only a weak proposal for human review",
    )
