import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.models.question_bookmark import QuestionBookmark
from app.modules.learning.models.question_note import QuestionNote


class QuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def commit(self) -> None:
        await self.session.commit()

    async def get_bookmark(self, user_id: uuid.UUID, content_item_id: uuid.UUID) -> QuestionBookmark | None:
        result = await self.session.execute(
            select(QuestionBookmark).where(
                QuestionBookmark.user_id == user_id, QuestionBookmark.content_item_id == content_item_id
            )
        )
        return result.scalar_one_or_none()

    async def bookmarked_ids(self, user_id: uuid.UUID, content_item_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not content_item_ids:
            return set()
        result = await self.session.execute(
            select(QuestionBookmark.content_item_id).where(
                QuestionBookmark.user_id == user_id, QuestionBookmark.content_item_id.in_(content_item_ids)
            )
        )
        return set(result.scalars().all())

    def add_bookmark(self, bookmark: QuestionBookmark) -> None:
        self.session.add(bookmark)

    async def delete_bookmark(self, bookmark: QuestionBookmark) -> None:
        await self.session.delete(bookmark)

    async def get_note(self, user_id: uuid.UUID, content_item_id: uuid.UUID) -> QuestionNote | None:
        result = await self.session.execute(
            select(QuestionNote).where(QuestionNote.user_id == user_id, QuestionNote.content_item_id == content_item_id)
        )
        return result.scalar_one_or_none()

    def add_note(self, note: QuestionNote) -> None:
        self.session.add(note)

    async def delete_note(self, note: QuestionNote) -> None:
        await self.session.delete(note)
