"""Independent numerical verification for Seed V2 numerical remediation.

Deterministic solvers for the four FAIL concept families. Does NOT trust stored answers.
"""
from __future__ import annotations

import math
import re
from typing import Any


def _opts(body: dict) -> list[dict]:
    return list(body.get("options") or [])


def _correct(body: dict) -> str:
    return str(body.get("correct_option") or "").strip().upper()


def _stem(body: dict) -> str:
    return str(body.get("stem") or "")


def parse_sci(text: str) -> list[float]:
    """Extract numbers including a × 10^{b} forms."""
    vals: list[float] = []
    for m in re.finditer(
        r"([-+]?[0-9]+(?:\.[0-9]+)?)\s*(?:\\\\times|×|x)\s*10\^\{?(-?\d+)\}?",
        text,
        re.I,
    ):
        vals.append(float(m.group(1)) * (10 ** int(m.group(2))))
    for m in re.finditer(r"([-+]?[0-9]+(?:\.[0-9]+)?)", text):
        # skip exponents already consumed roughly by checking context — keep simple
        vals.append(float(m.group(1)))
    return vals


def option_numeric_values(options: list[dict]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for o in options:
        lab = str(o.get("label") or "").upper()
        raw = str(o.get("text") or "")
        m2 = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*\\times\s*10\^\{(-?\d+)\}", raw)
        if m2:
            out[lab] = float(m2.group(1)) * (10 ** int(m2.group(2)))
            continue
        m = re.search(r"([-+]?[0-9]+(?:\.[0-9]+)?)", raw)
        out[lab] = float(m.group(1)) if m else None
    return out


def validate_option_set(options: list[dict], *, expected_value: float | None = None, abs_tol: float = 1e-9, rel_tol: float = 1e-6) -> dict[str, Any]:
    labels = [str(o.get("label") or "").upper() for o in options]
    texts = [str(o.get("text") or "").strip() for o in options]
    issues: list[str] = []
    if sorted(labels) != ["A", "B", "C", "D"]:
        issues.append("OPTION_LABELS_NOT_ABCD")
    if len(texts) != 4:
        issues.append("OPTION_COUNT_NE_4")
    if len(set(t.lower() for t in texts)) != 4:
        issues.append("DUPLICATE_OPTION_TEXTS")
    nums = option_numeric_values(options)
    numeric_vals = [v for v in nums.values() if v is not None]
    if len(numeric_vals) != len(set(round(v, 12) for v in numeric_vals)):
        issues.append("DUPLICATE_NUMERIC_OPTIONS")
    matching_labels: list[str] = []
    if expected_value is not None:
        for lab, v in nums.items():
            if v is None:
                continue
            if math.isclose(v, expected_value, rel_tol=rel_tol, abs_tol=abs_tol):
                matching_labels.append(lab)
        if len(matching_labels) == 0:
            issues.append("CORRECT_RESULT_ABSENT_FROM_OPTIONS")
        elif len(matching_labels) > 1:
            issues.append("CORRECT_RESULT_IN_MULTIPLE_OPTIONS")
    return {
        "ok": not issues,
        "issues": issues,
        "matching_labels": matching_labels,
        "numeric_by_label": nums,
    }


def explanation_mentions_answer(body: dict, *, computed: Any) -> dict[str, Any]:
    expl = str(body.get("explanation") or "")
    correct = _correct(body)
    issues: list[str] = []
    if not expl.strip():
        issues.append("EMPTY_EXPLANATION")
    # Soft: explanation should mention correct option letter or computed value
    mentions_letter = bool(re.search(rf"\boption\s*{correct}\b|\({correct}\)|answer\s*is\s*{correct}", expl, re.I))
    return {"ok": len(issues) == 0, "issues": issues, "mentions_correct_letter": mentions_letter, "length": len(expl)}


def verify_momentum_inelastic(body: dict) -> dict[str, Any]:
    """Solve perfectly inelastic 1D collision for impulse on stationary mass + KE loss."""
    text = _stem(body)
    m = re.search(
        r"mass\s*\$?([0-9.]+).*?(?:moving|moves).*?(?:velocity|speed)\s*(?:of\s*)?\$?([0-9.]+).*?"
        r"(?:stationary|at rest).*?mass\s*\$?([0-9.]+)",
        text,
        re.I | re.S,
    )
    if not m:
        m = re.search(
            r"mass\s*\$?([0-9.]+).*?(?:velocity|speed)\s*(?:of\s*)?\$?([0-9.]+).*?"
            r"(?:stationary|at rest).*?mass\s*\$?([0-9.]+)",
            text,
            re.I | re.S,
        )
    if not m:
        return {"status": "REQUIRES_REVIEW", "reason": "MOMENTUM_PATTERN_NOT_PARSED", "family": "momentum"}
    m1, v1, m2 = map(float, m.groups())
    v = (m1 * v1) / (m1 + m2)
    impulse_on_2 = abs(m2 * v)
    ke_loss = 0.5 * m1 * v1 * v1 - 0.5 * (m1 + m2) * v * v
    matched = None
    for o in _opts(body):
        ot = str(o.get("text") or "")
        nums = [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)", ot)]
        if len(nums) < 2:
            continue
        # Prefer (impulse, ke_loss) order; also allow swapped if clearly labeled
        a, b = nums[0], nums[1]
        if math.isclose(a, impulse_on_2, abs_tol=1e-6) and math.isclose(b, ke_loss, abs_tol=1e-6):
            matched = str(o.get("label") or "").upper()
            break
        if math.isclose(b, impulse_on_2, abs_tol=1e-6) and math.isclose(a, ke_loss, abs_tol=1e-6):
            matched = str(o.get("label") or "").upper()
            break
    if not matched:
        return {
            "status": "FAIL",
            "family": "momentum",
            "computed": {"impulse_on_stationary": impulse_on_2, "ke_loss": ke_loss, "v_common": v},
            "equations": ["v=(m1*v1)/(m1+m2)", "J_on_2=m2*v", "ΔKE=½m1v1²-½(m1+m2)v²"],
            "inputs": {"m1": m1, "v1": v1, "m2": m2},
            "expected_option": None,
            "stored_answer": _correct(body),
            "option_validation": validate_option_set(_opts(body)),
            "reason": "CORRECT_RESULT_ABSENT_FROM_OPTIONS",
        }
    stored = _correct(body)
    status = "PASS" if matched == stored else "FAIL"
    return {
        "status": status,
        "family": "momentum",
        "computed": {"impulse_on_stationary": impulse_on_2, "ke_loss": ke_loss, "v_common": v},
        "equations": ["v=(m1*v1)/(m1+m2)", "J_on_2=m2*v", "ΔKE=½m1v1²-½(m1+m2)v²"],
        "inputs": {"m1": m1, "v1": v1, "m2": m2},
        "expected_option": matched,
        "stored_answer": stored,
        "option_validation": validate_option_set(_opts(body)),
        "single_correct_in_options": True,
    }


def verify_work_energy(body: dict) -> dict[str, Any]:
    text = _stem(body)

    # Quadratic F(x)=(a x^2 ± b x) with Ki from ½mv² at x1, or given KE at x1
    mq = re.search(
        r"F\(x\)\s*=\s*\(\s*([+-]?[0-9.]+)\s*x\^2\s*([+-]\s*[0-9.]+)\s*x\s*\)",
        text,
        re.I,
    )
    if mq:
        a = float(mq.group(1).replace(" ", ""))
        b = float(mq.group(2).replace(" ", ""))
        xs = re.findall(r"x\s*=\s*\$?\s*([0-9.]+)", text)
        if len(xs) < 2:
            # sometimes "at x = 0" once and "reaches x = 2"
            xs = re.findall(r"x\s*=\s*\$?\s*([0-9.]+)\\?text\{?\s*m\s*\}?|x\s*=\s*\$?\s*([0-9.]+)", text)
            flat = [p for tup in xs for p in (tup if isinstance(tup, tuple) else (tup,)) if p]
            xs = flat
        # Extract ordered x values appearing after force definition more carefully:
        x_vals = [float(x) for x in re.findall(r"x\s*=\s*\$?\s*([0-9.]+)", text)]
        if len(x_vals) < 2:
            return {"status": "REQUIRES_REVIEW", "reason": "WORK_ENERGY_QUAD_MISSING_BOUNDS", "family": "work_energy"}
        x1, x2 = x_vals[0], x_vals[-1]
        ke_given = re.search(r"kinetic energy of\s*\$?([0-9.]+)\\text\{ J\}|kinetic energy of\s*\$?([0-9.]+)\s*J", text, re.I)
        if ke_given:
            ki = float(ke_given.group(1) or ke_given.group(2))
        else:
            mass_m = re.search(r"mass\s*\$?([0-9.]+)", text, re.I)
            vel_m = re.search(r"(?:velocity|speed)\s*(?:of\s*)?\$?([0-9.]+)", text, re.I)
            if not (mass_m and vel_m):
                return {"status": "REQUIRES_REVIEW", "reason": "WORK_ENERGY_QUAD_MISSING_KI", "family": "work_energy"}
            mass = float(mass_m.group(1))
            vi = float(vel_m.group(1))
            ki = 0.5 * mass * vi * vi

        def anti(x: float) -> float:
            return (a / 3.0) * x**3 + (b / 2.0) * x**2

        W = anti(x2) - anti(x1)
        kf = ki + W
        ov = validate_option_set(_opts(body), expected_value=kf, abs_tol=1e-6)
        matched = ov["matching_labels"][0] if len(ov["matching_labels"]) == 1 else None
        stored = _correct(body)
        if matched is None:
            return {
                "status": "FAIL",
                "family": "work_energy",
                "computed": {"W": W, "Kf": kf, "Ki": ki},
                "equations": ["W=∫(a x^2 + b x) dx", "Kf=Ki+W"],
                "inputs": {"a": a, "b": b, "x1": x1, "x2": x2, "Ki": ki},
                "expected_option": None,
                "stored_answer": stored,
                "option_validation": ov,
                "reason": "CORRECT_RESULT_ABSENT_OR_AMBIGUOUS",
            }
        return {
            "status": "PASS" if matched == stored else "FAIL",
            "family": "work_energy",
            "computed": {"W": W, "Kf": kf, "Ki": ki},
            "equations": ["W=∫(a x^2 + b x) dx", "Kf=Ki+W"],
            "inputs": {"a": a, "b": b, "x1": x1, "x2": x2, "Ki": ki},
            "expected_option": matched,
            "stored_answer": stored,
            "option_validation": ov,
            "single_correct_in_options": len(ov["matching_labels"]) == 1,
        }

    # Linear F(x)=ax+b or (ax-b) over interval
    m = re.search(
        r"mass\s*\$?([0-9.]+).*?(?:velocity|speed)\s*(?:of\s*)?\$?([0-9.]+).*?F\(x\)\s*=\s*\(?\s*([+-]?[0-9.]+)\s*x\s*([+-]\s*[0-9.]+)\s*\)?.*?"
        r"from\s*\$?x\s*=\s*([+-]?[0-9.]+).*?(?:to|reaches)\s*\$?x\s*=\s*([+-]?[0-9.]+)",
        text,
        re.I | re.S,
    )
    if not m:
        m = re.search(
            r"mass\s*\$?([0-9.]+).*?(?:velocity|speed)\s*(?:of\s*)?\$?([0-9.]+).*?F\(x\)\s*=\s*\(?\s*([+-]?[0-9.]+)\s*x\s*([+-]\s*[0-9.]+)\s*\)?.*?"
            r"x\s*=\s*([+-]?[0-9.]+).*?x\s*=\s*([+-]?[0-9.]+)",
            text,
            re.I | re.S,
        )
    if not m:
        return {"status": "REQUIRES_REVIEW", "reason": "WORK_ENERGY_PATTERN_NOT_PARSED", "family": "work_energy"}
    mass = float(m.group(1))
    vi = float(m.group(2))
    a = float(m.group(3).replace(" ", ""))
    b = float(m.group(4).replace(" ", ""))
    x1 = float(m.group(5))
    x2 = float(m.group(6))

    def antideriv(x: float) -> float:
        return 0.5 * a * x * x + b * x

    W = antideriv(x2) - antideriv(x1)
    kf = 0.5 * mass * vi * vi + W
    ov = validate_option_set(_opts(body), expected_value=kf, abs_tol=1e-6)
    matched = ov["matching_labels"][0] if len(ov["matching_labels"]) == 1 else None
    stored = _correct(body)
    if matched is None:
        return {
            "status": "FAIL",
            "family": "work_energy",
            "computed": {"W": W, "Kf": kf, "Ki": 0.5 * mass * vi * vi},
            "equations": ["W=∫F dx", "Kf=Ki+W"],
            "inputs": {"m": mass, "vi": vi, "a": a, "b": b, "x1": x1, "x2": x2},
            "expected_option": None,
            "stored_answer": stored,
            "option_validation": ov,
            "reason": "CORRECT_RESULT_ABSENT_OR_AMBIGUOUS",
        }
    return {
        "status": "PASS" if matched == stored else "FAIL",
        "family": "work_energy",
        "computed": {"W": W, "Kf": kf, "Ki": 0.5 * mass * vi * vi},
        "equations": ["W=∫(ax+b)dx", "Kf=Ki+W"],
        "inputs": {"m": mass, "vi": vi, "a": a, "b": b, "x1": x1, "x2": x2},
        "expected_option": matched,
        "stored_answer": stored,
        "option_validation": ov,
        "single_correct_in_options": len(ov["matching_labels"]) == 1,
    }


def _parse_sci_num(text: str, start: int = 0) -> tuple[float | None, int]:
    """Parse a number possibly as a \\times 10^{e} from text[start:]."""
    m = re.match(
        r"\s*\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:\\times|×)\s*10\^\{(-?\d+)\}\$?",
        text[start:],
    )
    if m:
        return float(m.group(1)) * (10 ** int(m.group(2))), start + m.end()
    m = re.match(r"\s*\$?\s*([0-9]+(?:\.[0-9]+)?)", text[start:])
    if m:
        return float(m.group(1)), start + m.end()
    return None, start


def verify_youngs_modulus(body: dict) -> dict[str, Any]:
    text = _stem(body)
    # Find length
    Lm = re.search(r"length\s*\$?([0-9.]+)", text, re.I)
    Am = re.search(r"area\s*\$?([0-9.]+)\s*\\times\s*10\^\{?(-?\d+)\}?", text, re.I)
    Ym = re.search(
        r"(?:Young'?s modulus.*?|Y\s*=\s*)\$?([0-9.]+)\s*\\times\s*10\^\{?(-?\d+)\}?",
        text,
        re.I | re.S,
    )
    if not (Lm and Am and Ym):
        return {"status": "REQUIRES_REVIEW", "reason": "YOUNG_PATTERN_NOT_PARSED", "family": "youngs"}
    L = float(Lm.group(1))
    A = float(Am.group(1)) * 10 ** int(Am.group(2))
    Y = float(Ym.group(1)) * 10 ** int(Ym.group(2))

    # Force: either explicit force/tension, or mass*g
    Fm = re.search(
        r"(?:force|tension|tensile force)\s*(?:of\s*)?\$?([0-9.]+)\s*(?:\\times\s*10\^\{?(-?\d+)\}?)?",
        text,
        re.I,
    )
    if Fm:
        F = float(Fm.group(1))
        if Fm.group(2):
            F *= 10 ** int(Fm.group(2))
    else:
        mm = re.search(r"(?:mass|load of mass)\s*\$?([0-9.]+).*?g\s*=\s*\$?([0-9.]+)", text, re.I | re.S)
        if not mm:
            return {"status": "REQUIRES_REVIEW", "reason": "YOUNG_FORCE_NOT_PARSED", "family": "youngs"}
        F = float(mm.group(1)) * float(mm.group(2))

    # Y may also use 10^n without braces
    if Ym is None:
        Ym = re.search(
            r"(?:Young'?s modulus.*?|Y\s*=\s*)\$?([0-9.]+)\s*\\times\s*10\^\{?(-?\d+)\}?",
            text,
            re.I | re.S,
        )
        if Ym:
            Y = float(Ym.group(1)) * 10 ** int(Ym.group(2))

    dL = F * L / (A * Y)
    ov = validate_option_set(_opts(body), expected_value=dL, rel_tol=1e-2, abs_tol=1e-9)
    matched = ov["matching_labels"][0] if len(ov["matching_labels"]) == 1 else None
    stored = _correct(body)
    # Also ask for Y given delta L
    if matched is None and re.search(r"Young'?s modulus", text, re.I) and re.search(r"elongation is measured", text, re.I):
        # Inverse problem: Y = FL/(A ΔL)
        dm = re.search(r"elongation.*?\$?([0-9.]+)\s*\\text\{\s*mm\s*\}", text, re.I | re.S)
        if dm:
            dL_mm = float(dm.group(1))
            dL_m = dL_mm / 1000.0
            Ycalc = F * L / (A * dL_m)
            ov = validate_option_set(_opts(body), expected_value=Ycalc, rel_tol=1e-2, abs_tol=1e6)
            matched = ov["matching_labels"][0] if len(ov["matching_labels"]) == 1 else None
            if matched is None:
                return {
                    "status": "FAIL",
                    "family": "youngs",
                    "computed": {"Y": Ycalc},
                    "equations": ["Y = FL / (A ΔL)"],
                    "inputs": {"F": F, "L": L, "A": A, "delta_L": dL_m},
                    "expected_option": None,
                    "stored_answer": stored,
                    "option_validation": ov,
                    "reason": "CORRECT_RESULT_ABSENT_OR_AMBIGUOUS",
                }
            return {
                "status": "PASS" if matched == stored else "FAIL",
                "family": "youngs",
                "computed": {"Y": Ycalc},
                "equations": ["Y = FL / (A ΔL)"],
                "inputs": {"F": F, "L": L, "A": A, "delta_L": dL_m},
                "expected_option": matched,
                "stored_answer": stored,
                "option_validation": ov,
                "single_correct_in_options": len(ov["matching_labels"]) == 1,
            }

    if matched is None:
        return {
            "status": "FAIL",
            "family": "youngs",
            "computed": {"delta_L": dL},
            "equations": ["ΔL = FL / (A Y)"],
            "inputs": {"F": F, "L": L, "A": A, "Y": Y},
            "expected_option": None,
            "stored_answer": stored,
            "option_validation": ov,
            "reason": "CORRECT_RESULT_ABSENT_OR_AMBIGUOUS",
        }
    return {
        "status": "PASS" if matched == stored else "FAIL",
        "family": "youngs",
        "computed": {"delta_L": dL},
        "equations": ["ΔL = FL / (A Y)"],
        "inputs": {"F": F, "L": L, "A": A, "Y": Y},
        "expected_option": matched,
        "stored_answer": stored,
        "option_validation": ov,
        "single_correct_in_options": len(ov["matching_labels"]) == 1,
    }


def _thin_lens_match_shift(body: dict, *, f: float, u1: float, u2: float, inputs: dict[str, Any]) -> dict[str, Any]:
    """Compute image shift from two object positions and match options (magnitude + direction)."""
    inv_v1 = 1 / f + 1 / u1
    inv_v2 = 1 / f + 1 / u2
    if abs(inv_v1) < 1e-15 or abs(inv_v2) < 1e-15:
        return {"status": "FAIL", "reason": "IMAGE_AT_INFINITY", "family": "thin_lens"}
    v1 = 1 / inv_v1
    v2 = 1 / inv_v2
    shift = v2 - v1
    direction = "away" if shift > 0 else "towards"
    matched = None
    for o in _opts(body):
        ot = str(o.get("text") or "")
        mm = re.search(r"([0-9.]+)\s*\\?text\{\s*cm\s*\}", ot)
        if not mm:
            mm = re.search(r"([0-9.]+)\s*cm", ot, re.I)
        if not mm:
            continue
        mag = float(mm.group(1))
        dir_ok = (("away" in ot.lower()) and shift > 0) or (
            ("towards" in ot.lower() or "toward" in ot.lower()) and shift < 0
        )
        if math.isclose(mag, abs(shift), abs_tol=0.05) and dir_ok:
            matched = str(o.get("label") or "").upper()
            break
    ov = validate_option_set(_opts(body), expected_value=abs(shift), abs_tol=0.05)
    if matched is None and len(ov["matching_labels"]) == 1:
        # Only accept magnitude-only match when a single option shares the value
        # AND direction words are absent from all options (rare).
        if not any(re.search(r"away|toward", str(o.get("text") or ""), re.I) for o in _opts(body)):
            matched = ov["matching_labels"][0]
    stored = _correct(body)
    computed = {"u1": u1, "u2": u2, "v1": v1, "v2": v2, "shift_cm": shift, "direction": direction}
    if matched is None:
        return {
            "status": "FAIL",
            "family": "thin_lens",
            "computed": computed,
            "equations": ["1/v - 1/u = 1/f", "shift = v2 - v1"],
            "inputs": inputs,
            "expected_option": None,
            "stored_answer": stored,
            "option_validation": ov,
            "reason": "CORRECT_RESULT_ABSENT_FROM_OPTIONS",
        }
    return {
        "status": "PASS" if matched == stored else "FAIL",
        "family": "thin_lens",
        "computed": computed,
        "equations": ["1/v - 1/u = 1/f", "shift = v2 - v1"],
        "inputs": inputs,
        "expected_option": matched,
        "stored_answer": stored,
        "option_validation": ov,
        "single_correct_in_options": True,
    }


def verify_thin_lens(body: dict) -> dict[str, Any]:
    text = _stem(body)
    fm = re.search(r"f\s*=\s*\+?\s*([0-9.]+)", text, re.I)
    if not fm:
        return {"status": "REQUIRES_REVIEW", "reason": "THIN_LENS_FOCAL_NOT_PARSED", "family": "thin_lens"}
    f = float(fm.group(1))

    # Form A: explicit signed object distances u1, u2
    u1m = re.search(r"u_?\{?1\}?\s*=\s*(-?[0-9.]+)", text, re.I)
    u2m = re.search(r"u_?\{?2\}?\s*=\s*(-?[0-9.]+)", text, re.I)
    if u1m and u2m:
        u1 = float(u1m.group(1))
        u2 = float(u2m.group(1))
        # Convention: object on the left is negative; coerce unsigned magnitudes
        if u1 > 0:
            u1 = -u1
        if u2 > 0:
            u2 = -u2
        return _thin_lens_match_shift(body, f=f, u1=u1, u2=u2, inputs={"f": f, "u1": u1, "u2": u2})

    # Form B: two object placement distances ("in front" / "away from the lens")
    text_no_f = re.sub(
        r"f\s*=\s*\+?\s*[0-9.]+\\?text\{\s*cm\s*\}",
        " ",
        text,
        flags=re.I,
    )
    placements = list(
        re.finditer(
            r"([0-9.]+)\\?text\{\s*cm\s*\}\$?\s*(in front(?: of the lens)?|away from the lens)",
            text_no_f,
            re.I,
        )
    )
    if len(placements) >= 2:
        u1 = -float(placements[0].group(1))
        u2 = -float(placements[1].group(1))
        return _thin_lens_match_shift(
            body,
            f=f,
            u1=u1,
            u2=u2,
            inputs={"f": f, "u1": u1, "u2": u2, "form": "object_placement_distances"},
        )

    # Form C: initial image distance + object moved toward the lens
    vm = re.search(
        r"(?:real image is formed at a distance of|image is formed at a distance of|real image).*?"
        r"\$?\s*([0-9.]+)\s*\\?text\{\s*cm\s*\}",
        text,
        re.I | re.S,
    )
    if not vm:
        vm = re.search(r"distance of\s*\$?\s*([0-9.]+)\s*\\?text\{\s*cm\s*\}", text, re.I)
    move = re.search(
        r"moved\s*\$?\s*([0-9.]+)\s*\\?text\{\s*cm\s*\}\$?\s*towards",
        text,
        re.I,
    )
    if not (vm and move):
        return {"status": "REQUIRES_REVIEW", "reason": "THIN_LENS_PATTERN_NOT_PARSED", "family": "thin_lens"}
    v1 = float(vm.group(1))
    du = float(move.group(1))
    # Real image ⇒ v>0, object on left u<0: 1/v - 1/u = 1/f ⇒ 1/u = 1/v - 1/f
    inv_u1 = 1 / v1 - 1 / f
    u1 = 1 / inv_u1
    u2 = u1 + du  # toward lens: u becomes less negative ⇒ add du
    return _thin_lens_match_shift(
        body,
        f=f,
        u1=u1,
        u2=u2,
        inputs={"f": f, "v1_given": v1, "move_toward_cm": du},
    )


SLOT_VERIFIERS = {
    "physics-10": verify_momentum_inelastic,
    "physics-11": verify_work_energy,
    "physics-20": verify_youngs_modulus,
    "physics-34": verify_thin_lens,
}


def verify_slot_body(slot_id: str, body: dict) -> dict[str, Any]:
    fn = SLOT_VERIFIERS.get(slot_id)
    if not fn:
        return {"status": "REQUIRES_REVIEW", "reason": "NO_VERIFIER_FOR_SLOT"}
    result = fn(body)
    result["explanation_check"] = explanation_mentions_answer(body, computed=result.get("computed"))
    # Structural options always
    if "option_validation" not in result:
        result["option_validation"] = validate_option_set(_opts(body))
    # If PASS but explanation empty → downgrade
    if result.get("status") == "PASS" and not result["explanation_check"]["ok"]:
        result["status"] = "REQUIRES_REVIEW"
        result["reason"] = "EXPLANATION_INVALID"
    return result


# Known original failure fixtures (regression)
ORIGINAL_FAILURE_EXPECTATIONS = {
    "physics-10": {"stored": "A", "independent_option": "C", "ke_loss": 24.0, "impulse": 8.0},
    "physics-11": {"stored": "C", "independent_option": "B", "kf": 24.0},
    "physics-20": {"stored": "A", "independent_option": "B", "delta_l": 0.002},
    "physics-34": {"stored": "A", "shift_cm": 7.5, "absent_from_options": True},
}
