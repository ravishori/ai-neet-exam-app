"""Structural eligibility classification for PYQ answer-review.

Standalone from app.modules.cms.schemas.content_bodies.QuestionBody: that
model requires a non-empty correct_option, which an ANSWER_PENDING staging
row never has, so it cannot validate option *shape* alone. This module
reimplements only the shape check (four present, non-empty, pairwise-
distinct option texts) against the staging representation
(pyq.questions.raw_options), using the same conservative normalization
rules verified in the 2026-10-22 four-option completeness audit
(docs/content-factory/PYQ_ANSWER_KEY_STATUS.md): Unicode NFKC + whitespace
collapse + casefold only, never stripping digits/symbols/units, so options
differing only in a numeral or unit stay distinct.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from app.modules.cms.schemas.content_bodies import find_prohibited_control_characters

_WS_RE = re.compile(r"\s+")
_IMAGE_REF_RE = re.compile(r"\b(figure|diagram|image|graph|shown below|shown above|as shown)\b", re.I)


class OptionEligibility(StrEnum):
    FOUR_VALID_OPTIONS = "FOUR_VALID_OPTIONS"
    MISSING_OPTION = "MISSING_OPTION"
    DUPLICATE_OPTIONS = "DUPLICATE_OPTIONS"
    MALFORMED_OPTIONS = "MALFORMED_OPTIONS"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"


_REVIEW_QUEUE_ELIGIBLE = frozenset({OptionEligibility.FOUR_VALID_OPTIONS})


def _is_empty(s: str | None) -> bool:
    return s is None or _WS_RE.sub("", s) == ""


def _normalize_for_dup_check(s: str | None) -> str:
    if s is None:
        return ""
    t = unicodedata.normalize("NFKC", s)
    return _WS_RE.sub(" ", t).strip().casefold()


def _has_internal_linebreak(s: str | None) -> bool:
    return bool(s) and ("\n" in s or "\r" in s)


def classify_option_structure(
    raw_options: dict[str, str | None], raw_stem: str | None = None
) -> OptionEligibility:
    """Classify a question's A-D option *structure* (never its correctness).
    Mirrors scripts/... classify_options.py used for the 2026-10-22 audit,
    kept in sync with that methodology deliberately.

    raw_stem is optional (for backward compatibility with callers that only
    have options in hand) but SHOULD always be passed in production code
    paths: the 2026-10-22 deeper integrity audit found 38 ANSWER_PENDING
    rows with embedded C0 control characters (U+0001, U+0004) inside
    raw_stem specifically — never inside an option — which this function
    would otherwise miss entirely, since it only inspected raw_options.
    The control-character rule itself is NOT reimplemented here: it is
    imported from app.modules.cms.schemas.content_bodies, the same rule
    QuestionBody/QuestionOption enforce at publication time, so this stays
    in sync with that gate by construction rather than by convention."""
    opts_raw = [raw_options.get("A"), raw_options.get("B"), raw_options.get("C"), raw_options.get("D")]

    empties = [_is_empty(o) for o in opts_raw]
    n_missing = sum(empties)

    none_values = [o is None for o in opts_raw]
    inconsistent_nullability = any(none_values) and not all(none_values)

    multiline_flags = [_has_internal_linebreak(o) for o in opts_raw]
    normed_all = [_normalize_for_dup_check(o) for o in opts_raw]
    multiline_dup_groups: dict[str, int] = {}
    for mflag, n in zip(multiline_flags, normed_all, strict=True):
        if mflag and n:
            multiline_dup_groups[n] = multiline_dup_groups.get(n, 0) + 1
    structurally_corrupted_duplicate = any(c >= 2 for c in multiline_dup_groups.values())

    image_dependent = any(_IMAGE_REF_RE.search(o or "") for o in opts_raw)

    control_char_corrupted = any(find_prohibited_control_characters(o or "") for o in opts_raw) or bool(
        find_prohibited_control_characters(raw_stem or "")
    )

    if inconsistent_nullability or structurally_corrupted_duplicate or control_char_corrupted:
        return OptionEligibility.MALFORMED_OPTIONS
    if image_dependent and n_missing > 0:
        return OptionEligibility.REQUIRES_MANUAL_REVIEW
    if n_missing > 0:
        return OptionEligibility.MISSING_OPTION
    if len(set(normed_all)) < 4:
        return OptionEligibility.DUPLICATE_OPTIONS
    return OptionEligibility.FOUR_VALID_OPTIONS


def is_review_queue_eligible(raw_options: dict[str, str | None], raw_stem: str | None = None) -> bool:
    return classify_option_structure(raw_options, raw_stem) in _REVIEW_QUEUE_ELIGIBLE
