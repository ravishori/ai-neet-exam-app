"""Typed reviewed-fact adapter for the deterministic MCQ engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.modules.cms.schemas.deterministic_fact_pack import DeterministicFact
from app.modules.cms.services.deterministic_mcq_engine import (
    EvidenceOption,
    ExplicitChoiceSpec,
)
from app.modules.cms.services.fact_quality_gate import (
    FactQualityGate,
    FactQualityResult,
    OptionDefensibility,
    QuestionConstruction,
    TaxonomyBinding,
)


class FactAdapterError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AdaptedFactQuestion:
    fact_id: str
    spec: ExplicitChoiceSpec
    quality: FactQualityResult
    source_pdf: str
    source_relative_path: str
    syllabus_binding: dict
    chapter_id: str
    chapter: str
    topic_id: str
    topic: str
    concept_id: str | None
    concept_name: str | None
    provenance: dict


class DeterministicFactToQuestionAdapter:
    """Run the quality gate and map an eligible reviewed fact to an engine spec."""

    def __init__(self, quality_gate: FactQualityGate | None = None) -> None:
        self.quality_gate = quality_gate or FactQualityGate()

    def adapt(
        self,
        fact: DeterministicFact,
        *,
        taxonomy: TaxonomyBinding,
        authoritative_syllabus_path: str | Path,
        source_root: Path | None = None,
    ) -> AdaptedFactQuestion:
        template = fact.question_template
        if template is None:
            raise FactAdapterError(
                "QUESTION_TEMPLATE_MISSING",
                f"{fact.fact_id} has no typed question template",
            )
        if not (fact.evidence_text or "").strip():
            raise FactAdapterError("EVIDENCE_MISSING", f"{fact.fact_id} has no evidence")
        if template.transformation not in fact.allowed_transformations:
            raise FactAdapterError(
                "TRANSFORMATION_UNSAFE",
                f"{template.transformation} is not declared by {fact.fact_id}",
            )

        construction = QuestionConstruction(
            stem=template.stem,
            transformation=template.transformation,
            correct_key=template.correct_key,
            options=tuple(
                OptionDefensibility(
                    key=option.key,
                    text=option.text,
                    evidence_quote=option.evidence_quote,
                    relation_to_stem=option.relation_to_stem,
                )
                for option in template.options
            ),
        )
        quality = self.quality_gate.evaluate(
            fact,
            taxonomy=taxonomy,
            authoritative_syllabus_path=authoritative_syllabus_path,
            question=construction,
            source_root=source_root,
        )
        if quality.fact_id != fact.fact_id:
            raise FactAdapterError(
                "FACT_QUALITY_ID_MISMATCH",
                "quality result is not bound to the adapted fact",
            )
        if not quality.mcq_eligible or quality.status != "FACT_APPROVED":
            codes = [reason.code for reason in quality.reasons]
            raise FactAdapterError(
                "FACT_NOT_MCQ_ELIGIBLE",
                f"{fact.fact_id}: {','.join(codes) or quality.status}",
            )

        spec = ExplicitChoiceSpec(
            fact_id=fact.fact_id,
            question_type=template.question_type,
            stem=template.stem,
            stem_evidence_quote=template.stem_evidence_quote,
            options=tuple(
                EvidenceOption(
                    key=option.key,
                    text=option.text,
                    evidence_quote=option.evidence_quote,
                )
                for option in template.options
            ),
            correct_key=template.correct_key,
            explanation=template.explanation,
            explanation_evidence_quote=template.explanation_evidence_quote,
            difficulty=template.difficulty,
        )
        return AdaptedFactQuestion(
            fact_id=fact.fact_id,
            spec=spec,
            quality=quality,
            source_pdf=fact.source_pdf,
            source_relative_path=fact.source_relative_path,
            syllabus_binding=fact.syllabus_binding.model_dump(exclude_none=True),
            chapter_id=fact.chapter_id,
            chapter=fact.chapter,
            topic_id=fact.topic_id,
            topic=fact.topic,
            concept_id=fact.concept_id,
            concept_name=fact.concept_name,
            provenance=fact.provenance.model_dump(exclude_none=True),
        )

    def adapt_many(
        self,
        facts: tuple[DeterministicFact, ...] | list[DeterministicFact],
        *,
        taxonomy: TaxonomyBinding,
        authoritative_syllabus_path: str | Path,
        source_root: Path | None = None,
        max_items: int = 5,
    ) -> tuple[AdaptedFactQuestion, ...]:
        ordered = sorted(facts, key=lambda fact: fact.fact_id)
        if len(ordered) > max_items:
            raise FactAdapterError(
                "FACT_PACK_LIMIT_EXCEEDED",
                f"{len(ordered)} facts exceeds adapter limit {max_items}",
            )
        return tuple(
            self.adapt(
                fact,
                taxonomy=taxonomy,
                authoritative_syllabus_path=authoritative_syllabus_path,
                source_root=source_root,
            )
            for fact in ordered
        )
