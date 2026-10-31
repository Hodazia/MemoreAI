from fastapi import APIRouter, Depends

from telegram_bot.api.dependencies import get_current_user
from telegram_bot.models.user import User
from telegram_bot.schemas.knowledge import (
    KnowledgeCreateRequest,
    KnowledgeCreateResponse,
)
from telegram_bot.services.knowledge_service import (
    add_user_knowledge,
)


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge"],
)


@router.post(
    "",
    response_model=KnowledgeCreateResponse,
)
async def create_knowledge(
    request: KnowledgeCreateRequest,
    current_user: User = Depends(get_current_user),
):

    result = await add_user_knowledge(
        user_id=current_user.id,
        text=request.text,
        source=request.source,
    )

    return result