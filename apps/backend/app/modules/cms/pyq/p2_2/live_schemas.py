"""Schemas for P2.2 live pilot tracks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

HumanVerdict = Literal["PENDING", "HUMAN_PASS", "HUMAN_FAIL", "HUMAN_INCONCLUSIVE"]
PilotVerdict = Literal["GREEN", "YELLOW", "RED"]
McqStatus = Literal["GENERATED", "VALIDATED", "REJECTED", "INCONCLUSIVE", "HUMAN_REVIEW"]

NCERT_MCQ_SYSTEM_PROMPT = """You generate ONE original NEET-style MCQ strictly grounded in the supplied NCERT source excerpt.

Rules:
- Use ONLY facts present in the supplied NCERT excerpt.
- Do NOT use general knowledge beyond the excerpt.
- Do NOT claim the question is from official NEET/NTA papers.
- Exactly four options A, B, C, D — distinct, non-empty, plausible.
- Exactly one defensible correct answer.
- Explanation must cite why the correct option follows from the excerpt.
- If the excerpt cannot support a fair MCQ: return status REJECTED with reason.
- Output strict JSON only.

JSON shape:
{
  "status": "GENERATED|REJECTED",
  "question": str,
  "options": {"A": str, "B": str, "C": str, "D": str},
  "correct_answer": "A"|"B"|"C"|"D",
  "explanation": str,
  "source_reference": str,
  "topic": str,
  "difficulty": "EASY"|"MEDIUM"|"HARD",
  "question_type": str,
  "source_support": "NCERT-SUPPORTED|GENERAL_KNOWLEDGE"
}
"""

MCQ_REVIEW_SYSTEM_PROMPT = """You independently review a candidate NEET MCQ against the supplied NCERT excerpt.

Check: stem clarity, four meaningful options, exactly one correct answer, NCERT support, ambiguity, duplicate options, answer-explanation consistency.

Return strict JSON:
{
  "verdict": "PASS|FAIL|INCONCLUSIVE",
  "answer_correct": true|false|null,
  "ncert_supported": true|false,
  "ambiguous": true|false,
  "issues": [str],
  "confidence": 0.0
}
"""


@dataclass
class LiveMcqRecord:
    mcq_id: str
    provider: str
    model: str
    status: McqStatus
    subject: str
    class_level: str
    chapter: int | None
    topic: str
    source_file: str
    source_page: int
    source_hash: str
    question: str = ""
    options: dict[str, str] = field(default_factory=dict)
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = ""
    question_type: str = ""
    source_support: str = ""
    review_verdict: str = "PENDING"
    review_provider: str = ""
    human_verdict: HumanVerdict = "PENDING"
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mcq_id": self.mcq_id,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "subject": self.subject,
            "class": self.class_level,
            "chapter": self.chapter,
            "topic": self.topic,
            "source_file": self.source_file,
            "source_page": self.source_page,
            "source_hash": self.source_hash,
            "question": self.question,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "difficulty": self.difficulty,
            "question_type": self.question_type,
            "source_support": self.source_support,
            "review_verdict": self.review_verdict,
            "review_provider": self.review_provider,
            "human_verdict": self.human_verdict,
            "cost_usd": self.cost_usd,
            "errors": self.errors,
            "provenance": self.provenance,
        }
