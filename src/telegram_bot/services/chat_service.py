from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.models.conversation import Conversation
from telegram_bot.models.message import Message
from telegram_bot.agents.agent import ask_agent


async def process_user_message(
    db: AsyncSession,
    *,
    user_id: int,
    conversation_id: int,
    content: str,
) -> str:
    """
    Shared application service.

    Used by:
    - Telegram message handler
    - Internal load testing
    - Future REST chat endpoint

    It persists both sides of the conversation.
    """

    # 1. Verify conversation ownership.
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )

    if conversation is None:
        raise ValueError("Conversation not found.")

    # 2. Persist incoming user message.
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=content,
    )

    db.add(user_message)
    await db.commit()

    # 3. Load conversation history.
    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id
        )
        .order_by(Message.created_at.asc())
    )

    history = result.scalars().all()

    # 4. Convert SQLAlchemy records into agent messages.
    messages = [
        (message.role, message.content)
        for message in history
    ]

    # 5. Invoke your actual agent.
    response = await ask_agent(
        messages=messages,
        user_id=user_id,
    )

    # 6. Persist assistant response.
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=response,
    )

    db.add(assistant_message)

    # Update conversation activity.
    # This assumes updated_at is writable in your model.
    from datetime import datetime, timezone

    conversation.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return response