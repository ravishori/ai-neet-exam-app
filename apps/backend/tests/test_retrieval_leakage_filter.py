"""Unit tests for RETRIEVAL-LEAKAGE-001 — pure, DB-free."""

from __future__ import annotations

from app.modules.cms.services.retrieval_leakage_filter import detect_retrieval_leakage


def test_detects_supplied_excerpt_phrase():
    stem = "Based on the supplied excerpt, what can be concluded about pteridophytes?"
    assert detect_retrieval_leakage(stem) == "the supplied excerpt"


def test_detects_cannot_be_determined_from_excerpt():
    stem = "This cannot be determined from the excerpt provided about De Broglie's postulate."
    assert detect_retrieval_leakage(stem) is not None


def test_detects_table_of_contents_leakage():
    stem = "The chapter's table of contents lists equipartition of energy — what topic does it belong to?"
    assert detect_retrieval_leakage(stem) == "table of contents"


def test_case_insensitive():
    stem = "According to THE SUPPLIED EXCERPT, what is the function of mitochondria?"
    assert detect_retrieval_leakage(stem) is not None


def test_normal_question_passes():
    stem = "What is the function of the mitochondria in a eukaryotic cell?"
    assert detect_retrieval_leakage(stem) is None


def test_none_and_empty_stem_safe():
    assert detect_retrieval_leakage(None) is None
    assert detect_retrieval_leakage("") is None


def test_legitimate_passage_word_without_leakage_phrase_passes():
    """'passage' alone (e.g. anatomical 'nasal passage') must not false-positive."""
    stem = "Air moving through the nasal passage is warmed and humidified before reaching the lungs. Which structure performs this function?"
    assert detect_retrieval_leakage(stem) is None
