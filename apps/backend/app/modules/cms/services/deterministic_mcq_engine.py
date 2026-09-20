"""Provider-free deterministic MCQ generation from explicit NCERT facts.

This module is pure with respect to application persistence: it calls no
provider and writes no database rows. Callers must supply a ready canonical
NCERT evidence pack and an explicit NEET-UG-2026 syllabus binding.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.modules.cms.services.fact_quality_gate import FactQualityResult
from app.modules.cms.services.factory_candidate_validation import (
    stem_hash,
    validate_candidate_body_detailed,
)
from app.modules.cms.services.factory_qa_gates import option_stem_hash
from app.modules.cms.services.ncert_claim_grounding import validate_ncert_claim_grounding
from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.cms.services.numerical_validation import classify_and_verify
from app.modules.cms.syllabus import assert_blueprint_neet_syllabus_scope
from app.modules.ingestion.services.ncert_canonical_source import (
    NcertSourceError,
    validate_ncert_generation_source,
)

ENGINE_VERSION = "python_mcq_engine_v1"
QuestionType = Literal[
    "DIRECT_FACT",
    "DEFINITION_IDENTIFICATION",
    "SI_UNIT_TERMINOLOGY",
    "CONTROLLED_NUMERICAL",
    "CONTROLLED_ASSOCIATION",
]

_WS = re.compile(r"\s+")
_NUMERICAL_RESULT_KEYS = {
    "v=u+at": "v",
    "v_avg": "v_avg",
    "v_rel": "v_ab",
    "projectile_R": "R",
    "vector_mag": "mag",
    "centripetal": "a_c",
    "F=ma": "F",
    "W=Fs": "W",
    "dK": "dK",
    "P=W/t": "P",
    "p_sum": "p",
    "f_max": "f_max",
    "x_cm": "x_cm",
    "tau=rF": "tau",
    "I=mr^2": "I",
}


def _normalise_evidence_text(value: str) -> str:
    return _WS.sub(" ", value or "").strip().casefold()


def _quote_is_present(quote: str, evidence_text: str) -> bool:
    needle = _normalise_evidence_text(quote)
    return bool(needle) and needle in _normalise_evidence_text(evidence_text)


@dataclass(frozen=True)
class EvidenceOption:
    key: str
    text: str
    evidence_quote: str


@dataclass(frozen=True)
class ExplicitChoiceSpec:
    fact_id: str
    question_type: Literal[
        "DIRECT_FACT",
        "DEFINITION_IDENTIFICATION",
        "SI_UNIT_TERMINOLOGY",
        "CONTROLLED_ASSOCIATION",
    ]
    stem: str
    stem_evidence_quote: str
    options: tuple[EvidenceOption, EvidenceOption, EvidenceOption, EvidenceOption]
    correct_key: str
    explanation: str
    explanation_evidence_quote: str
    difficulty: Literal["easy", "medium", "hard"] = "easy"


@dataclass(frozen=True)
class NumericalSpec:
    fact_id: str
    stem: str
    stem_evidence_quote: str
    calculation_check: dict
    correct_value: Decimal
    unit: str
    distractor_offsets: tuple[Decimal, Decimal, Decimal]
    formula_evidence_quote: str
    explanation: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_type: Literal["CONTROLLED_NUMERICAL"] = "CONTROLLED_NUMERICAL"


QuestionSpec = ExplicitChoiceSpec | NumericalSpec


@dataclass(frozen=True)
class DeterministicEvidenceContext:
    subject: str
    class_level: str
    chapter: str
    topic: str
    concept: str | None
    source_path: str
    constraints: dict
    provenance_tier: str
    evidence: NcertEvidencePack


@dataclass(frozen=True)
class DraftMcqCandidate:
    fact_id: str
    question_type: QuestionType
    status: Literal["DRAFT"]
    body: dict
    subject: str
    class_level: str
    chapter: str
    topic: str
    concept: str | None
    source_path: str
    source_relative_path: str
    evidence_pages: list[int]
    syllabus_binding: dict
    generation_method: str
    engine_version: str
    seed: int
    stem_hash: str
    option_stem_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SkippedCandidate:
    fact_id: str
    question_type: str
    reason: str
    details: list[str] = field(default_factory=list)


@dataclass
class DeterministicGenerationResult:
    attempted: int
    candidates: list[DraftMcqCandidate] = field(default_factory=list)
    skipped: list[SkippedCandidate] = field(default_factory=list)
    source_gate_failures: int = 0
    syllabus_gate_failures: int = 0
    validation_failures: int = 0
    duplicate_failures: int = 0
    numerical_failures: int = 0
    provider_api_calls: int = 0

    @property
    def created(self) -> int:
        return len(self.candidates)


class DeterministicMcqEngine:
    """Construct validated in-memory DRAFTs from explicit evidence-bound specs."""

    def generate_eligible(
        self,
        context: DeterministicEvidenceContext,
        specs: list[QuestionSpec],
        *,
        quality_results: dict[str, FactQualityResult],
        seed: int,
        existing_stem_hashes: set[str] | None = None,
        existing_option_stem_hashes: set[str] | None = None,
    ) -> DeterministicGenerationResult:
        """Generate only specs explicitly approved and MCQ-eligible by the fact gate."""
        eligible: list[QuestionSpec] = []
        skipped: list[SkippedCandidate] = []
        for spec in specs:
            quality = quality_results.get(spec.fact_id)
            if quality is None:
                skipped.append(
                    SkippedCandidate(
                        spec.fact_id,
                        spec.question_type,
                        "FACT_QUALITY_REVIEW_REQUIRED",
                        ["missing fact-quality result"],
                    )
                )
            elif not quality.mcq_eligible:
                skipped.append(
                    SkippedCandidate(
                        spec.fact_id,
                        spec.question_type,
                        "FACT_QUALITY_REJECTED"
                        if quality.status == "FACT_REJECTED"
                        else "FACT_QUALITY_REVIEW_REQUIRED",
                        [reason.code for reason in quality.reasons],
                    )
                )
            else:
                eligible.append(spec)

        generated = self.generate(
            context,
            eligible,
            seed=seed,
            existing_stem_hashes=existing_stem_hashes,
            existing_option_stem_hashes=existing_option_stem_hashes,
        )
        generated.attempted = len(specs)
        generated.skipped = skipped + generated.skipped
        generated.validation_failures += len(skipped)
        return generated

    def generate(
        self,
        context: DeterministicEvidenceContext,
        specs: list[QuestionSpec],
        *,
        seed: int,
        existing_stem_hashes: set[str] | None = None,
        existing_option_stem_hashes: set[str] | None = None,
    ) -> DeterministicGenerationResult:
        result = DeterministicGenerationResult(attempted=len(specs))
        existing_stems = set(existing_stem_hashes or set())
        existing_option_stems = set(existing_option_stem_hashes or set())

        try:
            source = validate_ncert_generation_source(context.source_path)
        except (NcertSourceError, OSError, RuntimeError) as exc:
            result.source_gate_failures = len(specs)
            result.skipped.extend(
                SkippedCandidate(
                    spec.fact_id,
                    spec.question_type,
                    "SOURCE_GATE_FAILED",
                    [getattr(exc, "code", type(exc).__name__)],
                )
                for spec in specs
            )
            return result

        syllabus = assert_blueprint_neet_syllabus_scope(
            context.constraints,
            academic_subject_code=context.subject,
        )
        if not syllabus.is_in_scope:
            result.syllabus_gate_failures = len(specs)
            result.skipped.extend(
                SkippedCandidate(
                    spec.fact_id,
                    spec.question_type,
                    "SYLLABUS_GATE_FAILED",
                    [syllabus.status, *syllabus.reasons],
                )
                for spec in specs
            )
            return result

        evidence = context.evidence
        evidence_source_matches = False
        if evidence.pdf_path:
            try:
                evidence_source_matches = (
                    source.resolved_path
                    == validate_ncert_generation_source(evidence.pdf_path).resolved_path
                )
            except (NcertSourceError, OSError, RuntimeError):
                evidence_source_matches = False
        if (
            not evidence.is_ready
            or not evidence.evidence_text.strip()
            or not evidence_source_matches
        ):
            result.source_gate_failures = len(specs)
            result.skipped.extend(
                SkippedCandidate(
                    spec.fact_id,
                    spec.question_type,
                    "NCERT_EVIDENCE_NOT_READY",
                    [evidence.status, evidence.detail or ""],
                )
                for spec in specs
            )
            return result

        for spec in specs:
            candidate_or_skip = self._generate_one(
                context,
                source.relative_posix,
                syllabus.to_dict(),
                spec,
                seed=seed,
            )
            if isinstance(candidate_or_skip, SkippedCandidate):
                result.skipped.append(candidate_or_skip)
                self._count_skip(result, candidate_or_skip)
                continue

            candidate = candidate_or_skip
            if candidate.stem_hash in existing_stems:
                skip = SkippedCandidate(
                    spec.fact_id,
                    spec.question_type,
                    "DUPLICATE_STEM",
                    [candidate.stem_hash],
                )
                result.skipped.append(skip)
                result.duplicate_failures += 1
                continue
            if candidate.option_stem_hash in existing_option_stems:
                skip = SkippedCandidate(
                    spec.fact_id,
                    spec.question_type,
                    "DUPLICATE_OPTION_STEM",
                    [candidate.option_stem_hash],
                )
                result.skipped.append(skip)
                result.duplicate_failures += 1
                continue

            existing_stems.add(candidate.stem_hash)
            existing_option_stems.add(candidate.option_stem_hash)
            result.candidates.append(candidate)
        return result

    @staticmethod
    def _count_skip(
        result: DeterministicGenerationResult,
        skipped: SkippedCandidate,
    ) -> None:
        if skipped.reason.startswith("NUMERICAL"):
            result.numerical_failures += 1
        elif skipped.reason.startswith("DUPLICATE"):
            result.duplicate_failures += 1
        elif skipped.reason.startswith("SOURCE") or skipped.reason.startswith("NCERT"):
            result.source_gate_failures += 1
        else:
            result.validation_failures += 1

    def _generate_one(
        self,
        context: DeterministicEvidenceContext,
        source_relative_path: str,
        syllabus_binding: dict,
        spec: QuestionSpec,
        *,
        seed: int,
    ) -> DraftMcqCandidate | SkippedCandidate:
        if isinstance(spec, NumericalSpec):
            built = self._build_numerical(context, spec, seed=seed)
        else:
            built = self._build_explicit_choice(context, spec, seed=seed)
        if isinstance(built, SkippedCandidate):
            return built

        detailed = validate_candidate_body_detailed(
            built,
            expected_difficulty=spec.difficulty,
            constraints=context.constraints,
        )
        if not detailed["ok"] or detailed["body"] is None:
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "VALIDATION_FAILED",
                list(detailed["errors"]),
            )
        body = detailed["body"]
        grounding = validate_ncert_claim_grounding(body, context.evidence)
        if not grounding.ok:
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "NCERT_GROUNDING_FAILED",
                grounding.error_codes,
            )

        sh = stem_hash(body["stem"])
        osh = option_stem_hash(body["stem"], body["options"])
        return DraftMcqCandidate(
            fact_id=spec.fact_id,
            question_type=spec.question_type,
            status="DRAFT",
            body=body,
            subject=context.subject,
            class_level=context.class_level,
            chapter=context.chapter,
            topic=context.topic,
            concept=context.concept,
            source_path=context.source_path,
            source_relative_path=source_relative_path,
            evidence_pages=list(context.evidence.page_numbers),
            syllabus_binding=syllabus_binding,
            generation_method="deterministic_python",
            engine_version=ENGINE_VERSION,
            seed=seed,
            stem_hash=sh,
            option_stem_hash=osh,
        )

    def _build_explicit_choice(
        self,
        context: DeterministicEvidenceContext,
        spec: ExplicitChoiceSpec,
        *,
        seed: int,
    ) -> dict | SkippedCandidate:
        evidence_text = context.evidence.evidence_text
        quotes = [
            spec.stem_evidence_quote,
            spec.explanation_evidence_quote,
            *(option.evidence_quote for option in spec.options),
        ]
        missing = [quote for quote in quotes if not _quote_is_present(quote, evidence_text)]
        if missing:
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "NCERT_EXPLICIT_FACT_MISSING",
                [quote[:120] for quote in missing],
            )

        keys = [option.key for option in spec.options]
        if len(set(keys)) != 4 or spec.correct_key not in keys:
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "INVALID_EXPLICIT_OPTIONS",
            )

        ordered = list(spec.options)
        rng = random.Random(
            hashlib.sha256(f"{seed}:{spec.fact_id}".encode()).hexdigest()
        )
        rng.shuffle(ordered)
        labels = ("A", "B", "C", "D")
        options = [
            {"label": label, "text": option.text}
            for label, option in zip(labels, ordered, strict=True)
        ]
        correct_label = next(
            label
            for label, option in zip(labels, ordered, strict=True)
            if option.key == spec.correct_key
        )
        return self._base_body(
            context,
            stem=spec.stem,
            options=options,
            correct_option=correct_label,
            explanation=spec.explanation,
            difficulty=spec.difficulty,
            source_excerpt=spec.explanation_evidence_quote,
        )

    def _build_numerical(
        self,
        context: DeterministicEvidenceContext,
        spec: NumericalSpec,
        *,
        seed: int,
    ) -> dict | SkippedCandidate:
        evidence_text = context.evidence.evidence_text
        missing = [
            quote
            for quote in (spec.stem_evidence_quote, spec.formula_evidence_quote)
            if not _quote_is_present(quote, evidence_text)
        ]
        if missing:
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "NCERT_EXPLICIT_FACT_MISSING",
                [quote[:120] for quote in missing],
            )

        numerical_status, detail = classify_and_verify(spec.calculation_check)
        if numerical_status != "NUMERICAL_COMPLETE":
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "NUMERICAL_RECOMPUTE_FAILED",
                [numerical_status, detail],
            )
        formula = str(spec.calculation_check.get("formula") or "")
        result_key = _NUMERICAL_RESULT_KEYS.get(formula)
        try:
            recomputed = Decimal(str(spec.calculation_check[result_key])) if result_key else None
        except (KeyError, InvalidOperation):
            recomputed = None
        if recomputed is None or recomputed != spec.correct_value:
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "NUMERICAL_ANSWER_MISMATCH",
                [f"declared={spec.correct_value}", f"recomputed={recomputed}"],
            )

        values = [spec.correct_value]
        values.extend(spec.correct_value + offset for offset in spec.distractor_offsets)
        if len(set(values)) != 4:
            return SkippedCandidate(
                spec.fact_id,
                spec.question_type,
                "NUMERICAL_AMBIGUOUS_OPTIONS",
            )
        rendered = [(value, f"{self._format_decimal(value)} {spec.unit}") for value in values]
        rng = random.Random(
            hashlib.sha256(f"{seed}:{spec.fact_id}".encode()).hexdigest()
        )
        rng.shuffle(rendered)
        labels = ("A", "B", "C", "D")
        options = [
            {"label": label, "text": text}
            for label, (_value, text) in zip(labels, rendered, strict=True)
        ]
        correct_label = next(
            label
            for label, (value, _text) in zip(labels, rendered, strict=True)
            if value == spec.correct_value
        )
        body = self._base_body(
            context,
            stem=spec.stem,
            options=options,
            correct_option=correct_label,
            explanation=spec.explanation,
            difficulty=spec.difficulty,
            source_excerpt=spec.formula_evidence_quote,
        )
        body["calculation_check"] = dict(spec.calculation_check)
        body["numerical_evidence"] = {
            "status": "NUMERICAL_COMPLETE",
            "given": {
                key: value
                for key, value in spec.calculation_check.items()
                if key not in {"formula", result_key}
            },
            "formula": formula,
            "substitution": spec.explanation,
            "result": str(spec.correct_value),
            "unit": spec.unit,
            "correct_option": correct_label,
            "calculation_check": dict(spec.calculation_check),
        }
        return body

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        rendered = format(value, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered

    @staticmethod
    def _base_body(
        context: DeterministicEvidenceContext,
        *,
        stem: str,
        options: list[dict],
        correct_option: str,
        explanation: str,
        difficulty: str,
        source_excerpt: str,
    ) -> dict:
        evidence = context.evidence
        return {
            "stem": stem,
            "options": options,
            "correct_option": correct_option,
            "explanation": explanation,
            "difficulty": difficulty,
            "bloom_level": "remember" if difficulty == "easy" else "apply",
            "ncert_evidence": {
                "verification_level": "SOURCE_TEXT_VERIFIED",
                "source_document": evidence.relative_posix or context.source_path,
                "class_level": context.class_level,
                "chapter": context.chapter,
                "section": evidence.section_heading,
                "page_number": None,
                "source_excerpt": source_excerpt,
                "verification_method": "deterministic_python_explicit_quote",
                "source_pdf_relpath": evidence.relative_posix,
            },
            "provenance": {
                "origin": "deterministic_python",
                "source": "canonical_ncert",
                "validation_process": "python_mcq_engine_v1",
                "verification_process": "generated_not_independently_ncert_certified",
                "class_level": context.class_level,
                "chapter": context.chapter,
                "section": evidence.section_heading,
            },
        }
