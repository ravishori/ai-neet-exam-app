from app.modules.ingestion.services.language_service import (
    LANGUAGE_NAMES,
    NotImplementedTranslationService,
    clean_text,
    detect_language,
    normalize_unicode,
    resolve_content_language,
)

ENGLISH_TEXT = (
    "Ohm's Law states that the current through a conductor is directly "
    "proportional to the potential difference across it, provided the "
    "temperature remains constant."
)

HINDI_TEXT = (
    "ओम का नियम कहता है कि किसी चालक में प्रवाहित धारा उसके सिरों के बीच "
    "विभवांतर के अनुक्रमानुपाती होती है, बशर्ते तापमान स्थिर रहे।"
)

MIXED_TEXT = (
    "ओम का नियम (Ohm's Law) बताता है कि करंट (current) वोल्टेज के "
    "समानुपाती होता है, प्रोवाइडेड कि तापमान स्थिर रहे, temperature "
    "should remain constant throughout the experiment."
)


def test_detects_english_text_with_high_confidence():
    result = detect_language(ENGLISH_TEXT)
    assert result.language_code == "en"
    assert result.confidence > 0.9


def test_detects_hindi_text_with_high_confidence():
    result = detect_language(HINDI_TEXT)
    assert result.language_code == "hi"
    assert result.confidence > 0.9


def test_detects_genuinely_mixed_text():
    result = detect_language(MIXED_TEXT)
    assert result.language_code == "mixed"
    assert result.confidence > 0.0


def test_text_with_no_alphabetic_content_defaults_to_english_with_zero_confidence():
    result = detect_language("3.14159   —   2 + 2 = 4")
    assert result.language_code == "en"
    assert result.confidence == 0.0


def test_mixed_confidence_is_lower_near_the_boundary_than_at_a_clean_split():
    # A perfect 50/50 split is confidently "mixed" (peaks at 1.0, per the
    # formula's own design); a ratio near the mixed/pure threshold is a much
    # less confident "mixed" call, since it's one letter away from being
    # classified as pure English or pure Hindi instead.
    balanced = "abcde" + "अआइई ऊ"  # 5 Latin, 5 Devanagari — ratio 0.5
    near_boundary = ("a" * 17) + "अआइई"  # 17 Latin, 4 Devanagari — ratio ~0.19, just past 0.15

    balanced_result = detect_language(balanced)
    boundary_result = detect_language(near_boundary)

    assert balanced_result.language_code == "mixed"
    assert boundary_result.language_code == "mixed"
    assert boundary_result.confidence < balanced_result.confidence


def test_normalize_unicode_strips_zero_width_characters():
    text = "Ohm​s Law‌ relates‍ voltage﻿ and current"
    normalized = normalize_unicode(text)
    assert "​" not in normalized
    assert "‌" not in normalized
    assert "‍" not in normalized
    assert "﻿" not in normalized


def test_normalize_unicode_collapses_extra_whitespace_but_keeps_paragraph_breaks():
    text = "Ohm's   Law    relates  voltage.\nCurrent  is   proportional."
    normalized = normalize_unicode(text)
    assert normalized == "Ohm's Law relates voltage.\nCurrent is proportional."


def test_normalize_unicode_applies_nfc_composition():
    # "e" + combining acute accent (decomposed) should compose to "é" (NFC)
    decomposed = "café"
    normalized = normalize_unicode(decomposed)
    assert normalized == "café"


def test_clean_text_normalizes_smart_quotes_and_dashes():
    text = "The “resistance” — sometimes called ‘R’ — doesn't change…"
    cleaned = clean_text(text)
    assert '"resistance"' in cleaned
    assert "'R'" in cleaned
    assert "-" in cleaned
    assert "..." in cleaned
    assert "‘" not in cleaned and "’" not in cleaned
    assert "“" not in cleaned and "”" not in cleaned


def test_clean_text_removes_replacement_character_ocr_artifact():
    # PyMuPDF's own known failure mode on this exact source (see
    # pdf_extraction_service.py) — "OHM�S LAW" from a mangled apostrophe glyph.
    cleaned = clean_text("OHM�S LAW")
    assert "�" not in cleaned
    assert cleaned == "OHMS LAW"


def test_clean_text_includes_unicode_normalization():
    text = "Ohm's​   Law"
    cleaned = clean_text(text)
    assert "​" not in cleaned
    assert "  " not in cleaned


def test_translation_service_stub_returns_not_implemented():
    service = NotImplementedTranslationService()
    assert service.translate("Ohm's Law", target_language="hi") is NotImplemented


def test_resolve_content_language_passes_through_supported_codes():
    assert resolve_content_language("hi", supported_languages=["en", "hi"]) == "hi"
    assert resolve_content_language("en", supported_languages=["en", "hi"]) == "en"


def test_resolve_content_language_falls_back_to_english_for_mixed():
    assert resolve_content_language("mixed", supported_languages=["en", "hi"]) == "en"


def test_resolve_content_language_falls_back_to_english_for_unsupported_or_missing():
    assert resolve_content_language("fr", supported_languages=["en", "hi"]) == "en"
    assert resolve_content_language(None, supported_languages=["en", "hi"]) == "en"


def test_language_names_cover_every_supported_code():
    assert LANGUAGE_NAMES["en"] == "English"
    assert LANGUAGE_NAMES["hi"] == "Hindi"
    assert LANGUAGE_NAMES["mixed"] == "Mixed"
