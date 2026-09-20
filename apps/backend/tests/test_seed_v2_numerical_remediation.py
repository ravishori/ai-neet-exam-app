"""Regression tests for V2 numerical remediation failure classes + verifiers."""
from __future__ import annotations

from app.modules.cms.services.factory_v2_numerical_verify import (
    ORIGINAL_FAILURE_EXPECTATIONS,
    validate_option_set,
    verify_momentum_inelastic,
    verify_slot_body,
    verify_thin_lens,
    verify_work_energy,
    verify_youngs_modulus,
)


def test_original_physics10_failure_class():
    body = {
        "stem": (
            "A block $A$ of mass $2\\text{ kg}$ moves along a smooth, straight horizontal track "
            "with a velocity of $6\\text{ m/s}$ towards a stationary block $B$ of mass $4\\text{ kg}$. "
            "The two blocks collide in a perfectly inelastic head-on collision and stick together."
        ),
        "options": [
            {"label": "A", "text": "Impulse = $8\\text{ N}\\cdot\\text{s}$, Energy lost = $16\\text{ J}$"},
            {"label": "B", "text": "Impulse = $12\\text{ N}\\cdot\\text{s}$, Energy lost = $24\\text{ J}$"},
            {"label": "C", "text": "Impulse = $8\\text{ N}\\cdot\\text{s}$, Energy lost = $24\\text{ J}$"},
            {"label": "D", "text": "Impulse = $12\\text{ N}\\cdot\\text{s}$, Energy lost = $16\\text{ J}$"},
        ],
        "correct_option": "A",
        "explanation": "placeholder",
    }
    r = verify_momentum_inelastic(body)
    assert r["status"] == "FAIL"
    assert r["expected_option"] == "C"
    assert r["computed"]["ke_loss"] == 24.0
    assert r["computed"]["impulse_on_stationary"] == 8.0
    assert ORIGINAL_FAILURE_EXPECTATIONS["physics-10"]["independent_option"] == "C"


def test_original_physics11_failure_class():
    body = {
        "stem": (
            "A particle of mass $2\\text{ kg}$ is initially moving along a straight line with a velocity of "
            "$3\\text{ m/s}$. The force varies with displacement $x$ according to $F(x) = (6x - 4)\\text{ N}$. "
            "Find the final kinetic energy after it travels from $x = 0\\text{ m}$ to $x = 3\\text{ m}$."
        ),
        "options": [
            {"label": "A", "text": "15 J"},
            {"label": "B", "text": "24 J"},
            {"label": "C", "text": "21 J"},
            {"label": "D", "text": "12 J"},
        ],
        "correct_option": "C",
        "explanation": "placeholder",
    }
    r = verify_work_energy(body)
    assert r["status"] == "FAIL"
    assert r["expected_option"] == "B"
    assert r["computed"]["Kf"] == 24.0


def test_original_physics20_failure_class():
    body = {
        "stem": (
            "A structural steel wire of length $2.0\\text{ m}$ and cross-sectional area "
            "$4.0 \\times 10^{-6}\\text{ m}^2$ is stretched by a force of $800\\text{ N}$. "
            "If Young's modulus for steel is $2.0 \\times 10^{11}\\text{ N/m}^2$, what is the elongation?"
        ),
        "options": [
            {"label": "A", "text": "$1.0 \\times 10^{-3}\\text{ m}$"},
            {"label": "B", "text": "$2.0 \\times 10^{-3}\\text{ m}$"},
            {"label": "C", "text": "$4.0 \\times 10^{-3}\\text{ m}$"},
            {"label": "D", "text": "$2.0 \\times 10^{-4}\\text{ m}$"},
        ],
        "correct_option": "A",
        "explanation": "placeholder",
    }
    r = verify_youngs_modulus(body)
    assert r["status"] == "FAIL"
    assert r["expected_option"] == "B"
    assert abs(r["computed"]["delta_L"] - 0.002) < 1e-12


def test_original_physics34_failure_class_absent_option():
    body = {
        "stem": (
            "A point object is placed on the principal axis of a thin convex lens of focal length "
            "$f = +15\\text{ cm}$. An initial real image is formed at a distance of $30\\text{ cm}$ "
            "from the lens. The object is then moved $5\\text{ cm}$ towards the lens. "
            "What is the shift in the position of the image?"
        ),
        "options": [
            {"label": "A", "text": "$30\\text{ cm}$ away from the lens"},
            {"label": "B", "text": "$30\\text{ cm}$ towards the lens"},
            {"label": "C", "text": "$15\\text{ cm}$ away from the lens"},
            {"label": "D", "text": "$15\\text{ cm}$ towards the lens"},
        ],
        "correct_option": "A",
        "explanation": "placeholder",
    }
    r = verify_thin_lens(body)
    assert r["status"] == "FAIL"
    assert abs(r["computed"]["shift_cm"] - 7.5) < 1e-9
    assert r.get("reason") == "CORRECT_RESULT_ABSENT_FROM_OPTIONS"


def test_thin_lens_pass_when_correct_option_present():
    body = {
        "stem": (
            "A point object is placed on the principal axis of a thin convex lens of focal length "
            "$f = +15\\text{ cm}$. An initial real image is formed at a distance of $30\\text{ cm}$ "
            "from the lens. The object is then moved $5\\text{ cm}$ towards the lens. "
            "What is the shift in the position of the image?"
        ),
        "options": [
            {"label": "A", "text": "$7.5\\text{ cm}$ away from the lens"},
            {"label": "B", "text": "$7.5\\text{ cm}$ towards the lens"},
            {"label": "C", "text": "$15\\text{ cm}$ away from the lens"},
            {"label": "D", "text": "$30\\text{ cm}$ away from the lens"},
        ],
        "correct_option": "A",
        "explanation": "Using 1/v-1/u=1/f, shift is 7.5 cm away. Option A.",
    }
    r = verify_slot_body("physics-34", body)
    assert r["status"] == "PASS"
    assert r["expected_option"] == "A"


def test_option_set_requires_unique_correct_value():
    opts = [
        {"label": "A", "text": "2.0 m"},
        {"label": "B", "text": "2.0 m"},
        {"label": "C", "text": "3.0 m"},
        {"label": "D", "text": "4.0 m"},
    ]
    r = validate_option_set(opts, expected_value=2.0)
    assert not r["ok"]
    assert "DUPLICATE_OPTION_TEXTS" in r["issues"] or "DUPLICATE_NUMERIC_OPTIONS" in r["issues"] or "CORRECT_RESULT_IN_MULTIPLE_OPTIONS" in r["issues"]


def test_thin_lens_u1_u2_object_form_pass():
    body = {
        "stem": (
            "A small object is placed on the principal axis in front of a thin convex lens of focal length "
            "$f = +18\\text{ cm}$. Initially, the object is located at a distance of $u_1 = -30\\text{ cm}$ "
            "from the optical centre of the lens. The object is then shifted along the principal axis to a new "
            "position such that its distance from the lens becomes $u_2 = -45\\text{ cm}$."
        ),
        "options": [
            {"label": "A", "text": "Shifts by $15\\text{ cm}$ away from the lens"},
            {"label": "B", "text": "Shifts by $15\\text{ cm}$ towards the lens"},
            {"label": "C", "text": "Shifts by $7.5\\text{ cm}$ towards the lens"},
            {"label": "D", "text": "Shifts by $7.5\\text{ cm}$ away from the lens"},
        ],
        "correct_option": "B",
        "explanation": "v1=+45, v2=+30, shift 15 cm towards. Option B.",
    }
    r = verify_thin_lens(body)
    assert r["status"] == "PASS"
    assert r["expected_option"] == "B"
    assert abs(r["computed"]["shift_cm"] - (-15.0)) < 1e-9


def test_thin_lens_object_placement_distances_pass():
    body = {
        "stem": (
            "A small luminous object is placed on the principal axis of a thin converging lens of focal length "
            "$f = +10\\text{ cm}$. Initially, the object is at a distance of $30\\text{ cm}$ in front of the lens. "
            "The object is then moved along the axis to a new position $15\\text{ cm}$ in front of the lens."
        ),
        "options": [
            {"label": "A", "text": "Shifts by $15\\text{ cm}$ towards the lens"},
            {"label": "B", "text": "Shifts by $15\\text{ cm}$ away from the lens"},
            {"label": "C", "text": "Shifts by $30\\text{ cm}$ away from the lens"},
            {"label": "D", "text": "Shifts by $45\\text{ cm}$ away from the lens"},
        ],
        "correct_option": "B",
        "explanation": "v1=+15, v2=+30, shift +15 cm away. Option B.",
    }
    r = verify_thin_lens(body)
    assert r["status"] == "PASS"
    assert r["expected_option"] == "B"
    assert abs(r["computed"]["shift_cm"] - 15.0) < 1e-9
