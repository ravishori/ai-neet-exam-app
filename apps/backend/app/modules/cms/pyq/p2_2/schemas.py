"""P2.2 AI-assisted source recovery schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TriageCategory = Literal[
    "DETERMINISTIC_RECOVERABLE",
    "AI_MULTIMODAL_RECOVERABLE",
    "HUMAN_REVIEW",
    "SOURCE_INSUFFICIENT",
]

AIRecoveryStatus = Literal["RECOVERED", "NOT_RECOVERABLE", "INCONCLUSIVE"]

RecoveryStatus = Literal[
    "PENDING",
    "DETERMINISTIC_RECOVERED",
    "AI_RECOVERED",
    "NOT_RECOVERABLE",
    "INCONCLUSIVE",
]

VerificationStatus = Literal[
    "PENDING",
    "VERIFIED",
    "FAILED",
    "HUMAN_REVIEW",
    "NOT_APPLICABLE",
    "INCONCLUSIVE",
]

ConsensusResult = Literal["UNANIMOUS", "MAJORITY", "DISAGREEMENT", "SINGLE_PROVIDER"]

SourceFidelityGrade = Literal["A", "B", "C", "D", "E", "INCONCLUSIVE"]

ValidationVerdict = Literal["PASS", "FAIL", "INCONCLUSIVE"]

RECOVERY_PROMPT_CONTRACT = """You are reconstructing an extracted NEET PYQ using supplied source evidence.
Use ONLY the supplied evidence.
Do not use general knowledge to fill missing words.
Do not invent question text.
Do not invent options.
Do not solve the question.
Do not rewrite the question for grammatical correctness.
Do not normalize scientific terminology unless the supplied source supports it.
Preserve the source wording as closely as possible.
If the evidence does not establish the missing content:
return INCONCLUSIVE or NOT_RECOVERABLE.
Your task is source reconstruction, not question generation.
Return strict JSON only."""


@dataclass
class TriageResult:
    question_id: str
    category: TriageCategory
    reason: str
    original_status: str
    missing_fields: list[str] = field(default_factory=list)
    known_defects: list[str] = field(default_factory=list)


@dataclass
class AIRecoveryOutput:
    status: AIRecoveryStatus
    stem: str = ""
    options: dict[str, str] = field(default_factory=dict)
    changed_fields: list[str] = field(default_factory=list)
    source_evidence_used: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    foreign_text_detected: bool = False
    confidence: float = 0.0
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stem": self.stem,
            "options": self.options,
            "changed_fields": self.changed_fields,
            "source_evidence_used": self.source_evidence_used,
            "uncertainties": self.uncertainties,
            "foreign_text_detected": self.foreign_text_detected,
            "confidence": self.confidence,
        }


@dataclass
class ProviderAttempt:
    provider: str
    model: str
    candidate_id: str
    attempt: int
    timestamp: str
    status: str
    request_id: str | None = None
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    output: AIRecoveryOutput | None = None


@dataclass
class RecoveryRecord:
    question_id: str
    source_evidence_hash: str
    recovery_request_hash: str
    original_status: str
    triage: dict[str, Any]
    evidence_package: dict[str, Any]
    providers: list[dict[str, Any]] = field(default_factory=list)
    recovery_status: RecoveryStatus = "PENDING"
    verification_status: VerificationStatus = "PENDING"
    consensus: ConsensusResult | None = None
    source_fidelity: SourceFidelityGrade = "INCONCLUSIVE"
    foreign_text_detected: bool = False
    changes: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    human_verified: bool = False
    recovered_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "source_evidence_hash": self.source_evidence_hash,
            "recovery_request_hash": self.recovery_request_hash,
            "original_status": self.original_status,
            "triage": self.triage,
            "providers": self.providers,
            "recovery_status": self.recovery_status,
            "verification_status": self.verification_status,
            "consensus": self.consensus,
            "source_fidelity": self.source_fidelity,
            "foreign_text_detected": self.foreign_text_detected,
            "changes": self.changes,
            "uncertainties": self.uncertainties,
            "human_verified": self.human_verified,
            "recovered_fields": self.recovered_fields,
        }
