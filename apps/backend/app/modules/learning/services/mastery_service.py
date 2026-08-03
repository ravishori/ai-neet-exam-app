import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.models import ConceptMastery, KnowledgeUnitMastery, MicroCompetencyMastery
from app.modules.learning.repositories.mastery_repository import MasteryRepository

MASTERY_ATTEMPT_FLOOR = 3
MASTERY_SCORE_THRESHOLD = 80

# Simplified spaced repetition — see ADR-0016. No ease factor, no history:
# the schedule is just "how soon should this mastery_level resurface".
REVIEW_INTERVAL_DAYS = {"LEARNING": 1, "PRACTICING": 3, "MASTERED": 7}


def compute_mastery(attempts_count: int, correct_count: int) -> tuple[int, str]:
    if attempts_count == 0:
        return 0, "NOT_STARTED"

    score = round(100 * correct_count / attempts_count)

    if attempts_count < MASTERY_ATTEMPT_FLOOR:
        return score, "LEARNING"
    if score >= MASTERY_SCORE_THRESHOLD:
        return score, "MASTERED"
    return score, "PRACTICING"


def next_review_at_for(level: str) -> datetime | None:
    interval_days = REVIEW_INTERVAL_DAYS.get(level)
    if interval_days is None:
        return None
    return datetime.now(UTC) + timedelta(days=interval_days)


class MasteryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MasteryRepository(session)

    async def recompute_for_content_items(self, user_id: uuid.UUID, content_item_ids: list[uuid.UUID]) -> None:
        # Micro-competencies first (ADR-0021) — concept-level rollup below
        # reads their just-recomputed mastery for any concept that has them.
        micro_competency_ids = await self.repo.micro_competency_ids_for_content_items(content_item_ids)
        for mc_id in micro_competency_ids:
            await self._recompute_micro_competency(user_id, mc_id)

        concept_ids = await self.repo.concept_ids_for_content_items(content_item_ids)
        for concept_id in concept_ids:
            await self._recompute_one(user_id, concept_id)

        # Knowledge-Unit-grained mastery (ADR-0028 Phase D) — independent of
        # the concept/micro-competency rollups above, not a replacement for
        # either. A content item with no Knowledge Unit lineage (pre-ADR-0024
        # seeded questions) simply contributes nothing here.
        knowledge_unit_ids = await self.repo.knowledge_unit_ids_for_content_items(content_item_ids)
        for knowledge_unit_id in knowledge_unit_ids:
            await self._recompute_knowledge_unit(user_id, knowledge_unit_id)

        await self.repo.commit()

    async def _recompute_micro_competency(self, user_id: uuid.UUID, micro_competency_id: uuid.UUID) -> None:
        attempts_count, correct_count, last_attempt_at = await self.repo.aggregate_answers_for_micro_competency(
            user_id, micro_competency_id
        )
        score, level = compute_mastery(attempts_count, correct_count)

        row = await self.repo.get_micro_competency_mastery(user_id, micro_competency_id)
        if row is None:
            row = MicroCompetencyMastery(user_id=user_id, micro_competency_id=micro_competency_id)
            self.repo.add_micro_competency_mastery(row)

        row.attempts_count = attempts_count
        row.correct_count = correct_count
        row.mastery_score = score
        row.mastery_level = level
        row.last_attempt_at = last_attempt_at

    async def _recompute_knowledge_unit(self, user_id: uuid.UUID, knowledge_unit_id: uuid.UUID) -> None:
        attempts_count, correct_count, last_attempt_at = await self.repo.aggregate_answers_for_knowledge_unit(
            user_id, knowledge_unit_id
        )
        score, level = compute_mastery(attempts_count, correct_count)

        row = await self.repo.get_knowledge_unit_mastery(user_id, knowledge_unit_id)
        if row is None:
            row = KnowledgeUnitMastery(user_id=user_id, knowledge_unit_id=knowledge_unit_id)
            self.repo.add_knowledge_unit_mastery(row)

        row.attempts_count = attempts_count
        row.correct_count = correct_count
        row.mastery_score = score
        row.mastery_level = level
        row.last_attempt_at = last_attempt_at
        row.next_review_at = next_review_at_for(level)

    async def get_weak_knowledge_units(self, user_id: uuid.UUID, limit: int = 10) -> list[dict]:
        """The Knowledge-Unit-grained analogue of get_weak_concept_names —
        see ADR-0028 Phase D / KnowledgeService.get_weak_areas."""
        rows = await self.repo.get_weak_knowledge_units(user_id, limit)
        return [
            {
                "knowledge_unit_id": str(row.knowledge_unit_id),
                "mastery_score": row.mastery_score,
                "mastery_level": row.mastery_level,
                "attempts_count": row.attempts_count,
                "correct_count": row.correct_count,
            }
            for row in rows
        ]

    async def _recompute_one(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> None:
        attempts_count, correct_count, last_attempt_at = await self._concept_level_counts(user_id, concept_id)
        score, level = compute_mastery(attempts_count, correct_count)

        row = await self.repo.get(user_id, concept_id)
        if row is None:
            row = ConceptMastery(user_id=user_id, concept_id=concept_id)
            self.repo.add(row)

        row.attempts_count = attempts_count
        row.correct_count = correct_count
        row.mastery_score = score
        row.mastery_level = level
        row.last_attempt_at = last_attempt_at
        row.next_review_at = next_review_at_for(level)

    async def _concept_level_counts(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> tuple[int, int, datetime | None]:
        """Rolls up from the concept's micro-competencies (weighted by their
        own attempt counts, so a heavily-drilled skill counts more than one
        answered once) when any of them have attempts. Falls back to the
        direct concept-wide aggregate — today's ADR-0015 behavior — for a
        concept with no micro-competencies, or none attempted yet. See
        ADR-0021."""
        micro_competencies = await self.repo.get_micro_competencies_for_concept(concept_id)
        if micro_competencies:
            attempted_rows = []
            for mc in micro_competencies:
                row = await self.repo.get_micro_competency_mastery(user_id, mc.id)
                if row and row.attempts_count > 0:
                    attempted_rows.append(row)

            if attempted_rows:
                attempts_count = sum(r.attempts_count for r in attempted_rows)
                correct_count = sum(r.correct_count for r in attempted_rows)
                last_attempt_at = max(r.last_attempt_at for r in attempted_rows if r.last_attempt_at)
                return attempts_count, correct_count, last_attempt_at

        return await self.repo.aggregate_answers(user_id, concept_id)

    async def get_concept_mastery(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> dict:
        row = await self.repo.get(user_id, concept_id)
        return _row_to_dict(concept_id, row)

    async def get_topic_mastery(self, user_id: uuid.UUID, topic_id: uuid.UUID) -> dict:
        pairs = await self.repo.get_for_topic(user_id, topic_id)
        concepts = [
            {"concept_id": str(concept.id), "concept_name": concept.name, **_row_to_dict(concept.id, row)}
            for concept, row in pairs
        ]
        attempted = [c for c in concepts if c["attempts_count"] > 0]
        average_score = round(sum(c["mastery_score"] for c in attempted) / len(attempted), 1) if attempted else 0.0
        return {"topic_id": str(topic_id), "average_score": average_score, "concepts": concepts}

    async def get_overview(self, user_id: uuid.UUID) -> list[dict]:
        return await self.repo.get_overview(user_id)

    async def get_micro_competency_breakdown(self, user_id: uuid.UUID, concept_id: uuid.UUID) -> list[dict]:
        pairs = await self.repo.get_micro_competency_mastery_for_concept(user_id, concept_id)
        return [{"micro_competency_id": str(mc.id), "name": mc.name, **_mc_row_to_dict(row)} for mc, row in pairs]


def _row_to_dict(concept_id: uuid.UUID, row: ConceptMastery | None) -> dict:
    if row is None:
        return {
            "concept_id": str(concept_id),
            "attempts_count": 0,
            "correct_count": 0,
            "mastery_score": 0,
            "mastery_level": "NOT_STARTED",
            "last_attempt_at": None,
        }
    return {
        "concept_id": str(concept_id),
        "attempts_count": row.attempts_count,
        "correct_count": row.correct_count,
        "mastery_score": row.mastery_score,
        "mastery_level": row.mastery_level,
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
    }


def _mc_row_to_dict(row: MicroCompetencyMastery | None) -> dict:
    if row is None:
        return {
            "attempts_count": 0,
            "correct_count": 0,
            "mastery_score": 0,
            "mastery_level": "NOT_STARTED",
            "last_attempt_at": None,
        }
    return {
        "attempts_count": row.attempts_count,
        "correct_count": row.correct_count,
        "mastery_score": row.mastery_score,
        "mastery_level": row.mastery_level,
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
    }
