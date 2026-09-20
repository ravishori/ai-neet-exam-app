"""Deterministic NCERT-aligned Physics MCQ bank for T6-D (≤ MAX_CANDIDATES).

Provenance: Gate-4 P0 concept NCERT section refs + Class XI PDF path on disk.
Questions are curated parametric templates with independently checked answers —
not LLM fabrications and not legacy-5000 content.

T6-E-FIX: no near-duplicate padding to fill 100; complete numerical contracts;
option-position shuffle; SECTION_VERIFIED evidence (never fabricated pages).
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.modules.academic.physics_p0_manifest import PHYSICS_P0_CHAPTERS
from app.modules.cms.acquisition.physics_t6d_constants import (
    BATCH_ID,
    MAX_CANDIDATES,
    NCERT_XI_CHAPTER_PDF,
    STUDY_MATERIAL_PHYSICS_XI,
    pilot_id,
    pilot_slug,
)
from app.modules.cms.services.numerical_validation import classify_and_verify
from app.modules.cms.services.publication_gates import build_section_ncert_evidence


Difficulty = Literal["easy", "medium", "hard"]
G = 10.0  # m/s² — NEET-friendly convention used consistently in numericals


@dataclass(frozen=True)
class ConceptLineage:
    chapter_code: str
    chapter_name: str
    topic_code: str
    topic_name: str
    concept_code: str
    concept_name: str
    ncert_reference: str
    ncert_chapter_num: int
    source_pdf_relpath: str


@dataclass
class PilotCandidate:
    seq: int
    pilot_qid: str
    slug: str
    concept_code: str
    topic_code: str
    chapter_code: str
    ncert_reference: str
    source_pdf_relpath: str
    stem: str
    options: list[dict[str, str]]
    correct_option: str
    explanation: str
    difficulty: Difficulty
    calculation_check: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    batch_id: str = BATCH_ID
    origin: str = "t6d-ncert-curated"
    question_type: str = "conceptual"

    def body(self) -> dict[str, Any]:
        calc = self.calculation_check or {}
        num_status, _ = classify_and_verify(calc if calc else None)
        ncert_ev = build_section_ncert_evidence(
            ncert_reference=self.ncert_reference,
            source_pdf_relpath=self.source_pdf_relpath,
        )
        return {
            "stem": self.stem,
            "options": self.options,
            "correct_option": self.correct_option,
            "explanation": self.explanation,
            "difficulty": self.difficulty,
            "bloom_level": "apply",
            "ncert_evidence": ncert_ev,
            "provenance": {
                "origin": self.origin,
                "source": self.source_pdf_relpath,
                "batch_id": self.batch_id,
                "validation_process": f"{self.batch_id.split('-')[1]}-gates",
                "verification_process": "section_reference_plus_pdf",
                "class_level": "11",
                "chapter": self.chapter_code,
                "section": self.ncert_reference,
            },
            "calculation_check": calc or None,
            "numerical_evidence": {
                "status": num_status,
                "formula": calc.get("formula"),
                "given": {k: v for k, v in calc.items() if k != "formula"},
                "result": calc.get("v")
                or calc.get("R")
                or calc.get("F")
                or calc.get("W")
                or calc.get("dK")
                or calc.get("P")
                or calc.get("p")
                or calc.get("mag")
                or calc.get("a_c")
                or calc.get("f_max")
                or calc.get("x_cm")
                or calc.get("tau")
                or calc.get("I")
                or calc.get("v_avg")
                or calc.get("v_ab"),
                "unit": calc.get("unit"),
                "correct_option": self.correct_option,
                "calculation_check": calc,
            },
        }


def _chapter_num_from_ncert(ref: str) -> int:
    m = re.search(r"Ch\s+(\d+)", ref)
    if not m:
        raise ValueError(f"Cannot parse NCERT chapter from {ref!r}")
    return int(m.group(1))


def concept_lineages() -> list[ConceptLineage]:
    rows: list[ConceptLineage] = []
    for ch in PHYSICS_P0_CHAPTERS:
        for topic in ch.topics:
            for concept in topic.concepts:
                n = _chapter_num_from_ncert(concept.ncert_reference)
                pdf = NCERT_XI_CHAPTER_PDF.get(n)
                if not pdf:
                    continue
                rows.append(
                    ConceptLineage(
                        chapter_code=ch.code,
                        chapter_name=ch.name,
                        topic_code=topic.code,
                        topic_name=topic.name,
                        concept_code=concept.code,
                        concept_name=concept.name,
                        ncert_reference=concept.ncert_reference,
                        ncert_chapter_num=n,
                        source_pdf_relpath=f"{STUDY_MATERIAL_PHYSICS_XI}/{pdf}",
                    )
                )
    return rows


def lineage_by_concept() -> dict[str, ConceptLineage]:
    return {r.concept_code: r for r in concept_lineages()}


def _opts(a: str, b: str, c: str, d: str) -> list[dict[str, str]]:
    return [{"label": "A", "text": a}, {"label": "B", "text": b}, {"label": "C", "text": c}, {"label": "D", "text": d}]


def _shuffle_options(options: list[dict[str, str]], correct: str, *, seed: int) -> tuple[list[dict[str, str]], str]:
    """Permute option texts across A–D; keep correct answer identity by text."""
    correct_text = next(o["text"] for o in options if o["label"] == correct)
    texts = [o["text"] for o in options]
    rng = random.Random(seed)
    rng.shuffle(texts)
    new_opts = [{"label": lab, "text": t} for lab, t in zip(("A", "B", "C", "D"), texts, strict=True)]
    new_correct = next(o["label"] for o in new_opts if o["text"] == correct_text)
    return new_opts, new_correct


def _cand(
    seq: int,
    lin: ConceptLineage,
    *,
    stem: str,
    options: list[dict[str, str]],
    correct: str,
    explanation: str,
    difficulty: Difficulty,
    calc: dict[str, Any] | None = None,
    shuffle: bool = True,
    batch_id: str = BATCH_ID,
    origin: str = "t6d-ncert-curated",
    question_type: str = "conceptual",
) -> PilotCandidate:
    opts, correct_label = (options, correct)
    if shuffle:
        opts, correct_label = _shuffle_options(options, correct, seed=10_000 + seq)
    qid = pilot_id(seq) if batch_id == BATCH_ID else f"t6f1-{seq:04d}"
    slug = pilot_slug(seq) if batch_id == BATCH_ID else f"{batch_id}-q{seq:04d}"
    return PilotCandidate(
        seq=seq,
        pilot_qid=qid,
        slug=slug,
        concept_code=lin.concept_code,
        topic_code=lin.topic_code,
        chapter_code=lin.chapter_code,
        ncert_reference=lin.ncert_reference,
        source_pdf_relpath=lin.source_pdf_relpath,
        stem=stem,
        options=opts,
        correct_option=correct_label,
        explanation=explanation,
        difficulty=difficulty,
        calculation_check=calc or {},
        batch_id=batch_id,
        origin=origin,
        question_type=question_type,
        tags=[
            batch_id,
            f"pilot_qid:{qid}",
            "subject:physics",
            "class:11",
            f"chapter:{lin.chapter_code}",
            f"topic:{lin.topic_code}",
            f"concept:{lin.concept_code}",
            f"ncert:{lin.ncert_reference}",
            f"source_pdf:{Path(lin.source_pdf_relpath).name}",
            f"validation:{batch_id.split('-')[1] if '-' in batch_id else 'pilot'}-gates",
            "ncert_level:SECTION_VERIFIED",
            f"question_type:{question_type}",
        ],
    )


def _round_nice(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def build_bank() -> list[PilotCandidate]:
    """Build up to MAX_CANDIDATES curated candidates — never pad with near-duplicates."""
    L = lineage_by_concept()
    out: list[PilotCandidate] = []
    seq = 0

    def add(c: PilotCandidate) -> None:
        nonlocal seq
        if len(out) >= MAX_CANDIDATES:
            return
        out.append(c)
        seq = c.seq

    def next_seq() -> int:
        return len(out) + 1

    # --- Kinematics / Motion in a Straight Line (heavy for TOPIC isolation) ---
    lin = L["kinematic-equations"]
    for i, (u, a, t) in enumerate([(10, 2, 5), (0, 4, 3), (20, -2, 4), (5, 5, 2), (15, 1, 10), (8, 3, 4), (12, -4, 2), (0, 10, 2)]):
        v = u + a * t
        s = u * t + 0.5 * a * t * t
        wrong = [v + 2, v - 3, -v if v else 1]
        add(
            _cand(
                next_seq(),
                lin,
                stem=(
                    f"A particle starts with velocity {u} m/s and constant acceleration {a} m/s². "
                    f"Its velocity after {t} s is (take kinematic equation v = u + at; NCERT XI Ch 2):"
                ),
                options=_opts(f"{_round_nice(wrong[0])} m/s", f"{_round_nice(v)} m/s", f"{_round_nice(wrong[1])} m/s", f"{_round_nice(wrong[2])} m/s"),
                correct="B",
                explanation=f"v = u + at = {u} + ({a})({t}) = {_round_nice(v)} m/s. Displacement in same interval would be s = {_round_nice(s)} m.",
                difficulty="easy",
                calc={"formula": "v=u+at", "u": u, "a": a, "t": t, "v": v, "s": s},
            )
        )

    lin = L["instantaneous-velocity-acceleration"]
    for i, (dx, dt) in enumerate([(12, 3), (20, 4), (15, 5), (8, 2)]):
        v = dx / dt
        add(
            _cand(
                next_seq(),
                lin,
                stem=(
                    f"Along a straight line, a particle’s position changes by {dx} m in {dt} s at nearly constant rate. "
                    f"The average velocity over this interval is (NCERT XI Ch 2 §2.2–2.3):"
                ),
                options=_opts(f"{_round_nice(v)} m/s", f"{_round_nice(v * 2)} m/s", f"{_round_nice(dx * dt)} m/s", f"{_round_nice(dt / dx)} m/s"),
                correct="A",
                explanation=f"Average velocity = Δx/Δt = {dx}/{dt} = {_round_nice(v)} m/s.",
                difficulty="easy",
                calc={"formula": "v_avg", "dx": dx, "dt": dt, "v_avg": v, "unit": "m/s"},
            )
        )

    lin = L["relative-velocity-1d"]
    for i, (va, vb) in enumerate([(20, 5), (15, 10), (30, 10), (12, 4)]):
        vrel = va - vb
        add(
            _cand(
                next_seq(),
                lin,
                stem=(
                    f"Car A moves at {va} m/s and car B at {vb} m/s in the same direction on a straight road. "
                    f"Velocity of A relative to B is (NCERT XI Ch 2 §2.5):"
                ),
                options=_opts(f"{_round_nice(va + vb)} m/s", f"{_round_nice(vrel)} m/s", f"{_round_nice(vb - va)} m/s", f"{_round_nice(va)} m/s"),
                correct="B",
                explanation=f"v_AB = v_A − v_B = {va} − {vb} = {_round_nice(vrel)} m/s (same direction).",
                difficulty="easy",
                calc={"formula": "v_rel", "va": va, "vb": vb, "v_ab": vrel, "unit": "m/s"},
            )
        )

    # --- Motion in a Plane ---
    lin = L["projectile-motion"]
    for i, (u, deg) in enumerate([(20, 30), (10, 45), (40, 30), (20, 45), (30, 60), (50, 45), (15, 30), (25, 45)]):
        th = math.radians(deg)
        R = (u * u * math.sin(2 * th)) / G
        # Prefer exact known cases
        if deg == 45:
            R = (u * u) / G
        elif deg == 30:
            R = (u * u * math.sqrt(3) / 2) / G  # sin(60)=√3/2
            R = (u * u * math.sin(math.radians(60))) / G
        R_round = round(R, 2)
        distractors = [round(R * 0.5, 2), round(R * 2, 2), round(u * u / G, 2)]
        add(
            _cand(
                next_seq(),
                lin,
                stem=(
                    f"A projectile is launched with speed {u} m/s at {deg}° to the horizontal. "
                    f"Taking g = {G:g} m/s², its horizontal range is approximately (NCERT XI Ch 3 §3.9):"
                ),
                options=_opts(
                    f"{_round_nice(distractors[0])} m",
                    f"{_round_nice(distractors[1])} m",
                    f"{_round_nice(R_round)} m",
                    f"{_round_nice(distractors[2])} m" if abs(distractors[2] - R_round) > 0.05 else f"{_round_nice(R_round + 5)} m",
                ),
                correct="C",
                explanation=f"R = u² sin(2θ)/g = ({u})² sin({2*deg}°)/{G:g} ≈ {_round_nice(R_round)} m.",
                difficulty="medium",
                calc={"formula": "projectile_R", "u": u, "theta_deg": deg, "g": G, "R": R_round, "unit": "m"},
            )
        )

    lin = L["vectors-in-plane-motion"]
    for i, (ax, ay) in enumerate([(3, 4), (5, 12), (8, 6), (9, 12)]):
        mag = math.hypot(ax, ay)
        add(
            _cand(
                next_seq(),
                lin,
                stem=(
                    f"A displacement vector in a plane has components Δx = {ax} m and Δy = {ay} m. "
                    f"Its magnitude is (NCERT XI Ch 3 §3.2–3.7):"
                ),
                options=_opts(f"{_round_nice(ax + ay)} m", f"{_round_nice(mag)} m", f"{_round_nice(ax * ay)} m", f"{_round_nice(abs(ax - ay))} m"),
                correct="B",
                explanation=f"|r| = √(Δx² + Δy²) = √({ax}² + {ay}²) = {_round_nice(mag)} m.",
                difficulty="easy",
                calc={"formula": "vector_mag", "ax": ax, "ay": ay, "mag": mag, "unit": "m"},
            )
        )

    lin = L["uniform-circular-motion"]
    for i, (v, r) in enumerate([(10, 5), (20, 10), (6, 2), (15, 5)]):
        a = v * v / r
        add(
            _cand(
                next_seq(),
                lin,
                stem=(
                    f"A particle moves in uniform circular motion with speed {v} m/s on a circle of radius {r} m. "
                    f"The centripetal acceleration magnitude is (NCERT XI Ch 3 §3.10):"
                ),
                options=_opts(f"{_round_nice(v / r)} m/s²", f"{_round_nice(a)} m/s²", f"{_round_nice(v * r)} m/s²", f"{_round_nice(2 * a)} m/s²"),
                correct="B",
                explanation=f"a_c = v²/r = {v}²/{r} = {_round_nice(a)} m/s² toward the centre.",
                difficulty="easy",
                calc={"formula": "centripetal", "v": v, "r": r, "a_c": a, "unit": "m/s^2"},
            )
        )

    # --- Units / significant figures / dimensions ---
    lin = L["si-base-and-derived-units"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Which of the following is an SI base unit (NCERT XI Ch 1 §1.2)?",
            options=_opts("newton", "joule", "kelvin", "pascal"),
            correct="C",
            explanation="Kelvin is an SI base unit. Newton, joule and pascal are derived.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="The SI unit of force (newton) is a derived unit equal to (NCERT XI Ch 1 §1.2):",
            options=_opts("kg m/s", "kg m/s²", "kg m²/s²", "kg/s²"),
            correct="B",
            explanation="1 N = 1 kg·m/s² from F = ma.",
            difficulty="easy",
        )
    )

    lin = L["significant-figures"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="The number of significant figures in 0.00250 is (NCERT XI Ch 1 §1.3):",
            options=_opts("2", "3", "4", "5"),
            correct="B",
            explanation="Leading zeros are not significant; 250 with trailing zero after decimal → 3 significant figures.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="When 2.5 and 1.25 are added, the result reported to correct significant figures is (NCERT XI Ch 1 §1.3):",
            options=_opts("3.75", "3.8", "3.750", "4"),
            correct="B",
            explanation="For addition, limit is least number of decimal places (one) → 3.8.",
            difficulty="medium",
        )
    )

    lin = L["dimensional-formulae"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Dimensional formula of kinetic energy is (NCERT XI Ch 1 §1.4–1.5):",
            options=_opts("[M L T⁻¹]", "[M L² T⁻²]", "[M L² T⁻¹]", "[M L T⁻²]"),
            correct="B",
            explanation="KE = ½mv² → [M][L T⁻¹]² = [M L² T⁻²].",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="Dimensional formula of pressure is (NCERT XI Ch 1 §1.4–1.5):",
            options=_opts("[M L⁻¹ T⁻²]", "[M L T⁻²]", "[M L² T⁻²]", "[M L⁻² T⁻²]"),
            correct="A",
            explanation="Pressure = force/area → [M L T⁻²]/[L²] = [M L⁻¹ T⁻²].",
            difficulty="easy",
        )
    )

    lin = L["dimensional-analysis-applications"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="If force F depends on mass m, acceleration a as F = k m^x a^y, dimensional consistency requires (NCERT XI Ch 1 §1.6):",
            options=_opts("x=1, y=1", "x=2, y=1", "x=1, y=2", "x=0, y=1"),
            correct="A",
            explanation="[F]=[M L T⁻²]; [m^x a^y]=[M]^x [L T⁻²]^y ⇒ x=1, y=1.",
            difficulty="medium",
        )
    )

    # --- Laws of motion ---
    lin = L["newtons-laws"]
    for m, a in [(2, 3), (5, 2), (4, 4)]:
        F = m * a
        add(
            _cand(
                next_seq(),
                lin,
                stem=f"A net force acts on mass {m} kg producing acceleration {a} m/s². The force magnitude is (NCERT XI Ch 4):",
                options=_opts(f"{_round_nice(F)} N", f"{_round_nice(m + a)} N", f"{_round_nice(m / a)} N", f"{_round_nice(2 * F)} N"),
                correct="A",
                explanation=f"F = ma = {m}×{a} = {_round_nice(F)} N (Newton’s second law).",
                difficulty="easy",
                calc={"formula": "F=ma", "m": m, "a": a, "F": F, "unit": "N"},
            )
        )

    lin = L["conservation-of-momentum"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="In the absence of external force, the total linear momentum of a system (NCERT XI Ch 4 §4.7):",
            options=_opts("increases", "decreases", "remains constant", "becomes zero"),
            correct="C",
            explanation="Conservation of linear momentum: if F_ext = 0, total momentum is constant.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="Two masses 2 kg and 3 kg move toward each other at 3 m/s and 2 m/s. Total momentum before collision (same line) is:",
            options=_opts("0 kg m/s", "12 kg m/s", "1 kg m/s", "5 kg m/s"),
            correct="A",
            explanation="p = 2×3 − 3×2 = 6 − 6 = 0 (opposite directions).",
            difficulty="medium",
            calc={"formula": "p_sum", "m1": 2, "v1": 3, "m2": 3, "v2": -2, "p": 0, "unit": "kg m/s"},
        )
    )

    lin = L["friction"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Kinetic friction on a sliding block (NCERT XI Ch 4 §4.9) is typically:",
            options=_opts("independent of normal force", "μ_k N, opposing relative motion", "always greater than static friction", "directed along the velocity"),
            correct="B",
            explanation="f_k = μ_k N, opposite to relative sliding velocity.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="For μ_s = 0.4 and N = 50 N, maximum static friction is approximately:",
            options=_opts("10 N", "20 N", "50 N", "125 N"),
            correct="B",
            explanation="f_max = μ_s N = 0.4 × 50 = 20 N.",
            difficulty="easy",
            calc={"formula": "f_max", "mu": 0.4, "N": 50, "f_max": 20, "unit": "N"},
        )
    )

    lin = L["dynamics-uniform-circular-motion"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="For uniform circular motion, the net force toward the centre equals (NCERT XI Ch 4 §4.10):",
            options=_opts("mv", "mv/r", "mv²/r", "mω"),
            correct="C",
            explanation="Centripetal force F_c = mv²/r.",
            difficulty="easy",
        )
    )

    # --- Work energy power ---
    lin = L["work-by-a-force"]
    for F, s in [(10, 4), (5, 6), (8, 3)]:
        W = F * s
        add(
            _cand(
                next_seq(),
                lin,
                stem=f"A constant force {F} N displaces a body by {s} m along its line of action. Work done is (NCERT XI Ch 5 §5.3):",
                options=_opts(f"{_round_nice(W)} J", f"{_round_nice(F + s)} J", f"{_round_nice(F / s)} J", f"{_round_nice(2 * W)} J"),
                correct="A",
                explanation=f"W = F·s = {F}×{s} = {_round_nice(W)} J when force and displacement are parallel.",
                difficulty="easy",
                calc={"formula": "W=Fs", "F": F, "s": s, "W": W, "unit": "J"},
            )
        )

    lin = L["work-energy-theorem"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="According to the work–energy theorem (NCERT XI Ch 5 §5.6), net work done on a particle equals:",
            options=_opts("change in potential energy", "change in kinetic energy", "change in momentum", "power"),
            correct="B",
            explanation="W_net = ΔK.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="A 2 kg particle speeds from 3 m/s to 5 m/s. Net work done is:",
            options=_opts("8 J", "16 J", "4 J", "32 J"),
            correct="B",
            explanation="ΔK = ½m(v²−u²) = ½×2×(25−9) = 16 J.",
            difficulty="medium",
            calc={"formula": "dK", "m": 2, "u": 3, "v": 5, "dK": 16, "unit": "J"},
        )
    )

    lin = L["potential-energy"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Gravitational potential energy near Earth for mass m raised by height h (NCERT XI Ch 5 §5.7) is:",
            options=_opts("mg/h", "mgh", "½mgh", "m/g h"),
            correct="B",
            explanation="U = mgh (taking U=0 at the reference level).",
            difficulty="easy",
        )
    )

    lin = L["conservation-mechanical-energy"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="For a conservative force field with no non-conservative work (NCERT XI Ch 5 §5.8):",
            options=_opts("kinetic energy alone is constant", "potential energy alone is constant", "mechanical energy K+U is constant", "momentum is always zero"),
            correct="C",
            explanation="Mechanical energy is conserved when only conservative forces do work.",
            difficulty="easy",
        )
    )

    lin = L["power"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Average power when 100 J of work is done in 4 s is (NCERT XI Ch 5 §5.10):",
            options=_opts("25 W", "400 W", "50 W", "4 W"),
            correct="A",
            explanation="P_avg = W/t = 100/4 = 25 W.",
            difficulty="easy",
            calc={"formula": "P=W/t", "W": 100, "t": 4, "P": 25, "unit": "W"},
        )
    )

    lin = L["collisions"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="In a perfectly inelastic collision of two free particles (NCERT XI Ch 5 §5.11):",
            options=_opts("kinetic energy is conserved", "they stick and move with common velocity", "momentum is not conserved", "relative speed after equals relative speed before"),
            correct="B",
            explanation="Perfectly inelastic: bodies coalesce; momentum conserved, KE not.",
            difficulty="easy",
        )
    )

    # --- Rotational ---
    lin = L["centre-of-mass-system"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="For two equal masses at x=0 and x=2 m, the centre of mass is at (NCERT XI Ch 6 §6.2):",
            options=_opts("0 m", "1 m", "2 m", "0.5 m"),
            correct="B",
            explanation="x_cm = (m·0 + m·2)/(2m) = 1 m.",
            difficulty="easy",
            calc={"formula": "x_cm", "x1": 0, "x2": 2, "x_cm": 1, "unit": "m"},
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="The centre of mass of a uniform rod of length L lies (NCERT XI Ch 6 §6.2):",
            options=_opts("at one end", "at L/4 from an end", "at its geometric centre", "outside the rod"),
            correct="C",
            explanation="For a uniform rod, CM is at the midpoint.",
            difficulty="easy",
        )
    )

    lin = L["motion-of-centre-of-mass"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Acceleration of the centre of mass of a system equals (NCERT XI Ch 6 §6.3):",
            options=_opts("zero always", "F_ext / M", "F_int / M", "sum of all accelerations"),
            correct="B",
            explanation="M a_cm = F_ext.",
            difficulty="easy",
        )
    )

    lin = L["torque"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Torque of force F about a point is (NCERT XI Ch 6 §6.7):",
            options=_opts("F · r", "r × F", "F / r", "r · F × v"),
            correct="B",
            explanation="τ = r × F.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="A force 5 N acts perpendicular at 2 m from a pivot. Torque magnitude is:",
            options=_opts("2.5 N m", "10 N m", "7 N m", "0.4 N m"),
            correct="B",
            explanation="τ = rF sin90° = 2×5 = 10 N·m.",
            difficulty="easy",
            calc={"formula": "tau=rF", "r": 2, "F": 5, "tau": 10, "unit": "N m"},
        )
    )

    lin = L["angular-momentum"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Angular momentum of a particle about origin is (NCERT XI Ch 6 §6.7):",
            options=_opts("p × r", "r × p", "r · p", "p / r"),
            correct="B",
            explanation="L = r × p.",
            difficulty="easy",
        )
    )

    lin = L["moment-of-inertia"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Moment of inertia of a point mass m at distance r from axis is (NCERT XI Ch 6 §6.9):",
            options=_opts("mr", "m/r", "mr²", "m²r"),
            correct="C",
            explanation="I = mr² for a point mass.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="For m = 2 kg at r = 3 m, I about the axis is:",
            options=_opts("6 kg m²", "18 kg m²", "9 kg m²", "12 kg m²"),
            correct="B",
            explanation="I = mr² = 2×9 = 18 kg·m².",
            difficulty="easy",
            calc={"formula": "I=mr^2", "m": 2, "r": 3, "I": 18, "unit": "kg m^2"},
        )
    )

    lin = L["rotational-kinematics"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Analog of v = u + at in pure rotation (constant α) is (NCERT XI Ch 6 §6.10):",
            options=_opts("ω = ω0 + αt", "θ = ωt", "τ = Iα only", "L = Iω only"),
            correct="A",
            explanation="ω = ω₀ + αt for constant angular acceleration.",
            difficulty="easy",
        )
    )

    lin = L["dynamics-of-rotational-motion"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Newton’s second law for rotation about a fixed axis is (NCERT XI Ch 6 §6.11):",
            options=_opts("F = ma", "τ = Iα", "p = mv", "W = τθ always"),
            correct="B",
            explanation="τ_net = Iα.",
            difficulty="easy",
        )
    )

    # --- Solids ---
    lin = L["stress-strain-definitions"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Longitudinal stress is defined as (NCERT XI Ch 8 §8.2):",
            options=_opts("force × area", "force / area", "extension / length", "force × length"),
            correct="B",
            explanation="Stress = restoring force per unit area.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="Longitudinal strain is (NCERT XI Ch 8 §8.2):",
            options=_opts("ΔL / L", "L / ΔL", "F / A", "Y ΔL"),
            correct="A",
            explanation="Strain = change in length / original length.",
            difficulty="easy",
        )
    )

    lin = L["stress-strain-curve"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="On a typical stress–strain curve for a metal, the elastic limit is near (NCERT XI Ch 8 §8.4):",
            options=_opts("the origin only", "the end of the approximately linear region", "fracture point only", "zero stress always"),
            correct="B",
            explanation="Beyond the elastic limit, permanent set appears; linear Hooke region ends near there.",
            difficulty="medium",
        )
    )

    lin = L["youngs-modulus"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Young’s modulus Y equals (NCERT XI Ch 8 §8.5):",
            options=_opts("stress × strain", "strain / stress", "longitudinal stress / longitudinal strain", "bulk stress / strain"),
            correct="C",
            explanation="Y = (F/A)/(ΔL/L).",
            difficulty="easy",
        )
    )

    lin = L["shear-modulus"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Shear modulus relates (NCERT XI Ch 8 §8.5):",
            options=_opts("volume stress and volume strain", "shear stress and shear strain", "only tensile stress", "density and strain"),
            correct="B",
            explanation="η = shear stress / shear strain.",
            difficulty="easy",
        )
    )

    lin = L["bulk-modulus"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Bulk modulus B is (NCERT XI Ch 8 §8.5):",
            options=_opts("-ΔP / (ΔV/V)", "ΔV/V", "Y/3 always", "shear stress / strain"),
            correct="A",
            explanation="B = −ΔP/(ΔV/V) (negative sign: compression decreases volume).",
            difficulty="easy",
        )
    )

    # --- Fluids ---
    lin = L["hydrostatic-pressure-pascal"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Pressure at depth h in an incompressible liquid of density ρ is (gauge) (NCERT XI Ch 9 §9.2):",
            options=_opts("ρgh", "ρg/h", "ρ/h", "gh/ρ"),
            correct="A",
            explanation="P = ρgh (gauge).",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="Pascal’s law states that a pressure change in an enclosed incompressible fluid is transmitted:",
            options=_opts("only downward", "undiminished in all directions", "only to the walls", "inversely with depth"),
            correct="B",
            explanation="Pascal’s law: pressure is transmitted equally throughout the fluid.",
            difficulty="easy",
        )
    )

    lin = L["streamline-flow"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="In steady streamline flow, streamlines (NCERT XI Ch 9 §9.3):",
            options=_opts("intersect freely", "do not cross", "must be straight", "imply zero velocity"),
            correct="B",
            explanation="Streamlines do not cross; each fluid particle has unique velocity direction at a point.",
            difficulty="easy",
        )
    )

    lin = L["bernoullis-principle"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Bernoulli’s equation for steady, incompressible, non-viscous flow along a streamline (NCERT XI Ch 9 §9.4) conserves:",
            options=_opts("P + ρgh + ½ρv²", "P only", "½ρv² only", "ρgh only"),
            correct="A",
            explanation="P + ρgh + ½ρv² = constant along a streamline (ideal conditions).",
            difficulty="medium",
        )
    )

    lin = L["viscosity"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Viscous force between layers of a fluid is (NCERT XI Ch 9 §9.5) proportional to:",
            options=_opts("velocity gradient", "velocity squared only", "density only", "temperature only"),
            correct="A",
            explanation="Newton’s law of viscosity: F/A = η (dv/dz).",
            difficulty="easy",
        )
    )

    lin = L["surface-tension"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Surface tension has SI unit (NCERT XI Ch 9 §9.6):",
            options=_opts("N/m", "N/m²", "J", "Pa s"),
            correct="A",
            explanation="Surface tension = force per unit length (N/m), also energy per unit area.",
            difficulty="easy",
        )
    )

    # --- Thermodynamics ---
    lin = L["zeroth-and-first-law"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="The first law of thermodynamics is essentially (NCERT XI Ch 11 §11.3–11.5):",
            options=_opts("conservation of energy for a thermodynamic system", "entropy always decreases", "heat flows from cold to hot", "PV = constant always"),
            correct="A",
            explanation="ΔQ = ΔU + ΔW (sign convention as in NCERT discussion of first law).",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="Zeroth law of thermodynamics introduces the concept of:",
            options=_opts("entropy", "temperature", "internal energy only", "enthalpy only"),
            correct="B",
            explanation="Thermal equilibrium → temperature as an empirical property.",
            difficulty="easy",
        )
    )

    lin = L["second-law-and-carnot"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="A Carnot engine operating between T_h and T_c (kelvin) has efficiency (NCERT XI Ch 11 §11.9–11.11):",
            options=_opts("1 − T_c/T_h", "1 − T_h/T_c", "T_h/T_c", "T_c/T_h"),
            correct="A",
            explanation="η = 1 − T_c/T_h for Carnot engine.",
            difficulty="hard",
        )
    )

    lin = L["heat-internal-energy-work"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Internal energy of an ideal gas depends primarily on (NCERT XI Ch 11 §11.4):",
            options=_opts("volume only", "pressure only", "temperature", "shape of container only"),
            correct="C",
            explanation="For an ideal gas, U is a function of temperature.",
            difficulty="easy",
        )
    )

    lin = L["thermodynamic-process-types"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="In an isothermal process for an ideal gas (NCERT XI Ch 11 §11.8):",
            options=_opts("ΔT = 0 and ΔU = 0", "ΔQ = 0", "ΔW = 0 always", "pressure is constant"),
            correct="A",
            explanation="Isothermal ⇒ ΔT = 0 ⇒ ΔU = 0 for ideal gas.",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="An adiabatic process for an ideal gas is characterized by:",
            options=_opts("ΔQ = 0", "ΔT = 0", "ΔV = 0", "ΔP = 0"),
            correct="A",
            explanation="Adiabatic: no heat exchange (ΔQ = 0).",
            difficulty="easy",
        )
    )

    # --- Kinetic theory ---
    lin = L["behaviour-of-gases"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Ideal gas equation is (NCERT XI Ch 12 §12.3):",
            options=_opts("PV = μRT", "P = ρgh", "F = ma", "V = IR"),
            correct="A",
            explanation="PV = μRT (μ = amount of gas in moles).",
            difficulty="easy",
        )
    )
    add(
        _cand(
            next_seq(),
            lin,
            stem="At constant temperature, Boyle’s law states:",
            options=_opts("P ∝ V", "P ∝ 1/V", "V ∝ T", "P ∝ T"),
            correct="B",
            explanation="Boyle: PV = constant at fixed T and μ.",
            difficulty="easy",
        )
    )

    lin = L["kinetic-interpretation-temperature"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Absolute temperature of an ideal gas is proportional to (NCERT XI Ch 12 §12.4):",
            options=_opts("average kinetic energy per molecule", "volume only", "pressure only", "number of molecules only"),
            correct="A",
            explanation="(1/2)m⟨v²⟩ = (3/2)k_B T.",
            difficulty="easy",
        )
    )

    lin = L["law-of-equipartition"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="By equipartition, each quadratic energy term contributes (NCERT XI Ch 12 §12.5):",
            options=_opts("(1/2)k_B T per molecule", "k_B T per molecule", "2k_B T", "zero"),
            correct="A",
            explanation="Each degree of freedom: (1/2)k_B T average energy.",
            difficulty="easy",
        )
    )

    lin = L["mean-free-path"]
    add(
        _cand(
            next_seq(),
            lin,
            stem="Mean free path of gas molecules (NCERT XI Ch 12 §12.7) decreases when:",
            options=_opts("number density decreases", "molecular diameter decreases", "number density increases", "temperature definition changes units only"),
            correct="C",
            explanation="λ ≈ 1/(√2 π d² n) — higher n ⇒ shorter mean free path.",
            difficulty="hard",
        )
    )

    # Quality > quantity: do NOT pad with near-duplicate kinematics (T6-E-FIX).
    out = out[:MAX_CANDIDATES]
    # Re-number seq/slug/pilot_qid/tags for contiguous 001..N (preserve shuffled options)
    relabeled: list[PilotCandidate] = []
    for i, c in enumerate(out, start=1):
        lin = L[c.concept_code]
        relabeled.append(
            _cand(
                i,
                lin,
                stem=c.stem,
                options=c.options,
                correct=c.correct_option,
                explanation=c.explanation,
                difficulty=c.difficulty,
                calc=c.calculation_check,
                shuffle=False,
            )
        )
    return relabeled
