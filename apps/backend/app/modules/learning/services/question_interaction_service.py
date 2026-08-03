import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.models.question_bookmark import QuestionBookmark
from app.modules.learning.models.question_note import QuestionNote
from app.modules.learning.repositories.question_repository import QuestionRepository


class QuestionInteractionService:
    def __init__(self, session: AsyncSession):
        self.repo = QuestionRepository(session)

    async def toggle_bookmark(self, user_id: uuid.UUID, content_item_id: uuid.UUID) -> bool:
        existing = await self.repo.get_bookmark(user_id, content_item_id)
        if existing:
            await self.repo.delete_bookmark(existing)
            await self.repo.commit()
            return False
        self.repo.add_bookmark(QuestionBookmark(user_id=user_id, content_item_id=content_item_id))
        await self.repo.commit()
        return True

    async def get_note(self, user_id: uuid.UUID, content_item_id: uuid.UUID) -> str | None:
        note = await self.repo.get_note(user_id, content_item_id)
        return note.note_text if note else None

    async def upsert_note(self, user_id: uuid.UUID, content_item_id: uuid.UUID, note_text: str) -> str:
        existing = await self.repo.get_note(user_id, content_item_id)
        if existing:
            existing.note_text = note_text
        else:
            self.repo.add_note(QuestionNote(user_id=user_id, content_item_id=content_item_id, note_text=note_text))
        await self.repo.commit()
        return note_text

    async def delete_note(self, user_id: uuid.UUID, content_item_id: uuid.UUID) -> None:
        existing = await self.repo.get_note(user_id, content_item_id)
        if existing:
            await self.repo.delete_note(existing)
            await self.repo.commit()
