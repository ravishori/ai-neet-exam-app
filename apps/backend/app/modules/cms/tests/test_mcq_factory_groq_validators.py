"""Unit tests for the core MCQ-FACTORY-GROQ-001 deterministic validators.

No network calls. No live LLM provider. No real database — the one test
that reaches the real ``publication_gates.evaluate_question_publication_gates``
function uses a mocked AsyncSession (unittest.mock), never a live Postgres
connection, consistent with the task's "no live DB required" constraint.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import fitz
import pytest

from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf
from app.modules.cms.mcq_factory_groq.schemas import GeneratedMcqCandidate
from app.modules.cms.mcq_factory_groq.validators import (
    CorpusAnswerRecord,
    InMemoryTaxonomyResolver,
    VerificationVerdict,
    detect_duplicate_options,
    detect_placeholder_options,
    evaluate_publication_readiness,
    find_cross_corpus_conflicts,
    gate_reviewer,
    recompute_numerical,
    run_deterministic_validation_pipeline,
    verify_source_evidence_relocatable,
)

SUBJECT_ID = "11111111-1111-1111-1111-111111111111"
CHAPTER_ID = "22222222-2222-2222-2222-222222222222"
TOPIC_ID = "33333333-3333-3333-3333-333333333333"
CONCEPT_ID = "44444444-4444-4444-4444-444444444444"

OTHER_SUBJECT_ID = "99999999-9999-9999-9999-999999999999"


def _taxonomy_resolver(*, consistent: bool = True) -> InMemoryTaxonomyResolver:
    return InMemoryTaxonomyResolver(
        subjects={SUBJECT_ID: None, OTHER_SUBJECT_ID: None},
        chapters={CHAPTER_ID: SUBJECT_ID if consistent else OTHER_SUBJECT_ID},
        topics={TOPIC_ID: CHAPTER_ID},
        concepts={CONCEPT_ID: TOPIC_ID},
    )


def _write_pdf(path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(str(path))
    doc.close()


def _good_candidate(doc_id: str, quoted_snippet: str, *, page: int = 1) -> GeneratedMcqCandidate:
    return GeneratedMcqCandidate.model_validate(
        {
            "stem": "According to the evidence, what force equals mass times acceleration?",
            "options": [
                {"label": "A", "text": "Newton's second law"},
                {"label": "B", "text": "Newton's third law"},
                {"label": "C", "text": "Ohm's law"},
                {"label": "D", "text": "Hooke's law"},
            ],
            "correct_option": "A",
            "explanation": "Newton's second law states F = m times a, as given in the evidence chunk.",
            "source_evidence": {"doc_id": doc_id, "page": page, "quoted_snippet": quoted_snippet},
            "taxonomy": {
                "subject_id": SUBJECT_ID,
                "chapter_id": CHAPTER_ID,
                "topic_id": TOPIC_ID,
                "concept_id": CONCEPT_ID,
            },
            "difficulty": "medium",
        }
    )


# --- placeholder / duplicate option detection --------------------------------


def test_detect_placeholder_options_flags_literal_placeholders():
    options = [
        {"label": "A", "text": "Option A"},
        {"label": "B", "text": "Mitochondria"},
        {"label": "C", "text": "TBD"},
        {"label": "D", "text": ""},
    ]
    flagged = detect_placeholder_options(options)
    assert set(flagged) == {"A", "C", "D"}


def test_detect_placeholder_options_allows_real_short_answers():
    options = [
        {"label": "A", "text": "ATP"},
        {"label": "B", "text": "ADP"},
        {"label": "C", "text": "NADH"},
        {"label": "D", "text": "FADH2"},
    ]
    assert detect_placeholder_options(options) == []


def test_detect_duplicate_options_flags_normalized_duplicates():
    options = [
        {"label": "A", "text": "The mitochondria"},
        {"label": "B", "text": "the Mitochondria!"},
        {"label": "C", "text": "Ribosome"},
        {"label": "D", "text": "Golgi body"},
    ]
    assert detect_duplicate_options(options) == ["A", "B"]


def test_detect_duplicate_options_no_false_positive_on_distinct_text():
    options = [
        {"label": "A", "text": "Mitochondria"},
        {"label": "B", "text": "Ribosome"},
        {"label": "C", "text": "Golgi body"},
        {"label": "D", "text": "Nucleus"},
    ]
    assert detect_duplicate_options(options) == []


# --- taxonomy resolver --------------------------------------------------


def test_taxonomy_resolver_consistent_chain():
    resolver = _taxonomy_resolver(consistent=True)
    candidate = _good_candidate("doc", "snippet text here that is long enough")
    resolution = resolver.resolve(candidate.taxonomy)
    assert resolution.consistent is True
    assert resolution.reasons == []


def test_taxonomy_resolver_rejects_unknown_id():
    resolver = _taxonomy_resolver(consistent=True)
    from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds

    bad = TaxonomyIds(
        subject_id=SUBJECT_ID,
        chapter_id="does-not-exist",
        topic_id=TOPIC_ID,
        concept_id=CONCEPT_ID,
    )
    resolution = resolver.resolve(bad)
    assert resolution.consistent is False
    assert any("TAXONOMY_CHAPTER_NOT_FOUND" in r for r in resolution.reasons)


def test_taxonomy_resolver_rejects_chapter_under_wrong_subject():
    resolver = _taxonomy_resolver(consistent=False)  # chapter actually under OTHER_SUBJECT_ID
    candidate = _good_candidate("doc", "snippet text here that is long enough")
    resolution = resolver.resolve(candidate.taxonomy)
    assert resolution.consistent is False
    assert "TAXONOMY_CHAPTER_NOT_UNDER_SUBJECT" in resolution.reasons


def test_taxonomy_resolver_allows_null_concept_id():
    resolver = _taxonomy_resolver(consistent=True)
    from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds

    ids = TaxonomyIds(subject_id=SUBJECT_ID, chapter_id=CHAPTER_ID, topic_id=TOPIC_ID, concept_id=None)
    resolution = resolver.resolve(ids)
    assert resolution.consistent is True


# --- provenance re-location (anti-fabrication) --------------------------


def test_provenance_check_passes_for_exact_relocatable_snippet(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    _write_pdf(pdf_path, "Newtons second law states that force equals mass times acceleration in classical mechanics.")
    doc = index_pdf(pdf_path)
    candidate = _good_candidate(doc.doc_id, "force equals mass times acceleration", page=1)

    result = verify_source_evidence_relocatable(candidate, doc)
    assert result.ok is True
    assert result.relocated_page == 1


def test_provenance_check_rejects_fabricated_snippet(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    _write_pdf(pdf_path, "This page is about photosynthesis in chloroplasts and has nothing to do with physics.")
    doc = index_pdf(pdf_path)
    candidate = _good_candidate(doc.doc_id, "a sentence that was never actually written on this page", page=1)

    result = verify_source_evidence_relocatable(candidate, doc)
    assert result.ok is False
    assert any("FABRICATED" in r for r in result.reasons)


def test_provenance_check_rejects_doc_id_mismatch(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    _write_pdf(pdf_path, "Some real content about Newtons second law of motion and force.")
    doc = index_pdf(pdf_path)
    candidate = _good_candidate("completely-different-doc-id", "Newtons second law", page=1)

    result = verify_source_evidence_relocatable(candidate, doc)
    assert result.ok is False
    assert any("DOC_ID_MISMATCH" in r for r in result.reasons)


def test_provenance_check_flags_page_mismatch_but_finds_elsewhere(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    doc_bytes = fitz.open()
    doc_bytes.new_page().insert_text((72, 72), "Irrelevant first page content about geography.")
    doc_bytes.new_page().insert_text((72, 72), "Newtons second law states force equals mass times acceleration.")
    doc_bytes.save(str(pdf_path))
    doc_bytes.close()

    doc = index_pdf(pdf_path)
    # Candidate claims page 1, but the snippet actually lives on page 2.
    candidate = _good_candidate(doc.doc_id, "force equals mass times acceleration", page=1)

    result = verify_source_evidence_relocatable(candidate, doc)
    assert result.ok is False
    assert result.relocated_page == 2
    assert any("PAGE_MISMATCH" in r for r in result.reasons)


# --- cross-corpus answer conflicts --------------------------------------


def test_find_cross_corpus_conflicts_detects_disagreeing_answer():
    candidate = _good_candidate("doc", "snippet text here that is long enough")
    corpus = [
        CorpusAnswerRecord(
            source="staging:batch-x",
            stem=candidate.stem,
            correct_option_text_norm="ohms law",  # disagrees with candidate's "Newton's second law"
        )
    ]
    conflicts = find_cross_corpus_conflicts(candidate, corpus)
    assert conflicts
    assert "ANSWER_CONFLICT_WITH" in conflicts[0]


def test_find_cross_corpus_conflicts_no_conflict_for_different_stem():
    candidate = _good_candidate("doc", "snippet text here that is long enough")
    corpus = [
        CorpusAnswerRecord(
            source="staging:batch-x",
            stem="A totally unrelated question about chemistry.",
            correct_option_text_norm="something else",
        )
    ]
    assert find_cross_corpus_conflicts(candidate, corpus) == []


def test_find_cross_corpus_conflicts_agreeing_answer_is_not_a_conflict():
    candidate = _good_candidate("doc", "snippet text here that is long enough")
    corpus = [
        CorpusAnswerRecord(
            source="staging:batch-x",
            stem=candidate.stem,
            correct_option_text_norm="newtons second law",
        )
    ]
    assert find_cross_corpus_conflicts(candidate, corpus) == []


# --- numerical recomputation (reuses numerical_validation.classify_and_verify) --


def test_recompute_numerical_not_numerical_when_absent():
    status, _detail = recompute_numerical(None)
    assert status == "NOT_NUMERICAL"


def test_recompute_numerical_complete_for_correct_formula():
    status, _detail = recompute_numerical({"formula": "F=ma", "m": 2.0, "a": 3.0, "F": 6.0})
    assert status == "NUMERICAL_COMPLETE"


def test_recompute_numerical_invalid_for_wrong_arithmetic():
    status, _detail = recompute_numerical({"formula": "F=ma", "m": 2.0, "a": 3.0, "F": 999.0})
    assert status == "NUMERICAL_INVALID"


def test_recompute_numerical_incomplete_for_missing_keys():
    status, _detail = recompute_numerical({"formula": "F=ma", "m": 2.0})
    assert status == "NUMERICAL_INCOMPLETE"


# --- reviewer gate (never silently overridden) --------------------------


def test_gate_reviewer_pending_is_yellow_not_green():
    outcome = gate_reviewer(None)
    assert outcome.passed is False
    assert outcome.severity == "YELLOW"


def test_gate_reviewer_disagreement_is_red():
    outcome = gate_reviewer(VerificationVerdict(answer_supported=False, ambiguous=False))
    assert outcome.passed is False
    assert outcome.severity == "RED"


def test_gate_reviewer_ambiguous_is_red_even_if_answer_supported():
    outcome = gate_reviewer(VerificationVerdict(answer_supported=True, ambiguous=True))
    assert outcome.passed is False
    assert outcome.severity == "RED"


def test_gate_reviewer_agreement_passes():
    outcome = gate_reviewer(VerificationVerdict(answer_supported=True, ambiguous=False))
    assert outcome.passed is True


# --- full orchestration ---------------------------------------------------


def test_pipeline_classifies_green_when_everything_passes(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    _write_pdf(pdf_path, "Newtons second law states that force equals mass times acceleration precisely.")
    doc = index_pdf(pdf_path)
    candidate = _good_candidate(doc.doc_id, "force equals mass times acceleration", page=1)

    report = run_deterministic_validation_pipeline(
        candidate,
        document=doc,
        taxonomy_resolver=_taxonomy_resolver(consistent=True),
        existing_corpus=[],
        calculation_check=None,
        verification=VerificationVerdict(answer_supported=True, ambiguous=False),
    )
    assert report.classification == "GREEN"
    assert report.sampling_eligible is True
    assert report.quarantine is False
    assert report.stem_hash
    assert report.option_stem_hash


def test_pipeline_quarantines_red_on_fabricated_citation(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    _write_pdf(pdf_path, "Unrelated content about chloroplasts and photosynthesis only.")
    doc = index_pdf(pdf_path)
    candidate = _good_candidate(doc.doc_id, "a quote that absolutely does not appear anywhere here", page=1)

    report = run_deterministic_validation_pipeline(
        candidate,
        document=doc,
        taxonomy_resolver=_taxonomy_resolver(consistent=True),
        verification=VerificationVerdict(answer_supported=True, ambiguous=False),
    )
    assert report.classification == "RED"
    assert report.quarantine is True
    assert "P_PROVENANCE" in report.failing_gate_codes


def test_pipeline_quarantines_red_on_bad_taxonomy(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    _write_pdf(pdf_path, "Newtons second law states that force equals mass times acceleration precisely.")
    doc = index_pdf(pdf_path)
    candidate = _good_candidate(doc.doc_id, "force equals mass times acceleration", page=1)

    report = run_deterministic_validation_pipeline(
        candidate,
        document=doc,
        taxonomy_resolver=_taxonomy_resolver(consistent=False),
        verification=VerificationVerdict(answer_supported=True, ambiguous=False),
    )
    assert report.classification == "RED"
    assert "T_TAXONOMY" in report.failing_gate_codes


def test_pipeline_never_green_when_reviewer_disagrees(tmp_path):
    pdf_path = tmp_path / "s.pdf"
    _write_pdf(pdf_path, "Newtons second law states that force equals mass times acceleration precisely.")
    doc = index_pdf(pdf_path)
    candidate = _good_candidate(doc.doc_id, "force equals mass times acceleration", page=1)

    report = run_deterministic_validation_pipeline(
        candidate,
        document=doc,
        taxonomy_resolver=_taxonomy_resolver(consistent=True),
        verification=VerificationVerdict(answer_supported=False, ambiguous=False, notes="disagree"),
    )
    assert report.classification != "GREEN"
    assert "R_REVIEWER" in report.failing_gate_codes


def test_pipeline_yellow_when_reviewer_pending():
    pdf_path = None
    # Build a minimal doc inline rather than via tmp_path fixture arg.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        pdf_path = Path(d) / "s.pdf"
        _write_pdf(pdf_path, "Newtons second law states that force equals mass times acceleration precisely.")
        doc = index_pdf(pdf_path)
        candidate = _good_candidate(doc.doc_id, "force equals mass times acceleration", page=1)

        report = run_deterministic_validation_pipeline(
            candidate,
            document=doc,
            taxonomy_resolver=_taxonomy_resolver(consistent=True),
            verification=None,
        )
        assert report.classification == "YELLOW"
        assert report.sampling_eligible is False
        assert report.quarantine is False


# --- publication_gates integration (mocked AsyncSession, no live DB) ----


@pytest.mark.asyncio
async def test_evaluate_publication_readiness_calls_real_publication_gates():
    candidate = _good_candidate("doc", "snippet text here that is long enough")
    # Force concept_id None so publication_gates never issues the
    # Concept/Topic/Chapter/Subject join query (that path needs real DB
    # rows and is out of scope for this offline unit test).
    candidate.taxonomy.concept_id = None

    mock_session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))

    report = await evaluate_publication_readiness(
        mock_session,
        candidate,
        ncert_evidence={
            "verification_level": "SECTION_VERIFIED",
            "source_document": "NCERT Class XI Physics",
            "class_level": "11",
            "chapter": "Laws of Motion",
            "section": "4.4",
            "verification_method": "unit-test",
        },
        provenance={"origin": "groq_factory_test", "source": "unit-test-fixture"},
    )

    assert report.structural_ok is True
    assert report.ncert_ok is True
    assert report.provenance_ok is True
    # review_state_ok is always False for a DRAFT — callers must read
    # content_ready, never passed, exactly as trusted_factory_submission.py does.
    assert report.review_state_ok is False
    assert report.content_ready is True
    mock_session.execute.assert_awaited()
