from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.api.dependencies import get_current_user
from telegram_bot.core.database import get_db
from telegram_bot.models.document import Document 
from telegram_bot.models.user import User
from telegram_bot.schemas.documents import DocumentResponse

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )

    return result.scalars().all()
