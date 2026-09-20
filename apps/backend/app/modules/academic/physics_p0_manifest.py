"""TALOS Physics P0 taxonomy — Gate-4 approved 74-node implementable manifest.

Authoritative source: docs/audits/TALOS_PHYSICS_P0_GATE4_FINAL_RECONCILIATION_20260902.md

Scope:
  design inventory = 79
  Gravitation provisional = 5 (EXCLUDED)
  implementable = 74 = 5 chapters + 24 topics + 45 concepts

Gravitation topic/concept codes MUST NOT appear in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NodeType = Literal["chapter", "topic", "concept"]

# Forbidden Gravitation fill codes (Gate-4 hard exclusion)
GRAVITATION_EXCLUDED_CODES: frozenset[str] = frozenset(
    {
        "newtons-law-of-gravitation",
        "universal-law-of-gravitation",
        "gravity-potential-satellites",
        "acceleration-due-to-gravity",
        "orbital-motion-satellites",
    }
)

APPROVED_P0_DESIGN_NODES = 79
GRAVITATION_EXCLUDED_NODES = 5
IMPLEMENTABLE_VERIFIED_NODES = 74


@dataclass(frozen=True)
class ConceptSpec:
    code: str
    name: str
    ncert_reference: str
    summary: str = ""


@dataclass(frozen=True)
class TopicSpec:
    code: str
    name: str
    concepts: tuple[ConceptSpec, ...]


@dataclass(frozen=True)
class ChapterSpec:
    code: str
    name: str
    """If True, chapter must be created when missing. If False, chapter must already exist."""
    create_if_missing: bool
    ncert_chapter: str
    neet_weightage_percent: float | None
    display_order: int | None  # only used when creating; None = append after max
    topics: tuple[TopicSpec, ...]


def _c(code: str, name: str, ncert: str, summary: str = "") -> ConceptSpec:
    return ConceptSpec(code=code, name=name, ncert_reference=ncert, summary=summary or name)


def _t(code: str, name: str, *concepts: ConceptSpec) -> TopicSpec:
    return TopicSpec(code=code, name=name, concepts=concepts)


# ---------------------------------------------------------------------------
# Hierarchy (Gravitation fill intentionally absent)
# ---------------------------------------------------------------------------

PHYSICS_P0_CHAPTERS: tuple[ChapterSpec, ...] = (
    ChapterSpec(
        code="units-and-measurement",
        name="Units and Measurement",
        create_if_missing=True,
        ncert_chapter="XI Ch 1",
        neet_weightage_percent=2.0,
        display_order=20,
        topics=(
            _t(
                "si-units-and-measurement",
                "SI Units and Measurement",
                _c("si-base-and-derived-units", "SI Base and Derived Units", "NCERT XI Physics Ch 1 §1.2"),
            ),
            _t(
                "significant-figures-and-errors",
                "Significant Figures and Errors",
                _c("significant-figures", "Significant Figures", "NCERT XI Physics Ch 1 §1.3"),
            ),
            _t(
                "dimensions-and-dimensional-analysis",
                "Dimensions and Dimensional Analysis",
                _c("dimensional-formulae", "Dimensional Formulae", "NCERT XI Physics Ch 1 §1.4-1.5"),
                _c(
                    "dimensional-analysis-applications",
                    "Dimensional Analysis Applications",
                    "NCERT XI Physics Ch 1 §1.6",
                ),
            ),
        ),
    ),
    ChapterSpec(
        code="kinematics",
        name="Kinematics",
        create_if_missing=False,
        ncert_chapter="XI Ch 2 + Ch 3 (topic trees)",
        neet_weightage_percent=None,
        display_order=None,
        topics=(
            _t(
                "motion-in-a-straight-line",
                "Motion in a Straight Line",
                _c(
                    "instantaneous-velocity-acceleration",
                    "Instantaneous Velocity and Acceleration",
                    "NCERT XI Physics Ch 2 §2.2-2.3",
                ),
                _c("kinematic-equations", "Kinematic Equations", "NCERT XI Physics Ch 2 §2.4"),
                _c(
                    "relative-velocity-1d",
                    "Relative Velocity in One Dimension",
                    "NCERT XI Physics Ch 2 §2.5",
                ),
            ),
            _t(
                "motion-in-a-plane",
                "Motion in a Plane",
                _c("vectors-in-plane-motion", "Vectors in Plane Motion", "NCERT XI Physics Ch 3 §3.2-3.7"),
                _c("projectile-motion", "Projectile Motion", "NCERT XI Physics Ch 3 §3.9"),
                _c("uniform-circular-motion", "Uniform Circular Motion", "NCERT XI Physics Ch 3 §3.10"),
            ),
        ),
    ),
    ChapterSpec(
        code="laws-of-motion",
        name="Laws of Motion",
        create_if_missing=False,
        ncert_chapter="XI Ch 4",
        neet_weightage_percent=None,
        display_order=None,
        topics=(
            _t(
                "newtons-laws-and-momentum",
                "Newton's Laws and Momentum",
                _c("newtons-laws", "Newton's Laws of Motion", "NCERT XI Physics Ch 4 §4.3-4.6"),
                _c("conservation-of-momentum", "Conservation of Momentum", "NCERT XI Physics Ch 4 §4.7"),
            ),
            _t(
                "friction-and-common-forces",
                "Friction and Common Forces",
                _c("friction", "Friction", "NCERT XI Physics Ch 4 §4.9"),
            ),
            _t(
                "dynamics-of-circular-motion",
                "Dynamics of Circular Motion",
                _c(
                    "dynamics-uniform-circular-motion",
                    "Dynamics of Uniform Circular Motion",
                    "NCERT XI Physics Ch 4 §4.10",
                ),
            ),
        ),
    ),
    ChapterSpec(
        code="work-energy-power",
        name="Work, Energy and Power",
        create_if_missing=False,
        ncert_chapter="XI Ch 5",
        neet_weightage_percent=None,
        display_order=None,
        topics=(
            _t(
                "work-and-kinetic-energy",
                "Work and Kinetic Energy",
                _c("work-by-a-force", "Work by a Force", "NCERT XI Physics Ch 5 §5.3"),
                _c("work-energy-theorem", "Work–Energy Theorem", "NCERT XI Physics Ch 5 §5.6"),
            ),
            _t(
                "potential-energy-and-conservation",
                "Potential Energy and Conservation",
                _c("potential-energy", "Potential Energy", "NCERT XI Physics Ch 5 §5.7"),
                _c(
                    "conservation-mechanical-energy",
                    "Conservation of Mechanical Energy",
                    "NCERT XI Physics Ch 5 §5.8",
                ),
            ),
            _t(
                "power-and-collisions",
                "Power and Collisions",
                _c("power", "Power", "NCERT XI Physics Ch 5 §5.10"),
                _c("collisions", "Collisions", "NCERT XI Physics Ch 5 §5.11"),
            ),
        ),
    ),
    ChapterSpec(
        code="systems-of-particles-rotational-motion",
        name="Systems of Particles and Rotational Motion",
        create_if_missing=True,
        ncert_chapter="XI Ch 6",
        neet_weightage_percent=4.0,
        display_order=21,
        topics=(
            _t(
                "centre-of-mass",
                "Centre of Mass",
                _c("centre-of-mass-system", "Centre of Mass of a System", "NCERT XI Physics Ch 6 §6.2"),
                _c("motion-of-centre-of-mass", "Motion of the Centre of Mass", "NCERT XI Physics Ch 6 §6.3"),
            ),
            _t(
                "torque-and-angular-momentum",
                "Torque and Angular Momentum",
                _c("torque", "Torque", "NCERT XI Physics Ch 6 §6.7"),
                _c("angular-momentum", "Angular Momentum", "NCERT XI Physics Ch 6 §6.7"),
            ),
            _t(
                "moment-of-inertia-rotational-dynamics",
                "Moment of Inertia and Rotational Dynamics",
                _c("moment-of-inertia", "Moment of Inertia", "NCERT XI Physics Ch 6 §6.9"),
                _c("rotational-kinematics", "Rotational Kinematics", "NCERT XI Physics Ch 6 §6.10"),
                _c(
                    "dynamics-of-rotational-motion",
                    "Dynamics of Rotational Motion",
                    "NCERT XI Physics Ch 6 §6.11",
                ),
            ),
        ),
    ),
    ChapterSpec(
        code="mechanical-properties-of-solids",
        name="Mechanical Properties of Solids",
        create_if_missing=True,
        ncert_chapter="XI Ch 8",
        neet_weightage_percent=2.0,
        display_order=22,
        topics=(
            _t(
                "stress-and-strain",
                "Stress and Strain",
                _c(
                    "stress-strain-definitions",
                    "Definitions of Stress and Strain",
                    "NCERT XI Physics Ch 8 §8.2",
                ),
                _c("stress-strain-curve", "Stress–Strain Curve", "NCERT XI Physics Ch 8 §8.4"),
            ),
            _t(
                "elastic-moduli",
                "Elastic Moduli",
                _c("youngs-modulus", "Young's Modulus", "NCERT XI Physics Ch 8 §8.5"),
                _c("shear-modulus", "Shear Modulus", "NCERT XI Physics Ch 8 §8.5"),
                _c("bulk-modulus", "Bulk Modulus", "NCERT XI Physics Ch 8 §8.5"),
            ),
        ),
    ),
    ChapterSpec(
        code="mechanical-properties-of-fluids",
        name="Mechanical Properties of Fluids",
        create_if_missing=True,
        ncert_chapter="XI Ch 9",
        neet_weightage_percent=2.0,
        display_order=23,
        topics=(
            _t(
                "pressure-in-fluids",
                "Pressure in Fluids",
                _c(
                    "hydrostatic-pressure-pascal",
                    "Hydrostatic Pressure and Pascal's Law",
                    "NCERT XI Physics Ch 9 §9.2",
                ),
            ),
            _t(
                "fluid-flow-and-bernoulli",
                "Fluid Flow and Bernoulli",
                _c("streamline-flow", "Streamline Flow", "NCERT XI Physics Ch 9 §9.3"),
                _c("bernoullis-principle", "Bernoulli's Principle", "NCERT XI Physics Ch 9 §9.4"),
            ),
            _t(
                "viscosity-and-surface-tension",
                "Viscosity and Surface Tension",
                _c("viscosity", "Viscosity", "NCERT XI Physics Ch 9 §9.5"),
                _c("surface-tension", "Surface Tension", "NCERT XI Physics Ch 9 §9.6"),
            ),
        ),
    ),
    ChapterSpec(
        code="thermodynamics-physics",
        name="Thermodynamics",
        create_if_missing=False,
        ncert_chapter="XI Ch 11",
        neet_weightage_percent=None,
        display_order=None,
        topics=(
            _t(
                "laws-of-thermodynamics",
                "Laws of Thermodynamics",
                _c("zeroth-and-first-law", "Zeroth and First Law", "NCERT XI Physics Ch 11 §11.3-11.5"),
                _c("second-law-and-carnot", "Second Law and Carnot Engine", "NCERT XI Physics Ch 11 §11.9-11.11"),
            ),
            _t(
                "heat-work-internal-energy",
                "Heat, Work and Internal Energy",
                _c(
                    "heat-internal-energy-work",
                    "Heat Internal Energy and Work",
                    "NCERT XI Physics Ch 11 §11.4",
                ),
            ),
            _t(
                "thermodynamic-processes",
                "Thermodynamic Processes",
                _c(
                    "thermodynamic-process-types",
                    "Thermodynamic Process Types",
                    "NCERT XI Physics Ch 11 §11.8",
                ),
            ),
        ),
    ),
    ChapterSpec(
        code="kinetic-theory",
        name="Kinetic Theory",
        create_if_missing=True,
        ncert_chapter="XI Ch 12",
        neet_weightage_percent=2.0,
        display_order=24,
        topics=(
            _t(
                "kinetic-theory-ideal-gas",
                "Kinetic Theory of an Ideal Gas",
                _c("behaviour-of-gases", "Behaviour of Gases", "NCERT XI Physics Ch 12 §12.3"),
                _c(
                    "kinetic-interpretation-temperature",
                    "Kinetic Interpretation of Temperature",
                    "NCERT XI Physics Ch 12 §12.4",
                ),
            ),
            _t(
                "equipartition-and-mean-free-path",
                "Equipartition and Mean Free Path",
                _c("law-of-equipartition", "Law of Equipartition of Energy", "NCERT XI Physics Ch 12 §12.5"),
                _c("mean-free-path", "Mean Free Path", "NCERT XI Physics Ch 12 §12.7"),
            ),
        ),
    ),
)


def iter_manifest_nodes() -> list[dict]:
    """Flat list of the 74 implementable nodes for audits/tests."""
    nodes: list[dict] = []
    for ch in PHYSICS_P0_CHAPTERS:
        if ch.create_if_missing:
            nodes.append(
                {
                    "node_type": "chapter",
                    "code": ch.code,
                    "name": ch.name,
                    "parent_code": "PHYSICS",
                    "parent_type": "subject",
                    "ncert_chapter": ch.ncert_chapter,
                    "source_status": "NCERT VERIFIED",
                    "create_if_missing": True,
                }
            )
        for topic in ch.topics:
            nodes.append(
                {
                    "node_type": "topic",
                    "code": topic.code,
                    "name": topic.name,
                    "parent_code": ch.code,
                    "parent_type": "chapter",
                    "ncert_chapter": ch.ncert_chapter,
                    "source_status": "NCERT VERIFIED",
                    "create_if_missing": True,
                }
            )
            for concept in topic.concepts:
                nodes.append(
                    {
                        "node_type": "concept",
                        "code": concept.code,
                        "name": concept.name,
                        "parent_code": topic.code,
                        "parent_type": "topic",
                        "ncert_chapter": concept.ncert_reference,
                        "source_status": "NCERT VERIFIED",
                        "create_if_missing": True,
                    }
                )
    return nodes


def validate_manifest() -> dict:
    """Static integrity checks — no DB."""
    nodes = iter_manifest_nodes()
    errors: list[str] = []

    chapters = [n for n in nodes if n["node_type"] == "chapter"]
    topics = [n for n in nodes if n["node_type"] == "topic"]
    concepts = [n for n in nodes if n["node_type"] == "concept"]

    if len(nodes) != IMPLEMENTABLE_VERIFIED_NODES:
        errors.append(f"manifest size {len(nodes)} != {IMPLEMENTABLE_VERIFIED_NODES}")
    if len(chapters) != 5:
        errors.append(f"chapters {len(chapters)} != 5")
    if len(topics) != 24:
        errors.append(f"topics {len(topics)} != 24")
    if len(concepts) != 45:
        errors.append(f"concepts {len(concepts)} != 45")

    for n in nodes:
        if n["code"] in GRAVITATION_EXCLUDED_CODES:
            errors.append(f"Gravitation excluded code present: {n['code']}")
        if "gravitation" in n["code"] and n["node_type"] != "chapter":
            # chapter code gravitation is existing stub — not in create list
            errors.append(f"unexpected gravitation code: {n['code']}")

    # unique codes within type
    for level, group in (("chapter", chapters), ("topic", topics), ("concept", concepts)):
        codes = [n["code"] for n in group]
        if len(codes) != len(set(codes)):
            errors.append(f"duplicate {level} codes")

    # Solids naming
    solids_concepts = [n for n in concepts if n["code"] == "stress-strain-definitions"]
    if not solids_concepts or solids_concepts[0]["name"] != "Definitions of Stress and Strain":
        errors.append("Solids concept display name must be 'Definitions of Stress and Strain'")

    # Kinematics contract
    kin = next(ch for ch in PHYSICS_P0_CHAPTERS if ch.code == "kinematics")
    topic_codes = {t.code for t in kin.topics}
    if topic_codes != {"motion-in-a-straight-line", "motion-in-a-plane"}:
        errors.append(f"Kinematics topics incorrect: {topic_codes}")
    if kin.create_if_missing:
        errors.append("Kinematics must be existing chapter (create_if_missing=False)")

    return {
        "ok": not errors,
        "errors": errors,
        "counts": {"chapters": len(chapters), "topics": len(topics), "concepts": len(concepts), "total": len(nodes)},
        "nodes": nodes,
    }
