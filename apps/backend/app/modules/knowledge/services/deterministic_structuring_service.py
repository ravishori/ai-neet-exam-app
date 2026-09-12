"""Deterministic Knowledge Unit structuring — no AI provider calls.

Used by FACTORY-S1 source ingestion: splits section text into grounded
sentence-facts and runs the same mechanical grounding gate as ADR-0024.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.academic.models import Concept
from app.modules.ingestion.models import IngestionSection
from app.modules.ingestion.services.language_service import clean_text
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.modules.knowledge.services.grounding_check import check_grounding

logger = get_logger("knowledge.deterministic")

MIN_FACT_CHARS = 40
MAX_FACTS = 8
SUMMARY_MAX_CHARS = 500

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _content_hash(structured_facts: list[str]) -> str:
    canonical = json.dumps(structured_facts, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def extract_facts_from_section_text(text: str, *, max_facts: int = MAX_FACTS) -> list[str]:
    """Split cleaned section text into sentence-level facts."""
    cleaned = clean_text(text)
    if not cleaned.strip():
        return []
    sentences = _SENTENCE_SPLIT.split(cleaned)
    facts: list[str] = []
    for sentence in sentences:
        s = sentence.strip()
        if len(s) >= MIN_FACT_CHARS:
            facts.append(s)
        if len(facts) >= max_facts:
            break
    if not facts and len(cleaned.strip()) >= MIN_FACT_CHARS:
        facts.append(cleaned.strip()[:1200])
    return facts


def build_summary(facts: list[str], heading: str) -> str:
    if facts:
        joined = " ".join(facts[:2])
        return joined[:SUMMARY_MAX_CHARS]
    return heading[:SUMMARY_MAX_CHARS]


class DeterministicStructuringService:
    """Creates gate-checked KnowledgeUnits without calling AIGateway."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = KnowledgeRepository(session)

    async def structure_section(
        self,
        *,
        section: IngestionSection,
        concept: Concept,
        author_id: uuid.UUID | None = None,
    ) -> KnowledgeUnit | None:
        del author_id  # deterministic path — no AI audit actor required
        structured_facts = extract_facts_from_section_text(section.raw_text)
        if not structured_facts:
            logger.info("deterministic_structuring_no_facts", section=section.heading)
            return None

        summary = build_summary(structured_facts, section.heading)
        grounded, grounding_detail = check_grounding(structured_facts, section.raw_text)

        duplicate = await self.repo.find_duplicate(concept.id, summary) if grounded else None
        if duplicate:
            unit = KnowledgeUnit(
                version=duplicate.version,
                content_hash=duplicate.content_hash,
                structured_facts=list(duplicate.structured_facts),
                summary=duplicate.summary,
                source_section_id=section.id,
                concept_id=concept.id,
                extraction_confidence=duplicate.extraction_confidence,
                validation_status="FAILED",
                validation_detail=f"duplicate of existing knowledge unit {duplicate.id}",
            )
            self.repo.add(unit)
            await self.repo.commit()
            return unit

        status = "PASSED" if grounded else "FAILED"
        detail = grounding_detail if not grounded else None

        unit = KnowledgeUnit(
            version=1,
            content_hash=_content_hash(structured_facts),
            structured_facts=structured_facts,
            summary=summary,
            source_section_id=section.id,
            concept_id=concept.id,
            extraction_confidence=0.85,
            validation_status=status,
            validation_detail=detail,
        )
        self.repo.add(unit)
        await self.repo.commit()
        logger.info(
            "deterministic_knowledge_unit_created",
            unit_id=str(unit.id),
            concept=concept.name,
            status=status,
        )
        return unit
