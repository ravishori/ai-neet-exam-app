"""Production Seed V2 visual policy + deterministic visual materialization.

Visual requirements are explicit at slot/constraint level. Diagram archetypes
must not pass merely because an archetype string exists.

Generated visuals are factory scaffolding — not NCERT source evidence.
"""
from __future__ import annotations

from typing import Any

# Exact V2 planned visual slots (do not invent additional ones for the 100 cohort).
V2_VISUAL_SLOT_IDS: frozenset[str] = frozenset({"physics-05", "physics-21", "zoology-12"})

# visual_type = coarse family; visual_archetype = deterministic generator key.
V2_VISUAL_SLOT_SPECS: dict[str, dict[str, str]] = {
    "physics-05": {
        "visual_required": "true",
        "visual_type": "line_graph",
        "visual_archetype": "xt_slope_graph",
        "required_labels": "x_axis:time,y_axis:position,curve:x(t)",
    },
    "physics-21": {
        "visual_required": "true",
        "visual_type": "curve_graph",
        "visual_archetype": "stress_strain_curve",
        "required_labels": "x_axis:strain,y_axis:stress,regions:proportional,elastic,plastic",
    },
    "zoology-12": {
        "visual_required": "true",
        "visual_type": "schematic",
        "visual_archetype": "ecg_wave_schematic",
        "required_labels": "waves:P,QRS,T,baseline",
    },
}

DIAGRAM_ARCHETYPES: frozenset[str] = frozenset({"diagram_data_interpretation"})


def visual_fields_for_slot(slot: dict[str, Any]) -> dict[str, Any]:
    """Derive explicit visual fields for a V2 plan slot (no silent reinterpretation)."""
    slot_id = str(slot.get("slot_id") or "")
    if slot_id in V2_VISUAL_SLOT_SPECS:
        spec = V2_VISUAL_SLOT_SPECS[slot_id]
        return {
            "visual_required": True,
            "visual_type": spec["visual_type"],
            "visual_archetype": spec["visual_archetype"],
            "visual_required_labels": spec["required_labels"],
        }
    # All other slots in the frozen 100: explicitly non-visual.
    return {
        "visual_required": False,
        "visual_type": None,
        "visual_archetype": None,
        "visual_required_labels": None,
    }


def enrich_slot_with_visual_fields(slot: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the slot with explicit visual_* fields (plan identity preserved)."""
    out = dict(slot)
    fields = visual_fields_for_slot(slot)
    out.update(fields)
    return out


def build_v2_generation_constraints(slot: dict[str, Any], *, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Constraints blob for factory generation / validation — visual fields survive plan→request."""
    cons = dict(base or {})
    fields = visual_fields_for_slot(slot)
    cons["question_archetype"] = slot.get("question_archetype") or cons.get("question_archetype")
    cons["visual_required"] = bool(fields["visual_required"])
    cons["visual_type"] = fields["visual_type"]
    cons["visual_archetype"] = fields["visual_archetype"]
    if fields.get("visual_required_labels"):
        cons["visual_required_labels"] = fields["visual_required_labels"]
    cons["seed_slot_id"] = slot.get("slot_id") or cons.get("seed_slot_id")
    cons["plan_blueprint_id"] = slot.get("blueprint_id") or cons.get("plan_blueprint_id")
    # Explicit: generated visuals are not NCERT evidence.
    cons["visual_is_ncert_evidence"] = False
    return cons


def _svg_wrap(inner: str, *, title: str, width: int = 420, height: int = 260) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">'
        f"<title>{title}</title>"
        '<rect width="100%" height="100%" fill="#ffffff" stroke="#222222"/>'
        f"{inner}</svg>"
    )


def materialize_deterministic_visual(visual_archetype: str, *, visual_type: str | None = None) -> dict[str, Any]:
    """Programmatic scientific visual spec + SVG. Not NCERT evidence."""
    if visual_archetype == "xt_slope_graph":
        vtype = visual_type or "line_graph"
        svg = _svg_wrap(
            '<line x1="50" y1="220" x2="390" y2="220" stroke="#111" stroke-width="2"/>'
            '<line x1="50" y1="220" x2="50" y2="30" stroke="#111" stroke-width="2"/>'
            '<text x="200" y="245" font-size="12">time t</text>'
            '<text x="10" y="30" font-size="12">x</text>'
            '<polyline fill="none" stroke="#0b57d0" stroke-width="3" '
            'points="50,200 120,160 200,110 280,70 360,40"/>'
            '<text x="270" y="55" font-size="11" fill="#0b57d0">x(t)</text>',
            title="Position-time graph with positive slope",
        )
        return {
            "visual_type": vtype,
            "visual_archetype": visual_archetype,
            "diagram_description": (
                "Schematic x–t graph: time on horizontal axis, position on vertical axis, "
                "smooth curve with positive slope (instantaneous velocity related to slope)."
            ),
            "diagram_svg": svg,
            "visual_spec": {
                "type": vtype,
                "archetype": visual_archetype,
                "axes": {"x": "time t", "y": "position x"},
                "features": ["positive_slope_curve"],
                "labels": ["t", "x", "x(t)", "time", "position"],
                "generator": "factory_v2_deterministic_svg",
                "ncert_evidence": False,
            },
        }
    if visual_archetype == "stress_strain_curve":
        vtype = visual_type or "curve_graph"
        svg = _svg_wrap(
            '<line x1="50" y1="220" x2="390" y2="220" stroke="#111" stroke-width="2"/>'
            '<line x1="50" y1="220" x2="50" y2="30" stroke="#111" stroke-width="2"/>'
            '<text x="200" y="245" font-size="12">strain</text>'
            '<text x="8" y="30" font-size="12">stress</text>'
            '<polyline fill="none" stroke="#b06000" stroke-width="3" '
            'points="50,200 140,120 200,90 260,80 320,110 360,160"/>'
            '<text x="95" y="175" font-size="10">proportional</text>'
            '<text x="170" y="100" font-size="10">elastic</text>'
            '<text x="290" y="95" font-size="10">plastic</text>',
            title="Stress-strain curve with labeled regions",
        )
        return {
            "visual_type": vtype,
            "visual_archetype": visual_archetype,
            "diagram_description": (
                "Schematic stress–strain curve with labeled proportional, elastic, and plastic regions."
            ),
            "diagram_svg": svg,
            "visual_spec": {
                "type": vtype,
                "archetype": visual_archetype,
                "axes": {"x": "strain", "y": "stress"},
                "features": ["proportional_region", "elastic_region", "plastic_region"],
                "labels": ["strain", "stress", "proportional", "elastic", "plastic"],
                "generator": "factory_v2_deterministic_svg",
                "ncert_evidence": False,
            },
        }
    if visual_archetype == "ecg_wave_schematic":
        vtype = visual_type or "schematic"
        svg = _svg_wrap(
            '<line x1="40" y1="140" x2="400" y2="140" stroke="#999" stroke-width="1"/>'
            '<polyline fill="none" stroke="#c62828" stroke-width="3" '
            'points="40,140 80,140 100,110 120,140 150,140 170,60 185,180 200,140 250,140 280,100 310,140 380,140"/>'
            '<text x="95" y="100" font-size="12">P</text>'
            '<text x="165" y="50" font-size="12">QRS</text>'
            '<text x="275" y="90" font-size="12">T</text>'
            '<text x="160" y="230" font-size="12">ECG baseline</text>',
            title="Schematic ECG with P QRS T waves",
        )
        return {
            "visual_type": vtype,
            "visual_archetype": visual_archetype,
            "diagram_description": (
                "Schematic ECG trace on a baseline showing P wave, QRS complex, and T wave in sequence."
            ),
            "diagram_svg": svg,
            "visual_spec": {
                "type": vtype,
                "archetype": visual_archetype,
                "axes": {"x": "time", "y": "voltage"},
                "features": ["P_wave", "QRS_complex", "T_wave", "baseline"],
                "labels": ["P", "QRS", "T", "baseline"],
                "generator": "factory_v2_deterministic_svg",
                "ncert_evidence": False,
            },
        }
    raise ValueError(f"Unsupported V2 visual_archetype: {visual_archetype}")


def materialize_visual_for_slot(slot_id: str) -> dict[str, Any] | None:
    """Materialize the deterministic visual for a known V2 visual slot_id."""
    if slot_id not in V2_VISUAL_SLOT_SPECS:
        return None
    spec = V2_VISUAL_SLOT_SPECS[slot_id]
    return materialize_deterministic_visual(spec["visual_archetype"], visual_type=spec["visual_type"])


def attach_visual_to_body(body: dict[str, Any], *, constraints: dict[str, Any]) -> dict[str, Any]:
    """If visual_required, attach deterministic visual fields onto the MCQ body."""
    out = dict(body)
    if not constraints.get("visual_required"):
        return out
    # Prefer archetype (generator key); fall back to type if it happens to be a known generator.
    varch = constraints.get("visual_archetype") or constraints.get("visual_type")
    if not varch:
        return out
    # Do not overwrite an already-valid attached visual.
    if out.get("diagram_svg") and out.get("visual_spec"):
        return out
    visual = materialize_deterministic_visual(
        str(varch),
        visual_type=str(constraints.get("visual_type") or "") or None,
    )
    out["diagram_svg"] = visual["diagram_svg"]
    out["diagram_description"] = visual["diagram_description"]
    out["visual_spec"] = visual["visual_spec"]
    return out


def body_has_visual(body: dict[str, Any] | None) -> bool:
    if not body or not isinstance(body, dict):
        return False
    return bool(body.get("diagram_svg")) and bool(body.get("visual_spec"))
