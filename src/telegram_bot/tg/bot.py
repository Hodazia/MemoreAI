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
    document_upload_handler,
    documents_handler
)

from telegram_bot.tg.handlers import (
    WORKFLOW_NAME,
    WORKFLOW_PROMPT,
    WORKFLOW_TIME,
    WORKFLOW_CHANNELS,
    WORKFLOW_TIMEZONE, 

    workflow_create_start,
    workflow_name_input,
    workflow_prompt_input,
    workflow_time_input,
    workflow_timezone_input,
    workflow_channels_input,
    workflows_list_handler,
    workflow_enable_handler,
    workflow_disable_handler,
    workflow_run_handler,
    workflow_toggle_handler,
    workflow_cancel_handler
)

from telegram_bot.tg.memory_handlers import (
    remember_handler, 
    memory_handler,
    memory_edit_handler,
    forget_handler,
    forget_confirm_handler,
    forget_cancel_handler
)

from telegram_bot.tg.observability_commands import (
    ai_help,
    ai_health,
    ai_stats,
    ai_cost,
    ai_failures,
    ai_latency,
    ai_models,
    ai_trace,
    ai_report,
    ai_alerts,
    ai_monitor
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

    # application.add_handler(
    #     MessageHandler(
    #         filters.TEXT & ~filters.COMMAND,
    #         message_handler,
    #     )
    # )

    application.add_handler(
        CommandHandler("documents",documents_handler)
    )

    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            document_upload_handler
        )
    )


    workflow_creation_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "workflow_create",
                workflow_create_start,
            )
        ],
        states={
            WORKFLOW_NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                workflow_name_input,
            )
        ],
        WORKFLOW_PROMPT: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                workflow_prompt_input,
            )
        ],
        WORKFLOW_TIME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                workflow_time_input,
            )
        ],
        WORKFLOW_TIMEZONE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                workflow_timezone_input,
            )
        ],
        WORKFLOW_CHANNELS: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                workflow_channels_input,
            )
        ],
    },
    fallbacks=[
        CommandHandler(
            "cancel",
            workflow_cancel_handler,
        )
    ],
    )

    application.add_handler(workflow_creation_handler)


    application.add_handler(
        CommandHandler("workflows", workflows_list_handler)
    )

    application.add_handler(
        CommandHandler("workflow_enable", workflow_enable_handler)
    )

    application.add_handler(
        CommandHandler("workflow_disable", workflow_disable_handler)
    )

    application.add_handler(
        CommandHandler("workflow_run", workflow_run_handler)
    )

    application.add_handler(
        CommandHandler("remember",remember_handler)
    )


    application.add_handler(
        CommandHandler("memory", memory_handler)
    )

    application.add_handler(
        CommandHandler("memory_edit", memory_edit_handler)
    )

    application.add_handler(
        CommandHandler("forget", forget_handler)
    )

    application.add_handler(
        CommandHandler("forget_confirm", forget_confirm_handler)
    )

    application.add_handler(
        CommandHandler("forget_cancel", forget_cancel_handler)
    )

    #observability commands
    observability_handlers = [
        ("ai_help", ai_help),
        ("ai_health", ai_health),
        ("ai_stats", ai_stats),
        ("ai_cost", ai_cost),
        ("ai_failures", ai_failures),
        ("ai_latency", ai_latency),
        ("ai_models", ai_models),
        ("ai_trace", ai_trace),
        ("ai_report", ai_report),
        ("ai_alerts", ai_alerts),
        ("ai_monitor", ai_monitor),
    ]

    for command, callback in observability_handlers:
        application.add_handler(
            CommandHandler(command, callback)
        )

    # --------------------------------------------------
    # Catch-all text handler LAST
    # --------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler,
        )
    )


    return application