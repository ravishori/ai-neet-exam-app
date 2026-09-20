"""Unit tests for Production Seed V1 diversity remediations (B/C/E)."""

from __future__ import annotations

from app.modules.cms.prompts.factory_mcq import build_user_prompt
from app.modules.cms.services.factory_candidate_validation import validate_candidate_body
from app.modules.cms.services.factory_qa_gates import gate_e_answer_explanation
from app.modules.cms.services.factory_seed_diversity import (
    classify_against_prior,
    detect_forbidden_template,
    phenotype_explanation_error,
    seed_slot_spec,
)


def _mcq(**kwargs):
    body = {
        "stem": kwargs.get("stem", "What is Ohm's law relating V, I and R?"),
        "options": [
            {"label": "A", "text": kwargs.get("a", "V = IR")},
            {"label": "B", "text": kwargs.get("b", "V = I/R")},
            {"label": "C", "text": kwargs.get("c", "V = I + R")},
            {"label": "D", "text": kwargs.get("d", "V = R/I")},
        ],
        "correct_option": kwargs.get("correct", "A"),
        "explanation": kwargs.get(
            "explanation",
            "By definition Ohm's law states V equals I times R for ohmic conductors.",
        ),
        "difficulty": kwargs.get("difficulty", "medium"),
    }
    return body


def test_seed_slot_spec_diversified():
    slots = seed_slot_spec()
    assert len(slots) == 30
    by_subj = {}
    for s in slots:
        by_subj.setdefault(s["subject_code"], []).append(s)
    assert len(by_subj["PHYSICS"]) == 10
    assert len(by_subj["CHEMISTRY"]) == 10
    assert len(by_subj["BOTANY"]) == 5
    assert len(by_subj["ZOOLOGY"]) == 5
    chem_codes = [s["concept_code"] for s in by_subj["CHEMISTRY"]]
    assert chem_codes.count("lattice-energy") == 1
    assert "abo-blood-grouping" not in [s["concept_code"] for s in by_subj["ZOOLOGY"]]
    assert "photophosphorylation" not in [s["concept_code"] for s in by_subj["BOTANY"]]
    phys_codes = {s["concept_code"] for s in by_subj["PHYSICS"]}
    assert len(phys_codes) == 10


def test_forbidden_template_detection():
    assert detect_forbidden_template(
        "A wire is stretched so that its length increases by 20\\% at constant voltage"
    )
    assert detect_forbidden_template("non-cyclic photophosphorylation produces ATP and NADPH")
    assert detect_forbidden_template("Arrange the agglutination sequence with Anti-A and Anti-B") is not None
    assert detect_forbidden_template("Apply Blackman's law of limiting factors to CO2") is None


def test_prior_stem_near_duplicate_rejected():
    prior = ["A metallic wire is stretched uniformly so length increases by 20% under constant V"]
    label, code = classify_against_prior(
        stem="A metallic wire is stretched uniformly so that its length increases by 20% under constant V",
        option_texts=["0.69 I", "I", "1.2 I", "I/2"],
        prior_stems=prior,
    )
    assert label in {"NEAR_DUPLICATE", "NORMALIZED_DUPLICATE", "SAME_TEMPLATE_REPETITION"}
    assert code is not None


def test_unique_stem_allowed():
    label, code = classify_against_prior(
        stem="According to Bernoulli's principle, for steady ideal flow along a streamline, which quantity is conserved?",
        option_texts=["P + ρgh + ½ρv²", "P only", "KE only", "mass flux only"],
        prior_stems=["Ohm's law states V = IR for ohmic conductors at constant temperature."],
    )
    assert label in {"UNIQUE", "LEGITIMATE_CONCEPTUAL_OVERLAP"}
    assert code is None


def test_phenotype_explanation_incomplete():
    assert (
        phenotype_explanation_error(
            "A patient with blood group A positive needs transfusion. Sequence the ABO tests.",
            "Mix with Anti-A and Anti-B only; then major crossmatch.",
        )
        == "PHENOTYPE_EXPLANATION_INCOMPLETE"
    )
    assert (
        phenotype_explanation_error(
            "A patient with blood group A positive needs transfusion.",
            "ABO typing uses Anti-A/Anti-B; Rh typing uses Anti-D because the patient is Rh positive.",
        )
        is None
    )


def test_validate_body_phenotype_gate():
    ok, errs = validate_candidate_body(
        _mcq(
            stem="Patient is A positive. Choose correct typing reagents including Rh.",
            explanation="Only Anti-A and Anti-B are needed for grouping.",
        ),
        expected_difficulty="medium",
    )
    assert ok is None
    assert "PHENOTYPE_EXPLANATION_INCOMPLETE" in errs

    ok2, errs2 = validate_candidate_body(
        _mcq(
            stem="Patient is A positive. Choose correct typing reagents including Rh.",
            explanation="Use Anti-A, Anti-B and Anti-D because A positive means A antigen and Rh(D) present.",
        ),
        expected_difficulty="medium",
    )
    assert errs2 == [] and ok2 is not None


def test_gate_e_phenotype_red():
    body = _mcq(
        stem="Recipient is B positive. Arrange compatibility steps.",
        explanation="Perform ABO agglutination with Anti-A and Anti-B antisera only.",
    )
    g = gate_e_answer_explanation(body)
    assert g.passed is False
    assert "PHENOTYPE_EXPLANATION_INCOMPLETE" in g.failures


def test_prompt_includes_prior_stems_and_forbidden():
    text = build_user_prompt(
        subject_name="Physics",
        chapter_name="Current Electricity",
        topic_name="Ohm",
        concept_name="Ohm's Law",
        concept_summary=None,
        objective_title="Assess Ohm",
        objective_description=None,
        family_name="seed",
        family_intent="conceptual",
        difficulty="medium",
        constraints={
            "avoid_paraphrase_duplicates": True,
            "forbidden_templates": ["PHYS_STRETCH_20PCT_CURRENT"],
            "cognitive_operation": "relationship reasoning",
        },
        provenance_note="ai",
        prior_stems=["Prior stem about resistors in series."],
    )
    assert "PHYS_STRETCH_20PCT_CURRENT" in text
    assert "Prior stem about resistors" in text
    assert "Rh" in text or "Anti-D" in text
