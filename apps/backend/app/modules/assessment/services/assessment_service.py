import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.academic.repositories.academic_repository import AcademicRepository
from app.modules.assessment.models import Assessment, AssessmentQuestion, Attempt, AttemptAnswer
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository, sample_question_ids
from app.modules.learning.services.mastery_service import MasteryService

logger = get_logger("assessment")

SCOPE_TYPES = {"CONCEPT", "CHAPTER", "SUBJECT", "FULL"}
DEFAULT_PRACTICE_COUNT = 10

# Real NEET pattern: 45 questions/subject (Physics, Chemistry, Botany,
# Zoology) = 180 total, 200 marks, single 180-minute sitting — see
# ADR-0013's "Consequences": with the seed content this session has (~8
# questions across 4 subjects), a full mock degrades gracefully to
# whatever's actually published per subject rather than failing outright.
NEET_SUBJECT_QUESTION_QUOTA = 45
FULL_MOCK_DURATION_MINUTES = 180


class AssessmentWorkflowError(AppError):
    def __init__(self, message: str, *, code: str = "ASSESSMENT_ERROR", status_code: int = 409):
        super().__init__(message, code=code, status_code=status_code)


def get_content_body(item) -> dict:
    for v in item.versions:
        if v.id == item.current_version_id:
            return v.body
    return {}


class AssessmentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AssessmentRepository(session)

    async def _persist_assessment(
        self,
        *,
        assessment_type: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
        selected: list[uuid.UUID],
        marks: float,
        negative_marks: float,
        duration_minutes: int | None,
        title: str,
        author_id: uuid.UUID,
    ) -> Assessment:
        assessment = Assessment(
            assessment_type=assessment_type,
            scope_type=scope_type,
            scope_id=scope_id,
            title=title,
            duration_minutes=duration_minutes,
            marks_per_question=marks,
            negative_marks_per_question=negative_marks,
            question_count=len(selected),
            created_by=author_id,
        )
        self.repo.add_assessment(assessment)
        await self.repo.flush()

        for order_no, content_item_id in enumerate(selected):
            self.repo.add_question(
                AssessmentQuestion(assessment_id=assessment.id, content_item_id=content_item_id, order_no=order_no)
            )
        await self.repo.commit()
        logger.info("assessment_generated", assessment_id=str(assessment.id), type=assessment_type, count=len(selected))
        return await self.repo.get_assessment(assessment.id)

    async def _generate(
        self,
        *,
        assessment_type: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
        question_count: int | None,
        marks: float,
        negative_marks: float,
        duration_minutes: int | None,
        title: str,
        author_id: uuid.UUID,
    ) -> Assessment:
        if scope_type not in SCOPE_TYPES:
            raise AppError(f"Unknown scope_type: {scope_type}", code="INVALID_SCOPE", status_code=400)
        if scope_type != "FULL" and not scope_id:
            raise AppError(f"scope_id is required for scope_type={scope_type}", code="MISSING_SCOPE_ID", status_code=400)

        available = await self.repo.published_question_ids_for_scope(scope_type, scope_id)
        if not available:
            raise AppError(
                "No published questions available for this scope yet — try a broader scope.",
                code="NO_QUESTIONS_AVAILABLE",
                status_code=422,
            )

        selected = sample_question_ids(available, question_count or len(available))
        return await self._persist_assessment(
            assessment_type=assessment_type,
            scope_type=scope_type,
            scope_id=scope_id,
            selected=selected,
            marks=marks,
            negative_marks=negative_marks,
            duration_minutes=duration_minutes,
            title=title,
            author_id=author_id,
        )

    async def generate_practice(
        self, *, scope_type: str, scope_id: uuid.UUID | None, question_count: int | None, user_id: uuid.UUID
    ) -> Assessment:
        return await self._generate(
            assessment_type="PRACTICE",
            scope_type=scope_type,
            scope_id=scope_id,
            question_count=question_count or DEFAULT_PRACTICE_COUNT,
            marks=1,
            negative_marks=0,
            duration_minutes=None,
            title="Practice set",
            author_id=user_id,
        )

    async def generate_mock(
        self, *, scope_type: str, scope_id: uuid.UUID | None, question_count: int | None, user_id: uuid.UUID
    ) -> Assessment:
        available_count_hint = question_count  # None = use every available question in scope
        assessment = await self._generate(
            assessment_type="MOCK",
            scope_type=scope_type,
            scope_id=scope_id,
            question_count=available_count_hint,
            marks=4,
            negative_marks=1,
            duration_minutes=None,  # set below once we know the real question_count
            title="Mock test",
            author_id=user_id,
        )
        # NEET pace is ~1 minute/question — set duration now that question_count is known.
        assessment.duration_minutes = max(10, assessment.question_count)
        await self.repo.commit()
        return assessment

    async def generate_full_mock(self, *, user_id: uuid.UUID) -> tuple[Assessment, list[dict]]:
        """Real NEET-pattern mock: up to NEET_SUBJECT_QUESTION_QUOTA questions
        per subject, fixed 180-minute duration — not "every published
        question in scope" like generate_mock's FULL scope. Degrades
        gracefully per subject when fewer than the quota is published yet
        (ADR-0013's "Consequences": that's signal, not a bug), rather than
        failing outright unless literally nothing is published anywhere.
        Returns the assessment plus a per-subject coverage report so the
        caller can show the student honestly what they're about to sit,
        not a silently-shrunk paper."""
        subjects = await AcademicRepository(self.session).list_subjects()

        selected: list[uuid.UUID] = []
        coverage: list[dict] = []
        for subject in subjects:
            available = await self.repo.published_question_ids_for_scope("SUBJECT", subject.id)
            picked = sample_question_ids(available, min(len(available), NEET_SUBJECT_QUESTION_QUOTA))
            selected.extend(picked)
            coverage.append(
                {
                    "subject_id": str(subject.id),
                    "subject_name": subject.name,
                    "quota": NEET_SUBJECT_QUESTION_QUOTA,
                    "available": len(available),
                    "selected": len(picked),
                }
            )

        if not selected:
            raise AppError(
                "No published questions available yet for a full mock.",
                code="NO_QUESTIONS_AVAILABLE",
                status_code=422,
            )

        assessment = await self._persist_assessment(
            assessment_type="MOCK",
            scope_type="FULL",
            scope_id=None,
            selected=selected,
            marks=4,
            negative_marks=1,
            duration_minutes=FULL_MOCK_DURATION_MINUTES,
            title="Full NEET mock",
            author_id=user_id,
        )
        return assessment, coverage

    async def start_attempt(self, assessment_id: uuid.UUID, user_id: uuid.UUID) -> Attempt:
        assessment = await self.repo.get_assessment(assessment_id)
        if not assessment:
            raise AppError("Assessment not found", code="NOT_FOUND", status_code=404)

        attempt = Attempt(assessment_id=assessment.id, user_id=user_id, status="IN_PROGRESS", started_at=datetime.now(UTC))
        self.repo.add_attempt(attempt)
        await self.repo.commit()
        logger.info("attempt_started", attempt_id=str(attempt.id), assessment_id=str(assessment_id))
        return attempt

    async def _get_owned_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> Attempt:
        attempt = await self.repo.get_attempt(attempt_id)
        if not attempt or attempt.user_id != user_id:
            raise AppError("Attempt not found", code="NOT_FOUND", status_code=404)
        return attempt

    async def _auto_submit_if_expired(self, attempt: Attempt, user_id: uuid.UUID) -> Attempt:
        """Server-side deadline enforcement (closes the gap ADR-0013 flagged:
        'the client auto-submits on timer expiry; the server trusts
        submitted_at for v1'). Untimed assessments (duration_minutes is
        None — every PRACTICE, and any MOCK generated before this existed)
        are unaffected. A student who left an expired attempt open, or
        whose auto-submit request never reached the server, gets it
        force-submitted here the next time they touch it — not stuck
        IN_PROGRESS forever, and not able to keep answering past time."""
        if attempt.status != "IN_PROGRESS":
            return attempt
        assessment = await self.repo.get_assessment(attempt.assessment_id)
        if assessment.duration_minutes is None:
            return attempt
        deadline = attempt.started_at + timedelta(minutes=assessment.duration_minutes)
        if datetime.now(UTC) <= deadline:
            return attempt
        return await self.submit_attempt(attempt.id, user_id)

    async def get_attempt_for_student(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> Attempt:
        attempt = await self._get_owned_attempt(attempt_id, user_id)
        return await self._auto_submit_if_expired(attempt, user_id)

    async def save_answer(
        self,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        content_item_id: uuid.UUID,
        selected_option: str | None,
        confidence: str | None = None,
        marked_for_review: bool = False,
        time_spent_seconds: int | None = None,
    ) -> None:
        attempt = await self._get_owned_attempt(attempt_id, user_id)
        was_in_progress = attempt.status == "IN_PROGRESS"
        attempt = await self._auto_submit_if_expired(attempt, user_id)
        if was_in_progress and attempt.status != "IN_PROGRESS":
            raise AssessmentWorkflowError("Time is up — this attempt has been submitted automatically", code="ATTEMPT_EXPIRED")
        if attempt.status != "IN_PROGRESS":
            raise AssessmentWorkflowError("Cannot answer a submitted attempt")

        existing = await self.repo.get_answer(attempt_id, content_item_id)
        if existing:
            existing.selected_option = selected_option
            existing.confidence = confidence
            existing.marked_for_review = marked_for_review
            # A question can be revisited across many short viewings —
            # accumulate rather than overwrite, so total time reflects the
            # whole solving experience, not just the last visit.
            existing.time_spent_seconds = (existing.time_spent_seconds or 0) + (time_spent_seconds or 0)
        else:
            self.repo.add_answer(
                AttemptAnswer(
                    attempt_id=attempt_id,
                    content_item_id=content_item_id,
                    selected_option=selected_option,
                    confidence=confidence,
                    marked_for_review=marked_for_review,
                    time_spent_seconds=time_spent_seconds,
                )
            )
        await self.repo.commit()

    async def get_question_history(self, user_id: uuid.UUID, content_item_id: uuid.UUID) -> list[AttemptAnswer]:
        return await self.repo.answer_history_for_question(user_id, content_item_id)

    async def submit_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> Attempt:
        attempt = await self._get_owned_attempt(attempt_id, user_id)
        if attempt.status != "IN_PROGRESS":
            raise AssessmentWorkflowError("Attempt already submitted")

        assessment = await self.repo.get_assessment(attempt.assessment_id)
        question_ids = [q.content_item_id for q in assessment.questions]
        items_by_id = {i.id: i for i in await self.repo.get_content_items(question_ids)}
        answers_by_question = {a.content_item_id: a for a in attempt.answers}

        correct = incorrect = skipped = 0
        for content_item_id in question_ids:
            answer = answers_by_question.get(content_item_id)
            if not answer or not answer.selected_option:
                skipped += 1
                continue
            body = get_content_body(items_by_id[content_item_id])
            is_correct = answer.selected_option == body.get("correct_option")
            answer.is_correct = is_correct
            if is_correct:
                correct += 1
            else:
                incorrect += 1

        score = float(correct * float(assessment.marks_per_question) - incorrect * float(assessment.negative_marks_per_question))

        attempt.status = "SUBMITTED"
        attempt.submitted_at = datetime.now(UTC)
        attempt.score = score
        attempt.correct_count = correct
        attempt.incorrect_count = incorrect
        attempt.skipped_count = skipped
        await self.repo.commit()
        logger.info("attempt_submitted", attempt_id=str(attempt_id), score=score)

        await MasteryService(self.session).recompute_for_content_items(user_id, question_ids)

        return await self.repo.get_attempt(attempt_id)
