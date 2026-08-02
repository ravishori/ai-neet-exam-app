import hashlib
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.academic.models import Concept
from app.modules.ai.gateway.ai_gateway import AIGateway
from app.modules.ai.services.json_utils import parse_json_response
from app.modules.ingestion.models import IngestionSection
from app.modules.ingestion.services.language_service import clean_text
from app.modules.knowledge.models import KnowledgeUnit
from app.modules.knowledge.prompts import knowledge_structuring
from app.modules.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.modules.knowledge.services.grounding_check import check_grounding

logger = get_logger("knowledge")

MAX_SECTION_CHARS_IN_PROMPT = 8000


def _content_hash(structured_facts: list[str]) -> str:
    canonical = json.dumps(structured_facts, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class KnowledgeStructuringService:
    """Turns one ingested section's raw text into a versioned, gate-checked
    Knowledge Unit — see ADR-0024. Deliberately does not touch generation;
    the four existing content generators are untouched by this service."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = KnowledgeRepository(session)
        self.gateway = AIGateway(session)

    async def structure_section(
        self, *, section: IngestionSection, concept: Concept, author_id: uuid.UUID
    ) -> KnowledgeUnit | None:
        """Returns the created KnowledgeUnit (PASSED or FAILED) — never None
        unless the AI call itself produced nothing usable (fallback mode or
        unparseable JSON), in which case no row is created at all rather
        than recording a unit with no real content to gate-check."""
        # clean_text (ADR-0027) is applied here, at use time, rather than to
        # the stored raw_text — punctuation/OCR-artifact normalization helps
        # the model read the source cleanly without rewriting the citation
        # text section.raw_text is kept as (see IngestionSection docstring).
        user_prompt = knowledge_structuring.build_prompt(
            concept_name=concept.name,
            section_heading=section.heading,
            source_text=clean_text(section.raw_text)[:MAX_SECTION_CHARS_IN_PROMPT],
            source_page=section.source_page,
        )
        response = await self.gateway.generate(
            agent_type="KNOWLEDGE_STRUCTURING",
            system_prompt=knowledge_structuring.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=author_id,
            max_tokens=1200,
        )
        if response.is_fallback:
            logger.info("knowledge_structuring_fallback", section=section.heading)
            return None

        try:
            extracted = parse_json_response(response.text)
        except ValueError as exc:
            logger.error("knowledge_structuring_bad_json", section=section.heading, error=str(exc), raw=response.text[:200])
            return None

        structured_facts = extracted.get("structured_facts", [])
        summary = extracted.get("summary", "")
        model_confidence = float(extracted.get("extraction_confidence", 0.0))

        grounded, grounding_detail = check_grounding(structured_facts, section.raw_text)

        duplicate = None
        if grounded and summary:
            duplicate = await self.repo.find_duplicate(concept.id, summary)

        if not grounded:
            status, detail = "FAILED", grounding_detail
        elif duplicate:
            status, detail = "FAILED", f"duplicate of existing knowledge unit {duplicate.id}"
        else:
            status, detail = "PASSED", None

        unit = KnowledgeUnit(
            version=1,
            content_hash=_content_hash(structured_facts),
            structured_facts=structured_facts,
            summary=summary,
            source_section_id=section.id,
            concept_id=concept.id,
            extraction_confidence=model_confidence,
            validation_status=status,
            validation_detail=detail,
        )
        self.repo.add(unit)
        await self.repo.commit()

        logger.info(
            "knowledge_unit_created",
            unit_id=str(unit.id),
            concept=concept.name,
            status=status,
            detail=detail,
        )
        return unit
