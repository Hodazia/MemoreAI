import logging

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.agents.agent import ask_agent


logger = logging.getLogger(__name__)


async def start_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if update.message is None:
        return

    await update.message.reply_text(
        "👋 Hello!\n\n"
        "I'm an AI assistant powered by an LLM.\n\n"
        "Ask me anything!"
    )


async def help_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if update.message is None:
        return

    await update.message.reply_text(
        "Available commands:\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n\n"
        "You can also simply send me a question."
    )


async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if update.message is None:
        return

    user_message = update.message.text

    if not user_message:
        return

    logger.info(
        "Received message from Telegram user=%s",
        update.effective_user.id if update.effective_user else "unknown",
    )

    # Tell Telegram that the bot is processing the request.
    await update.message.chat.send_action("typing")

    try:
        response = await ask_agent(user_message)

        await update.message.reply_text(response)

    except Exception:
        logger.exception("Error while processing Telegram message")

        await update.message.reply_text(
            "Sorry, something went wrong while processing your request."
        )