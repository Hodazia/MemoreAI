from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.api.dependencies import get_admin_user
from telegram_bot.core.database import get_db
from telegram_bot.models.conversation import Conversation
from telegram_bot.models.message import Message
from telegram_bot.models.user import User


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get("/users")
async def get_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
    )

    users = result.scalars().all()

    return [
        {
            "id": user.id,
            "username": user.username,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
        for user in users
    ]


@router.get("/conversations")
async def get_all_conversations(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    result = await db.execute(
        select(Conversation)
        .order_by(
            Conversation.updated_at.desc()
        )
    )

    conversations = result.scalars().all()

    return [
        {
            "id": conversation.id,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        }
        for conversation in conversations
    ]

@router.get(
    "/conversations/{conversation_id}"
)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id
            == conversation_id
        )
        .order_by(Message.created_at)
    )

    messages = result.scalars().all()

    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        for message in messages
    ]


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    users_count = await db.scalar(
        select(func.count(User.id))
    )

    conversations_count = await db.scalar(
        select(func.count(Conversation.id))
    )

    messages_count = await db.scalar(
        select(func.count(Message.id))
    )

    return {
        "users": users_count,
        "conversations": conversations_count,
        "messages": messages_count,
    }