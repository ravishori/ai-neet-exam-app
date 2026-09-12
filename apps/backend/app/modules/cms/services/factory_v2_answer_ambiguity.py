"""Deterministic semantic answer-ambiguity signals for factory MCQs.

Not an LLM scientific judge. Distinguishes:
- STRUCTURALLY_VALID
- SEMANTIC_REVIEW_REQUIRED
- SEMANTIC_AMBIGUITY_DETECTED

High lexical similarity alone does not auto-reject scientifically valid items.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.cms.services.factory_candidate_validation import normalize_stem

STRUCTURALLY_VALID = "STRUCTURALLY_VALID"
SEMANTIC_REVIEW_REQUIRED = "SEMANTIC_REVIEW_REQUIRED"
SEMANTIC_AMBIGUITY_DETECTED = "SEMANTIC_AMBIGUITY_DETECTED"

# Aliases used by callers / tests
STATUS_STRUCTURALLY_VALID = STRUCTURALLY_VALID
STATUS_REVIEW_REQUIRED = SEMANTIC_REVIEW_REQUIRED
STATUS_AMBIGUITY_DETECTED = SEMANTIC_AMBIGUITY_DETECTED


def _tokset(text: str) -> set[str]:
    t = normalize_stem(text or "")
    return {w for w in t.split() if len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_OPTION_LETTER = re.compile(r"(?:option|answer)\s*([ABCD])\b", re.I)


@dataclass
class SemanticAnswerAssessment:
    semantic_status: str = STRUCTURALLY_VALID
    warnings: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    hard_fail: bool = False

    @property
    def status(self) -> str:
        return self.semantic_status

    @property
    def flags(self) -> list[str]:
        return list(self.signals)


def assess_semantic_answer_uniqueness(body: dict[str, Any]) -> SemanticAnswerAssessment:
    """Flag overlapping / dual-correct patterns without claiming full semantic certification."""
    out = SemanticAnswerAssessment()
    options = body.get("options") or []
    if len(options) != 4:
        return out
    by_label = {str(o.get("label", "")).upper(): str(o.get("text") or "") for o in options if isinstance(o, dict)}
    correct = str(body.get("correct_option") or "").upper()
    explanation = str(body.get("explanation") or "")

    # Explanation endorses multiple distinct option letters as correct.
    mentioned = {m.upper() for m in _OPTION_LETTER.findall(explanation)}
    if len(mentioned) >= 2:
        out.signals.append("EXPLANATION_REFERENCES_MULTIPLE_OPTIONS")
        out.semantic_status = SEMANTIC_REVIEW_REQUIRED
        out.warnings.append("SEMANTIC_REVIEW_REQUIRED")

    # Near-duplicate option texts (normalized).
    labels = sorted(by_label.keys())
    for i, la in enumerate(labels):
        for lb in labels[i + 1 :]:
            ja = _jaccard(_tokset(by_label[la]), _tokset(by_label[lb]))
            if ja >= 0.72:
                out.signals.append(f"HIGH_OPTION_OVERLAP:{la}/{lb}:{ja:.2f}")
                out.semantic_status = SEMANTIC_REVIEW_REQUIRED
                out.warnings.append("SEMANTIC_REVIEW_REQUIRED")

    # Zoology-15 style: two options both fully describe pulmonary+systemic topology/physiology.
    circuit_hits = []
    for lab, text in by_label.items():
        tl = text.lower()
        has_pulm = "pulmonary" in tl
        has_sys = "systemic" in tl
        has_rv = "right ventricle" in tl or re.search(r"\brv\b", tl)
        has_lv = "left ventricle" in tl or re.search(r"\blv\b", tl)
        if has_pulm and has_sys and has_rv and has_lv:
            circuit_hits.append(lab)
    if len(circuit_hits) >= 2:
        out.signals.append(f"DUAL_COMPLETE_CIRCUIT_OPTIONS:{','.join(circuit_hits)}")
        out.semantic_status = SEMANTIC_AMBIGUITY_DETECTED
        out.hard_fail = True
        out.warnings.append("SEMANTIC_AMBIGUITY_DETECTED")

    # Explanation soft-supports a non-correct option by quoting its distinctive phrase.
    if correct in by_label:
        for lab, text in by_label.items():
            if lab == correct:
                continue
            # Long distinctive fragment present in explanation (likely dual endorsement).
            frag = normalize_stem(text)[:48]
            if len(frag) >= 24 and frag in normalize_stem(explanation):
                out.signals.append(f"EXPLANATION_ECHOES_NONCORRECT:{lab}")
                if out.semantic_status == STRUCTURALLY_VALID:
                    out.semantic_status = SEMANTIC_REVIEW_REQUIRED
                out.warnings.append("SEMANTIC_REVIEW_REQUIRED")

    if out.semantic_status == STRUCTURALLY_VALID:
        out.signals.append("NO_DETERMINISTIC_AMBIGUITY_SIGNAL")
    return out


def assess_exactly_one_answer_semantics(body: dict[str, Any]) -> SemanticAnswerAssessment:
    """Public interface alias for the semantic ambiguity stage."""
    return assess_semantic_answer_uniqueness(body)
