"""P2.2-R1 independent MCQ validation schemas."""

from __future__ import annotations

from typing import Literal

FieldVerdict = Literal["PASS", "FAIL", "INCONCLUSIVE"]
OverallVerdict = Literal["PASS", "FAIL", "INCONCLUSIVE"]
NcertSupportClass = Literal[
    "DIRECT_NCERT_SUPPORT",
    "SUPPORTED_WITHIN_NCERT_CONTEXT",
    "WEAK_SUPPORT",
    "NO_SUPPORT",
    "INCONCLUSIVE",
]
DuplicateClass = Literal["EXACT_DUPLICATE", "NEAR_DUPLICATE", "SEMANTIC_DUPLICATE", "NO_DUPLICATE"]
QualityGrade = Literal["A", "B", "C", "D", "I"]
FailureCategory = Literal[
    "FACTUAL_ERROR",
    "WRONG_ANSWER",
    "MULTIPLE_CORRECT",
    "NCERT_UNSUPPORTED",
    "AMBIGUOUS",
    "BAD_OPTION",
    "DUPLICATE",
    "EXPLANATION_ERROR",
    "DIFFICULTY_ERROR",
    "SOURCE_ERROR",
    "FORMAT_ERROR",
    "OTHER",
]

VALIDATOR_SYSTEM_PROMPT = """You independently validate an existing NEET-style MCQ against supplied NCERT source evidence.

Rules:
- Do NOT rewrite or replace the question.
- Do NOT assume the generator is correct.
- Use ONLY the supplied NCERT excerpt plus the MCQ fields provided.
- Do not use unsupported outside knowledge.
- If evidence is insufficient, mark INCONCLUSIVE.
- If more than one option could reasonably be correct, overall=FAIL and ambiguity=FAIL.
- If proposed answer is unsupported by NCERT, correct_answer=FAIL.
- If explanation contradicts NCERT, explanation=FAIL.
- For numerical items, verify calculations independently when possible.

Return strict JSON only with this shape:
{
  "overall": "PASS|FAIL|INCONCLUSIVE",
  "stem": "PASS|FAIL|INCONCLUSIVE",
  "options": {"A":"PASS|FAIL|INCONCLUSIVE","B":"...","C":"...","D":"..."},
  "correct_answer": "PASS|FAIL|INCONCLUSIVE",
  "explanation": "PASS|FAIL|INCONCLUSIVE",
  "ncert_support": "PASS|FAIL|INCONCLUSIVE",
  "ambiguity": "PASS|FAIL|INCONCLUSIVE",
  "duplicate_risk": "PASS|FAIL|INCONCLUSIVE",
  "difficulty": "PASS|FAIL|INCONCLUSIVE",
  "ncert_support_class": "DIRECT_NCERT_SUPPORT|SUPPORTED_WITHIN_NCERT_CONTEXT|WEAK_SUPPORT|NO_SUPPORT|INCONCLUSIVE",
  "issues": [],
  "source_evidence": [],
  "confidence": 0.0
}
"""
