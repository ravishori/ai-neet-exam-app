"""P5 AMBER remediation A–E: visual enforcement, ambiguity, V2 sampler."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.modules.cms.services.factory_candidate_validation import (
    validate_candidate_body,
    validate_candidate_body_detailed,
)
from app.modules.cms.services.factory_sample_v2 import factory_sample_v2
from app.modules.cms.services.factory_v2_answer_ambiguity import (
    STATUS_AMBIGUITY_DETECTED,
    STATUS_REVIEW_REQUIRED,
    STATUS_STRUCTURALLY_VALID,
    assess_exactly_one_answer_semantics,
)
from app.modules.cms.services.factory_v2_visual import (
    V2_VISUAL_SLOT_SPECS,
    attach_visual_to_body,
    build_v2_generation_constraints,
    enrich_slot_with_visual_fields,
    materialize_visual_for_slot,
)

ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"


def _mcq(**kwargs) -> dict:
    body = {
        "stem": "According to NCERT, which statement is correct?",
        "options": [
            {"label": "A", "text": "Force equals mass times acceleration"},
            {"label": "B", "text": "Energy is measured only in candela"},
            {"label": "C", "text": "Momentum has no relation to velocity"},
            {"label": "D", "text": "Temperature is identical to heat transfer"},
        ],
        "correct_option": "A",
        "explanation": "Option A matches Newton second law; others contradict basic mechanics.",
        "difficulty": "medium",
    }
    body.update(kwargs)
    return body


# ---------------------------------------------------------------------------
# A — Visual blueprint propagation
# ---------------------------------------------------------------------------


def test_v2_plan_marks_exactly_three_visual_slots():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    visual_slots = []
    for s in plan["slots"]:
        enriched = enrich_slot_with_visual_fields(dict(s))
        if enriched["visual_required"]:
            visual_slots.append(enriched["slot_id"])
    assert visual_slots == ["physics-05", "physics-21", "zoology-12"]
    assert set(visual_slots) == set(V2_VISUAL_SLOT_SPECS.keys())


def test_visual_requirement_survives_plan_to_slot_to_constraints():
    for slot_id, expected in V2_VISUAL_SLOT_SPECS.items():
        slot = enrich_slot_with_visual_fields(
            {
                "slot_id": slot_id,
                "question_archetype": "diagram_data_interpretation",
                "intent": "test",
            }
        )
        assert slot["visual_required"] is True
        assert slot["visual_type"] == expected["visual_type"]
        assert slot["visual_archetype"] == expected["visual_archetype"]
        constraints = build_v2_generation_constraints(slot)
        assert constraints["visual_required"] is True
        assert constraints["visual_type"] == expected["visual_type"]
        assert constraints["visual_archetype"] == expected["visual_archetype"]


def test_non_visual_slot_constraints_explicit_false():
    slot = enrich_slot_with_visual_fields(
        {"slot_id": "physics-01", "question_archetype": "direct_ncert_conceptual", "intent": "x"}
    )
    assert slot["visual_required"] is False
    constraints = build_v2_generation_constraints(slot)
    assert constraints["visual_required"] is False
    assert constraints["visual_type"] is None


def test_no_extra_graphical_slots_invented_in_plan_cohort():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    assert len(plan["slots"]) == 100
    required = [s["slot_id"] for s in plan["slots"] if enrich_slot_with_visual_fields(s)["visual_required"]]
    assert required == ["physics-05", "physics-21", "zoology-12"]


# ---------------------------------------------------------------------------
# B/C — Visual materialization + validation
# ---------------------------------------------------------------------------


def test_materialize_visual_for_each_planned_archetype():
    for slot_id in V2_VISUAL_SLOT_SPECS:
        spec = materialize_visual_for_slot(slot_id)
        assert spec is not None
        assert "<svg" in spec["diagram_svg"]
        assert spec["visual_spec"]["ncert_evidence"] is False
        assert len(spec["visual_spec"]["labels"]) >= 1


def test_diagram_data_interpretation_without_visual_fails():
    body = _mcq(
        stem="From the given plot of x versus t, the slope equals velocity. What is the slope meaning?",
    )
    constraints = {
        "visual_required": True,
        "visual_type": "line_graph",
        "visual_archetype": "xt_slope_graph",
        "question_archetype": "diagram_data_interpretation",
    }
    validated, errs = validate_candidate_body(body, expected_difficulty="medium", constraints=constraints)
    assert validated is None
    assert any("VISUAL_REQUIRED" in e for e in errs)


def test_diagram_data_interpretation_with_valid_visual_passes():
    body = _mcq(
        stem="From the given x–t graph in the figure, the slope of the straight line equals which kinematic quantity?",
    )
    constraints = {
        "visual_required": True,
        "visual_type": "line_graph",
        "visual_archetype": "xt_slope_graph",
        "visual_required_labels": "x_axis:time,y_axis:position,curve:x(t)",
        "question_archetype": "diagram_data_interpretation",
        "visual_is_ncert_evidence": False,
    }
    body = attach_visual_to_body(body, constraints=constraints)
    validated, errs = validate_candidate_body(body, expected_difficulty="medium", constraints=constraints)
    assert errs == [], errs
    assert validated is not None


def test_visual_type_mismatch_fails():
    body = _mcq(
        stem="Using the figure of the ECG wave schematic, identify the QRS complex.",
    )
    # Attach ECG schematic
    body = attach_visual_to_body(
        body,
        constraints={
            "visual_required": True,
            "visual_type": "schematic",
            "visual_archetype": "ecg_wave_schematic",
        },
    )
    # Validate against graph expectation → mismatch
    constraints = {
        "visual_required": True,
        "visual_type": "line_graph",
        "visual_archetype": "xt_slope_graph",
        "question_archetype": "diagram_data_interpretation",
    }
    validated, errs = validate_candidate_body(body, expected_difficulty="medium", constraints=constraints)
    assert validated is None
    assert any("VISUAL_TYPE_MISMATCH" in e for e in errs)


def test_visual_not_required_passes_without_visual():
    body = _mcq()
    constraints = {"visual_required": False, "question_archetype": "direct_ncert_conceptual"}
    validated, errs = validate_candidate_body(body, expected_difficulty="medium", constraints=constraints)
    assert errs == []
    assert validated is not None


def test_visual_cannot_fabricate_ncert_evidence():
    constraints = {
        "visual_required": True,
        "visual_type": "line_graph",
        "visual_archetype": "xt_slope_graph",
        "visual_required_labels": "x_axis:time,y_axis:position,curve:x(t)",
    }
    body = attach_visual_to_body(
        _mcq(stem="From the figure of x versus t, what does the slope represent?"),
        constraints=constraints,
    )
    vs = dict(body["visual_spec"] or {})
    vs["ncert_evidence"] = True
    body["visual_spec"] = vs
    validated, errs = validate_candidate_body(body, expected_difficulty="medium", constraints=constraints)
    assert validated is None
    assert any("VISUAL_NCERT_EVIDENCE_FABRICATED" in e or "VISUAL_FALSE_NCERT_EVIDENCE" in e for e in errs)


def test_archetype_string_alone_does_not_satisfy_visual_requirement():
    """diagram_data_interpretation without visual must fail even if archetype string is set."""
    body = _mcq(stem="Interpret the diagram data as described in the stem text only.")
    constraints = {
        "visual_required": True,
        "visual_type": "schematic",
        "visual_archetype": "ecg_wave_schematic",
        "question_archetype": "diagram_data_interpretation",
    }
    detailed = validate_candidate_body_detailed(
        body, expected_difficulty="medium", constraints=constraints
    )
    assert detailed["ok"] is False
    assert detailed["visual_validation"]["passed"] is False


# ---------------------------------------------------------------------------
# D — Exactly-one-answer / Zoology-15 regression
# ---------------------------------------------------------------------------


def test_zoology_15_dual_defensible_pattern_detected():
    """Regression: forensic zoology-15 A+D both pulmonary+systemic+RV+LV → AMBIGUITY."""
    body = _mcq(
        stem=(
            "Which of the following comparative statements correctly contrasts the functional "
            "topology and physiological features of the human pulmonary circuit with those of "
            "the systemic circuit?"
        ),
        options=[
            {
                "label": "A",
                "text": (
                    "The pulmonary circuit operates at a lower vascular resistance and pressure, "
                    "receiving deoxygenated blood from the right ventricle, whereas the systemic "
                    "circuit operates under higher pressure to pump oxygenated blood from the "
                    "left ventricle to body tissues."
                ),
            },
            {
                "label": "B",
                "text": (
                    "The pulmonary circuit receives deoxygenated blood from the left atrium and "
                    "routes it through the pulmonary veins to the lungs, whereas the systemic "
                    "circuit receives oxygenated blood from the right atrium and routes it "
                    "through the aorta."
                ),
            },
            {
                "label": "C",
                "text": (
                    "The pulmonary circuit operates under higher vascular resistance than the "
                    "systemic circuit, ensuring rapid blood flow through capillaries, while the "
                    "systemic circuit operates at low resistance to protect delicate organ beds."
                ),
            },
            {
                "label": "D",
                "text": (
                    "The pulmonary circuit begins in the right ventricle and terminates at the "
                    "left atrium carrying oxygenated blood, whereas the systemic circuit begins "
                    "in the left ventricle and returns deoxygenated blood to the right atrium."
                ),
            },
        ],
        correct_option="A",
        explanation=(
            "Option A is correct because the pulmonary circuit pumps deoxygenated blood from the "
            "right ventricle to the lungs and back to the left atrium under relatively low "
            "vascular resistance and pressure."
        ),
    )
    assessment = assess_exactly_one_answer_semantics(body)
    assert assessment.status == STATUS_AMBIGUITY_DETECTED
    assert assessment.flags

    validated, errs = validate_candidate_body(
        body, expected_difficulty="medium", constraints={"visual_required": False}
    )
    assert validated is None
    assert any("SEMANTIC_AMBIGUITY_DETECTED" in e for e in errs)


def test_semantic_statuses_are_distinct():
    clean = _mcq()
    a = assess_exactly_one_answer_semantics(clean)
    assert a.status == STATUS_STRUCTURALLY_VALID

    near = _mcq(
        options=[
            {"label": "A", "text": "The acceleration equals g near Earth surface value"},
            {"label": "B", "text": "The acceleration equals g near the Earth surface value"},
            {"label": "C", "text": "Velocity remains perfectly constant always"},
            {"label": "D", "text": "Mass of the body increases rapidly"},
        ],
        correct_option="A",
        explanation="Only A is correct; B is a near-paraphrase of A about g.",
    )
    b = assess_exactly_one_answer_semantics(near)
    assert b.status in {STATUS_REVIEW_REQUIRED, STATUS_AMBIGUITY_DETECTED}


def test_v1_path_without_constraints_unchanged_structurally():
    """Historical callers without constraints still get structural-only checks."""
    body = _mcq()
    validated, errs = validate_candidate_body(body, expected_difficulty="medium")
    assert errs == []
    assert validated is not None


# ---------------------------------------------------------------------------
# E — factory_sample_v2
# ---------------------------------------------------------------------------


def _synthetic_population(n_per_subject: dict[str, int], *, with_visuals: bool = True) -> list[dict]:
    rows = []
    diffs = ["easy", "medium", "hard"]
    archetypes = ["direct_ncert_conceptual", "formula_application", "diagram_data_interpretation"]
    for subj, count in n_per_subject.items():
        for i in range(count):
            is_visual = False
            if with_visuals:
                if subj == "Physics" and i < 2:
                    is_visual = True
                if subj == "Zoology" and i == 0:
                    is_visual = True
            rows.append(
                {
                    "id": str(uuid4()),
                    "blueprint_id": str(uuid4()),
                    "subject_name": subj,
                    "difficulty": diffs[i % 3],
                    "question_archetype": archetypes[i % 3],
                    "visual_required": is_visual,
                    "is_numerical": i % 4 == 0,
                }
            )
    return rows


def test_factory_sample_v2_reproducible_same_seed():
    rows = _synthetic_population({"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15})
    a = factory_sample_v2(rows, sample_size=20, seed=42)
    b = factory_sample_v2(rows, sample_size=20, seed=42)
    assert a["sampled_ids"] == b["sampled_ids"]
    assert a["seed"] == 42
    assert a["requested_sample_size"] == 20
    assert a["actual_sample_size"] == 20


def test_factory_sample_v2_different_seed_can_differ():
    rows = _synthetic_population({"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15})
    a = factory_sample_v2(rows, sample_size=20, seed=42)
    b = factory_sample_v2(rows, sample_size=20, seed=99)
    assert a["seed"] != b["seed"]


def test_factory_sample_v2_subject_representation():
    rows = _synthetic_population({"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15})
    report = factory_sample_v2(rows, sample_size=20, seed=42)
    dist = report["subject_distribution"]
    for subj in ("Physics", "Chemistry", "Botany", "Zoology"):
        assert dist.get(subj, 0) >= 1, f"missing subject {subj}: {dist}"


def test_factory_sample_v2_visual_representation_when_present():
    rows = _synthetic_population({"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15})
    assert any(r["visual_required"] for r in rows)
    report = factory_sample_v2(rows, sample_size=20, seed=42)
    assert report["visual_distribution"].get("visual_required", 0) >= 1
    assert "difficulty_distribution" in report
    assert "archetype_distribution" in report
    assert "numerical_distribution" in report
    assert len(report["sampled_ids"]) == report["actual_sample_size"]


def test_sample_v1_policy_untouched_in_qa_service():
    from app.modules.cms.models.factory_qa import SAMPLING_POLICY_V1

    assert SAMPLING_POLICY_V1 == "factory_sample_v1"
