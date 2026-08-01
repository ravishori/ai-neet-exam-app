from datetime import UTC, datetime, timedelta

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Chapter, Concept, Subject, Topic
from app.modules.ai.models import AIRequestLog
from app.modules.assessment.models import Assessment, Attempt, AttemptAnswer
from app.modules.cms.models import ContentItem

MIN_ATTEMPTS_FOR_CONCEPT_STATS = 3


def safe_percent(numerator: float, denominator: int, decimals: int = 1) -> float:
    if not denominator:
        return 0.0
    return round(100 * numerator / denominator, decimals)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_attempt_totals(self) -> dict:
        result = await self.session.execute(
            select(
                Assessment.assessment_type,
                func.count(Attempt.id),
                func.avg(
                    cast(Attempt.score, Numeric) / func.nullif(Assessment.question_count * Assessment.marks_per_question, 0) * 100
                ),
            )
            .join(Assessment, Assessment.id == Attempt.assessment_id)
            .where(Attempt.status == "SUBMITTED")
            .group_by(Assessment.assessment_type)
        )
        rows = result.all()

        total_attempts = sum(r[1] for r in rows)
        weighted_score_sum = sum(float(r[2] or 0) * r[1] for r in rows)
        overall_average = round(weighted_score_sum / total_attempts, 1) if total_attempts else 0.0

        return {
            "total_attempts": total_attempts,
            "average_score_percent": overall_average,
            "by_type": [
                {"assessment_type": r[0], "attempts": r[1], "average_score_percent": round(float(r[2] or 0), 1)}
                for r in rows
            ],
        }

    async def get_attempts_trend(self, days: int = 14) -> list[dict]:
        since = datetime.now(UTC) - timedelta(days=days)
        day_col = func.date(Attempt.submitted_at)
        result = await self.session.execute(
            select(day_col, func.count(Attempt.id))
            .where(Attempt.status == "SUBMITTED", Attempt.submitted_at >= since)
            .group_by(day_col)
            .order_by(day_col)
        )
        counts_by_day = {row[0]: row[1] for row in result.all()}

        today = datetime.now(UTC).date()
        return [
            {
                "date": (today - timedelta(days=offset)).isoformat(),
                "attempts": counts_by_day.get(today - timedelta(days=offset), 0),
            }
            for offset in range(days - 1, -1, -1)
        ]

    async def get_weakest_concepts(self, limit: int = 10) -> list[dict]:
        total = func.count(AttemptAnswer.id)
        correct = func.count(AttemptAnswer.id).filter(AttemptAnswer.is_correct.is_(True))
        accuracy = cast(correct, Numeric) / total * 100

        result = await self.session.execute(
            select(Concept.id, Concept.name, Subject.name, total, correct, accuracy)
            .select_from(AttemptAnswer)
            .join(ContentItem, ContentItem.id == AttemptAnswer.content_item_id)
            .join(Concept, Concept.id == ContentItem.concept_id)
            .join(Topic, Topic.id == Concept.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Subject, Subject.id == Chapter.subject_id)
            .where(AttemptAnswer.is_correct.is_not(None))
            .group_by(Concept.id, Concept.name, Subject.name)
            .having(total >= MIN_ATTEMPTS_FOR_CONCEPT_STATS)
            .order_by(accuracy)
            .limit(limit)
        )
        return [
            {
                "concept_id": str(row[0]),
                "concept_name": row[1],
                "subject_name": row[2],
                "attempts": row[3],
                "correct": row[4],
                "accuracy_percent": round(float(row[5]), 1),
            }
            for row in result.all()
        ]

    async def get_ai_usage_overview(self) -> dict:
        result = await self.session.execute(
            select(
                func.count(AIRequestLog.id),
                func.coalesce(func.sum(AIRequestLog.estimated_cost_usd), 0),
                func.count(AIRequestLog.id).filter(AIRequestLog.is_fallback.is_(True)),
                func.count(AIRequestLog.id).filter(AIRequestLog.success.is_(True)),
            )
        )
        total, total_cost, fallback_count, success_count = result.one()
        return {
            "total_requests": total,
            "total_cost_usd": round(float(total_cost), 4),
            "fallback_rate_percent": safe_percent(fallback_count, total),
            "success_rate_percent": safe_percent(success_count, total),
        }

    async def get_ai_usage_by_agent(self) -> list[dict]:
        result = await self.session.execute(
            select(
                AIRequestLog.agent_type,
                func.count(AIRequestLog.id),
                func.coalesce(func.sum(AIRequestLog.estimated_cost_usd), 0),
                func.avg(AIRequestLog.latency_ms),
                func.count(AIRequestLog.id).filter(AIRequestLog.success.is_(True)),
            )
            .group_by(AIRequestLog.agent_type)
            .order_by(AIRequestLog.agent_type)
        )
        return [
            {
                "agent_type": row[0],
                "requests": row[1],
                "total_cost_usd": round(float(row[2]), 4),
                "average_latency_ms": round(float(row[3] or 0)),
                "success_rate_percent": safe_percent(row[4], row[1]),
            }
            for row in result.all()
        ]
