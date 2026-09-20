"""Shared fixtures for Phase D pilot tests (ADR-0032).

Layer A (integration): controlled section text + AI responses that pass the
real ``check_grounding`` gate — never bypass grounding in production code.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

from app.modules.ai.gateway.base import AIResponse
from app.modules.ingestion.services.pdf_extraction_service import ExtractedSection

# Vocabulary aligned with test_knowledge_structuring.py — passes real check_grounding.
MOCK_SECTION_HEADING = "3.4 OHM'S LAW"
MOCK_SECTION_PAGE = 3
MOCK_SECTION_TEXT = (
    "Ohm's Law states that the current through a conductor is directly proportional to the "
    "potential difference across it, provided the temperature remains constant. This is "
    "written V = IR, where R is the resistance of the conductor in ohms."
)

MOCK_STRUCTURED_FACTS = [
    "Current through a conductor is proportional to potential difference across it.",
]
MOCK_KU_SUMMARY = "Ohm's Law relates current and voltage in a conductor at constant temperature."

MCQ_JSON = (
    '[{"stem": "According to Ohm\'s Law, current through a conductor is proportional to what?", '
    '"options": [{"label": "A", "text": "Potential difference"}, {"label": "B", "text": "Resistance only"}, '
    '{"label": "C", "text": "Temperature"}, {"label": "D", "text": "Charge"}], '
    '"correct_option": "A", "explanation": "From the source section.", '
    '"difficulty": "easy", "bloom_level": "recall"}]'
)
CONCEPT_NOTE_JSON = '{"summary": "Ohm\'s Law relates current and potential difference.", "sections": ["V = IR"]}'
REVISION_SHEET_JSON = '{"formulas": ["Ohms Law: V = IR"]}'
FLASHCARD_JSON = '[{"front": "State Ohm\'s Law", "back": "V = IR"}]'
EVALUATOR_JSON = '{"concerns": "", "flags": [], "confidence": 0.9}'


def mock_extraction_patch(
    *,
    section_text: str = MOCK_SECTION_TEXT,
    heading: str = MOCK_SECTION_HEADING,
    source_page: int = MOCK_SECTION_PAGE,
) -> tuple[Callable, Callable]:
    section = ExtractedSection(heading=heading, source_page=source_page, text=section_text)

    def fake_extract_pages(_file_path: str) -> list[str]:
        return [section_text]

    def fake_split_into_sections(_pages: list[str]) -> list[ExtractedSection]:
        return [section]

    return fake_extract_pages, fake_split_into_sections


def mock_empty_visual_assets(*_args, **_kwargs) -> list:
    return []


def knowledge_structuring_response(*, section_text: str | None = None) -> str:
    """AI JSON whose facts overlap the mock (or supplied) section text."""
    _ = section_text  # facts are pre-validated against MOCK_SECTION_TEXT
    return json.dumps(
        {
            "structured_facts": MOCK_STRUCTURED_FACTS,
            "summary": MOCK_KU_SUMMARY,
            "extraction_confidence": 0.95,
        }
    )


def pilot_ai_gateway_factory(*, mcq_json: str = MCQ_JSON) -> Callable:
    async def fake_generate(self, *, agent_type, **kwargs):
        if agent_type == "KNOWLEDGE_STRUCTURING":
            return AIResponse(
                text=knowledge_structuring_response(),
                model="test-model",
                prompt_tokens=50,
                completion_tokens=50,
                is_fallback=False,
                cost_usd=0.001,
            )
        if agent_type == "INGESTION_MCQ":
            return AIResponse(
                text=mcq_json,
                model="test-model",
                prompt_tokens=50,
                completion_tokens=50,
                is_fallback=False,
                cost_usd=0.001,
            )
        if agent_type == "INGESTION_CONCEPT_NOTE":
            return AIResponse(
                text=CONCEPT_NOTE_JSON,
                model="test-model",
                prompt_tokens=50,
                completion_tokens=50,
                is_fallback=False,
                cost_usd=0.001,
            )
        if agent_type == "INGESTION_REVISION_SHEET":
            return AIResponse(
                text=REVISION_SHEET_JSON,
                model="test-model",
                prompt_tokens=50,
                completion_tokens=50,
                is_fallback=False,
                cost_usd=0.001,
            )
        if agent_type == "INGESTION_FLASHCARDS":
            return AIResponse(
                text=FLASHCARD_JSON,
                model="test-model",
                prompt_tokens=50,
                completion_tokens=50,
                is_fallback=False,
                cost_usd=0.001,
            )
        if agent_type == "EVALUATOR":
            return AIResponse(
                text=EVALUATOR_JSON,
                model="test-model",
                prompt_tokens=50,
                completion_tokens=50,
                is_fallback=False,
                cost_usd=0.001,
            )
        return AIResponse(
            text="[]",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=10,
            is_fallback=False,
            cost_usd=0.0,
        )

    return fake_generate


def unique_pilot_run_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
