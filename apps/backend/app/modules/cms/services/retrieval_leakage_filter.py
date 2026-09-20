"""RETRIEVAL-LEAKAGE-001 — cheap heuristic filter for meta-questions where a
generated stem surfaces its own retrieval/RAG scaffolding ("the supplied
excerpt...") instead of testable NEET subject content.

Found in the 400-MCQ pilot content audit (2026-09-19): 8/99 sampled
questions were meta-questions about a source document rather than real
biology/physics content (e.g. "what can be concluded from the supplied
excerpt about pteridophytes?" with answer "cannot be determined").

Deliberately a plain substring check, not an LLM judge — this must stay
cheap enough to run on every candidate, always on, regardless of bulk mode.
"""

from __future__ import annotations

_LEAKAGE_PHRASES: tuple[str, ...] = (
    "the supplied excerpt",
    "the excerpt provided",
    "the provided excerpt",
    "based on the excerpt",
    "from the excerpt",
    "cannot be determined from the excerpt",
    "insufficient information in the excerpt",
    "the passage provided",
    "the provided passage",
    "the passage above",
    "according to the given passage",
    "from the given passage",
    "which section number",
    "table of contents",
)


def detect_retrieval_leakage(stem: str | None) -> str | None:
    """Return the matched leakage phrase if `stem` looks like it leaked
    retrieval/RAG scaffolding instead of asking real subject content, else
    None. Case-insensitive, substring-based, intentionally cheap."""
    if not stem:
        return None
    lowered = stem.lower()
    for phrase in _LEAKAGE_PHRASES:
        if phrase in lowered:
            return phrase
    return None
