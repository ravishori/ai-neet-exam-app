"""Independent auditors for declared question_type and difficulty.

Declared generator metadata is never treated as truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.cms.acquisition.mmf.contract_v2 import AUDITED_QUESTION_TYPES

AuditMatch = Literal["MATCH", "MISMATCH"]
AuditedDifficulty = Literal["EASY", "MEDIUM", "HARD", "UNCERTAIN"]
AuditedQuestionType = Literal[
    "FACTUAL",
    "CONCEPTUAL",
    "DIRECT",
    "STATEMENT_BASED",
    "COMPARISON",
    "APPLICATION",
    "MULTI_STATEMENT",
]

_MULTI = re.compile(
    r"(?i)\b(which of the following statements|consider the following|assertion|reason|"
    r"match the|columns?|both\s+[ivx]+|statement[s]?\s*[ivx123])\b"
)
_COMPARE = re.compile(r"(?i)\b(differ|difference|compare|whereas|unlike|similar to|as compared)\b")
_APP = re.compile(r"(?i)\b(if |suppose|a student|would|predict|consequence|based on)\b")
_FACT = re.compile(r"(?i)\b(is known as|is called|example of|belongs to|phylum|class )\b")
_CONCEPT = re.compile(r"(?i)\b(because|why |explain|concept|characteri[sz]ed by)\b")
_DIRECT = re.compile(r"(?i)^(which|what|who|where)\b")
_STMT = re.compile(r"(?i)\b(statement[-\s]?based|read the statements|given below are)\b")


def normalize_declared_question_type(raw: str | None) -> str:
    t = (raw or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "STATEMENTBASED": "STATEMENT_BASED",
        "STATEMENT_BASED": "STATEMENT_BASED",
        "MULTI_STATEMENT": "MULTI_STATEMENT",
        "STATEMENT_ANALYSIS": "MULTI_STATEMENT",
        "COMPARATIVE": "COMPARISON",
        "COMPARISON": "COMPARISON",
        "CONCEPT": "CONCEPTUAL",
        "CONCEPT_CHECK": "CONCEPTUAL",
        "CONCEPTUAL": "CONCEPTUAL",
        "KNOWLEDGE": "FACTUAL",
        "FACTUAL": "FACTUAL",
        "MCQ": "DIRECT",
        "STANDARD": "DIRECT",
        "SINGLE_CORRECT_MCQ": "DIRECT",
        "DIRECT": "DIRECT",
        "APPLICATION": "APPLICATION",
        "ANALYTICAL": "APPLICATION",
        "ASSERTION_REASONING": "MULTI_STATEMENT",
        "ASSERTION_STATEMENT": "MULTI_STATEMENT",
        "MATCHING": "COMPARISON",
        "MATCH_RELATIONSHIP": "COMPARISON",
    }
    return aliases.get(t, t)


def audit_question_type(stem: str, *, declared: str | None = None) -> AuditedQuestionType:
    s = stem or ""
    if _MULTI.search(s) or re.search(r"\b(i\)|ii\)|iii\)|1\.|2\.|3\.)", s):
        return "MULTI_STATEMENT"
    if _STMT.search(s):
        return "STATEMENT_BASED"
    if _COMPARE.search(s):
        return "COMPARISON"
    if _APP.search(s) and len(s) > 120:
        return "APPLICATION"
    if _CONCEPT.search(s):
        return "CONCEPTUAL"
    if _FACT.search(s):
        return "FACTUAL"
    if _DIRECT.search(s.strip()):
        return "DIRECT"
    return "FACTUAL"


def question_type_compatible(declared_norm: str, audited: str) -> bool:
    if declared_norm == audited:
        return True
    groups = [
        {"FACTUAL", "DIRECT", "KNOWLEDGE", "MCQ", "STANDARD", "SINGLE_CORRECT_MCQ"},
        {"CONCEPTUAL", "CONCEPT", "CONCEPT_CHECK"},
        {"STATEMENT_BASED", "MULTI_STATEMENT", "STATEMENT_ANALYSIS", "ASSERTION_REASONING", "ASSERTION_STATEMENT"},
        {"COMPARISON", "COMPARATIVE", "MATCHING", "MATCH_RELATIONSHIP"},
        {"APPLICATION", "ANALYTICAL"},
    ]
    for g in groups:
        if declared_norm in g and audited in g:
            return True
    return False


@dataclass(frozen=True)
class QuestionTypeAudit:
    declared: str
    declared_normalized: str
    audited: AuditedQuestionType
    status: AuditMatch
    reason_code: str


def audit_question_type_report(stem: str, declared: str | None) -> QuestionTypeAudit:
    audited = audit_question_type(stem, declared=declared)
    declared_raw = declared or ""
    declared_norm = normalize_declared_question_type(declared_raw)
    if declared_norm not in AUDITED_QUESTION_TYPES and declared_norm not in {
        "KNOWLEDGE",
        "MCQ",
        "STANDARD",
        "SINGLE_CORRECT_MCQ",
        "CONCEPT",
        "CONCEPT_CHECK",
        "COMPARATIVE",
        "STATEMENT_ANALYSIS",
        "ASSERTION_REASONING",
        "ASSERTION_STATEMENT",
        "ANALYTICAL",
        "MATCHING",
        "MATCH_RELATIONSHIP",
        "STATEMENTBASED",
    }:
        # Unknown declared label — still compare after soft normalize
        pass
    if question_type_compatible(declared_norm, audited):
        return QuestionTypeAudit(
            declared=declared_raw,
            declared_normalized=declared_norm,
            audited=audited,
            status="MATCH",
            reason_code="TYPE_MATCH",
        )
    reason = "TYPE_MISMATCH_INCOMPATIBLE_FAMILY"
    if not declared_raw.strip():
        reason = "TYPE_MISMATCH_MISSING_DECLARED"
    elif declared_norm not in AUDITED_QUESTION_TYPES and not question_type_compatible(declared_norm, audited):
        reason = "TYPE_MISMATCH_NONSTANDARD_DECLARED_LABEL"
    return QuestionTypeAudit(
        declared=declared_raw,
        declared_normalized=declared_norm,
        audited=audited,
        status="MISMATCH",
        reason_code=reason,
    )


def audit_difficulty(
    *,
    stem: str,
    question_type: str | None,
    options: dict[str, str],
) -> AuditedDifficulty:
    qt = normalize_declared_question_type(question_type)
    opts = [options.get(k, "") for k in ("A", "B", "C", "D")]
    avg_opt = sum(len(o) for o in opts) / 4 if opts else 0
    n_stmt = len(re.findall(r"(?i)\b(statement|i\)|ii\)|iii\)|assertion|reason)\b", stem))
    hard = 0
    easy = 0
    if qt in {"MULTI_STATEMENT", "ASSERTION_REASONING", "COMPARISON", "APPLICATION"}:
        hard += 1
    if n_stmt >= 2 or len(stem) > 280:
        hard += 1
    if re.search(r"(?i)\b(except|incorrect|not true|all of the above|none)\b", stem):
        hard += 1
    if avg_opt > 80:
        hard += 1
    if len(stem) < 90 and qt in {"FACTUAL", "DIRECT"} and avg_opt < 45:
        easy += 2
    if re.search(r"(?i)\b(is called|known as|example)\b", stem) and len(stem) < 140:
        easy += 1
    if hard >= 2:
        return "HARD"
    if easy >= 2 and hard == 0:
        return "EASY"
    if hard == 1 and easy == 0:
        return "MEDIUM"
    if easy == 1 and hard == 0:
        return "EASY"
    if hard == 0 and easy == 0 and 90 <= len(stem) <= 220:
        return "MEDIUM"
    return "UNCERTAIN"


@dataclass(frozen=True)
class DifficultyAudit:
    declared: str
    audited: AuditedDifficulty
    agreement: bool | None
    reason_code: str


def audit_difficulty_report(
    *,
    stem: str,
    declared_difficulty: str | None,
    question_type: str | None,
    options: dict[str, str],
) -> DifficultyAudit:
    audited = audit_difficulty(stem=stem, question_type=question_type, options=options)
    declared = (declared_difficulty or "").strip().lower()
    if audited == "UNCERTAIN":
        return DifficultyAudit(
            declared=declared,
            audited=audited,
            agreement=None,
            reason_code="DIFFICULTY_AUDIT_UNCERTAIN",
        )
    if declared.upper() == audited:
        return DifficultyAudit(
            declared=declared,
            audited=audited,
            agreement=True,
            reason_code="DIFFICULTY_AGREE",
        )
    order = {"easy": 0, "medium": 1, "hard": 2}
    if declared not in order:
        return DifficultyAudit(
            declared=declared,
            audited=audited,
            agreement=False,
            reason_code="DIFFICULTY_MISMATCH_INVALID_DECLARED",
        )
    if order[declared] > order[audited.lower()]:
        code = "DIFFICULTY_MISMATCH_INFLATION"
    else:
        code = "DIFFICULTY_MISMATCH_DEFLATION"
    return DifficultyAudit(declared=declared, audited=audited, agreement=False, reason_code=code)


def audit_candidate_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    """Produce declared-vs-audited report without mutating the candidate."""
    stem = str(raw.get("stem") or "")
    declared_type = raw.get("declared_question_type") or raw.get("question_type")
    declared_diff = raw.get("declared_difficulty") or raw.get("difficulty")
    opts = raw.get("options") or {}
    if not isinstance(opts, dict):
        opts = {}
    qt = audit_question_type_report(stem, str(declared_type) if declared_type is not None else None)
    df = audit_difficulty_report(
        stem=stem,
        declared_difficulty=str(declared_diff) if declared_diff is not None else None,
        question_type=str(declared_type) if declared_type is not None else None,
        options={k: str(opts.get(k) or "") for k in ("A", "B", "C", "D")},
    )
    return {
        "declared_question_type": qt.declared,
        "audited_question_type": qt.audited,
        "question_type_status": qt.status,
        "question_type_reason_code": qt.reason_code,
        "declared_difficulty": df.declared,
        "audited_difficulty": df.audited,
        "difficulty_agreement": df.agreement,
        "difficulty_reason_code": df.reason_code,
    }


__all__ = [
    "DifficultyAudit",
    "QuestionTypeAudit",
    "audit_candidate_metadata",
    "audit_difficulty",
    "audit_difficulty_report",
    "audit_question_type",
    "audit_question_type_report",
    "normalize_declared_question_type",
    "question_type_compatible",
]
