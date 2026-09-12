"""FACTORY-P4 deterministic QA gates + fingerprint helpers.

No AI judge. Scientific certification is never claimed.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash, validate_candidate_body

QA_VERSION = "factory_qa_v1"
SEMANTIC_DEDUPE_NOT_AVAILABLE = "SEMANTIC_DEDUPE_NOT_AVAILABLE"

_OFFICIAL_CLAIM = re.compile(
    r"\b(official\s+nta|nta\s+official|official\s+neet\s+paper|verbatim\s+from\s+ncert|"
    r"copied\s+from\s+ncert|this\s+is\s+an?\s+nta\s+question)\b",
    re.IGNORECASE,
)
_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)\s+instructions|system\s+prompt|api[_ ]?key|"
    r"anthropic|sk-[a-z0-9]{10,}|BEGIN PRIVATE KEY)",
    re.IGNORECASE,
)
_INTERNAL_LEAK = re.compile(
    r"(content_factory|generation_candidate|factory_qa_v\d|DATABASE_URL|trinetra_dev_pw)",
    re.IGNORECASE,
)

# System-controlled factory lineage tags (P3.1+) — excluded from injection/impersonation scans.
_TRUSTED_FACTORY_LINEAGE_TAG_PREFIXES: tuple[str, ...] = (
    "factory-p3",
    "batch:",
    "job:",
    "run:",
    "blueprint:",
    "bp-v:",
    "family:",
    "provider:",
    "model:",
    "routing:",
    "provenance:",
)


def _is_trusted_factory_lineage_tag(tag: str) -> bool:
    normalized = (tag or "").strip()
    if not normalized:
        return True
    if normalized == "factory-p3":
        return True
    return any(normalized.startswith(prefix) for prefix in _TRUSTED_FACTORY_LINEAGE_TAG_PREFIXES if prefix.endswith(":"))


def _gate_g_question_content_blob(body: dict[str, Any]) -> str:
    """Untrusted model-generated fields scanned for safety violations."""
    return " ".join(
        [
            str(body.get("stem", "")),
            str(body.get("explanation", "")),
            " ".join(str(o.get("text", "")) for o in (body.get("options") or []) if isinstance(o, dict)),
        ]
    )


def _gate_g_untrusted_tags_blob(tags: list[str] | None) -> str:
    """Non-lineage tags may still carry user/editor content worth scanning."""
    untrusted = [t for t in (tags or []) if not _is_trusted_factory_lineage_tag(t)]
    return " ".join(untrusted)


@dataclass
class GateOutcome:
    code: str
    passed: bool
    severity: str  # RED | YELLOW | INFO
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def option_stem_hash(stem: str, options: list[dict[str, Any]]) -> str:
    parts = [normalize_stem(stem)]
    for opt in sorted(options, key=lambda o: o.get("label", "")):
        parts.append(f"{opt.get('label')}:{normalize_stem(str(opt.get('text', '')))}")
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def gate_a_structure(body: dict[str, Any] | None) -> GateOutcome:
    if not body or not isinstance(body, dict):
        return GateOutcome("A_STRUCTURE", False, "RED", failures=["MISSING_BODY"])
    validated, errs = validate_candidate_body(
        body, expected_difficulty=str(body.get("difficulty") or "medium")
    )
    # Structure-only: ignore difficulty mismatch here (Gate B owns blueprint difficulty)
    structural = [e for e in errs if e != "DIFFICULTY_MISMATCH" and not e.startswith("ANSWER_")]
    if validated is None and any(e.startswith("SCHEMA") for e in errs):
        return GateOutcome("A_STRUCTURE", False, "RED", failures=errs or ["SCHEMA_INVALID"])
    stem = (body.get("stem") or "").strip()
    explanation = (body.get("explanation") or "").strip()
    options = body.get("options") or []
    failures: list[str] = []
    if not stem:
        failures.append("EMPTY_STEM")
    if not explanation:
        failures.append("EMPTY_EXPLANATION")
    if len(options) != 4:
        failures.append("OPTION_COUNT")
    labels = [o.get("label") for o in options if isinstance(o, dict)]
    texts = [str(o.get("text", "")).strip() for o in options if isinstance(o, dict)]
    if len(set(labels)) != 4:
        failures.append("OPTION_LABELS")
    if len(set(texts)) != 4 or any(not t for t in texts):
        failures.append("OPTION_TEXTS_UNIQUE")
    correct = body.get("correct_option")
    if correct not in labels:
        failures.append("INVALID_ANSWER")
    difficulty = body.get("difficulty")
    if difficulty not in {"easy", "medium", "hard"}:
        failures.append("INVALID_DIFFICULTY")
    failures.extend(structural)
    # Deduplicate while preserving order
    seen: set[str] = set()
    uniq = []
    for f in failures:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return GateOutcome("A_STRUCTURE", not uniq, "RED" if uniq else "INFO", failures=uniq)


def gate_e_answer_explanation(body: dict[str, Any] | None) -> GateOutcome:
    if not body:
        return GateOutcome("E_ANSWER", False, "RED", failures=["MISSING_BODY"])
    _, errs = validate_candidate_body(body, expected_difficulty=str(body.get("difficulty") or "medium"))
    contradictions = [
        e
        for e in errs
        if e
        in {
            "ANSWER_EXPLANATION_CONTRADICTION",
            "EMPTY_CORRECT_OPTION",
            "PHENOTYPE_EXPLANATION_INCOMPLETE",
        }
    ]
    warnings: list[str] = []
    if "EXPLANATION_TOO_SHORT" in errs:
        warnings.append("EXPLANATION_TOO_SHORT")
    # Explicit: we do NOT scientifically certify correctness.
    warnings.append("NO_SCIENTIFIC_CERTIFICATION")
    if contradictions:
        return GateOutcome(
            "E_ANSWER",
            False,
            "RED",
            failures=contradictions,
            warnings=warnings,
            detail={"note": "Deterministic contradiction only — not scientific validation"},
        )
    return GateOutcome("E_ANSWER", True, "INFO", warnings=warnings)


def gate_g_safety(body: dict[str, Any] | None, *, tags: list[str] | None = None) -> GateOutcome:
    if not body:
        return GateOutcome("G_SAFETY", False, "RED", failures=["MISSING_BODY"])
    content_blob = _gate_g_question_content_blob(body)
    untrusted_tags_blob = _gate_g_untrusted_tags_blob(tags)
    user_facing_blob = f"{content_blob} {untrusted_tags_blob}".strip()
    failures: list[str] = []
    warnings: list[str] = []
    if _OFFICIAL_CLAIM.search(user_facing_blob):
        failures.append("OFFICIAL_SOURCE_IMPERSONATION")
    if _INJECTION.search(content_blob):
        failures.append("PROMPT_INJECTION_OR_SECRET")
    if _INTERNAL_LEAK.search(user_facing_blob):
        failures.append("INTERNAL_METADATA_LEAK")
    # Irrelevant / empty already covered; flag very short stem as warning
    if len(str(body.get("stem", "")).strip()) < 12:
        warnings.append("SUSPICIOUSLY_SHORT_STEM")
    return GateOutcome("G_SAFETY", not failures, "RED" if failures else "INFO", failures=failures, warnings=warnings)


def classify_from_gates(
    gates: list[GateOutcome],
    *,
    duplicate_class: str,
) -> tuple[str, bool, bool]:
    """Return (classification, sampling_eligible, quarantine).

    GREEN = eligible for GREEN sampling pool only — not scientifically certified.
    YELLOW = 100% human-review eligibility (excluded from GREEN sample).
    RED = factory quarantine (still DRAFT in ECAEP).
    """
    red = any(g.severity == "RED" and not g.passed for g in gates)
    yellow_signals = any(g.severity == "YELLOW" and not g.passed for g in gates)
    # Non-blocking warnings do not force YELLOW unless duplicate risk / explicit YELLOW gate.
    soft_yellow = any(
        w in {"EXPLANATION_TOO_SHORT", "SUSPICIOUSLY_SHORT_STEM", "FALLBACK_PROVIDER", "MISSING_NONCRITICAL_META"}
        for g in gates
        for w in g.warnings
    )
    if duplicate_class in {"EXACT_DUPLICATE", "NORMALIZED_DUPLICATE"}:
        red = True
    if duplicate_class == "POSSIBLE_DUPLICATE":
        yellow_signals = True

    if red:
        return "RED", False, True
    if yellow_signals or soft_yellow:
        return "YELLOW", False, False
    return "GREEN", True, False
