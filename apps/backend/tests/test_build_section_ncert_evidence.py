"""Unit tests for build_section_ncert_evidence()'s subject/class-aware
source_document derivation (fix for the hardcoded "NCERT Class XI Physics"
label that was wrong for any non-Physics-XI caller).

Pure function, no DB, no provider — safe to run anywhere.
"""

from __future__ import annotations

import pytest

from app.modules.cms.services.publication_gates import build_section_ncert_evidence


@pytest.mark.parametrize(
    ("subject", "class_level", "expected_document", "expected_method_suffix"),
    [
        ("Physics", "11", "NCERT Class XI Physics", "Class XI PDF on disk"),
        ("Physics", "12", "NCERT Class XII Physics", "Class XII PDF on disk"),
        ("Chemistry", "11", "NCERT Class XI Chemistry", "Class XI PDF on disk"),
        ("Chemistry", "12", "NCERT Class XII Chemistry", "Class XII PDF on disk"),
        ("Botany", "11", "NCERT Class XI Botany", "Class XI PDF on disk"),
        ("Botany", "12", "NCERT Class XII Botany", "Class XII PDF on disk"),
        ("Zoology", "11", "NCERT Class XI Zoology", "Class XI PDF on disk"),
        ("Zoology", "12", "NCERT Class XII Zoology", "Class XII PDF on disk"),
    ],
)
def test_source_document_reflects_subject_and_class(subject, class_level, expected_document, expected_method_suffix):
    ev = build_section_ncert_evidence(
        ncert_reference=f"NCERT {class_level} {subject} Ch 1 §1.1",
        source_pdf_relpath=f"Class {class_level}/{subject}/chapter1.pdf",
        class_level=class_level,
        subject=subject,
    )
    assert ev["source_document"] == expected_document
    assert ev["verification_method"].endswith(expected_method_suffix)
    assert ev["class_level"] == class_level


def test_verification_level_is_always_section_verified():
    ev = build_section_ncert_evidence(
        ncert_reference="NCERT XI Physics Ch 2 §2.4",
        source_pdf_relpath="Class 11/Physics/ch2.pdf",
        class_level="11",
        subject="Physics",
    )
    assert ev["verification_level"] == "SECTION_VERIFIED"


def test_never_invents_page_number_or_excerpt():
    ev = build_section_ncert_evidence(
        ncert_reference="NCERT XII Botany Ch 5 §5.3",
        source_pdf_relpath="Class 12/Botany/ch5.pdf",
        class_level="12",
        subject="Botany",
    )
    assert ev["page_number"] is None
    assert ev["source_excerpt"] is None


def test_source_pdf_relpath_passed_through_unchanged():
    relpath = "Class 12/Zoology/leph204.pdf"
    ev = build_section_ncert_evidence(
        ncert_reference="NCERT XII Zoology Ch 4 §4.2",
        source_pdf_relpath=relpath,
        class_level="12",
        subject="Zoology",
    )
    assert ev["source_pdf_relpath"] == relpath


def test_unknown_class_level_falls_back_to_literal_value():
    """Defensive: an unexpected class_level string (not 11/12) must not
    crash — it's used as-is rather than mapped to a Roman numeral."""
    ev = build_section_ncert_evidence(
        ncert_reference="NCERT X Physics Ch 1 §1.1",
        source_pdf_relpath="Class 10/Physics/ch1.pdf",
        class_level="10",
        subject="Physics",
    )
    assert ev["source_document"] == "NCERT Class 10 Physics"
    assert ev["class_level"] == "10"


def test_existing_callers_default_behavior_unchanged():
    """Both real callers (physics_t6d_bank.py, cms/seed.py) call this with
    only ncert_reference + source_pdf_relpath — defaults must still
    produce exactly the original hardcoded string."""
    ev = build_section_ncert_evidence(
        ncert_reference="NCERT XI Physics Ch 1 §1.2",
        source_pdf_relpath="StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf",
    )
    assert ev["source_document"] == "NCERT Class XI Physics"
    assert ev["verification_method"] == "Gate-4 section reference + Class XI PDF on disk"
