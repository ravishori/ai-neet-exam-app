from pyq_subject_classifier.normalize import combined_question_text, normalize_text


def test_normalize_collapses_whitespace():
    assert normalize_text("a   b\n\tc") == "a b c"


def test_normalize_strips_ocr_junk_and_smart_quotes():
    assert normalize_text("it’s \x0bok”") == "it's ok\""


def test_normalize_empty():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


def test_combined_question_text_includes_options():
    text = combined_question_text("What is X?", {"A": "energy", "B": "mass", "C": "", "D": None})
    assert "energy" in text
    assert "mass" in text
    assert "What is X" in text
