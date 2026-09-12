from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.models.conversation import Conversation
from telegram_bot.models.message import Message


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: int,
) -> Conversation:

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == user_id
        )
        .order_by(
            Conversation.updated_at.desc()
        )
        .limit(1)
    )

    conversation = result.scalar_one_or_none()

    if conversation:
        return conversation

    conversation = Conversation(
        user_id=user_id,
        title="Telegram Conversation",
    )

    db.add(conversation)

    await db.commit()
    await db.refresh(conversation)

    return conversation


async def save_message(
    db: AsyncSession,
    conversation_id: int,
    role: str,
    content: str,
) -> Message:

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    db.add(message)

    await db.commit()
    await db.refresh(message)

    return message


async def get_conversation_messages(
    db: AsyncSession,
    conversation_id: int,
    limit: int = 20,
) -> list[Message]:

    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id
            == conversation_id
        )
        .order_by(
            Message.created_at.desc()
        )
        .limit(limit)
    )

    messages = list(result.scalars().all())

    messages.reverse()

    return messages