"""Phase 4 — unit tests for the pure, DB-free quality-audit modules."""

from pyq_subject_classifier.answer_quality import audit_assertions_for_question
from pyq_subject_classifier.duplicates import find_exact_duplicates, find_near_duplicates
from pyq_subject_classifier.evidence_gaps import GAP_CATEGORIES, classify_gap_reason
from pyq_subject_classifier.legacy_provenance import classify_legacy_provenance
from pyq_subject_classifier.quality_checks import (
    check_question_integrity,
    normalize_for_dedup,
    options_hash,
    stem_hash,
)

# ---------- normalization ----------

def test_normalize_for_dedup_strips_case_punctuation_whitespace():
    a = normalize_for_dedup("What is  the SI unit of Force?")
    b = normalize_for_dedup("what is the si unit of force")
    assert a == b


def test_normalize_for_dedup_handles_none_and_empty():
    assert normalize_for_dedup(None) == ""
    assert normalize_for_dedup("") == ""


def test_stem_hash_deterministic_and_case_insensitive():
    h1 = stem_hash("The mitochondria is the powerhouse of the cell.")
    h2 = stem_hash("THE MITOCHONDRIA IS THE POWERHOUSE OF THE CELL")
    assert h1 == h2
    assert h1 == stem_hash("The mitochondria is the powerhouse of the cell.")  # repeatable


def test_options_hash_ignores_key_order_not_values():
    h1 = options_hash({"A": "1", "B": "2", "C": "3", "D": "4"})
    h2 = options_hash({"D": "4", "C": "3", "B": "2", "A": "1"})
    assert h1 == h2
    h3 = options_hash({"A": "1", "B": "2", "C": "3", "D": "5"})
    assert h1 != h3


# ---------- integrity checks ----------

def test_check_question_integrity_clean_row_has_no_issues():
    issues = check_question_integrity(
        raw_stem="What is the SI unit of force acting on a body?",
        raw_options={"A": "Newton", "B": "Joule", "C": "Watt", "D": "Pascal"},
        question_number=1, subject="Physics",
    )
    assert issues == []


def test_check_question_integrity_flags_missing_stem():
    issues = check_question_integrity(raw_stem="", raw_options={"A": "x", "B": "y", "C": "z", "D": "w"}, question_number=1, subject=None)
    assert "MISSING_STEM" in issues


def test_check_question_integrity_flags_missing_options():
    issues = check_question_integrity(raw_stem="A valid enough question stem here", raw_options={"A": "x"}, question_number=1, subject=None)
    assert "MISSING_SOME_OPTIONS" in issues


def test_check_question_integrity_flags_duplicate_option_text():
    issues = check_question_integrity(
        raw_stem="A valid enough question stem here",
        raw_options={"A": "Same text", "B": "Same text", "C": "Other", "D": "Another"},
        question_number=1, subject=None,
    )
    assert "DUPLICATE_OPTION_TEXT" in issues


def test_check_question_integrity_flags_invalid_subject_value():
    issues = check_question_integrity(
        raw_stem="A valid enough question stem here",
        raw_options={"A": "a", "B": "b", "C": "c", "D": "d"},
        question_number=1, subject="Geology",
    )
    assert any(i.startswith("INVALID_SUBJECT_VALUE") for i in issues)


# ---------- duplicate detection ----------

def _row(qid, stem, options, year="2020", paper="P1", num=1):
    return {"question_id": qid, "raw_stem": stem, "raw_options": options, "exam_year": year, "paper_code": paper, "question_number": num}


def test_find_exact_duplicates_stem_and_options_match():
    rows = [
        _row("q1", "What is the SI unit of force?", {"A": "Newton", "B": "Joule", "C": "Watt", "D": "Pascal"}),
        _row("q2", "what is the si unit of force", {"A": "Newton", "B": "Joule", "C": "Watt", "D": "Pascal"}),
    ]
    findings = find_exact_duplicates(rows)
    assert {f.question_id for f in findings} == {"q1", "q2"}
    assert all(f.match_type == "EXACT_STEM_AND_OPTIONS" for f in findings)


def test_find_exact_duplicates_same_stem_different_options_is_exact_stem_only():
    rows = [
        _row("q1", "What is the SI unit of force?", {"A": "Newton", "B": "Joule", "C": "Watt", "D": "Pascal"}),
        _row("q2", "what is the si unit of force", {"A": "Kg", "B": "m", "C": "s", "D": "A"}),
    ]
    findings = find_exact_duplicates(rows)
    assert {f.question_id for f in findings} == {"q1", "q2"}
    assert all(f.match_type == "EXACT_STEM" for f in findings)


def test_find_exact_duplicates_no_duplicates_returns_empty():
    rows = [
        _row("q1", "Question one about photosynthesis in plants", {"A": "a", "B": "b", "C": "c", "D": "d"}),
        _row("q2", "Question two about Newtons laws of motion", {"A": "a", "B": "b", "C": "c", "D": "d"}),
    ]
    assert find_exact_duplicates(rows) == []


def test_find_near_duplicates_high_word_overlap_grouped():
    rows = [
        _row("q1", "The mitochondria is the powerhouse of the eukaryotic cell structure", {}),
        _row("q2", "The mitochondria is called the powerhouse of the eukaryotic cell", {}),
        _row("q3", "Photosynthesis occurs in the chloroplast of green plant cells", {}),
    ]
    findings = find_near_duplicates(rows, exclude_ids=set())
    grouped_ids = {f.question_id for f in findings}
    assert grouped_ids == {"q1", "q2"}
    assert all(f.match_type == "NEAR_DUPLICATE" for f in findings)


def test_find_near_duplicates_excludes_ids_already_marked_exact():
    rows = [
        _row("q1", "The mitochondria is the powerhouse of the eukaryotic cell structure", {}),
        _row("q2", "The mitochondria is the powerhouse of the eukaryotic cell structure", {}),
    ]
    findings = find_near_duplicates(rows, exclude_ids={"q1", "q2"})
    assert findings == []


def test_duplicate_detection_is_deterministic_across_runs():
    rows = [
        _row("q1", "What is the SI unit of force?", {"A": "Newton", "B": "Joule", "C": "Watt", "D": "Pascal"}),
        _row("q2", "what is the si unit of force", {"A": "Newton", "B": "Joule", "C": "Watt", "D": "Pascal"}),
        _row("q3", "The mitochondria is the powerhouse of the eukaryotic cell structure", {}),
        _row("q4", "The mitochondria is called the powerhouse of the eukaryotic cell", {}),
    ]
    exact1 = find_exact_duplicates(rows)
    exact2 = find_exact_duplicates(rows)
    assert exact1 == exact2
    near1 = find_near_duplicates(rows, exclude_ids={f.question_id for f in exact1})
    near2 = find_near_duplicates(rows, exclude_ids={f.question_id for f in exact2})
    assert near1 == near2


# ---------- answer-assertion quality ----------

def test_audit_assertions_no_assertions_is_not_an_issue():
    assert audit_assertions_for_question("q1", {"A": "a", "B": "b", "C": "c", "D": "d"}, []) == []


def test_audit_assertions_flags_option_outside_a_d():
    issues = audit_assertions_for_question(
        "q1", {"A": "a", "B": "b", "C": "c", "D": "d"},
        [{"asserted_option": "E", "verification_status": "VERIFIED", "assertion_source": "src1"}],
    )
    assert "ANSWER_OUTSIDE_A_D:E" in issues


def test_audit_assertions_flags_reference_to_missing_option():
    issues = audit_assertions_for_question(
        "q1", {"A": "a", "B": "b"},
        [{"asserted_option": "C", "verification_status": "VERIFIED", "assertion_source": "src1"}],
    )
    assert "ANSWER_REFERENCES_MISSING_OPTION:C" in issues


def test_audit_assertions_flags_contradictory_verified_assertions():
    issues = audit_assertions_for_question(
        "q1", {"A": "a", "B": "b", "C": "c", "D": "d"},
        [
            {"asserted_option": "A", "verification_status": "VERIFIED", "assertion_source": "src1"},
            {"asserted_option": "B", "verification_status": "VERIFIED", "assertion_source": "src2"},
        ],
    )
    assert "CONTRADICTORY_VERIFIED_ASSERTIONS" in issues


def test_audit_assertions_flags_missing_provenance():
    issues = audit_assertions_for_question(
        "q1", {"A": "a", "B": "b", "C": "c", "D": "d"},
        [{"asserted_option": "A", "verification_status": "UNVERIFIED", "assertion_source": ""}],
    )
    assert "MISSING_ASSERTION_PROVENANCE" in issues


def test_audit_assertions_never_invents_or_infers_answer():
    # No assertions at all -> function must not fabricate one; result is simply empty.
    assert audit_assertions_for_question("q1", {"A": "a", "B": "b", "C": "c", "D": "d"}, []) == []


# ---------- evidence-gap categorization ----------

def test_classify_gap_reason_no_ncert_match_when_all_scores_zero():
    reason = classify_gap_reason(
        quality_issues=[], physics_score=0, chemistry_score=0, biology_score=0,
        top_subject=None, second_subject=None, score_margin=0, match_type=None,
    )
    assert reason == "NO_NCERT_MATCH"


def test_classify_gap_reason_insufficient_text_overrides_scores():
    reason = classify_gap_reason(
        quality_issues=["MISSING_STEM"], physics_score=20, chemistry_score=5, biology_score=0,
        top_subject="Physics", second_subject="Chemistry", score_margin=15, match_type=None,
    )
    assert reason == "INSUFFICIENT_TEXT"


def test_classify_gap_reason_cross_disciplinary_on_tie():
    reason = classify_gap_reason(
        quality_issues=[], physics_score=12, chemistry_score=12, biology_score=0,
        top_subject="Physics", second_subject="Chemistry", score_margin=0, match_type=None,
    )
    assert reason == "CROSS_DISCIPLINARY"


def test_classify_gap_reason_weak_ncert_match_below_ten():
    reason = classify_gap_reason(
        quality_issues=[], physics_score=8, chemistry_score=0, biology_score=0,
        top_subject="Physics", second_subject=None, score_margin=8, match_type=None,
    )
    assert reason == "WEAK_NCERT_MATCH"


def test_classify_gap_reason_ambiguous_physics_chemistry():
    reason = classify_gap_reason(
        quality_issues=[], physics_score=20, chemistry_score=1, biology_score=0,
        top_subject="Physics", second_subject="Chemistry", score_margin=19, match_type=None,
    )
    assert reason == "AMBIGUOUS_PHYSICS_CHEMISTRY"


def test_classify_gap_reason_always_returns_known_category():
    reason = classify_gap_reason(
        quality_issues=[], physics_score=1, chemistry_score=0, biology_score=0,
        top_subject="Physics", second_subject=None, score_margin=1, match_type=None,
    )
    assert reason in GAP_CATEGORIES


def test_classify_gap_reason_deterministic_repeatable():
    kwargs = dict(
        quality_issues=[], physics_score=15, chemistry_score=3, biology_score=0,
        top_subject="Physics", second_subject="Chemistry", score_margin=12, match_type=None,
    )
    assert classify_gap_reason(**kwargs) == classify_gap_reason(**kwargs)


# ---------- legacy provenance ----------

def test_classify_legacy_provenance_no_evidence():
    result = classify_legacy_provenance(current_subject="Biology", recomputed_top_subject=None, recomputed_status="UNRESOLVED", recomputed_top_score=0)
    assert result["provenance_status"] == "SUPPORTED_BY_SOURCE_METADATA"
    assert result["conflict_status"] == "NO_CONFLICT"


def test_classify_legacy_provenance_supported_by_ncert():
    result = classify_legacy_provenance(current_subject="Physics", recomputed_top_subject="Physics", recomputed_status="RESOLVED", recomputed_top_score=25)
    assert result["provenance_status"] == "SUPPORTED_BY_NCERT"
    assert result["ncert_match"] is True
    assert result["conflict_status"] == "NO_CONFLICT"


def test_classify_legacy_provenance_conflicting_evidence():
    result = classify_legacy_provenance(current_subject="Physics", recomputed_top_subject="Chemistry", recomputed_status="RESOLVED", recomputed_top_score=25)
    assert result["provenance_status"] == "CONFLICTING_EVIDENCE"
    assert result["conflict_status"] == "CONFLICT"
    assert result["recommended_action"] == "HUMAN_REVIEW_RECOMMENDED"


def test_classify_legacy_provenance_weakly_supported_ambiguous():
    result = classify_legacy_provenance(current_subject="Physics", recomputed_top_subject="Chemistry", recomputed_status="AMBIGUOUS", recomputed_top_score=8)
    assert result["provenance_status"] == "WEAKLY_SUPPORTED"
    assert result["conflict_status"] == "NO_CONFLICT"


def test_classify_legacy_provenance_never_changes_subject():
    # The function's return value carries no "new subject" field at all —
    # it can only describe evidence, never mutate the classification.
    result = classify_legacy_provenance(current_subject="Physics", recomputed_top_subject="Chemistry", recomputed_status="RESOLVED", recomputed_top_score=25)
    assert "new_subject" not in result
    assert "subject" not in result
