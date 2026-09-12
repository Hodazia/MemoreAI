
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from telegram import Update

from telegram_bot.core.config import get_settings
from telegram_bot.tg.bot import create_telegram_application
from telegram_bot.core.admin import create_admin_if_not_exists
from telegram_bot.api.auth import router as auth_router
from telegram_bot.api.admin import router as admin_router
import telegram_bot.models
from telegram_bot.core.database import create_tables


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

settings = get_settings()

telegram_application = create_telegram_application()


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting application...")

    #create DB tables
    await create_tables()

    await telegram_application.initialize()
    await telegram_application.start()
    await create_admin_if_not_exists()

    if settings.webhook_base_url:

        webhook_url = (
            f"{settings.webhook_base_url}"
            f"{settings.webhook_path}"
        )

        logger.info(
            "Setting Telegram webhook: %s",
            webhook_url,
        )

        await telegram_application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )

    yield

    logger.info("Stopping application...")

    if settings.webhook_base_url:
        await telegram_application.bot.delete_webhook()

    await telegram_application.stop()
    await telegram_application.shutdown()


app = FastAPI(
    title="Telegram AI Agent",
    description="AI Agent running inside Telegram",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(admin_router)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "telegram-ai-agent",
        "environment": settings.app_env,
    }


@app.post(settings.webhook_path)
async def telegram_webhook(request: Request):

    try:
        data = await request.json()

        update = Update.de_json(
            data=data,
            bot=telegram_application.bot,
        )

        await telegram_application.update_queue.put(update)

        return {
            "status": "ok",
        }

    except Exception as exc:

        logger.exception(
            "Failed to process Telegram webhook"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to process Telegram update",
        ) from exc