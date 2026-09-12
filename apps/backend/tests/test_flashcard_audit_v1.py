"""Unit tests for flashcard Seed V1 audit decision gates."""

from scripts.audit_flashcard_seed_v1 import decide_status, provenance_class, quality_flags


def test_decide_status_rejects_front_equals_back():
    status, reason, labels = decide_status(
        flags=["AMBIGUOUS:front_equals_back"],
        prov="NCERT_VERIFIED",
        ncert_score=0.9,
        tax="VALID",
    )
    assert status == "REJECTED"
    assert "AMBIGUOUS" in labels


def test_decide_status_verified_requires_strong_ncert():
    status, _, _ = decide_status(
        flags=[],
        prov="NCERT_VERIFIED",
        ncert_score=0.8,
        tax="VALID",
    )
    assert status == "VERIFIED"


def test_decide_status_below_threshold_is_review():
    status, reason, labels = decide_status(
        flags=[],
        prov="NCERT_VERIFIED",
        ncert_score=0.6,
        tax="VALID",
    )
    assert status == "REVIEW"
    assert "NEEDS_REVIEW" in labels
    assert "below_verified_threshold" in reason


def test_decide_status_taxonomy_needs_review_blocks_verified():
    status, _, labels = decide_status(
        flags=[],
        prov="NCERT_VERIFIED",
        ncert_score=0.9,
        tax="NEEDS_REVIEW",
    )
    assert status == "REVIEW"
    assert "NEEDS_REVIEW" in labels


def test_provenance_ncert_without_support_is_unsupported():
    assert provenance_class({"source": "NCERT", "source_reference": "Ch.1"}, 0.1) == "UNSUPPORTED"


def test_quality_flags_short_front():
    flags = quality_flags({"front": "Hi?", "back": "answer", "explanation": "", "difficulty": "easy"})
    assert any(f.startswith("AMBIGUOUS:front_too_short") for f in flags)
