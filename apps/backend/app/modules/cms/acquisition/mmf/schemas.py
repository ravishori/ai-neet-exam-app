"""Versioned candidate + generation-batch contracts for MMF."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CANDIDATE_SCHEMA_VERSION = "mmf_candidate_v1"
CANDIDATE_SCHEMA_VERSION_V2 = "mmf_candidate_v2"
BATCH_SCHEMA_VERSION = "mmf_batch_v1"

QUESTION_PATTERNS = frozenset(
    {
        "DIRECT",
        "FACTUAL",
        "CONCEPTUAL",
        "STATEMENT_BASED",
        "COMPARISON",
        "APPLICATION",
        "MULTI_STATEMENT",
        "OTHER_SUPPORTED_TYPES",
        "conceptual",
        "factual",
        "application",
        "statement_based",
        "comparison",
        "assertion_reasoning",
        "match_relationship",
        "numerical",
    }
)


class CandidateStatus(StrEnum):
    GENERATED = "GENERATED"
    NORMALIZED = "NORMALIZED"
    VALID = "VALID"
    INVALID = "INVALID"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    SEMANTIC_DUPLICATE = "SEMANTIC_DUPLICATE"
    VALID_VARIANT = "VALID_VARIANT"
    REJECTED = "REJECTED"
    READY_FOR_DRAFT_IMPORT = "READY_FOR_DRAFT_IMPORT"


class GenerationBatchStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CandidateOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    A: str = Field(min_length=1)
    B: str = Field(min_length=1)
    C: str = Field(min_length=1)
    D: str = Field(min_length=1)


class CandidateProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["ai_generated"] = "ai_generated"
    generation_source: str = "supplied_source_material"
    validation_process: str = "UNVERIFIED_CANDIDATE"
    provider: str
    model: str
    prompt_version: str
    batch_id: str
    contract_version: str | None = None


class CandidateRecord(BaseModel):
    """File-based AI candidate — never a ContentItem."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = CANDIDATE_SCHEMA_VERSION
    candidate_id: str = Field(min_length=8, max_length=128)
    generation_batch_id: str
    provider: str
    model: str
    model_version: str | None = None
    generated_at: datetime
    source_document: str
    source_sha256: str = Field(min_length=64, max_length=64)
    contract_version: str | None = None
    subject: str
    class_level: str = Field(alias="class")
    chapter: str
    topic: str
    concept: str
    question_type: str
    question_pattern: str | None = None
    difficulty: Literal["easy", "medium", "hard"]
    stem: str = Field(min_length=1)
    options: CandidateOptions
    correct_answer: Literal["A", "B", "C", "D"]
    explanation: str = Field(min_length=1)
    source_evidence: str = Field(min_length=1)
    provenance: CandidateProvenance
    prompt_version: str
    status: CandidateStatus = CandidateStatus.GENERATED
    fingerprint: str | None = None
    duplicate_of: str | None = None
    duplicate_reason: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    # Contract V2 optional overlays — declared metadata is never authoritative.
    # Existing v1 POC artifacts omit these fields; validators compute audits externally.
    declared_question_type: str | None = None
    audited_question_type: str | None = None
    question_type_audit_status: Literal["MATCH", "MISMATCH"] | None = None
    question_type_mismatch_reason: str | None = None
    declared_difficulty: Literal["easy", "medium", "hard"] | None = None
    audited_difficulty: Literal["EASY", "MEDIUM", "HARD", "UNCERTAIN"] | None = None
    difficulty_agreement: bool | None = None
    concept_status: Literal["RESOLVED", "UNRESOLVED"] | None = None

    @field_validator("source_sha256")
    @classmethod
    def _sha_hex(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("source_sha256 must be 64 hex chars")
        return v.lower()

    @field_validator("provider_metadata")
    @classmethod
    def _no_secrets_in_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        banned = ("api_key", "apikey", "authorization", "secret", "password", "token")
        for key in v:
            lk = str(key).lower()
            if any(b in lk for b in banned):
                raise ValueError(f"provider_metadata must not contain secret key: {key}")
            val = v[key]
            if isinstance(val, str) and any(b in val.lower() for b in ("sk-", "api_key=")):
                raise ValueError("provider_metadata value looks like a secret")
        return v

    @model_validator(mode="after")
    def _provenance_align(self) -> CandidateRecord:
        if self.provenance.batch_id != self.generation_batch_id:
            raise ValueError("provenance.batch_id must match generation_batch_id")
        if self.provenance.provider != self.provider:
            raise ValueError("provenance.provider must match provider")
        if self.provenance.prompt_version != self.prompt_version:
            raise ValueError("provenance.prompt_version must match prompt_version")
        if not self.question_pattern:
            object.__setattr__(
                self,
                "question_pattern",
                self.question_type.upper() if self.question_type.islower() else self.question_type,
            )
        return self


class ProviderAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    enabled: bool = False
    model: str | None = None
    requested_count: int = Field(ge=0)


class DifficultyTargets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    easy: float = Field(default=0.25, ge=0.0, le=1.0)
    medium: float = Field(default=0.50, ge=0.0, le=1.0)
    hard: float = Field(default=0.25, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _sum_one(self) -> DifficultyTargets:
        total = self.easy + self.medium + self.hard
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"difficulty targets must sum to 1.0, got {total}")
        return self


class GenerationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = BATCH_SCHEMA_VERSION
    batch_id: str
    source_sha256: str
    source_path: str
    source_reference: str | None = None
    subject: str
    class_level: str = Field(alias="class")
    chapter: str
    requested_candidate_count: int = Field(ge=0)
    providers: list[ProviderAllocation]
    prompt_version: str
    difficulty_targets: DifficultyTargets = Field(default_factory=DifficultyTargets)
    created_at: datetime
    status: GenerationBatchStatus = GenerationBatchStatus.PLANNED
    live_generation_enabled: bool = False
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _allocation_sum(self) -> GenerationBatch:
        total = sum(p.requested_count for p in self.providers)
        if total != self.requested_candidate_count:
            raise ValueError(
                f"provider allocation sum {total} != requested_candidate_count {self.requested_candidate_count}"
            )
        return self
