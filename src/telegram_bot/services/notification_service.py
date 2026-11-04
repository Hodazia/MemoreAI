import aiosmtplib

from email.message import EmailMessage
from telegram import Bot
from telegram_bot.core.config import get_settings

settings = get_settings()

async def send_email_report(recipient:str,subject:str, body:str):
    if not all([
        settings.smtp_username,
        settings.smtp_password,
        settings.smtp_from
    ]):
        raise RuntimeError(
            "SMTP Configuration is incomplete"
        )

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        start_tls=True,
        username=settings.smtp_username,
        password=settings.smtp_password,
        timeout=30,
    )

async def send_telegram_report(
    telegram_chat_id:int,
    body:str
):

    # Telegram messages have a length limit.
    # Keep this first version safely below that limit.
    text = body[:4000]

    async with Bot(
        token=settings.telegram_bot_token
    ) as bot:
        await bot.send_message(
            chat_id=telegram_chat_id,
            text=text,
        )