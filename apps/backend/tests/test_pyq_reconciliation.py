# -*- coding: utf-8 -*-
"""Regression tests for scripts/pyq_image_pipeline/reconciliation.py --
the footer-cleanup regex and image-association proposal logic used in the
reconciliation pass over the already-staged `pyq_image_staging` rows.

Pure-function tests; no DB or source PDFs required.
"""
from __future__ import annotations

from scripts.pyq_image_pipeline.reconciliation import (
    clean_footer_text,
    footer_cleanup_status,
    propose_image_candidate,
)


def test_clean_footer_text_strips_mid_string_domain_and_page_number():
    before = "Detritivores\nwww.vedantu.com\n16"
    after, changed = clean_footer_text(before)
    assert changed is True
    assert after == "Detritivores"
    assert "vedantu" not in after


def test_clean_footer_text_strips_mid_string_leak_leaving_later_options_intact():
    before = (
        "Gaseous nutrient cycle \nCarbon and sulphur \nwww.vedantu.com\n17\n"
        "Sedimentary nutrient cycle \nNitrogen and phosphorus"
    )
    after, changed = clean_footer_text(before)
    assert changed is True
    assert "vedantu" not in after
    # Content before AND after the leak must both survive.
    assert "Carbon and sulphur" in after
    assert "Nitrogen and phosphorus" in after


def test_clean_footer_text_strips_full_paper_header_and_trailing_solution():
    before = (
        "5\nNATIONAL    ELIGIBILITY CUM ENTRANCE TEST \n"
        "NEET (UG),       2015 (CODE-A)\nAnswers & Solutions\nChemistry"
    )
    after, changed = clean_footer_text(before)
    assert changed is True
    assert after == "5"


def test_clean_footer_text_is_a_noop_on_already_clean_text():
    before = "Industrial melanism is an example of natural selection."
    after, changed = clean_footer_text(before)
    assert changed is False
    assert after == before


def test_clean_footer_text_never_mutates_input_string():
    before = "Mycoplasma\nwww.vedantu.com\n19"
    original = before
    clean_footer_text(before)
    assert before == original  # str is immutable but guard the contract


def test_footer_cleanup_status_full_vs_partial():
    assert footer_cleanup_status("Mycoplasma") == "FULL"
    assert footer_cleanup_status("still has NEET (UG) residue") == "PARTIAL"


def test_propose_image_candidate_high_confidence_single_image_single_question():
    cand, conf, evidence = propose_image_candidate(
        questions_on_page=["q1"], unlinked_images_on_page=1, already_linked_images_on_page=0
    )
    assert cand == "q1"
    assert conf == "HIGH"
    assert "only unlinked image" in evidence


def test_propose_image_candidate_medium_when_multiple_unlinked_images_share_page():
    cand, conf, evidence = propose_image_candidate(
        questions_on_page=["q1"], unlinked_images_on_page=3, already_linked_images_on_page=0
    )
    assert conf == "MEDIUM"
    assert cand == "q1"


def test_propose_image_candidate_low_when_multiple_questions_share_page():
    cand, conf, evidence = propose_image_candidate(
        questions_on_page=["q1", "q2"], unlinked_images_on_page=5, already_linked_images_on_page=0
    )
    assert conf == "LOW"
    assert "not a real association" in evidence


def test_propose_image_candidate_none_when_no_question_on_page():
    cand, conf, evidence = propose_image_candidate(
        questions_on_page=[], unlinked_images_on_page=1, already_linked_images_on_page=0
    )
    assert cand is None
    assert conf == "NONE"


def test_propose_image_candidate_never_returns_high_when_already_linked_image_present():
    """A page that already has a confidently-linked image should not also
    get a HIGH proposal for its remaining unlinked image -- that would be
    exactly the kind of silent/overconfident link the task rules forbid."""
    cand, conf, evidence = propose_image_candidate(
        questions_on_page=["q1"], unlinked_images_on_page=1, already_linked_images_on_page=1
    )
    assert conf != "HIGH"
