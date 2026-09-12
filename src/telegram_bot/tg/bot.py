from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from telegram_bot.core.config import get_settings
from telegram_bot.tg.handlers import (
    help_handler,
    message_handler,
    start_handler,
)


settings = get_settings()


def create_telegram_application() -> Application:

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .updater(None)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start_handler)
    )

    application.add_handler(
        CommandHandler("help", help_handler)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler,
        )
    )

    return application