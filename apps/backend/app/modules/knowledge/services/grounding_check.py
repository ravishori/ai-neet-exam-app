"""Mechanical source-verification gate — see ADR-0024.

Deliberately not a model call: checks that each claimed fact actually
shares substantive vocabulary with the source text it's supposed to come
from, before any AI judgment is trusted. This is the direct fix the AI
Content Lifecycle Specification's own self-review called for ("Source
Verification... needs a more mechanical check... before it can be trusted
as a hard gate") — a claim that fails this never reaches a model asking
"does this look grounded to you," because that question has the same
blind spots as the thing it's supposed to catch.
"""

import re

MIN_SIGNIFICANT_WORD_LENGTH = 4
OVERLAP_THRESHOLD = 0.5
MAX_FAILURE_PREVIEW = 3

# Common English function words — excluded so overlap is measured on the
# words that actually carry meaning, not "the", "with", "that", etc.
_STOPWORDS = frozenset(
    {
        "this", "that", "these", "those", "with", "from", "into", "onto",
        "have", "has", "had", "were", "was", "are", "is", "be", "been",
        "being", "will", "would", "could", "should", "shall", "must",
        "than", "then", "when", "where", "which", "while", "about",
        "there", "their", "they", "them", "such", "each", "some", "more",
        "most", "other", "only", "also", "both", "same", "very", "just",
        "over", "under", "between", "across", "through", "within", "without",
        "does", "did", "not", "and", "for", "the", "its", "it's",
    }
)


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if len(w) >= MIN_SIGNIFICANT_WORD_LENGTH and w not in _STOPWORDS}


def is_fact_grounded(fact: str, source_text: str) -> bool:
    """A fact with no substantive words at all (e.g. a bare symbol) passes
    trivially — there's nothing for this check to meaningfully evaluate,
    and rejecting it would be a false positive this gate shouldn't produce."""
    fact_words = _significant_words(fact)
    if not fact_words:
        return True
    source_words = _significant_words(source_text)
    overlap_ratio = len(fact_words & source_words) / len(fact_words)
    return overlap_ratio >= OVERLAP_THRESHOLD


def check_grounding(structured_facts: list[str], source_text: str) -> tuple[bool, str | None]:
    """Returns (passed, failure_detail). All facts must be grounded for the
    whole Knowledge Unit to pass — this is a hard gate, not a majority vote."""
    if not structured_facts:
        return False, "no structured facts extracted"

    ungrounded = [fact for fact in structured_facts if not is_fact_grounded(fact, source_text)]
    if ungrounded:
        preview = "; ".join(f[:80] for f in ungrounded[:MAX_FAILURE_PREVIEW])
        return False, f"{len(ungrounded)}/{len(structured_facts)} facts failed source-overlap check: {preview}"

    return True, None
