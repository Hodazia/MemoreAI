from datetime import datetime, timezone

from sqlalchemy import select

from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.models.conversation import Conversation
from telegram_bot.models.message import Message
from telegram_bot.agents.agent import ask_agent


async def process_user_message(
    *,
    user_id: int,
    conversation_id: int,
    content: str,
) -> str:

    # -------------------------------------------
    # 1. Validate conversation and persist input
    # -------------------------------------------

    async with AsyncSessionLocal() as db:

        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )

        if conversation is None:
            raise ValueError("Conversation not found.")

        db.add(
            Message(
                conversation_id=conversation_id,
                role="user",
                content=content,
            )
        )

        conversation.updated_at = datetime.now(timezone.utc)

        await db.commit()

    # -------------------------------------------
    # 2. Fetch conversation history
    # -------------------------------------------

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Message)
            .join(
                Conversation,
                Message.conversation_id == Conversation.id,
            )
            .where(
                Message.conversation_id == conversation_id,
                Conversation.user_id == user_id,
            )
            .order_by(Message.created_at.asc())
        )

        history = result.scalars().all()

        messages = [
            (message.role, message.content)
            for message in history
        ]

    # The DB session is now closed.
    # We don't hold a DB connection during the LLM call.

    # -------------------------------------------
    # 3. Invoke the actual AI agent
    # -------------------------------------------

    response = await ask_agent(
        messages=messages,
        user_id=user_id,
    )

    # -------------------------------------------
    # 4. Persist assistant response
    # -------------------------------------------

    async with AsyncSessionLocal() as db:

        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )

        if conversation is None:
            raise ValueError("Conversation was deleted.")

        db.add(
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
        )

        conversation.updated_at = datetime.now(timezone.utc)

        await db.commit()

    return response