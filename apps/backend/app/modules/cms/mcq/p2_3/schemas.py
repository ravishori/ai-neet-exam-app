"""P2.3 NCERT MCQ content factory schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PROMPT_VERSION = "p2_3_mcq_v1"
RUN_PHASE = "P2.3"

ValidationStatus = Literal["READY", "MINOR_REVISION", "MAJOR_REVISION", "REJECT", "INCONCLUSIVE"]
HumanGrade = Literal["A", "B", "C", "D", "I"]
DuplicateStatus = Literal["EXACT_DUPLICATE", "NEAR_DUPLICATE", "SEMANTIC_DUPLICATE", "NO_DUPLICATE"]
QuestionType = Literal[
    "factual",
    "conceptual",
    "statement_based",
    "assertion_reasoning",
    "application",
    "numerical",
    "match_relationship",
]

P2_3_GENERATION_PROMPT = """You generate ONE original NEET-style MCQ strictly grounded in the supplied NCERT concept blueprint and source excerpt.

Rules:
- Use ONLY facts in the NCERT excerpt for this specific concept.
- Do NOT use general knowledge beyond the excerpt.
- Follow the requested question_type and difficulty exactly.
- Exactly four options A, B, C, D — distinct, meaningful, non-empty.
- Exactly one defensible correct answer.
- Explanation must cite NCERT-supported reasoning only.
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


@dataclass
class ConceptSlot:
    concept_id: str
    source_id: str
    subject: str
    class_level: str
    chapter: int | None
    topic: str
    source_locator: str
    source_file: str
    source_page: int
    source_excerpt_hash: str
    excerpt_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "source_id": self.source_id,
            "subject": self.subject,
            "class": self.class_level,
            "chapter": self.chapter,
            "topic": self.topic,
            "source_locator": self.source_locator,
            "source_file": self.source_file,
            "source_page": self.source_page,
            "source_excerpt_hash": self.source_excerpt_hash,
        }


@dataclass
class GenerationSlot:
    slot_index: int
    concept: ConceptSlot
    question_type: str
    difficulty: str
    generation_provider: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_index": self.slot_index,
            **self.concept.to_dict(),
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "generation_provider": self.generation_provider,
        }


@dataclass
class McqRecord:
    question_id: str
    run_id: str
    batch_id: str
    slot_index: int
    concept_id: str
    subject: str
    class_level: str
    chapter: int | None
    topic: str
    question_type: str
    difficulty: str
    source_id: str
    source_locator: str
    source_file: str
    source_page: int
    source_excerpt_hash: str
    question: str = ""
    options: dict[str, str] = field(default_factory=dict)
    correct_option: str = ""
    explanation: str = ""
    source_support: str = ""
    generation_provider: str = ""
    generation_model: str = ""
    generation_prompt_version: str = PROMPT_VERSION
    generation_status: str = "PENDING"
    qa_status: str = "PENDING"
    validation_status: ValidationStatus = "INCONCLUSIVE"
    validator_provider: str = ""
    validator_model: str = ""
    validator_reason: str = ""
    validator_confidence: float = 0.0
    duplicate_status: DuplicateStatus = "NO_DUPLICATE"
    duplicate_of: str | None = None
    similarity_score: float = 0.0
    human_review_status: str = "NOT_SAMPLED"
    human_grade: HumanGrade | None = None
    final_status: ValidationStatus = "INCONCLUSIVE"
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    origin: str = "p2_3_generation"

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "run_id": self.run_id,
            "batch_id": self.batch_id,
            "slot_index": self.slot_index,
            "concept_id": self.concept_id,
            "subject": self.subject,
            "class": self.class_level,
            "chapter": self.chapter,
            "topic": self.topic,
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "source_file": self.source_file,
            "source_page": self.source_page,
            "source_excerpt_hash": self.source_excerpt_hash,
            "question": self.question,
            "options": self.options,
            "correct_option": self.correct_option,
            "correct_answer": self.correct_option,
            "explanation": self.explanation,
            "source_support": self.source_support,
            "generation_provider": self.generation_provider,
            "generation_model": self.generation_model,
            "generation_prompt_version": self.generation_prompt_version,
            "generation_status": self.generation_status,
            "qa_status": self.qa_status,
            "validation_status": self.validation_status,
            "validator_provider": self.validator_provider,
            "validator_model": self.validator_model,
            "validator_reason": self.validator_reason,
            "validator_confidence": self.validator_confidence,
            "duplicate_status": self.duplicate_status,
            "duplicate_of": self.duplicate_of,
            "similarity_score": self.similarity_score,
            "human_review_status": self.human_review_status,
            "human_grade": self.human_grade,
            "final_status": self.final_status,
            "cost_usd": self.cost_usd,
            "errors": self.errors,
            "provenance": self.provenance,
            "origin": self.origin,
        }
