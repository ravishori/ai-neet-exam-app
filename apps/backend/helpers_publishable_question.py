"""Shared publishable QUESTION body for tests (T6-E-FIX publication gates)."""

from __future__ import annotations

from typing import Any

from app.modules.cms.services.publication_gates import build_section_ncert_evidence, build_test_provenance


def publishable_question_body(
    stem: str = "Ohm's law relates which quantities?",
    *,
    correct_option: str = "A",
    difficulty: str = "easy",
    explanation: str = "V = IR relates potential difference, current and resistance.",
    options: list[dict[str, str]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "stem": stem,
        "options": options
        or [
            {"label": "A", "text": "V, I, R"},
            {"label": "B", "text": "Force and mass"},
            {"label": "C", "text": "Charge and time"},
            {"label": "D", "text": "Energy and power only"},
        ],
        "correct_option": correct_option,
        "explanation": explanation,
        "difficulty": difficulty,
        "ncert_evidence": build_section_ncert_evidence(
            ncert_reference="NCERT XI Physics Ch 1 §1.2",
            source_pdf_relpath="StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf",
        ),
        "provenance": build_test_provenance(),
        "numerical_evidence": {"status": "NOT_NUMERICAL", "calculation_check": {}},
        "calculation_check": None,
    }
    body.update(overrides)
    return body
