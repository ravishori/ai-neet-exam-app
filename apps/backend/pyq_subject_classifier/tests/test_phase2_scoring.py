from pyq_subject_classifier.ncert_index import SubjectTermIndex
from pyq_subject_classifier.phase2_index import ChapterEntry, Phase2Index
from pyq_subject_classifier.phase2_scoring import classify_phase2


def _term_idx():
    idx = SubjectTermIndex()
    idx.exclusive_words = {
        "Physics": {"kinematics", "acceleration", "velocity", "gravitation", "newton", "torque"},
        "Chemistry": {"molarity", "electrolysis", "titration", "reagent"},
        "Biology": {"chloroplast", "mitochondria", "photosynthesis", "chromosome"},
    }
    return idx


def _phase2_idx():
    idx = Phase2Index()
    idx.chapters["keph105"] = ChapterEntry(
        chapter_id="keph105", subject="Physics", book="keph105.pdf", class_level="11",
        words={"kinematics", "acceleration", "velocity", "gravitation", "newton", "torque", "motion"},
        normalized_text="a body undergoes uniformly accelerated motion under gravitation near earth surface constant",
    )
    idx.chapters["kech106"] = ChapterEntry(
        chapter_id="kech106", subject="Chemistry", book="kech106.pdf", class_level="11",
        words={"molarity", "electrolysis", "titration", "reagent"},
        normalized_text="the molarity of a solution is defined as moles of solute per litre",
    )
    idx.chapters["kebo104"] = ChapterEntry(
        chapter_id="kebo104", subject="Biology", book="kebo104.pdf", class_level="11",
        words={"chloroplast", "mitochondria", "photosynthesis", "chromosome"},
        normalized_text="the chloroplast is the site of photosynthesis in plant cells containing chromosome",
    )
    return idx


def test_chapter_concentration_resolves_clear_case():
    result = classify_phase2(
        "A body undergoes kinematics with acceleration and velocity under gravitation, find torque using newton laws",
        {"A": "1 m/s", "B": "2 m/s", "C": "3 m/s", "D": "4 m/s"},
        _term_idx(), _phase2_idx(),
    )
    assert result.classification_status == "RESOLVED"
    assert result.predicted_subject == "Physics"
    assert result.confidence in ("HIGH", "MEDIUM")


def test_exact_phrase_match_contributes_evidence():
    result = classify_phase2(
        "The molarity of a solution is defined as moles of solute per litre for titration reagent electrolysis",
        {"A": "x", "B": "y", "C": "z", "D": "w"},
        _term_idx(), _phase2_idx(),
    )
    assert result.predicted_subject == "Chemistry"
    match_types = {e.get("match_type") for e in result.evidence}
    assert "EXACT_NCERT_PHRASE" in match_types or "CHAPTER_CONCENTRATION" in match_types


def test_option_evidence_is_weighted_lower_than_stem():
    """A single subject keyword only in options must not alone resolve."""
    result = classify_phase2(
        "What is the correct value according to the following statement given above",
        {"A": "chloroplast", "B": "x", "C": "y", "D": "z"},
        _term_idx(), _phase2_idx(),
    )
    assert result.classification_status != "RESOLVED"


def test_single_generic_word_never_resolves():
    idx = _term_idx()
    idx.exclusive_words["Physics"].add("energy")  # simulate accidental leakage
    result = classify_phase2("What is the energy value calculate following", {}, idx, _phase2_idx())
    # one weak term alone (score < required margin) must not be RESOLVED
    assert result.classification_status != "RESOLVED"


def test_cross_subject_overlap_does_not_force_classification():
    result = classify_phase2(
        "Discuss energy pressure temperature work equilibrium radiation in general terms",
        {}, _term_idx(), _phase2_idx(),
    )
    assert result.classification_status in ("UNRESOLVED", "AMBIGUOUS")


def test_margin_examples_from_spec():
    from pyq_subject_classifier.phase2_scoring import Phase2Result

    r_high = Phase2Result({"Physics": 27, "Chemistry": 8, "Biology": 0}, "Physics", "Chemistry", 19, "HIGH", "RESOLVED", [])
    assert r_high.predicted_subject == "Physics"

    r_ambiguous = Phase2Result({"Physics": 18, "Chemistry": 17, "Biology": 0}, "Physics", "Chemistry", 1, "LOW", "AMBIGUOUS", [])
    assert r_ambiguous.predicted_subject is None


def test_unresolved_when_zero_evidence():
    result = classify_phase2("completely unrelated text with no scientific terms at all", {}, _term_idx(), _phase2_idx())
    assert result.classification_status == "UNRESOLVED"
    assert result.predicted_subject is None


def test_formula_style_terms_supplement_not_standalone():
    """A lone formula-ish term ('velocity') without chapter concentration
    should not alone push to RESOLVED."""
    result = classify_phase2("Define velocity in the following statement", {}, _term_idx(), _phase2_idx())
    assert result.classification_status != "RESOLVED"


def test_ncert_provenance_present_when_resolved():
    result = classify_phase2(
        "The chloroplast contains chromosome material and is the site of photosynthesis in mitochondria-rich cells",
        {"A": "a", "B": "b", "C": "c", "D": "d"},
        _term_idx(), _phase2_idx(),
    )
    if result.classification_status == "RESOLVED":
        assert result.evidence
        assert all("ncert_book" in e for e in result.evidence)
