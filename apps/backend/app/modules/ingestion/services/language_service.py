"""Language processing — see ADR-0027.

KISS by design: language *identification* here is a mechanical script-ratio
check (Devanagari vs. Latin character counts), not a statistical/ML
classifier — the same "mechanical gate, not model self-assertion"
discipline already used by knowledge/grounding_check.py. It needs no new
dependency, is fully deterministic, and is exactly as accurate as this
project currently needs: distinguishing English, Hindi, and a mix of the
two in NCERT/NEET source material, not general-purpose language ID across
dozens of languages.

Supported languages come from Settings.supported_languages (default
["en", "hi"]) — adding a third language is a config change plus whatever
new detection/normalization rules it needs, not a change to this module's
shape. See LANGUAGE_NAMES below for the one place a new code's display
name would need to be added.
"""
import unicodedata
from dataclasses import dataclass
from typing import Protocol

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mixed": "Mixed",
}

# Unicode block for Devanagari (used by Hindi) — see
# https://unicode.org/charts/PDF/U0900.pdf. Latin is checked via str.isascii
# letter ranges rather than a second Unicode block table, since NCERT/NEET
# English source text is always plain ASCII Latin in practice.
_DEVANAGARI_RANGE = (0x0900, 0x097F)

# Ratio thresholds for classifying the script mix of a text. Text with less
# than 15% of either script is treated as effectively pure in the other;
# anything in between is genuinely mixed (e.g. an English question stem
# with a Hindi gloss, common in bilingual NEET material).
HINDI_RATIO_THRESHOLD = 0.85
ENGLISH_RATIO_THRESHOLD = 0.15

# Characters that are invisible but not whitespace — left over from some
# PDF encodings and from copy-pasted web text. Stripped during
# normalization because they corrupt both language detection (they count as
# neither script) and downstream string matching (e.g. duplicate-stem
# checks) if left in.
_ZERO_WIDTH_CHARS = ("​", "‌", "‍", "﻿")

# Smart-quote and OCR-artifact characters normalized to their plain ASCII
# equivalents. Deliberately narrow — this is real punctuation NCERT/NEET
# source PDFs are known to produce (see pdf_extraction_service.py's own
# apostrophe-mangling fix for the same class of problem), not a general
# Unicode-punctuation-folding table.
_PUNCTUATION_MAP = {
    "‘": "'", "’": "'",  # left/right single quotation mark
    "“": '"', "”": '"',  # left/right double quotation mark
    "–": "-", "—": "-",  # en dash, em dash
    "…": "...",  # horizontal ellipsis
    "�": "",  # replacement character — a failed-decode artifact, not content
}


@dataclass
class LanguageDetectionResult:
    language_code: str  # "en" | "hi" | "mixed"
    confidence: float  # 0.0-1.0


def detect_language(text: str) -> LanguageDetectionResult:
    """Mechanical script-ratio detection — see module docstring. Confidence
    is how far the script ratio sits from the ambiguous middle, not a model
    probability: 1.0 for a text that's entirely one script, tapering to its
    lowest point at an exactly 50/50 mix."""
    devanagari_count = 0
    latin_count = 0
    for ch in text:
        code_point = ord(ch)
        if _DEVANAGARI_RANGE[0] <= code_point <= _DEVANAGARI_RANGE[1]:
            devanagari_count += 1
        elif ch.isascii() and ch.isalpha():
            latin_count += 1

    total = devanagari_count + latin_count
    if total == 0:
        # No alphabetic signal at all (numbers, symbols, whitespace only) —
        # default to English rather than claim a detection that has no
        # basis, with confidence reflecting that there's nothing to go on.
        return LanguageDetectionResult(language_code="en", confidence=0.0)

    hindi_ratio = devanagari_count / total

    if hindi_ratio >= HINDI_RATIO_THRESHOLD:
        return LanguageDetectionResult(language_code="hi", confidence=hindi_ratio)
    if hindi_ratio <= ENGLISH_RATIO_THRESHOLD:
        return LanguageDetectionResult(language_code="en", confidence=1.0 - hindi_ratio)
    # Genuinely mixed: confidence peaks at 1.0 exactly at a 50/50 split and
    # falls off toward either threshold.
    distance_from_midpoint = abs(hindi_ratio - 0.5)
    confidence = 1.0 - (distance_from_midpoint / 0.35)  # 0.35 = 0.5 - ENGLISH_RATIO_THRESHOLD
    return LanguageDetectionResult(language_code="mixed", confidence=max(0.0, confidence))


def normalize_unicode(text: str) -> str:
    """Safe, lossless-in-meaning cleanup applied to text that will be
    *stored* (e.g. IngestionSection.raw_text) — NFC normalization, zero-width
    character removal, and whitespace collapsing. Deliberately does not
    touch punctuation or OCR artifacts (see clean_text for that) since
    raw_text is kept as an audit/citation source and shouldn't be rewritten
    more aggressively than "make the encoding correct.\""""
    text = unicodedata.normalize("NFC", text)
    for zwc in _ZERO_WIDTH_CHARS:
        text = text.replace(zwc, "")
    # Collapse runs of horizontal whitespace, but preserve paragraph breaks
    # (pdf_extraction_service's heading regex and section splitting depend
    # on newline structure).
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(lines).strip()


def clean_text(text: str) -> str:
    """More aggressive cleanup applied at *use* time (e.g. building an AI
    prompt), not persisted over the stored raw_text: punctuation/quote
    normalization and OCR-artifact removal. Includes normalize_unicode's
    cleanup so callers can use this alone when they don't need the raw_text
    preserved separately."""
    text = normalize_unicode(text)
    for artifact, replacement in _PUNCTUATION_MAP.items():
        text = text.replace(artifact, replacement)
    return text


class TranslationService(Protocol):
    """Interface for future implementation — see ADR-0027. Deliberately not
    implemented: this project supports English and Hindi as source-content
    languages only; nothing today needs to translate FROM one INTO the
    other. Any real implementation (calling an MT API, or an AIGateway
    prompt) is separately scoped, separately justified, future work."""

    def translate(self, text: str, target_language: str) -> object:
        ...


class NotImplementedTranslationService:
    """The only TranslationService implementation that exists today. Every
    call returns the `NotImplemented` singleton, per this ADR's explicit
    scope — not a raised exception, since nothing calls this yet and there
    is no error condition to signal, only an unimplemented one."""

    def translate(self, text: str, target_language: str) -> object:
        return NotImplemented


def resolve_content_language(language_code: str | None, supported_languages: list[str]) -> str:
    """Maps a detected section language onto the value actually stored on
    cms.content_items.language (ADR-0019), which is a simple "which language
    is this content in" tag for serving decisions — "mixed" doesn't fit
    that purpose (content can't be served as half-Hindi-half-English to a
    single preferred_language reader), so it falls back to English, the
    same fallback philosophy ADR-0019 already established for missing
    translations."""
    if language_code in supported_languages and language_code != "mixed":
        return language_code
    return "en"
