"""Numerical validation contract (T6-E-FIX).

NUMERICAL_COMPLETE → eligible for scientific PASS
NUMERICAL_INCOMPLETE → FAIL/HOLD
NUMERICAL_INVALID → FAIL
NOT_NUMERICAL → conceptual scientific path
"""

from __future__ import annotations

import math
from typing import Any

from app.modules.cms.schemas.question_evidence import NumericalStatus

# formula value → required keys (including formula)
REQUIRED_KEYS: dict[str, set[str]] = {
    "v=u+at": {"formula", "u", "a", "t", "v"},
    "v_avg": {"formula", "dx", "dt", "v_avg"},
    "v_rel": {"formula", "va", "vb", "v_ab"},
    "projectile_R": {"formula", "u", "theta_deg", "g", "R"},
    "vector_mag": {"formula", "ax", "ay", "mag"},
    "centripetal": {"formula", "v", "r", "a_c"},
    "F=ma": {"formula", "m", "a", "F"},
    "W=Fs": {"formula", "F", "s", "W"},
    "dK": {"formula", "m", "u", "v", "dK"},
    "P=W/t": {"formula", "W", "t", "P"},
    "p_sum": {"formula", "m1", "v1", "m2", "v2", "p"},
    "f_max": {"formula", "mu", "N", "f_max"},
    "x_cm": {"formula", "x1", "x2", "x_cm"},
    "tau=rF": {"formula", "r", "F", "tau"},
    "I=mr^2": {"formula", "m", "r", "I"},
}

# Exact-match tolerance when no presentation precision is declared (T6-D convention).
_EXACT_NUMERIC_TOLERANCE = 1e-6
# Tolerance on already-rounded display values (float artefact only).
_DISPLAY_ROUND_TOLERANCE = 1e-9

# Distinctive result keys that imply a numerical payload even without formula
_HINT_KEYS = (
    "v",
    "v_avg",
    "v_ab",
    "R",
    "mag",
    "a_c",
    "F",
    "W",
    "dK",
    "P",
    "p",
    "f_max",
    "x_cm",
    "tau",
    "I",
)


def classify_and_verify(calc: dict[str, Any] | None) -> tuple[NumericalStatus, str]:
    """Return (status, detail). COMPLETE only when formula+keys present and recompute matches."""
    if not calc:
        return "NOT_NUMERICAL", "conceptual/no-numeric-check"

    formula = calc.get("formula")
    looks_numerical = bool(formula) or any(k in calc for k in _HINT_KEYS)
    if not looks_numerical:
        return "NOT_NUMERICAL", "conceptual/no-numeric-check"

    if not formula or formula not in REQUIRED_KEYS:
        return "NUMERICAL_INCOMPLETE", f"incomplete:missing-or-unknown-formula:{formula!r}"

    need = REQUIRED_KEYS[formula]
    if not need <= set(calc):
        missing = sorted(need - set(calc))
        return "NUMERICAL_INCOMPLETE", f"incomplete:missing-keys:{missing}"

    try:
        ok, msg = _recompute(formula, calc)
        if not ok:
            return "NUMERICAL_INVALID", msg
        return "NUMERICAL_COMPLETE", msg
    except Exception as exc:  # noqa: BLE001
        return "NUMERICAL_INVALID", f"calc-error:{exc}"


def _verify_vector_mag(calc: dict[str, Any]) -> tuple[bool, str]:
    """Validate |r| = hypot(ax, ay) against declared presentation or exact precision."""
    ax, ay, stored = calc["ax"], calc["ay"], calc["mag"]
    try:
        exact = math.hypot(float(ax), float(ay))
        stored_f = float(stored)
    except (TypeError, ValueError):
        return False, "vector mag invalid components"

    precision = calc.get("mag_precision")
    if precision is not None:
        try:
            p = int(precision)
        except (TypeError, ValueError):
            return False, "invalid mag_precision"
        if p < 0:
            return False, "invalid mag_precision"
        expected_display = round(exact, p)
        if abs(expected_display - stored_f) > _DISPLAY_ROUND_TOLERANCE:
            return False, "vector mag mismatch"
        return True, "vector mag ok"

    if abs(exact - stored_f) <= _EXACT_NUMERIC_TOLERANCE:
        return True, "vector mag ok"

    # Implicit 2-decimal presentation when stored mag equals round(exact, 2).
    # Backward compat for T6-F1 historical payloads generated before mag_precision.
    if abs(round(exact, 2) - stored_f) <= _DISPLAY_ROUND_TOLERANCE:
        return True, "vector mag ok"

    return False, "vector mag mismatch"


def _recompute(kind: str, calc: dict[str, Any]) -> tuple[bool, str]:
    if kind == "v=u+at":
        expected = calc["u"] + calc["a"] * calc["t"]
        if abs(expected - calc["v"]) > 1e-6:
            return False, f"v mismatch: {expected} vs {calc['v']}"
        return True, "v=u+at ok"
    if kind == "v_avg":
        if abs(calc["dx"] / calc["dt"] - calc["v_avg"]) > 1e-6:
            return False, "v_avg mismatch"
        return True, "v_avg ok"
    if kind == "v_rel":
        if abs(calc["va"] - calc["vb"] - calc["v_ab"]) > 1e-6:
            return False, "relative velocity mismatch"
        return True, "v_rel ok"
    if kind == "projectile_R":
        u, deg, g = calc["u"], calc["theta_deg"], calc["g"]
        R = (u * u * math.sin(math.radians(2 * deg))) / g
        if abs(R - calc["R"]) > 0.15:
            return False, f"range mismatch {R} vs {calc['R']}"
        return True, "projectile R ok"
    if kind == "vector_mag":
        return _verify_vector_mag(calc)
    if kind == "centripetal":
        if abs(calc["v"] ** 2 / calc["r"] - calc["a_c"]) > 1e-6:
            return False, "centripetal mismatch"
        return True, "a_c ok"
    if kind == "F=ma":
        if abs(calc["m"] * calc["a"] - calc["F"]) > 1e-6:
            return False, "F=ma mismatch"
        return True, "F=ma ok"
    if kind == "W=Fs":
        if abs(calc["F"] * calc["s"] - calc["W"]) > 1e-6:
            return False, "W=Fs mismatch"
        return True, "W=Fs ok"
    if kind == "dK":
        expected = 0.5 * calc["m"] * (calc["v"] ** 2 - calc["u"] ** 2)
        if abs(expected - calc["dK"]) > 1e-6:
            return False, f"dK mismatch {expected} vs {calc['dK']}"
        return True, "dK ok"
    if kind == "P=W/t":
        if abs(calc["W"] / calc["t"] - calc["P"]) > 1e-6:
            return False, "P=W/t mismatch"
        return True, "P=W/t ok"
    if kind == "p_sum":
        expected = calc["m1"] * calc["v1"] + calc["m2"] * calc["v2"]
        if abs(expected - calc["p"]) > 1e-6:
            return False, f"p mismatch {expected} vs {calc['p']}"
        return True, "p_sum ok"
    if kind == "f_max":
        if abs(calc["mu"] * calc["N"] - calc["f_max"]) > 1e-6:
            return False, "f_max mismatch"
        return True, "f_max ok"
    if kind == "x_cm":
        expected = (calc["x1"] + calc["x2"]) / 2
        if abs(expected - calc["x_cm"]) > 1e-6:
            return False, "x_cm mismatch"
        return True, "x_cm ok"
    if kind == "tau=rF":
        if abs(calc["r"] * calc["F"] - calc["tau"]) > 1e-6:
            return False, "tau mismatch"
        return True, "tau=rF ok"
    if kind == "I=mr^2":
        if abs(calc["m"] * calc["r"] ** 2 - calc["I"]) > 1e-6:
            return False, "I mismatch"
        return True, "I=mr^2 ok"
    return False, f"unknown kind {kind}"
