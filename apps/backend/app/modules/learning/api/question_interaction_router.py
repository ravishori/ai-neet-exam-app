import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.identity.dependencies import get_current_user, verify_csrf
from app.modules.identity.models.user import User
from app.modules.learning.services.question_interaction_service import QuestionInteractionService
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/learning/questions", tags=["learning"], dependencies=[Depends(get_current_user)])


class NoteRequest(BaseModel):
    note_text: str = Field(max_length=5000)


@router.post("/{content_item_id}/bookmark/toggle", dependencies=[Depends(verify_csrf)])
async def toggle_bookmark(content_item_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    bookmarked = await QuestionInteractionService(db).toggle_bookmark(user.id, content_item_id)
    return envelope(success=True, data={"bookmarked": bookmarked})


@router.get("/{content_item_id}/note")
async def get_note(content_item_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    note_text = await QuestionInteractionService(db).get_note(user.id, content_item_id)
    return envelope(success=True, data={"note_text": note_text})


@router.put("/{content_item_id}/note", dependencies=[Depends(verify_csrf)])
async def upsert_note(
    content_item_id: uuid.UUID, payload: NoteRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    note_text = await QuestionInteractionService(db).upsert_note(user.id, content_item_id, payload.note_text)
    return envelope(success=True, data={"note_text": note_text})


@router.delete("/{content_item_id}/note", dependencies=[Depends(verify_csrf)])
async def delete_note(content_item_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await QuestionInteractionService(db).delete_note(user.id, content_item_id)
    return envelope(success=True, data={"note_text": None})
