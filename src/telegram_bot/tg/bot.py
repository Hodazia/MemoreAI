from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from telegram_bot.core.config import get_settings
from telegram_bot.tg.handlers import (
    LOGIN_PASSWORD,
    LOGIN_USERNAME,
    REGISTER_PASSWORD,
    REGISTER_USERNAME,
    help_handler,
    login_password,
    login_start,
    login_username,
    logout_handler,
    message_handler,
    register_password,
    register_start,
    register_username,
    start_handler,
)


settings = get_settings()


def create_telegram_application():

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .updater(None)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_handler,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_handler,
        )
    )

    application.add_handler(
        CommandHandler(
            "logout",
            logout_handler,
        )
    )

    registration_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "register",
                register_start,
            )
        ],

        states={

            REGISTER_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    register_username,
                )
            ],

            REGISTER_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    register_password,
                )
            ],
        },

        fallbacks=[],
    )

    login_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "login",
                login_start,
            )
        ],

        states={

            LOGIN_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    login_username,
                )
            ],

            LOGIN_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    login_password,
                )
            ],
        },

        fallbacks=[],
    )

    application.add_handler(
        registration_handler
    )

    application.add_handler(
        login_handler
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler,
        )
    )

    return application