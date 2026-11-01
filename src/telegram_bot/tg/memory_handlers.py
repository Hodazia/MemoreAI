import logging

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from telegram_bot.services.memory_service import create_memory,list_memories, update_memory, delete_memory, delete_all_memories
from telegram_bot.services.auth_service import get_telegram_session
from telegram_bot.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def get_authenticated_user_id(
    telegram_user_id:int,
) -> int | None:
    async with AsyncSessionLocal() as db:
            session = await get_telegram_session(
                db,
                telegram_user_id,
            )

            if session is None:
                return None

            return session.user_id

async def remember_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    user_id = await get_authenticated_user_id(
        telegram_user.id
    )

    if user_id is None:
        await message.reply_text(
            "Please /login before saving memories."
        )
        return

    # /remember requires text after the command.
    content = " ".join(context.args).strip()

    if not content:
        await message.reply_text(
            "Usage:\n"
            "/remember I prefer Java for backend interviews."
        )
        return

    try:
        async with AsyncSessionLocal() as db:
            memory = await create_memory(
                db,
                user_id,
                content,
            )
            await db.commit()

            memory_id = memory.id

    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    await message.reply_text(
        f"🧠 Memory saved!\n\n"
        f"ID: {memory_id}\n"
        f"Memory: {content}\n\n"
        f"Use /memory to inspect saved memories."
    )


async def memory_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    user_id = await get_authenticated_user_id(
        telegram_user.id
    )

    if user_id is None:
        await message.reply_text(
            "Please /login to view your memories."
        )
        return

    async with AsyncSessionLocal() as db:
        memories = await list_memories(db, user_id)

    if not memories:
        await message.reply_text(
            "You haven't saved any memories yet.\n\n"
            "Example:\n"
            "/remember I prefer Java for backend interviews."
        )
        return

    # Keep each Telegram message below its size limit.
    header = f"🧠 Your saved memories ({len(memories)}):\n\n"
    chunks = []
    current = header

    for memory in memories:
        entry = f"ID: {memory.id}\n{memory.content}\n\n"

        if len(current) + len(entry) > 3500:
            chunks.append(current)
            current = ""

        current += entry

    if current:
        chunks.append(current)

    chunks.append(
        "Edit: /memory_edit ID new text\n"
        "Delete one: /forget ID\n"
        "Delete all: /forget all"
    )

    for chunk in chunks:
        await message.reply_text(chunk)


async def memory_edit_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    user_id = await get_authenticated_user_id(
        telegram_user.id
    )

    if user_id is None:
        await message.reply_text(
            "Please /login before editing memories."
        )
        return

    # Expected: /memory_edit 12 I now prefer Spring Boot.
    if len(context.args) < 2:
        await message.reply_text(
            "Usage:\n"
            "/memory_edit 12 I now prefer Spring Boot."
        )
        return

    try:
        memory_id = int(context.args[0])
    except ValueError:
        await message.reply_text(
            "The memory ID must be a number."
        )
        return

    content = " ".join(context.args[1:]).strip()

    try:
        async with AsyncSessionLocal() as db:
            memory = await update_memory(
                db,
                user_id,
                memory_id,
                content,
            )

            if memory is None:
                await message.reply_text(
                    "Memory not found in your account."
                )
                return

            await db.commit()

    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    await message.reply_text(
        f"✅ Memory {memory_id} updated:\n\n{content}"
    )


async def forget_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    user_id = await get_authenticated_user_id(
        telegram_user.id
    )

    if user_id is None:
        await message.reply_text(
            "Please /login before deleting memories."
        )
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage:\n"
            "/forget 12\n"
            "/forget all"
        )
        return

    target = context.args[0].lower()

    if target == "all":
        context.user_data["pending_forget_all"] = True

        await message.reply_text(
            "⚠️ This will permanently delete all your saved "
            "memories.\n\n"
            "To confirm, send /forget_confirm.\n"
            "To cancel, send /forget_cancel."
        )
        return

    try:
        memory_id = int(target)
    except ValueError:
        await message.reply_text(
            "Provide a valid memory ID or use /forget all."
        )
        return

    async with AsyncSessionLocal() as db:
        deleted = await delete_memory(
            db,
            user_id,
            memory_id,
        )

        if deleted:
            await db.commit()

    if deleted:
        await message.reply_text(
            f"🗑️ Memory {memory_id} deleted."
        )
    else:
        await message.reply_text(
            "Memory not found in your account."
        )


async def forget_confirm_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    if not context.user_data.get("pending_forget_all"):
        await message.reply_text(
            "There is no pending delete-all request."
        )
        return

    # Re-authenticate at the time of deletion.
    user_id = await get_authenticated_user_id(
        telegram_user.id
    )

    if user_id is None:
        context.user_data.pop("pending_forget_all", None)
        await message.reply_text(
            "Please /login before deleting memories."
        )
        return

    async with AsyncSessionLocal() as db:
        deleted_count = await delete_all_memories(
            db,
            user_id,
        )
        await db.commit()

    context.user_data.pop("pending_forget_all", None)

    await message.reply_text(
        f"🗑️ Deleted {deleted_count} saved memories."
    )


async def forget_cancel_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if message is None:
        return

    context.user_data.pop("pending_forget_all", None)

    await message.reply_text(
        "Delete-all cancelled. Your memories are unchanged."
    )

'''
Command	Behaviour
/remember ...	Saves a memory, returning its ID
/memory	Lists all saved memories
/memory_edit ID ...	Updates one of the user's memories
/forget ID	Deletes one memory
/forget all	Requests confirmation before deleting all
/forget_confirm	Executes the pending delete-all request
/forget_cancel	Cancels the pending deletion

'''