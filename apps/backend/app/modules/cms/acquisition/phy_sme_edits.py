"""WAVE-P0-11B — final SME-approved PHY-01–PHY-10 payloads (exact text)."""

from __future__ import annotations

import uuid

# Hierarchy UUIDs from PHYSICS_ACADEMIC_HIERARCHY_GAPS.md / live trinetra_db
CONCEPT_PARALLEL_PLATE = uuid.UUID("29560b80-2c9d-4093-98cf-9ee7533fba3a")
CONCEPT_SPHERICAL_MIRROR = uuid.UUID("a44cd8ef-9881-4812-9848-bac03dde7e61")
CONCEPT_COULOMB = uuid.UUID("38563952-1621-4afa-b82d-4804adbfb18b")
CONCEPT_PRINCIPAL_FOCUS = uuid.UUID("9f91ab55-6fb7-41b9-beb3-60400693fe20")
CONCEPT_REFRACTIVE_INDEX = uuid.UUID("537dff93-6e0a-4a5c-9a58-2ebac1b4eea8")
CONCEPT_LENS_POWER = uuid.UUID("77aa17aa-8f6b-4604-bad0-691b1172e5e8")

SME_REF = "docs/product/PHY_01_10_FINAL_SME_PROPOSALS.md + WAVE-P0-11B"


def _q(
    *,
    stem: str,
    a: str,
    b: str,
    c: str,
    d: str,
    answer: str,
    explanation: str,
    difficulty: str,
) -> dict:
    return {
        "stem": stem,
        "options": [
            {"label": "A", "text": a},
            {"label": "B", "text": b},
            {"label": "C", "text": c},
            {"label": "D", "text": d},
        ],
        "correct_option": answer,
        "explanation": explanation,
        "difficulty": difficulty,
    }


# Each entry: label, id, title, concept_id | None (None = leave mapping), body
PHY_SME_EDITS: list[dict] = [
    {
        "label": "PHY-01",
        "id": uuid.UUID("8721e193-2d6e-433a-81d9-ceb2b31aef01"),
        "title": "Parallel plate capacitance dependence",
        "concept_id": CONCEPT_PARALLEL_PLATE,  # unchanged but explicit
        "update_concept": False,
        "body": _q(
            stem="Capacitance of a vacuum parallel-plate capacitor is proportional to:",
            a="Separation between plates only",
            b="Area of plates / separation between plates",
            c="Square of the plate area",
            d="Product of plate area and separation",
            answer="B",
            explanation=(
                "For a vacuum parallel-plate capacitor, C = ε₀A/d, so C ∝ A/d. "
                "Options that depend only on separation, on A², or on A·d do not match this dependence."
            ),
            difficulty="easy",
        ),
    },
    {
        "label": "PHY-02",
        "id": uuid.UUID("f51bd10d-70c1-4bc1-98f3-490f723ec549"),
        "title": "Concave mirror principal focus",
        "concept_id": CONCEPT_PRINCIPAL_FOCUS,
        "update_concept": True,
        "body": _q(
            stem="Rays parallel to the principal axis of a concave mirror, after reflection, pass through:",
            a="Centre of curvature",
            b="Pole",
            c="Principal focus",
            d="Midpoint between pole and centre of curvature only if the aperture is large",
            answer="C",
            explanation=(
                "By definition, paraxial rays parallel to the principal axis converge, after reflection "
                "from a concave mirror, at the principal focus. The centre of curvature applies to rays "
                "directed toward C; the pole lies on the mirror surface."
            ),
            difficulty="easy",
        ),
    },
    {
        "label": "PHY-03",
        "id": uuid.UUID("fbfa14ed-b9cc-4016-8c4b-d08f997ecdd6"),
        "title": "Dielectric after battery disconnection",
        "concept_id": CONCEPT_PARALLEL_PLATE,
        "update_concept": False,
        "body": _q(
            stem=(
                "A parallel-plate capacitor is charged by a battery and then disconnected. "
                "A dielectric of dielectric constant K > 1 is then inserted to completely fill the gap. "
                "Which statement is correct?"
            ),
            a="Capacitance decreases and charge on the plates increases",
            b="Capacitance increases, charge on the plates remains constant, and potential difference decreases",
            c="Capacitance and potential difference both remain constant",
            d="Capacitance becomes infinite and energy stored becomes zero",
            answer="B",
            explanation=(
                "After disconnection, charge Q on the plates is fixed. Inserting the dielectric increases "
                "capacitance to C′ = KC. From V = Q/C, the potential difference decreases. Capacitance does "
                "not become infinite for finite K; charge does not increase after disconnection."
            ),
            difficulty="medium",
        ),
    },
    {
        "label": "PHY-04",
        "id": uuid.UUID("4d0ab71e-a997-4ac1-ad17-ba24f030a19c"),
        "title": "Spherical mirror formula",
        "concept_id": CONCEPT_SPHERICAL_MIRROR,
        "update_concept": False,
        "body": _q(
            stem="Under the Cartesian sign convention used for spherical mirrors, the mirror formula is:",
            a="1/v − 1/u = 1/f",
            b="1/v + 1/u = 1/f",
            c="1/f = 1/u − 1/v",
            d="f = (u + v)/2",
            answer="B",
            explanation=(
                "The standard spherical-mirror relation is 1/v + 1/u = 1/f (Cartesian signs). "
                "Option A is a difference form that is not the usual mirror formula; C rearranges incorrectly; "
                "D is not the mirror formula."
            ),
            difficulty="easy",
        ),
    },
    {
        "label": "PHY-05",
        "id": uuid.UUID("f7b0f62f-1fcb-4a69-9052-455e00f7cb84"),
        "title": "Capacitor energy at constant charge",
        "concept_id": CONCEPT_PARALLEL_PLATE,
        "update_concept": False,
        "body": _q(
            stem=(
                "A capacitor of capacitance C carries charge Q. If the capacitance is doubled while the "
                "charge remains constant, the energy stored becomes:"
            ),
            a="Twice the original energy",
            b="Half the original energy",
            c="Four times the original energy",
            d="Unchanged",
            answer="B",
            explanation=(
                "With charge fixed, U = Q²/(2C). Doubling C halves U. "
                "(If voltage were fixed instead, U = ½CV² would double — that is a different constraint.)"
            ),
            difficulty="medium",
        ),
    },
    {
        "label": "PHY-06",
        "id": uuid.UUID("9a0ae17f-38f3-4141-8dad-389ae265195c"),
        "title": "Focal length and radius of curvature",
        "concept_id": CONCEPT_SPHERICAL_MIRROR,
        "update_concept": False,
        "body": _q(
            stem=(
                "For a spherical mirror of small aperture, the focal length f is related to the radius "
                "of curvature R approximately by:"
            ),
            a="f = R",
            b="f = R/2",
            c="f = 2R",
            d="f = √R",
            answer="B",
            explanation="Under the paraxial (small-aperture) approximation, f = R/2 for a spherical mirror.",
            difficulty="easy",
        ),
    },
    {
        "label": "PHY-07",
        "id": uuid.UUID("4b928b5f-da43-4361-89db-312b6c6950a4"),
        "title": "Net force at midpoint of two like charges",
        "concept_id": CONCEPT_COULOMB,
        "update_concept": False,
        "body": _q(
            stem=(
                "Two equal positive point charges are fixed on the x-axis at x = −a and x = +a (a > 0). "
                "A third positive point charge is placed at the origin (x = 0). "
                "The net electrostatic force on the charge at the origin is:"
            ),
            a="Along the positive x-direction",
            b="Along the negative x-direction",
            c="Zero",
            d="Perpendicular to the x-axis",
            answer="C",
            explanation=(
                "By Coulomb's law, the force from the charge at +a on the positive test charge at the origin "
                "is equal in magnitude to the force from the charge at −a, and the two forces are opposite "
                "along the x-axis. By superposition, the vector sum is zero."
            ),
            difficulty="easy",
        ),
    },
    {
        "label": "PHY-08",
        "id": uuid.UUID("6d7b9e60-e56f-46e0-b553-654aba9c4a47"),
        "title": "Absolute refractive index",
        "concept_id": CONCEPT_REFRACTIVE_INDEX,
        "update_concept": True,
        "body": _q(
            stem="Absolute refractive index of a medium is:",
            a="Speed of light in medium / speed in vacuum",
            b="Speed of light in vacuum / speed in medium",
            c="Always less than 1",
            d="Equal to wavelength only",
            answer="B",
            explanation=(
                "Absolute refractive index is defined as n = c/v, where c is the speed of light in vacuum "
                "and v is the speed of light in the medium. Option A inverts this definition. Absolute "
                "refractive index is not \"always less than 1,\" and it is not equal to wavelength alone."
            ),
            difficulty="easy",
        ),
    },
    {
        "label": "PHY-09",
        "id": uuid.UUID("961327ff-e291-4c57-a5c2-4f2de51f9004"),
        "title": "Coulomb force two-factor scaling",
        "concept_id": CONCEPT_COULOMB,
        "update_concept": False,
        "body": _q(
            stem=(
                "The Coulomb force between two point charges is F when they are separated by distance r. "
                "If both charges are doubled and the separation is also doubled, the new force is:"
            ),
            a="F/4",
            b="F",
            c="2F",
            d="4F",
            answer="B",
            explanation=(
                "F ∝ q₁q₂ / r². New force F′ ∝ (2q₁)(2q₂) / (2r)² = 4 q₁q₂ / (4 r²) = q₁q₂ / r² ∝ F. "
                "Therefore F′ = F."
            ),
            difficulty="medium",
        ),
    },
    {
        "label": "PHY-10",
        "id": uuid.UUID("18238e36-2102-4aea-acca-9c9709d0722e"),
        "title": "Combined thin-lens power",
        "concept_id": CONCEPT_LENS_POWER,
        "update_concept": True,
        "body": _q(
            stem=(
                "Two thin lenses in contact in air have powers +2.0 D and −0.5 D. "
                "The focal length of the combination is:"
            ),
            a="+0.67 m",
            b="+2.5 m",
            c="−2.0 m",
            d="+0.40 m",
            answer="A",
            explanation=(
                "For thin lenses in contact, powers add: P = P₁ + P₂ = 2.0 + (−0.5) = +1.5 D. "
                "Focal length of the combination is f = 1/P = 1/1.5 m = 2/3 m ≈ +0.67 m. "
                "The positive net power means a converging combination. Option B uses 1/(2.0−0.5) incorrectly "
                "as if subtracting focal lengths; D is 1/2.5; C has the wrong sign/magnitude."
            ),
            difficulty="medium",
        ),
    },
]
