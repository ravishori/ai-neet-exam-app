from pyq_subject_classifier.ncert_index import SubjectTermIndex
from pyq_subject_classifier.scoring import classify_text


def _index(physics_words, chemistry_words, biology_words):
    idx = SubjectTermIndex()
    idx.exclusive_words = {
        "Physics": set(physics_words),
        "Chemistry": set(chemistry_words),
        "Biology": set(biology_words),
    }
    idx.word_evidence = {
        w: {"subject": "Physics", "book": "keph101.pdf", "chapter": "keph101", "class": "11", "page": 1}
        for w in physics_words
    }
    idx.word_evidence.update(
        {w: {"subject": "Chemistry", "book": "kech101.pdf", "chapter": "kech101", "class": "11", "page": 1} for w in chemistry_words}
    )
    idx.word_evidence.update(
        {w: {"subject": "Biology", "book": "kebo101.pdf", "chapter": "kebo101", "class": "11", "page": 1} for w in biology_words}
    )
    return idx


def test_deterministic_scoring_picks_clear_winner():
    idx = _index(
        physics_words=["kinematics", "acceleration", "velocity", "gravitation", "thermodynamics"],
        chemistry_words=["equilibrium", "reagent"],
        biology_words=["chloroplast", "mitochondria"],
    )
    text = "kinematics acceleration velocity gravitation thermodynamics newton"
    result = classify_text(text, idx)
    assert result.predicted_subject == "Physics"
    assert result.status == "RESOLVED"
    assert result.confidence in ("HIGH", "MEDIUM", "LOW")
    assert result.scores["Physics"] == 5


def test_shared_vocabulary_is_never_counted_for_either_subject():
    """'energy' style words that appear in >1 subject's NCERT corpus must
    never be exclusive-vocabulary evidence for any subject."""
    idx = SubjectTermIndex()
    idx.word_subject_counts = {"energy": {"Physics": 10, "Chemistry": 5, "Biology": 0}}
    for subj in ("Physics", "Chemistry", "Biology"):
        idx.exclusive_words[subj] = {
            w for w, counts in idx.word_subject_counts.items()
            if counts.get(subj, 0) > 0 and all(counts.get(o, 0) == 0 for o in ("Physics", "Chemistry", "Biology") if o != subj)
        }
    assert "energy" not in idx.exclusive_words["Physics"]
    assert "energy" not in idx.exclusive_words["Chemistry"]

    result = classify_text("energy energy energy", idx)
    assert result.status == "UNRESOLVED"
    assert result.predicted_subject is None


def test_ambiguous_when_tied():
    idx = _index(physics_words=["kinematics"], chemistry_words=["reagent"], biology_words=[])
    result = classify_text("kinematics reagent", idx)
    assert result.status == "AMBIGUOUS"
    assert result.predicted_subject is None


def test_unresolved_when_no_evidence():
    idx = _index(physics_words=["kinematics"], chemistry_words=[], biology_words=[])
    result = classify_text("completely unrelated stem text here", idx)
    assert result.status == "UNRESOLVED"
    assert result.predicted_subject is None
    assert result.confidence == "UNRESOLVED"


def test_never_invents_fake_precision_percentage():
    idx = _index(physics_words=["kinematics", "velocity", "acceleration", "gravitation", "newton", "torque"], chemistry_words=[], biology_words=[])
    text = "kinematics velocity acceleration gravitation newton torque"
    result = classify_text(text, idx)
    assert isinstance(result.scores["Physics"], int)
    assert result.confidence in ("HIGH", "MEDIUM", "LOW", "UNRESOLVED")
