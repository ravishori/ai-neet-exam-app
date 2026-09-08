"""Deterministic validation + stem normalization for FACTORY-P3 candidates."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import ValidationError

from app.modules.cms.schemas.content_bodies import QuestionBody

_STEM_NOISE = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_stem(stem: str) -> str:
    text = stem.lower().strip()
    text = _STEM_NOISE.sub("", text)
    text = _WS.sub(" ", text)
    return text


def stem_hash(stem: str) -> str:
    return hashlib.sha256(normalize_stem(stem).encode("utf-8")).hexdigest()


def parse_mcq_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        raise ValueError("AI output must be raw JSON without markdown fences")
    return json.loads(text)


def _validate_visual_constraints(body: dict[str, Any], constraints: dict[str, Any] | None) -> list[str]:
    if not constraints or not bool(constraints.get("visual_required")):
        return []

    errors: list[str] = []
    svg = (body.get("diagram_svg") or "").strip()
    desc = (body.get("diagram_description") or "").strip()
    spec = body.get("visual_spec")
    expected_type = constraints.get("visual_type")
    expected_archetype = constraints.get("visual_archetype")

    if not svg:
        errors.append("VISUAL_REQUIRED_MISSING_SVG")
        errors.append("VISUAL_REQUIRED_BUT_MISSING")
    if not isinstance(spec, dict) or not spec:
        errors.append("VISUAL_REQUIRED_MISSING_SPEC")
        if "VISUAL_REQUIRED_BUT_MISSING" not in errors:
            errors.append("VISUAL_REQUIRED_BUT_MISSING")
    if not desc:
        errors.append("VISUAL_REQUIRED_MISSING_DESCRIPTION")

    if expected_type:
        observed = spec.get("type") if isinstance(spec, dict) else None
        if not observed:
            errors.append("VISUAL_TYPE_MISSING")
        elif observed != expected_type:
            errors.append("VISUAL_TYPE_MISMATCH")

    if expected_archetype and isinstance(spec, dict):
        observed_arch = spec.get("archetype")
        if observed_arch and observed_arch != expected_archetype:
            errors.append("VISUAL_ARCHETYPE_MISMATCH")

    required_labels_raw = constraints.get("visual_required_labels") or ""
    if required_labels_raw and isinstance(spec, dict):
        label_blob = " ".join(str(x) for x in (spec.get("labels") or [])).lower()
        label_blob += " " + " ".join(f"{k}:{v}" for k, v in (spec.get("axes") or {}).items()).lower()
        label_blob += " " + svg.lower() + " " + desc.lower()
        for part in str(required_labels_raw).split(","):
            token = part.split(":")[-1].strip().lower()
            if token and token not in label_blob:
                errors.append(f"VISUAL_LABEL_MISSING:{token}")

    stem = str(body.get("stem") or "").lower()
    if not any(tok in stem for tok in ("figure", "diagram", "graph", "curve", "ecg", "shown", "trace", "plot")):
        errors.append("VISUAL_STEM_REFERENCE_MISSING")

    if constraints.get("visual_is_ncert_evidence") is True:
        errors.append("VISUAL_FALSE_NCERT_EVIDENCE_CLAIM")
        errors.append("VISUAL_NCERT_EVIDENCE_FABRICATED")
    if isinstance(spec, dict) and spec.get("ncert_evidence") is True:
        errors.append("VISUAL_FALSE_NCERT_EVIDENCE_CLAIM")
        errors.append("VISUAL_NCERT_EVIDENCE_FABRICATED")

    seen: set[str] = set()
    uniq: list[str] = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq


def validate_candidate_body(
    body: dict[str, Any],
    *,
    expected_difficulty: str,
    constraints: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (validated_body, error_codes). Empty error_codes means pass (may still warn)."""
    detailed = validate_candidate_body_detailed(
        body, expected_difficulty=expected_difficulty, constraints=constraints
    )
    return detailed["body"], detailed["errors"]


def validate_candidate_body_detailed(
    body: dict[str, Any],
    *,
    expected_difficulty: str,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structural + visual + semantic validation contract.

    semantic_status ∈ {STRUCTURALLY_VALID, SEMANTIC_REVIEW_REQUIRED, SEMANTIC_AMBIGUITY_DETECTED}
    Hard failures (including SEMANTIC_AMBIGUITY_DETECTED) populate errors and null body.
    SEMANTIC_REVIEW_REQUIRED alone does not reject; it is returned as a warning.
    """
    from app.modules.cms.services.factory_v2_answer_ambiguity import (
        SEMANTIC_AMBIGUITY_DETECTED,
        STRUCTURALLY_VALID,
        assess_semantic_answer_uniqueness,
    )

    errors: list[str] = []
    warnings: list[str] = []
    try:
        qb = QuestionBody.model_validate(body)
    except ValidationError as exc:
        return {
            "ok": False,
            "body": None,
            "errors": [f"SCHEMA:{exc.errors()[0].get('type', 'invalid')}"],
            "warnings": [],
            "structural_status": "STRUCTURALLY_INVALID",
            "semantic_status": STRUCTURALLY_VALID,
            "semantic_signals": [],
            "visual_validation": {"required": bool(constraints and constraints.get("visual_required")), "passed": False, "errors": []},
        }

    data = qb.model_dump()
    if data["difficulty"] != expected_difficulty:
        errors.append("DIFFICULTY_MISMATCH")

    correct = data["correct_option"]
    correct_text = next(o["text"] for o in data["options"] if o["label"] == correct)
    explanation = data["explanation"].strip()
    if len(explanation) < 20:
        errors.append("EXPLANATION_TOO_SHORT")

    mentioned = re.findall(r"(?:option|answer)\s*([ABCD])\b", explanation, flags=re.IGNORECASE)
    if mentioned:
        unique = {m.upper() for m in mentioned}
        if len(unique) == 1 and correct not in unique:
            errors.append("ANSWER_EXPLANATION_CONTRADICTION")

    if not correct_text.strip():
        errors.append("EMPTY_CORRECT_OPTION")

    from app.modules.cms.services.factory_seed_diversity import phenotype_explanation_error

    pheno_err = phenotype_explanation_error(data["stem"], explanation)
    if pheno_err:
        errors.append(pheno_err)

    visual_errors = _validate_visual_constraints(data, constraints)
    errors.extend(visual_errors)
    visual_required = bool(constraints and constraints.get("visual_required"))
    visual_validation = {
        "required": visual_required,
        "passed": (not visual_required) or (not any(e.startswith("VISUAL_") for e in visual_errors)),
        "errors": list(visual_errors),
    }

    semantic = assess_semantic_answer_uniqueness(data)
    warnings.extend([w for w in semantic.warnings if w not in warnings])
    if semantic.hard_fail:
        errors.append(SEMANTIC_AMBIGUITY_DETECTED)

    if errors:
        structural_status = "STRUCTURALLY_INVALID"
        if any(e.startswith("VISUAL_") for e in errors):
            structural_status = "VISUAL_VALIDATION_FAILED"
        elif SEMANTIC_AMBIGUITY_DETECTED in errors and not any(
            e.startswith("SCHEMA") or e.startswith("VISUAL_") for e in errors
        ):
            structural_status = STRUCTURALLY_VALID  # structure ok; semantic hard-fail
        return {
            "ok": False,
            "body": None,
            "errors": errors,
            "warnings": warnings,
            "structural_status": structural_status,
            "semantic_status": semantic.semantic_status,
            "semantic_signals": semantic.signals,
            "visual_validation": visual_validation,
        }

    if semantic.semantic_status != STRUCTURALLY_VALID:
        warnings.append("REQUIRES_REVIEW")

    return {
        "ok": True,
        "body": data,
        "errors": [],
        "warnings": warnings,
        "structural_status": STRUCTURALLY_VALID,
        "semantic_status": semantic.semantic_status,
        "semantic_signals": semantic.signals,
        "visual_validation": visual_validation,
    }
